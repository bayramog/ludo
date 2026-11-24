#!/usr/bin/env python3
"""Portable filesystem/settings contracts; execute directly, not via pytest.

The same file runs on real Windows and Linux in CI. Simulated platform cases
only test path selection; they are not evidence of Windows runtime execution.
"""
import io
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ENGINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE))
# Isolate before importing anything that may resolve state. On Windows HOME
# alone does not override Path.home() or the local/roaming application roots.
_sandbox = tempfile.TemporaryDirectory(prefix='ludo-path-tests-')
os.environ.update(HOME=_sandbox.name, USERPROFILE=_sandbox.name,
                  LOCALAPPDATA=str(Path(_sandbox.name) / 'AppData' / 'Local'),
                  APPDATA=str(Path(_sandbox.name) / 'AppData' / 'Roaming'))
from romm_sync_engine import paths, profiles, settings_file, sync_core
from romm_sync_engine.sync_core import SettingsManager


class PathSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ludo paths öğ-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.local = self.home / 'AppData' / 'Local'
        env = patch.dict(os.environ, HOME=str(self.home), USERPROFILE=str(self.home),
                         LOCALAPPDATA=str(self.local), APPDATA=str(self.home / 'roaming'))
        env.start(); self.addCleanup(env.stop)
        state = patch.multiple(paths, _app_id='ludo', _library_dir_name='Ludo',
                               _locked=False, _profile=paths.DEFAULT_PROFILE,
                               _profile_locked=False)
        state.start(); self.addCleanup(state.stop)
        SettingsManager._shared.clear()
        SettingsManager._mtimes.clear()

    def test_imports_this_checkout(self):
        for module in (paths, profiles, settings_file, sync_core):
            self.assertEqual(Path(module.__file__).resolve().parent.parent, ENGINE)

    def test_named_windows_profile_shares_only_machine_state(self):
        with patch.object(sys, 'platform', 'win32'):
            root = paths.machine_dir()
            self.assertEqual(root, self.local / 'ludo')
            self.assertEqual(paths.profile_dir('default'), root)
            target = paths.profile_dir('player-two')
            self.assertFalse(target.exists())
            paths.set_profile('player-two')
            self.assertEqual(paths.config_dir(), root / 'profiles' / 'player-two')
            self.assertEqual(paths.cache_dir(), target / 'cache')
            self.assertEqual(paths.machine_cache_dir(), root / 'cache')
            self.assertEqual(paths.library_dir(), self.home / 'Ludo')
            with self.assertRaises(RuntimeError):
                paths.set_profile('default')

    def test_legacy_windows_machine_root_keeps_all_profiles_together(self):
        legacy = self.home / '.config' / 'ludo'
        target = legacy / 'profiles' / 'player-two'
        target.mkdir(parents=True)
        marker = target / 'settings.ini'
        marker.write_text('[Download]\nrom_directory = ROM arşivi %50\n', encoding='utf-8')
        before = marker.read_bytes()
        (self.local / 'ludo').mkdir(parents=True)
        with patch.object(sys, 'platform', 'win32'):
            paths.set_profile('player-two')
            self.assertEqual(paths.machine_dir(), legacy)
            self.assertEqual(paths.config_dir(), target)
            self.assertEqual(paths.profile_dir('default'), legacy)
            self.assertEqual(marker.read_bytes(), before)
            self.assertFalse((self.local / 'ludo' / 'profiles').exists())

    def test_linux_named_profile_keeps_upstream_layout(self):
        with patch.object(sys, 'platform', 'linux'):
            paths.set_profile('player-two')
            root = self.home / '.config' / 'ludo'
            self.assertEqual(paths.config_dir(), root / 'profiles' / 'player-two')
            self.assertEqual(paths.machine_dir(), root)

    def test_missing_named_profile_does_not_read_default_credentials(self):
        settings = SettingsManager()
        settings.set('RomM', 'client_token', 'default-only-test-token')
        before = settings.config_file.read_bytes()
        with patch.multiple(paths, _profile='player-two', _profile_locked=False):
            other = SettingsManager()
            self.assertEqual(other.config_dir, settings.config_dir / 'profiles' / 'player-two')
            self.assertEqual(other.get('RomM', 'client_token'), '')
            other.set('RomM', 'client_token', 'second-only-test-token')
            self.assertIsNot(other.config, settings.config)
        self.assertEqual(settings.config_file.read_bytes(), before)
        self.assertEqual(SettingsManager().get('RomM', 'client_token'), 'default-only-test-token')

    def test_profile_creation_copies_literal_utf8_paths_without_credentials(self):
        # Seed the file directly so this tests the upstream profile-copy reader
        # even before SettingsManager gains literal-value persistence.
        source = paths.config_dir() / 'settings.ini'
        roms = str(self.home / 'ROM arşivi %50')
        source.write_text('[RomM]\nclient_token = default-only-test-token\n'
                          '[Download]\nrom_directory = ' + roms + '\n', encoding='utf-8')
        before = source.read_bytes()
        profile = profiles.create('İkinci oyuncu')
        with patch.multiple(paths, _profile=profile, _profile_locked=False):
            settings = SettingsManager()
            self.assertEqual(settings.get('Download', 'rom_directory'), roms)
            self.assertEqual(settings.get('RomM', 'client_token'), '')
            self.assertEqual(settings.get('Download', 'save_directory'),
                             str(profiles.save_dirs(profile)['saves']))
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(profiles.get(profiles.load(), profile)['name'], 'İkinci oyuncu')

    def test_legacy_locale_survives_profile_copy_and_utf8_save(self):
        settings = SettingsManager()
        roms = 'C:/Users/Café/ROMs %50'
        settings.set('Download', 'rom_directory', roms)
        settings.set('Download', 'save_directory', 'C:/Saves')
        settings.set('Device', 'device_name', 'test-host')
        settings.set('RomM', 'client_token', 'test-only-legacy-token')
        text = io.StringIO()
        settings.config.write(text)
        legacy = text.getvalue().encode('cp1252')
        # Deterministic legacy-locale fixtures for both platforms. Keep
        # pathlib and the rest of the process on their real platform.
        for platform_name in ('nt', 'posix'):
            simulated_os = SimpleNamespace(**{**vars(os), 'name': platform_name})
            with self.subTest(platform=platform_name), \
                    patch.object(settings_file, 'os', simulated_os), \
                    patch.object(settings_file.locale, 'getencoding', return_value='cp1252'):
                settings.config_file.write_bytes(legacy)
                profile = profiles.create('New player')
                self.assertEqual(settings.config_file.read_bytes(), legacy)
                settings.load_settings()
                self.assertEqual(settings.get('Download', 'rom_directory'), roms)
                self.assertEqual(settings.get('RomM', 'client_token'), 'test-only-legacy-token')
                settings.save_settings()
                self.assertIn(roms, settings.config_file.read_text(encoding='utf-8'))
                with patch.multiple(paths, _profile=profile, _profile_locked=False):
                    copied = SettingsManager()
                    self.assertEqual(copied.get('Download', 'rom_directory'), roms)
                    self.assertEqual(copied.get('RomM', 'client_token'), '')

    def test_invalid_utf8_with_utf8_locale_is_not_rewritten(self):
        settings = SettingsManager()
        invalid = b'[Download]\nrom_directory = \xff\n'
        settings.config_file.write_bytes(invalid)
        with patch.object(settings_file.locale, 'getencoding', return_value='utf-8'):
            with self.assertRaises(UnicodeDecodeError):
                settings.load_settings()
        self.assertEqual(settings.config_file.read_bytes(), invalid)
        self.assertFalse(list(settings.config_dir.glob('settings-*.tmp')))

    def test_legacy_settings_migrate_with_ansi_stdout(self):
        source = paths.config_dir() / 'settings.ini'
        roms = str(self.home / 'ROM arşivi %50')
        source.write_text('[Download]\nrom_directory = ' + roms + '\n', encoding='utf-8')
        # A redirected Windows stdout can be CP1252 even when settings use
        # UTF-8. A diagnostic must not interrupt loading the migrated file.
        with io.TextIOWrapper(io.BytesIO(), encoding='cp1252') as output:
            with patch.object(sys, 'stdout', output):
                settings = SettingsManager()
            output.flush()
            self.assertIn(b'Settings migrated to latest version', output.buffer.getvalue())
        self.assertEqual(settings.get('Download', 'rom_directory'), roms)
        self.assertTrue(settings.config.has_section('Device'))
        self.assertIn(roms, source.read_text(encoding='utf-8'))

    def test_profile_paths_reject_windows_escape_and_device_names(self):
        for name in (r'..\escape', r'C:\escape', 'C:drive', 'NUL', 'con.txt',
                     'COM1', 'a.', 'a ', 'a\x00b', 'a?b', '.hidden'):
            for operation in (paths.set_profile, paths.profile_dir):
                with self.subTest(name=name, operation=operation.__name__), self.assertRaises(ValueError):
                    operation(name)

    def test_new_windows_profile_uses_local_not_roaming(self):
        with patch.object(sys, 'platform', 'win32'):
            self.assertEqual(paths.config_dir(), self.local / 'ludo')
            self.assertTrue((self.local / 'ludo').is_dir())
            self.assertFalse((self.home / '.config').exists())

    def test_windows_without_localappdata_uses_user_profile(self):
        os.environ.pop('LOCALAPPDATA')
        with patch.object(sys, 'platform', 'win32'):
            self.assertEqual(paths.config_dir(), self.home / 'AppData' / 'Local' / 'ludo')

    def test_relative_appdata_is_rejected(self):
        os.environ['LOCALAPPDATA'] = 'relative'
        with patch.object(sys, 'platform', 'win32'), self.assertRaises(ValueError):
            paths.config_dir()

    def test_legacy_windows_state_is_not_silently_migrated(self):
        legacy = self.home / '.config' / 'ludo'
        legacy.mkdir(parents=True)
        marker = legacy / 'settings.ini'
        marker.write_text('[RomM]\nurl = https://example.invalid\n', encoding='utf-8')
        (self.local / 'ludo').mkdir(parents=True)
        before = marker.read_bytes()
        with patch.object(sys, 'platform', 'win32'):
            self.assertEqual(paths.config_dir(), legacy)
            self.assertEqual(marker.read_bytes(), before)

    def test_linux_decky_path_does_not_change(self):
        with patch.object(sys, 'platform', 'linux'):
            self.assertEqual(paths.config_dir(), self.home / '.config' / 'ludo')

    def test_existing_library_remains_authoritative(self):
        self.assertEqual(paths.library_dir(), self.home / 'Ludo')
        legacy = self.home / 'RomMSync'
        legacy.mkdir()
        self.assertEqual(paths.library_dir(), legacy)

    def test_names_cannot_escape_or_select_windows_devices(self):
        for name in ('', '.', '..', '../escape', r'..\escape', 'C:drive', 'NUL',
                     'con.txt', 'COM1', 'a.', 'a ', 'a\x00b', 'a?b'):
            for setter in (paths.set_app_id, paths.set_library_dir_name):
                with self.subTest(name=name, setter=setter.__name__), self.assertRaises(ValueError):
                    setter(name)
        paths.set_app_id('ludo-test')
        paths.config_dir()
        with self.assertRaises(RuntimeError):
            paths.set_app_id('another-app')

    def test_unicode_credentials_and_paths_round_trip_in_new_process(self):
        settings = SettingsManager()
        settings.set('RomM', 'client_token', 'test-only-öğ-token')
        settings.set('Download', 'rom_directory', str(self.home / 'ROM arşivi %50'))
        self.assertNotIn('test-only-öğ-token', settings.config_file.read_text(encoding='utf-8'))
        code = """
import sys
sys.path.insert(0, sys.argv[1])
from romm_sync_engine import paths
paths.set_app_id('ludo')
from romm_sync_engine.sync_core import SettingsManager
s = SettingsManager()
assert s.get('RomM', 'client_token') == 'test-only-öğ-token'
assert s.get('Download', 'rom_directory') == sys.argv[2]
"""
        result = subprocess.run([sys.executable, '-c', code, str(ENGINE),
                                 str(self.home / 'ROM arşivi %50')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_settings_does_not_require_fchmod(self):
        with patch.object(os, 'fchmod', side_effect=AssertionError('Unix-only'), create=True):
            settings = SettingsManager()
            settings.set('System', 'debug_mode', 'true')
        if os.name != 'nt':
            self.assertEqual(stat.S_IMODE(settings.config_file.stat().st_mode), 0o600)

    def test_replace_failure_preserves_previous_settings_and_cleans_temp(self):
        settings = SettingsManager()
        before = settings.config_file.read_bytes()
        with patch.object(os, 'replace', side_effect=PermissionError('destination busy')):
            with self.assertRaises(PermissionError):
                settings.set('System', 'debug_mode', 'true')
        self.assertEqual(settings.config_file.read_bytes(), before)
        self.assertEqual(list(settings.config_dir.glob('settings-*.tmp')), [])
        settings.save_settings()
        SettingsManager._shared.clear()
        SettingsManager._mtimes.clear()
        self.assertEqual(SettingsManager().get('System', 'debug_mode'), 'true')

    def test_serialization_failure_closes_file_and_preserves_previous_data(self):
        settings = SettingsManager()
        before = settings.config_file.read_bytes()
        handles = []
        def fail(handle):
            handles.append(handle)
            handle.write('[partial]')
            raise OSError('disk full')
        with patch.object(settings.config, 'write', side_effect=fail), self.assertRaises(OSError):
            settings.save_settings()
        self.assertTrue(handles[0].closed)
        self.assertEqual(settings.config_file.read_bytes(), before)
        self.assertEqual(list(settings.config_dir.glob('settings-*.tmp')), [])

    def test_fdopen_failure_closes_descriptor(self):
        settings = SettingsManager()
        fds = []
        def fail(fd, *args, **kwargs):
            fds.append(fd)
            raise OSError('cannot open stream')
        with patch.object(os, 'fdopen', side_effect=fail), self.assertRaises(OSError):
            settings.save_settings()
        with self.assertRaises(OSError):
            os.fstat(fds[0])
        self.assertEqual(list(settings.config_dir.glob('settings-*.tmp')), [])

    def test_fsync_failure_closes_descriptor_and_preserves_previous_settings(self):
        settings = SettingsManager()
        before = settings.config_file.read_bytes()
        fds = []
        def fail(fd):
            fds.append(fd)
            raise OSError('disk flush failed')
        with patch.object(os, 'fsync', side_effect=fail), self.assertRaises(OSError):
            settings.set('System', 'debug_mode', 'true')
        self.assertEqual(settings.config_file.read_bytes(), before)
        self.assertEqual(list(settings.config_dir.glob('settings-*.tmp')), [])
        with self.assertRaises(OSError):
            os.fstat(fds[0])

    def test_windows_account_fallback_does_not_import_pwd(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(sys, 'platform', 'win32'), \
                patch.object(os, 'getlogin', return_value='test-windows-user'):
            self.assertEqual(SettingsManager._env_user(), 'test-windows-user')

    def test_windows_account_is_independent_of_shell_user_variables(self):
        with patch.dict(os.environ, USER='root', LOGNAME='root', USERNAME='stale'), \
                patch.object(sys, 'platform', 'win32'), \
                patch.object(os, 'getlogin', return_value='test-windows-user'):
            self.assertEqual(SettingsManager._user(), 'test-windows-user')


if __name__ == '__main__':
    unittest.main()
