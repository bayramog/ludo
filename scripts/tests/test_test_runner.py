"""Execution contracts, using actual child processes and synthetic fixture repos."""
import json
import io
import os
from pathlib import Path
import subprocess
import shlex
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_support import (ROOT, OUTPUT_LIMIT, REPORT_LIMIT, engine_evidence,
                          fixture_environment, run_child, save_report, select_tests)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def child(self, source, **kwargs):
        script = self.root / 'fixture.py'
        script.write_text(source, encoding='utf-8')
        return run_child([sys.executable, str(script)], self.root,
                         self.root / 'profile', **kwargs)

    def inventory(self, portable=('test_one.py',), excluded=None):
        folder = self.root / 'engine' / 'tests'
        folder.mkdir(parents=True)
        for name in (*portable, *(excluded or {})):
            (folder / name).touch()
        manifest = self.root / 'platforms.json'
        manifest.write_text(json.dumps({'engine': {'portable': list(portable),
                                                  'windows_exclusions': excluded or {}}}))
        return manifest

    def test_interpreter_cwd_roots_and_credentials_are_isolated(self):
        with patch.dict(os.environ, {'ROMM_TOKEN': 'must-not-reach-child',
                                    'PYTHONPATH': '/wrong/checkout'}):
            result = self.child(f'''import os, sys
from pathlib import Path
assert Path.cwd() == Path({str(self.root)!r})
assert sys.executable == {sys.executable!r}
assert 'ROMM_TOKEN' not in os.environ
for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'TMPDIR', 'TEMP', 'TMP'):
    assert Path(os.environ[key]).is_relative_to(Path({str(self.root / 'profile')!r}))
assert '/wrong/checkout' not in os.environ['PYTHONPATH']
print('ok isolated')
''')
        self.assertEqual(result['status'], 'passed')

    def test_empty_filter_fails_real_entrypoint(self):
        p = subprocess.run([sys.executable, str(ROOT / 'engine/tests/run.py'),
                            'does-not-exist-in-this-suite'], cwd=self.root,
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn('No test files matched', p.stderr)

    def test_silent_script_is_not_a_test(self):
        self.assertEqual(self.child('pass')['failure'], 'zero_tests')

    def test_large_success_output_does_not_hide_earlier_checks(self):
        result = self.child("print('ok assertion')\nprint('x' * 200000)")
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['evidence']['ok_lines'], 1)

    def test_failure_diagnostics_survive_legacy_windows_console_encoding(self):
        buffer = io.BytesIO()
        console = io.TextIOWrapper(buffer, encoding='cp1252')
        with patch('sys.stdout', console):
            result = self.child("print('game \U0001f3ae')\nraise SystemExit(1)")
        console.flush()
        self.assertIn('game \U0001f3ae', buffer.getvalue().decode('utf-8'))
        self.assertEqual(result['failure'], 'test_failure')
        console.detach()

    def test_windows_crlf_completion_marker(self):
        result = self.child("import sys\nsys.stdout.buffer.write(b'all independent Switch key sync checks passed\\r\\n')")
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['evidence']['completion_markers'], 1)

    def test_zero_unittest_suite_is_rejected(self):
        result = self.child('import unittest\nunittest.main()')
        self.assertEqual(result['status'], 'failed')
        self.assertIn(result['failure'], ('zero_tests', 'test_failure'))
        self.assertEqual(result['evidence']['unittest_cases'], 0)

    def test_child_failure_overrides_success_output(self):
        result = self.child("print('ok before failure')\nraise SystemExit(7)")
        self.assertEqual(result['exit_code'], 7)
        self.assertEqual(result['failure'], 'test_failure')

    def test_printed_failure_cannot_be_green(self):
        self.assertEqual(self.child("print('ok one')\nprint('FAIL two')")['failure'], 'test_failure')

    def test_spawn_failure_is_reported(self):
        result = run_child([str(self.root / 'missing-python')], self.root, self.root / 'profile')
        self.assertEqual(result['failure'], 'spawn_error')

    def test_timeout_is_failure(self):
        result = self.child('import time\ntime.sleep(10)', timeout=0.1)
        self.assertEqual(result['failure'], 'timeout')

    def test_unittest_skip_cannot_be_green(self):
        result = self.child('''import unittest
class Tests(unittest.TestCase):
    @unittest.skip('fixture')
    def test_skip(self): pass
unittest.main()
''')
        self.assertEqual(result['failure'], 'unexpected_skip')

    def test_unclassified_and_missing_files_fail(self):
        manifest = self.inventory()
        nested = self.root / 'engine/tests/nested'
        nested.mkdir()
        extra = nested / 'test_new.py'
        extra.touch()
        with self.assertRaisesRegex(ValueError, 'unclassified=.*test_new'):
            select_tests('engine', root=self.root, manifest=manifest)
        extra.unlink()
        (self.root / 'engine/tests/test_one.py').unlink()
        with self.assertRaisesRegex(ValueError, 'missing=.*test_one'):
            select_tests('engine', root=self.root, manifest=manifest)

    def test_filters_are_or_substrings_and_deduplicated(self):
        manifest = self.inventory(('test_one.py', 'test_two.py'))
        selected, excluded = select_tests('engine', ['one', 'test_one'], root=self.root, manifest=manifest)
        self.assertEqual([p.name for p in selected], ['test_one.py'])
        self.assertFalse(excluded)

    def test_exclusion_needs_reason_and_tracking_and_cannot_empty_selection(self):
        why = {'reason': 'fixture only', 'issue': 'https://github.com/bayramog/ludo/issues/11'}
        manifest = self.inventory(excluded={'test_windows.py': why})
        with patch('sys.platform', 'win32'):
            files, excluded = select_tests('engine', native=True, root=self.root, manifest=manifest)
            self.assertEqual(len(files), 1)
            self.assertEqual(excluded['test_windows.py'], why)
            with self.assertRaisesRegex(ValueError, 'no runnable'):
                select_tests('engine', ['windows'], native=True, root=self.root, manifest=manifest)
        why['issue'] = ''
        data = json.loads(manifest.read_text())
        data['engine']['windows_exclusions']['test_windows.py'] = why
        manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'reason and a fork issue'):
            select_tests('engine', root=self.root, manifest=manifest)

    def test_backend_empty_skipped_and_missing_reports_fail(self):
        for xml, expected in [(None, 'missing_test_report'),
                              ('<testsuites><testsuite tests="0"/></testsuites>', 'zero_tests'),
                              ('<testsuite tests="1" skipped="1"/>', 'unexpected_skip')]:
            with self.subTest(expected=expected):
                junit = self.root / 'junit.xml'
                junit.unlink(missing_ok=True)
                if xml:
                    junit.write_text(xml)
                self.assertEqual(self.child('pass', kind='app', junit=junit)['failure'], expected)

    def test_backend_failure_artifact_keeps_identity_but_omits_parameters_and_messages(self):
        junit = self.root / 'failure.xml'
        junit.write_text('<testsuite tests="1" failures="1"><testcase classname="tests.test_fixture" '
                         'name="test_auth[secret-fixture-value]"><failure>secret-fixture-value</failure>'
                         '</testcase></testsuite>')
        result = self.child('pass', kind='app', junit=junit)
        self.assertEqual(result['failure'], 'test_failure')
        self.assertEqual(result['failed_tests'], [{'test': 'test_auth',
                         'module': 'tests.test_fixture', 'outcome': 'failure'}])
        destination = self.root / 'evidence'
        save_report(result, destination)
        self.assertNotIn('secret-fixture-value', (destination / 'summary.json').read_text())

    def test_failure_artifact_is_bounded_and_does_not_contain_output_or_secrets(self):
        marker = 'sensitive-fixture-value-DO-NOT-UPLOAD'
        # Mock only printing to keep this negative test's console concise; the
        # child, bounded capture and actual JSON artifact are real.
        with patch('builtins.print'):
            result = self.child(f"print({marker!r} * 10000)\nraise RuntimeError({marker!r})")
        report = {'results': [result]}
        destination = self.root / 'evidence'
        save_report(report, destination)
        data = (destination / 'summary.json').read_text()
        self.assertGreater(result['output_bytes'], OUTPUT_LIMIT)
        self.assertLess(len(data.encode()), REPORT_LIMIT)
        self.assertNotIn(marker, data)
        self.assertNotIn('RuntimeError', data)
        self.assertEqual(result['traceback_locations'][-1], {'file': 'fixture.py', 'line': 2})
        self.assertEqual(list(destination.iterdir()), [destination / 'summary.json'])
        with self.assertRaises(FileExistsError):
            save_report(report, destination)

    @unittest.skipIf(os.name == 'nt', 'POSIX Bash bootstrap only; Windows installs deps explicitly (#11)')
    def test_bash_reuses_existing_venv_offline_when_path_python_lacks_deps(self):
        engine = self.root / 'engine'
        tests = engine / 'tests'
        tests.mkdir(parents=True)
        shutil.copyfile(ROOT / 'engine/tests/run.sh', tests / 'run.sh')
        (tests / 'run.py').write_text("import sys\nprint('offline fixture', sys.argv[1:])")
        fake_path = self.root / 'bin'
        fake_path.mkdir()
        for name in ('python', 'python3'):
            stub = fake_path / name
            stub.write_text('#!/bin/sh\nexit 1\n')
            stub.chmod(0o755)
        venv = engine / '.venv-tests' / 'bin'
        venv.mkdir(parents=True)
        python = venv / 'python'
        python.write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' "$@"\n')
        python.chmod(0o755)
        env = dict(os.environ, PATH=str(fake_path) + os.pathsep + os.environ['PATH'])
        env.pop('LUDO_TEST_PYTHON', None)
        p = subprocess.run(['bash', str(tests / 'run.sh'), 'keys', 'eden'], env=env,
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("offline fixture ['keys', 'eden']", p.stdout)
        self.assertNotIn('building', p.stderr)

    @unittest.skipIf(os.name == 'nt', 'POSIX Bash bootstrap only; Windows invokes its selected Python (#11)')
    def test_bash_invalid_explicit_interpreter_does_not_install_or_fall_back(self):
        env = dict(os.environ, LUDO_TEST_PYTHON=str(self.root / 'missing-python'))
        p = subprocess.run(['bash', str(ROOT / 'engine/tests/run.sh'), 'keys'], env=env,
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn('missing the engine', p.stderr)
        self.assertNotIn('building', p.stderr)

    @unittest.skipIf(os.name == 'nt', 'POSIX Bash adapter only; Windows uses run.py (F1-06/#11)')
    def test_bash_explicit_python_and_filter_work_without_dependency_install(self):
        env = dict(os.environ, LUDO_TEST_PYTHON=sys.executable)
        p = subprocess.run(['bash', str(ROOT / 'engine/tests/run.sh'), 'activity_actions'],
                           env=env, cwd=self.root, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('unittest_cases', p.stdout)
        self.assertIn('1 files, 0 failed', p.stdout)
        self.assertNotIn('building', p.stderr)


if __name__ == '__main__':
    unittest.main()
