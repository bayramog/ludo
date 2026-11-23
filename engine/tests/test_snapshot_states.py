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
    test_held_by_channel()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {FAILURES}")
        return 1
    print('all passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
