"""RomM 5.5 library fetch: lighter, bigger pages and deletions named by id.

  * every GET /api/roms asks for with_provider_metadata=false (half of each
    page; nothing reads it from a list), unless the caller set it;
  * the walk uses 500-row pages on 5.5 and keeps 100 elsewhere;
  * a platform that only lost games is settled from /api/roms/identifiers
    without a walk; anything the ids don't fully explain is still walked,
    and a downloaded game is kept as an orphan as on every delete path.
"""
import threading

from ludo_app.backend import LudoBackend
from romm_sync_engine.sync_core import (
    LIBRARY_PAGE_SIZE, LIBRARY_PAGE_SIZE_5_5, RomMClient, _without_provider_metadata,
    server_version_at_least)


def test_metadata_flag_added_unless_set():
    assert _without_provider_metadata(None) == {'with_provider_metadata': 'false'}
    assert _without_provider_metadata({'limit': 5}) == {'limit': 5, 'with_provider_metadata': 'false'}
    assert _without_provider_metadata({'with_provider_metadata': 'true'}) == {'with_provider_metadata': 'true'}
    assert _without_provider_metadata([('platform_ids', 1)]) == [
        ('platform_ids', 1), ('with_provider_metadata', 'false')]


def test_session_adds_flag_only_to_rom_lists():
    c = RomMClient('http://romm.test')
    sent = []
    c.session.send = lambda req, **kw: sent.append(req.url) or (_ for _ in ()).throw(RuntimeError)
    for url in ('http://romm.test/api/roms', 'http://romm.test/api/roms/5'):
        try:
            c.session.get(url, params={'limit': 1})
        except RuntimeError:
            pass
    assert 'with_provider_metadata=false' in sent[0]
    assert 'with_provider_metadata' not in sent[1]


def test_page_size_follows_server_version():
    assert server_version_at_least('5.5.0-beta.1', (5, 5, 0))
    assert server_version_at_least('5.10.2', (5, 5, 0))
    assert not server_version_at_least('5.4.1', (5, 5, 0))
    assert not server_version_at_least(None, (5, 5, 0))
    c = RomMClient.__new__(RomMClient)
    c.server_features = {}
    assert c.library_page_size == LIBRARY_PAGE_SIZE
    c.server_features = {'version': '5.4.1'}
    assert c.library_page_size == LIBRARY_PAGE_SIZE
    c.server_features = {'version': '5.5.0-beta.1'}
    assert c.library_page_size == LIBRARY_PAGE_SIZE_5_5


def _g(rid, pid=1, sibs=(), **kw):
    return {'rom_id': rid, 'romm_data': {'platform_id': pid,
                                        'sibling_roms': [{'id': s} for s in sibs]}, **kw}


def test_removals_by_identifiers():
    f = LudoBackend._removals_by_identifiers
    games = [_g(1), _g(2), _g(3, sibs=[4]), _g(9, pid=2), _g(7, is_orphan=True)]
    server = {1, 3, 4, 9}
    assert f(games, 1, 1, server) == {2}
    assert f(games, 1, 2, server) is None            # drop not explained: an add too
    assert f(games, 1, 1, {1, 2, 3}) is None         # a sibling went: walk
    assert f(games, 1, 1, None) is None
    assert f(games, 1, 0, server) is None


class _Client:
    def __init__(self, ids):
        self.ids, self.calls = ids, 0

    def get_rom_identifiers(self):
        self.calls += 1
        return self.ids


def _backend(games, ids):
    b = LudoBackend.__new__(LudoBackend)
    b._games_lock = threading.RLock()
    b._available_games = list(games)
    b._romm_client = _Client(ids)
    b._library_platform_totals = {1: 4, 2: 10}
    b._library_platform_marks = {}
    return b


def test_drop_settles_pure_deletions(tmp_path):
    kept_file = tmp_path / 'b.gba'
    kept_file.write_bytes(b'x')
    games = [_g(1), _g(2), _g(3, is_downloaded=True, local_path=str(kept_file)), _g(5), _g(9, pid=2)]
    b = _backend(games, {1, 5, 9})
    stats = {'removed': 0}
    changed = [(1, {'slug': 'gba'}, 2), (2, {'slug': 'nes'}, 9)]
    left = b._drop_deletions_by_identifiers(changed, {1: 4, 2: 10}, {1: 'm'}, None, stats)
    assert [c[0] for c in left] == [2]                 # nes: drop not explained, walked
    ids = {g['rom_id']: g for g in b._available_games}
    assert 2 not in ids
    assert ids[3].get('is_orphan') is True             # downloaded: kept, flagged
    assert stats['removed'] == 1
    assert b._library_platform_totals[1] == 2 and b._library_platform_marks[1] == 'm'


def test_forced_or_growing_platforms_never_ask():
    b = _backend([_g(1)], {1})
    changed = [(1, {}, 5)]
    assert b._drop_deletions_by_identifiers(changed, {1: 4}, {}, None, {'removed': 0}) == changed
    assert b._drop_deletions_by_identifiers([(1, {}, 3)], {1: 4}, {}, {1}, {'removed': 0}) == [(1, {}, 3)]
    assert b._romm_client.calls == 0
