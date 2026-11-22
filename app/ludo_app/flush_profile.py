"""Sync a closed profile's saves to RomM, then report what is still local-only.

Run as ``python -m ludo_app.flush_profile <profile id>`` in a process of its
own: the engine's paths are process-wide and fixed to one profile, so the open
profile's backend can't borrow them. Removing a profile runs this first and
deletes the profile's local saves only once nothing is left unsynced.

Prints one JSON line: ``{"status": "ok"|"no-account"|"offline"|"error",
"pending": <games still waiting>}``.
"""
import json
import logging
import sys
import time


def _report(status, pending=0, **extra):
    print(json.dumps({'status': status, 'pending': pending, **extra}), flush=True)


def _games(settings_url):
    from romm_sync_engine.paths import config_dir
    try:
        with open(config_dir() / 'library_snapshot.json', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return []
    if settings_url and data.get('server_url') and data['server_url'] != settings_url:
        return []
    return data.get('games') or []


def _syncable_pending(auto):
    """Games with saves still waiting to upload, leaving out files that match
    no game in the library: those have nowhere on RomM to go, so they can
    never sync and must not hold a removal up forever."""
    games = set()
    for group in auto.list_pending_saves():
        if any(auto.rom_id_for_save(f['path']) for f in group['files']):
            games.add(group['game'])
    return len(games)


def flush(profile_id, timeout=120):
    from romm_sync_engine import paths
    paths.set_app_id('ludo')
    paths.set_library_dir_name('Ludo')
    paths.set_profile(profile_id)

    from romm_sync_engine.sync_core import (
        AutoSyncManager, RetroArchInterface, RomMClient, SettingsManager)

    settings = SettingsManager()
    retroarch = RetroArchInterface()
    url = settings.get('RomM', 'url')
    username = settings.get('RomM', 'username')
    password = settings.get('RomM', 'password')
    token = settings.get('RomM', 'client_token', '')
    games = _games(url)
    auto = AutoSyncManager(
        romm_client=None, retroarch=retroarch, settings=settings,
        log_callback=lambda msg: logging.info(f"[FLUSH] {msg}"),
        get_games_callback=lambda: games, parent_window=None)
    pending = _syncable_pending(auto)
    if not pending:
        return 'ok', 0
    if not (url and (token or (username and password))):
        return 'no-account', pending

    client = RomMClient(url, username, password, client_token=token or None)
    if not client.authenticated:
        return 'offline', pending
    auto.romm_client = client
    auto.trigger_session_save_sync('profile removal')
    # The session runs on a thread of its own and holds this lock throughout.
    time.sleep(0.2)
    if auto._session_sync_lock.acquire(timeout=timeout):
        auto._session_sync_lock.release()
    auto._save_upload_fingerprints()
    return 'ok', _syncable_pending(auto)


def main(argv):
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    if len(argv) != 2:
        _report('error', error='usage: flush_profile <profile id>')
        return 2
    try:
        status, pending = flush(argv[1])
    except Exception as e:
        logging.exception('flush failed')
        _report('error', error=str(e))
        return 1
    _report(status, pending)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
