"""Regressions for fixtures that previously lost whole Windows suites."""
import contextlib
from datetime import datetime, timedelta
import io
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'engine/tests'))
import test_flatpak_launcher_path as launcher
import test_play_sessions as sessions


class FixtureTests(unittest.TestCase):
    def test_blank_card_fixture_survives_a_clock_tick(self):
        import test_pcee2_card as pcee

        class TickingClock(datetime):
            tick = 0

            @classmethod
            def now(cls):
                result = datetime(2026, 9, 15, 12) + timedelta(seconds=cls.tick)
                cls.tick += 1
                return result

        pcee.FAILURES.clear()
        with patch.object(pcee.ps2_memcard, 'datetime', types.SimpleNamespace(datetime=TickingClock)), \
                contextlib.redirect_stdout(io.StringIO()):
            pcee.main()
        self.assertEqual(pcee.FAILURES, [])

    def test_autosync_fixture_reads_metadata_only_after_release(self):
        import test_autosync_lock as locks
        owners = []
        original_lock, original_read = locks.lock_at, Path.read_text

        def tracked_lock(path):
            owner = original_lock(path)
            owners.append(owner)
            return owner

        def unlocked_read(path, *args, **kwargs):
            if any(owner._fd is not None for owner in owners):
                raise PermissionError('Windows denies reads through another handle')
            return original_read(path, *args, **kwargs)

        locks.FAILURES.clear()
        try:
            with patch.object(locks, 'lock_at', side_effect=tracked_lock), \
                    patch.object(Path, 'read_text', unlocked_read), \
                    contextlib.redirect_stdout(io.StringIO()):
                locks.main()
            self.assertEqual(locks.FAILURES, [])
        finally:
            for owner in owners:
                owner.release()

    def test_legacy_keys_fixture_isolates_windows_home_lookup(self):
        import test_keys_sync as keys
        original = keys.E._keys_marker_path

        def checked_marker():
            home = Path(os.environ['HOME'])
            for key in ('USERPROFILE', 'APPDATA', 'LOCALAPPDATA'):
                self.assertTrue(Path(os.environ[key]).is_relative_to(home),
                                f'legacy key receipt: {key} escaped the fixture')
            return original()

        with tempfile.TemporaryDirectory() as outer:
            with patch.dict(os.environ, **{key: outer for key in
                            ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA')}), \
                    patch.object(keys.E, '_keys_marker_path', side_effect=checked_marker):
                keys.legacy_archive_receipt()

    def test_cemu_install_fixture_isolates_windows_home_lookup(self):
        import test_cemu_saves as cemu
        with tempfile.TemporaryDirectory() as outer:
            cemu.FAILURES.clear()
            with patch.dict(os.environ, USERPROFILE=outer), \
                    patch.object(Path, 'home', side_effect=lambda: Path(os.environ['USERPROFILE'])), \
                    contextlib.redirect_stdout(io.StringIO()):
                cemu.test_installs(Path(outer) / 'case')
            self.assertEqual(cemu.FAILURES, [])

    def test_profile_fixtures_isolate_every_user_root(self):
        from test_cemu_sync import CemuSyncTest
        from test_eden_users import EdenUsersTest
        from test_profiles import ProfilesTest
        for cls in (CemuSyncTest, EdenUsersTest, ProfilesTest):
            with self.subTest(fixture=cls.__name__), tempfile.TemporaryDirectory() as outer:
                roots = {key: outer for key in
                         ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA',
                          'XDG_CONFIG_HOME', 'XDG_DATA_HOME')}
                with patch.dict(os.environ, roots):
                    case = cls()
                    case.setUp()
                    try:
                        for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA'):
                            self.assertTrue(Path(os.environ[key]).is_relative_to(case.home),
                                            f'{cls.__name__}: {key} escaped the case profile')
                    finally:
                        case.tearDown()

    def test_launcher_fixture_isolates_windows_home_lookup(self):
        with tempfile.TemporaryDirectory() as temporary:
            inherited = Path(temporary) / 'inherited-profile'
            with patch.dict(os.environ, USERPROFILE=str(inherited)), \
                    patch.object(Path, 'home', side_effect=lambda: Path(os.environ['USERPROFILE'])), \
                    contextlib.redirect_stdout(io.StringIO()):
                launcher.FAILURES.clear()
                self.assertEqual(launcher.main(), 0, launcher.FAILURES)
            self.assertFalse(inherited.exists(), 'fixture wrote outside its own profile')

    def test_session_recovery_fixture_does_not_require_host_boot_identity(self):
        sessions.FAILURES.clear()
        with patch.object(sessions.ps, 'boot_id', return_value=''), \
                contextlib.redirect_stdout(io.StringIO()):
            sessions.test_recovery()
        self.assertEqual(sessions.FAILURES, [])


if __name__ == '__main__':
    unittest.main()
