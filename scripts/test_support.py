"""Shared, stdlib-only execution and evidence for fixture-only test suites."""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'scripts' / 'test-platforms.json'
OUTPUT_LIMIT = 64 * 1024
REPORT_LIMIT = 256 * 1024


def select_tests(suite, patterns=(), native=False, *, root=ROOT, manifest=MANIFEST):
    """Account for every test file, including new and accidentally deleted files."""
    folder = root / suite / 'tests'
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob('test_*.py')}
    spec = json.loads(manifest.read_text(encoding='utf-8'))[suite]
    portable = spec['portable']
    excluded = spec['windows_exclusions']
    classified = set(portable) | set(excluded)
    if len(portable) != len(set(portable)) or set(portable) & set(excluded):
        raise ValueError(f'{suite}: duplicate test classification')
    if actual != classified:
        raise ValueError(f'{suite}: unclassified={sorted(actual - classified)}; '
                         f'missing={sorted(classified - actual)}')
    for name, why in excluded.items():
        if not why.get('reason') or not re.fullmatch(
                r'https://github.com/bayramog/ludo/issues/[1-9][0-9]*', why.get('issue', '')):
            raise ValueError(f'{name}: exclusion needs a reason and a fork issue')
    matching = sorted(n for n in actual if not patterns or any(p in n for p in patterns))
    if not matching:
        raise ValueError(f'No test files matched: {list(patterns)}')
    omitted = {n: excluded[n] for n in matching
               if native and sys.platform == 'win32' and n in excluded}
    selected = [folder / n for n in matching if n not in omitted]
    for name, why in omitted.items():
        print(f'EXCLUDED {suite}/{name}: {why["reason"]} ({why["issue"]})', flush=True)
    if not selected:
        raise ValueError('Selection contains no runnable test files')
    return selected, omitted


