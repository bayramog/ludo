"""Pairing again from the library banner must not park save sync.

Pairing holds the library fetch and save auto-sync for the setup wizard, and
only the wizard's finish lifts that hold. "Pair again" has no wizard behind
it, so save sync stayed off until the plugin reloaded: a PSP session played
right after re-pairing never uploaded (found while testing #97).

Run with:  pytest app/tests
"""
from pathlib import Path

import pytest

from ludo_app import backend as backend_mod
from ludo_app.backend import LudoBackend
from ludo_app.host import HostProfile

DESKTOP = HostProfile("1.0.0", "-x86_64.AppImage", Path("/tmp/desk-rt"), "desktop")


@pytest.fixture
def backend(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    b = LudoBackend(host=DESKTOP)
    monkeypatch.setattr(b, '_stop_sync', lambda *a, **k: None)
    monkeypatch.setattr(b, '_start_sync', lambda *a, **k: None)
    monkeypatch.setattr(backend_mod, '_record_activity', lambda *a, **k: None)
    return b


async def test_first_pairing_waits_for_the_wizard(backend):
    await backend._apply_pairing('https://romm.invalid', 'tok-1')
    assert backend._defer_library_fetch is True


async def test_pairing_again_keeps_sync_running(backend):
    s = backend._require_settings()
    s.set('RomM', 'url', 'https://romm.invalid')
    s.set('RomM', 'client_token', 'tok-old')
    await backend._apply_pairing('https://romm.invalid', 'tok-new')
    assert backend._defer_library_fetch is False
    assert s.get('RomM', 'client_token') == 'tok-new'


async def test_pairing_mid_setup_still_waits(backend):
    s = backend._require_settings()
    s.set('RomM', 'url', 'https://romm.invalid')
    s.set('RomM', 'client_token', 'tok-old')
    ds = backend_mod.load_decky_settings()
    ds['needs_onboarding'] = True
    backend_mod.save_decky_settings(ds)
    await backend._apply_pairing('https://romm.invalid', 'tok-new')
    assert backend._defer_library_fetch is True
