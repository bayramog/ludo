"""Direct settings RPCs share the engine's literal UTF-8/atomic file contract."""
import builtins
import configparser
import io
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from ludo_app import backend as backend_mod
from ludo_app.backend import LudoBackend
from ludo_app.host import HostProfile
from romm_sync_engine import paths
from romm_sync_engine.sync_core import SettingsManager


@pytest.fixture
def settings_backend(monkeypatch, tmp_path):
    for name, value in {
        'HOME': tmp_path, 'USERPROFILE': tmp_path,
        'LOCALAPPDATA': tmp_path / 'Local', 'APPDATA': tmp_path / 'Roaming',
    }.items():
        monkeypatch.setenv(name, str(value))
    for name, value in {'_app_id': 'ludo', '_profile': 'default',
                        '_locked': False, '_profile_locked': False}.items():
        monkeypatch.setattr(paths, name, value)
    settings = SettingsManager()
    backend = LudoBackend(host=HostProfile('test', '-x86_64.AppImage', tmp_path / 'runtime', 'desktop'))
    backend._settings = settings
    backend._retroarch = backend._romm_client = backend._collection_sync = backend._bios_tracking = None
    backend._steam_manager = SimpleNamespace(is_available=lambda: True)
    backend._available_games = []
    monkeypatch.setattr(backend, '_stop_sync', lambda: None)
    monkeypatch.setattr(backend_mod, 'CONFIG_DIR', settings.config_dir)
    monkeypatch.setattr(backend_mod, 'load_decky_settings', lambda: {})
    monkeypatch.setattr(backend_mod, 'save_decky_settings', lambda data: None)
    return backend, settings


async def call_rpc(backend, operation, collection):
    if operation == 'collection':
        return await backend.toggle_collection_sync(collection, True)
    if operation == 'steam':
        return (await backend.toggle_steam_integration(True))['success']
    return (await backend.reset_all_settings())['success']


def read_ini(path):
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path, encoding='utf-8')
    return parser


@pytest.mark.parametrize('operation', ['collection', 'steam', 'reset'])
@pytest.mark.parametrize('ansi_default', [False, True])
async def test_rpcs_preserve_literal_utf8_settings(settings_backend, monkeypatch, operation, ansi_default):
    backend, settings = settings_backend
    roms = str(Path.home() / 'ROM 東京 arşivi %50')
    collection = 'Oyunlar %50'
    settings.set('Download', 'rom_directory', roms)
    settings.set('RomM', 'client_token', 'test-only-credential')
    settings.set('Collections', 'actively_syncing', collection)
    encrypted = settings.config['RomM']['client_token']

    if ansi_default:
        # Deterministically emulate a legacy Windows default code page on any
        # host. Explicit UTF-8 operations must not depend on that default.
        for module in (builtins, io):
            original = module.open
            def ansi_open(file, mode='r', *args, _open=original, **kwargs):
                if (isinstance(file, (str, os.PathLike))
                        and Path(file) == settings.config_file and 'b' not in mode
                        and kwargs.get('encoding') in (None, 'locale')):
                    kwargs['encoding'] = 'cp1252'
                return _open(file, mode, *args, **kwargs)
            monkeypatch.setattr(module, 'open', ansi_open)

    assert await call_rpc(backend, operation, collection)
    saved = read_ini(settings.config_file)
    assert saved['Download']['rom_directory'] == roms
    assert saved['RomM']['client_token'] == encrypted
    assert saved['Collections']['actively_syncing'] == ('' if operation == 'reset' else collection)
    if operation == 'steam':
        assert saved['Steam']['enabled'] == 'true'
    settings.load_settings()
    assert settings.get('RomM', 'client_token') == 'test-only-credential'


@pytest.mark.parametrize('operation', ['collection', 'steam', 'reset'])
async def test_rpc_failed_replace_keeps_previous_settings(settings_backend, monkeypatch, operation):
    backend, settings = settings_backend
    settings.set('Collections', 'actively_syncing', 'Old library')
    before = settings.config_file.read_bytes()
    replace = os.replace
    def fail_settings_replace(source, target):
        if Path(target) == settings.config_file:
            raise PermissionError('settings destination busy')
        return replace(source, target)
    monkeypatch.setattr(os, 'replace', fail_settings_replace)
    assert not await call_rpc(backend, operation, 'New library')
    assert settings.config_file.read_bytes() == before
    assert not list(settings.config_dir.glob('settings-*.tmp'))