def fixture_environment(profile: Path, *, root=ROOT):
    # Do not pass account tokens, application overrides, proxy credentials or a
    # different checkout's PYTHONPATH into tests. Keep OS/interpreter essentials.
    allowed = {'PATH', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT',
               'SYSTEMDRIVE', 'PROCESSOR_ARCHITECTURE', 'NUMBER_OF_PROCESSORS',
               'LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH', 'LANG', 'LC_ALL',
               'USER', 'LOGNAME', 'USERNAME'}
    env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
    for directory in ('home', 'local', 'roaming', 'tmp'):
        (profile / directory).mkdir(parents=True, exist_ok=True)
    env.update(HOME=str(profile / 'home'), USERPROFILE=str(profile / 'home'),
               LOCALAPPDATA=str(profile / 'local'), APPDATA=str(profile / 'roaming'),
               TMPDIR=str(profile / 'tmp'), TMP=str(profile / 'tmp'), TEMP=str(profile / 'tmp'),
               XDG_CONFIG_HOME=str(profile / 'home' / '.config'),
               XDG_CACHE_HOME=str(profile / 'home' / '.cache'),
               PYTHONPATH=os.pathsep.join(str(root / p) for p in ('engine', 'app')),
               PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1',
               PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    return env


def engine_evidence(output):
    """Existing harnesses report checks, unittest cases, or a completion marker.

    These are separate counters, not an invented sum of assertions. A silent
    no-op (including a pytest-only module run as a script) must fail the gate.
    """
    output = output.replace('\r\n', '\n').replace('\r', '\n')
    cases = re.findall(r'^Ran (\d+) tests? in ', output, re.M)
    return {
        'unittest_cases': sum(map(int, cases)),
        'ok_lines': len(re.findall(r'^ok(?:\s|$)', output, re.M)),
        'completion_markers': len(re.findall(
            r'^all independent Switch key sync checks passed$', output, re.M)),
        'skipped': sum(map(int, re.findall(r'OK \(skipped=(\d+)\)', output))),
    }


def scan_engine_output(stream):
    """Count the whole stream without retaining huge fixture byte dumps."""
    counts = dict.fromkeys(engine_evidence('').keys(), 0)
    explicit_failure = False
    stream.seek(0)
    start_of_line = True
    while chunk := stream.readline(OUTPUT_LIMIT):
        if start_of_line:
            text = chunk.decode('utf-8', errors='replace')
            for key, value in engine_evidence(text).items():
                counts[key] += value
            explicit_failure |= bool(re.match(r'^FAIL(?:\s|$)', text))
        start_of_line = chunk.endswith(b'\n')
    return counts, explicit_failure


def run_child(command, cwd, profile, *, kind='engine', timeout=300, junit=None):
    start = time.monotonic()
    result = {'status': 'failed', 'exit_code': None, 'failure': None}
    with tempfile.TemporaryFile() as stream:
        try:
            child = subprocess.run(command, cwd=cwd, env=fixture_environment(profile),
                                   stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
            result['exit_code'] = child.returncode
        except subprocess.TimeoutExpired:
            result['failure'] = 'timeout'
        except OSError:
            result['failure'] = 'spawn_error'
        if kind == 'engine':
            evidence, explicit_failure = scan_engine_output(stream)
        stream.seek(0, 2)
        result['output_bytes'] = size = stream.tell()
        stream.seek(max(0, size - OUTPUT_LIMIT))
        output = stream.read(OUTPUT_LIMIT).decode('utf-8', errors='replace')
    result['seconds'] = round(time.monotonic() - start, 3)
    if kind == 'engine':
        meaningful = any(evidence[k] for k in ('unittest_cases', 'ok_lines', 'completion_markers'))
        skipped = evidence['skipped']
    else:
        evidence = {'tests': 0, 'failures': 0, 'errors': 0, 'skipped': 0}
        try:
            tree = ET.parse(junit).getroot()
            suites = [tree] if tree.tag == 'testsuite' else list(tree.iter('testsuite'))
            for suite in suites:
                for key in evidence:
                    evidence[key] += int(suite.get(key, '0'))
        except (OSError, ET.ParseError, ValueError, TypeError):
            result['failure'] = result['failure'] or 'missing_test_report'
        meaningful = evidence['tests'] > 0
        skipped = evidence['skipped']
        explicit_failure = evidence['failures'] + evidence['errors'] > 0
    result['evidence'] = evidence
    if not result['failure']:
        if result['exit_code'] != 0 or explicit_failure:
            result['failure'] = 'test_failure'
        elif not meaningful:
            result['failure'] = 'zero_tests'
        elif skipped:
            result['failure'] = 'unexpected_skip'
        else:
            result['status'] = 'passed'
    # Artifacts intentionally exclude stdout/stderr, exception messages, test
    # values, environment, profile files and raw JUnit (which embeds output).
    # A few traceback locations still make a failed file actionable.
    result['traceback_locations'] = [
        {'file': Path(path.replace('\\', '/')).name, 'line': int(line)}
        for path, line in re.findall(r'File "([^"]+\.py)", line (\d+)', output)[-12:]
    ]
    if result['status'] != 'passed':
        print(output, end='' if output.endswith('\n') else '\n', flush=True)
    return result


def new_report(suite):
    try:
        sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                      text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        sha = 'unknown'
    return {'schema': 1, 'suite': suite, 'commit': sha, 'os': platform.system(),
            'os_release': platform.release(), 'os_version': platform.version(),
            'machine': platform.machine(), 'python': platform.python_version(),
            'selected_files': 0, 'excluded': {}, 'results': []}


def save_report(report, destination):
    if destination is None:
        return
    destination = Path(destination)
    # Fresh directory per invocation; never mix a previous failure with a pass
    # or accidentally upload existing user files.
    destination.mkdir(parents=True, exist_ok=False)
    payload = json.dumps(report, indent=2, ensure_ascii=True) + '\n'
    if len(payload.encode()) > REPORT_LIMIT:
        raise ValueError('Structured test evidence exceeds 256 KiB')
    (destination / 'summary.json').write_text(payload, encoding='utf-8')


def run_suite(suite, patterns=(), native=False, report_dir=None, timeout=300):
    report = new_report(suite)
    print(f'{suite}: {report["os"]} {report["os_version"]}; Python {report["python"]}; '
          f'interpreter={sys.executable}; commit={report["commit"]}', flush=True)
    try:
        files, report['excluded'] = select_tests(suite, patterns, native)
        report['selected_files'] = len(files)
        print(f'Selected {len(files)} {suite} files; excluded {len(report["excluded"])}', flush=True)
        # Separate process/profile for every engine script; backend retains its
        # normal single pytest collection so suite-level regressions are covered.
        groups = [[file] for file in files] if suite == 'engine' else [files]
        for group in groups:
            with tempfile.TemporaryDirectory(prefix='ludo-tests-') as temporary:
                profile = Path(temporary)
                junit = profile / 'junit.xml'
                if suite == 'engine':
                    command = [sys.executable, str(group[0])]
                else:
                    command = [sys.executable, '-m', 'pytest', '-p', 'pytest_asyncio.plugin',
                               '-q', f'--junitxml={junit}', *map(str, group)]
                result = run_child(command, ROOT / suite, profile, kind=suite,
                                   timeout=timeout, junit=junit)
                result['files'] = [file.relative_to(ROOT / suite / 'tests').as_posix() for file in group]
                report['results'].append(result)
                print(f'{result["status"].upper()} {", ".join(result["files"])} '
                      f'{result["evidence"]} ({result["seconds"]}s)', flush=True)
        failures = sum(r['status'] != 'passed' for r in report['results'])
        print(f'{suite}: {len(files)} files, {failures} failed groups, '
              f'{len(report["excluded"])} documented exclusions', flush=True)
        report['status'] = 'failed' if failures else 'passed'
        return 1 if failures else 0
    except (ValueError, OSError, KeyError) as error:
        print(f'Configuration error: {error}', file=sys.stderr)
        report['status'] = 'configuration_error'
        return 2
    finally:
        save_report(report, report_dir)
