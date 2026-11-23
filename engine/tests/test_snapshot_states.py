"""States in channel snapshots, on disk (RomM 5.5).

A snapshot carries a states bank beside its save. Ludo reads the bank's slots
from the folder RetroArch reads for the game's core, keyed the way Argosy keys
them, and writes a downloaded bank back there. Asserted:

  * the core is the libretro library name, found through the .info files
    whether Ludo recorded the library name or the folder name;
  * only the core's own folder is scanned, slots keyed '0', 'N', 'auto',
    each with its screenshot; the launch's stem wins a slot both carry;
  * a download writes every slot the bank holds with its screenshot, backs
    up a differing local state when asked, and never deletes a slot the bank
    lacks; a refill only fills slots missing on disk;
  * a 409 for a file a channel holds is told apart from a real conflict.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from romm_sync_engine import save_channels  # noqa: E402
from romm_sync_engine.sync_core import AutoSyncManager, RetroArchInterface, RomMClient  # noqa: E402

FAILURES = []


def check(label, got, want):
    ok = got == want
    print(f"{'ok  ' if ok else 'FAIL'} {label}: got={got!r} want={want!r}")
    if not ok:
        FAILURES.append(label)


def _retroarch(info_dir):
    ra = RetroArchInterface.__new__(RetroArchInterface)
    ra.get_retroarch_config_setting = lambda key, default='': str(info_dir)
    ra.emulator_directory_map = {}
    return ra


def test_core_library_id():
    with tempfile.TemporaryDirectory() as d:
        info = Path(d)
        (info / 'mgba_libretro.info').write_text('corename = "mGBA"\n')
        (info / 'mednafen_psx_hw_libretro.info').write_text('corename = "Beetle PSX HW"\n')
        (info / 'melondsds_libretro.info').write_text('corename = "melonDS DS"\n')
        ra = _retroarch(info)
        check('library name as recorded', ra.core_library_id('mgba'), 'mgba')
        check('folder name resolved', ra.core_library_id('beetle_psx_hw'), 'mednafen_psx_hw')
        check('underscore spelling', ra.core_library_id('melonds_ds'), 'melondsds')
        check('unknown core', ra.core_library_id('nothing_here'), None)


class Api:
    def __init__(self, blobs):
        self.blobs, self.fetched = blobs, []

    def download(self, path):
        self.fetched.append(path)
        return self.blobs.get(path)


class Sync:
    def __init__(self, api):
        self.api = api


def _manager(states_dir, info_dir):
    m = AutoSyncManager.__new__(AutoSyncManager)
    m.retroarch = _retroarch(info_dir)
    m.retroarch.save_dirs = {'states': str(states_dir)}
    m.retroarch.get_save_subdir_mode = lambda kind: 'core'
    m._launch_stems = {1: 'Game (Track 1)'}
    m.log = lambda *a, **k: None
    return m


def test_scan_and_write():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        info = root / 'info'
        info.mkdir()
        (info / 'mgba_libretro.info').write_text('corename = "mGBA"\n')
        states = root / 'states'
        folder = states / 'mGBA'
        folder.mkdir(parents=True)
        other = states / 'VBA Next'
        other.mkdir()
        (folder / 'Game.state').write_bytes(b'zero')
        (folder / 'Game.state2').write_bytes(b'two')
        (folder / 'Game.state2.png').write_bytes(b'png2')
        (folder / 'Game.state.auto').write_bytes(b'auto-old')
        (folder / 'Game (Track 1).state2').write_bytes(b'two-launch')
        (folder / 'Other Game.state').write_bytes(b'not ours')
        (other / 'Game.state5').write_bytes(b'other core')

        m = _manager(states, info)
        game = {'rom_id': 1, 'name': 'Game', 'local_path': str(root / 'roms' / 'Game.gba')}
        local = m._channel_states(game, 'mgba')
        check('core', local.core, 'mgba')
        check('slots', [p.slot for p in local.parts], ['0', '2', 'auto'])
        two = next(p for p in local.parts if p.slot == '2')
        check('launch stem wins', two.path.name, 'Game (Track 1).state2')
        zero = next(p for p in local.parts if p.slot == '0')
        check('hash', zero.content_hash, RomMClient.compute_content_hash(folder / 'Game.state'))
        check('no screenshot', zero.screenshot, None)
        check('unknown core banks nothing', m._channel_states(game, 'nothing_here'), None)

        snap = {'states': {
            'mgba': {
                'auto': {'content_hash': 'new', 'download_path': '/a',
                         'screenshot': {'id': 1, 'download_path': '/a.png'}},
                '0': {'content_hash': zero.content_hash, 'download_path': '/zero'},
                '7': {'content_hash': 'seven', 'download_path': '/seven'},
            },
            'vba_next': {'5': {'content_hash': 'x', 'download_path': '/x'}},
        }}
        api = Api({'/a': b'auto-new', '/a.png': b'shot', '/seven': b'seven'})

        # Refill: only the slot missing here.
        ok = m._write_channel_states(Sync(api), game, local, snap, overwrite=False)
        check('refill ok', ok, True)
        check('refill fetched', api.fetched, ['/seven'])
        check('refill named after the launch', (folder / 'Game (Track 1).state7').read_bytes(), b'seven')
        check('refill kept local auto', (folder / 'Game.state.auto').read_bytes(), b'auto-old')

        # Download: overwrite differing slots, with backup and screenshot.
        api.fetched.clear()
        ok = m._write_channel_states(Sync(api), game, local, snap, overwrite=True, backup=True)
        check('download fetched differing only', sorted(api.fetched), ['/a', '/a.png', '/seven'])
        check('auto replaced', (folder / 'Game.state.auto').read_bytes(), b'auto-new')
        check('screenshot written', (folder / 'Game.state.auto.png').read_bytes(), b'shot')
        backups = [p.name for p in folder.glob('Game.state.auto.local-*')]
        check('local backed up', len(backups), 1)
        check('slot outside the bank kept', (folder / 'Game.state2').read_bytes(), b'two')
        check('other core untouched', (other / 'Game.state5').read_bytes(), b'other core')

        api = Api({})
        check('failed download reported',
              m._write_channel_states(Sync(api), game, local,
                                      {'states': {'mgba': {'9': {'content_hash': 'n',
                                                                 'download_path': '/nine'}}}},
                                      overwrite=True), False)


def test_channel_download_order():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        info = root / 'info'
        info.mkdir()
        (info / 'mgba_libretro.info').write_text('corename = "mGBA"\n')
        folder = root / 'states' / 'mGBA'
        folder.mkdir(parents=True)
        m = _manager(root / 'states', info)
        game = {'rom_id': 1, 'name': 'Game', 'local_path': str(root / 'roms' / 'Game.gba')}
        local = m._channel_states(game, 'mgba')
        save = root / 'Game.srm'
        save.write_bytes(b'old save')
        bank = {'mgba': {'1': {'content_hash': 'n', 'download_path': '/one'}}}

        class DlApi(Api):
            def __init__(self, blobs, save_bytes):
                super().__init__(blobs)
                self.save_bytes = save_bytes

            def save_content(self, sid):
                return self.save_bytes

        class DlSync(Sync):
            held = None

            def finish_download(self, rom_file_id, channel, snapshot):
                DlSync.held = snapshot['id']

        out = save_channels.ChannelOutcome('download', snapshot={'id': 9, 'save': {'id': 90},
                                                                 'states': bank})
        api = DlApi({'/one': b'one'}, None)
        res = m._write_channel_download(DlSync(api), 5, save, out, game=game, states=local)
        check('failed save download', res.kind, 'failed')
        check('no state written before the save is in hand', (folder / 'Game (Track 1).state1').exists(), False)

        out = save_channels.ChannelOutcome('download', snapshot={'id': 8, 'states': bank})
        res = m._write_channel_download(DlSync(DlApi({'/one': b'one'}, None)), 5, save, out,
                                        game=game, states=local)
        check('states-only snapshot downloads', res.kind, 'downloaded')
        check('its states land', (folder / 'Game (Track 1).state1').read_bytes(), b'one')
        check('and it is held', DlSync.held, 8)
        check('local save untouched', save.read_bytes(), b'old save')

        m._channel_state_dirs = {1: {str(folder.resolve())}}
        check('state in the scanned folder diverts', m._state_in_channel(1, folder / 'Game.state3'), True)
        check('another core keeps the legacy path',
              m._state_in_channel(1, root / 'states' / 'gpSP' / 'Game.state3'), False)
        check('another game keeps the legacy path', m._state_in_channel(2, folder / 'X.state'), False)


def test_held_by_channel():
    class R:
        def __init__(self, body, text=''):
            self._body, self.text = body, text

        def json(self):
            if self._body is None:
                raise ValueError
            return self._body

    check('channel 409', RomMClient._held_by_channel(R({'detail': 'The state belongs to a sync channel.'})), True)
    check('plain conflict', RomMClient._held_by_channel(R({'detail': 'Save conflict'})), False)
    check('text body', RomMClient._held_by_channel(R(None, 'belongs to a sync channel')), True)


def main():
    test_core_library_id()
    test_scan_and_write()
    test_channel_download_order()
    test_held_by_channel()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {FAILURES}")
        return 1
    print('all passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
