"""The API file ID is revalidated before a mod ZIP can be downloaded."""
import pytest
from ludo_app.backend import LudoBackend
from ludo_app.host import HostProfile
from mod_package_fixtures import client, M, MOD, TITLE, switch_mods


def test_only_existing_mod_zips_are_offered(client):
    result = M.state(client, 1200, TITLE)
    assert result['server'] == [{'file_id': 2, 'file_name': 'mods/backups/Example.zip',
                                  'package_id': '1200:2'}]
    assert result['installed'] == []


def test_forged_or_nonmod_file_id_never_downloads(client):
    for file_id in (1, 3, 4, 5, 999):
        assert M.install(client, 1200, TITLE, file_id, {}) == {'status': 'not-offered'}
    assert all('/content/' not in url for url, _ in client.calls)


def test_running_guard_stops_download_and_removal(client, monkeypatch):
    monkeypatch.setattr(M.emulator_saves, 'eden_is_running', lambda: True)
    assert M.install(client, 1200, TITLE, 2, {}) == {'status': 'running'}
    assert M.remove(TITLE, '1200:2') == {'status': 'running'}
    assert client.calls == []


def test_package_size_limit_stops_before_install(client, monkeypatch, tmp_path):
    monkeypatch.setattr(switch_mods, 'MAX_TOTAL_BYTES', 2)
    with pytest.raises(switch_mods.ModError):
        M.install(client, 1200, TITLE, 2, {})
    assert not (tmp_path / MOD).exists()


def test_recovery_before_launch_only_runs_for_a_pending_journal(monkeypatch):
    monkeypatch.setattr(M, 'pending', lambda: False)
    monkeypatch.setattr(M, 'recover', lambda: (_ for _ in ()).throw(AssertionError('unexpected recovery')))
    assert M.recover_before_launch() is None
    monkeypatch.setattr(M, 'pending', lambda: True)
    monkeypatch.setattr(M, 'recover', lambda: {'status': 'running'})
    assert 'Close Eden' in M.recover_before_launch()
    monkeypatch.setattr(M, 'recover', lambda: {'status': 'ok'})
    assert M.recover_before_launch() is None


async def test_both_launch_paths_share_the_mod_recovery_gate(monkeypatch, tmp_path):
    monkeypatch.setenv('HOME', str(tmp_path))
    backend = LudoBackend(host=HostProfile('test', '-x86_64.AppImage', tmp_path / 'runtime', 'desktop'))
    monkeypatch.setattr(backend, '_platform_slug_for', lambda g: g['platform_slug'])
    monkeypatch.setattr(M, 'recover_before_launch', lambda: 'recovery blocked')
    assert await backend._ready_to_boot({'platform_slug': 'switch'}, '/game.nsp') == (None, 'recovery blocked')
    assert await backend._ready_to_boot({'platform_slug': 'nes'}, '/game.nes') == ('/game.nes', None)
    backend._switch_fetch_state[42] = {'kind': 'mod'}
    path, reason = await backend._ready_to_boot({'platform_slug': 'switch'}, '/game.nsp')
    assert path is None and 'Wait for the mod' in reason
