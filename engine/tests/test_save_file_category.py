#!/usr/bin/env python3
"""A save is named after the game's own file, not its DLC or updates (#95).

find_rom_id_for_save_file matches a save against the ROM's `files` array. A
game with a DLC or update file must not claim saves named after that file;
a file with no category (top-level files, older snapshots) still counts.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from romm_sync_engine.sync_core import AutoSyncManager  # noqa: E402

FAILURES = []


def check(label, got, want):
    ok = got == want
    print(f"{'ok  ' if ok else 'FAIL'} {label}: got={got!r} want={want!r}")
    if not ok:
        FAILURES.append(label)


def manager(files):
    games = [{'rom_id': 7, 'name': 'Folder Game',
              'romm_data': {'fs_name_no_ext': 'Folder Game', 'name': 'Folder Game',
                            'platform_slug': 'psx', 'files': files}}]
    m = AutoSyncManager.__new__(AutoSyncManager)
    m.get_games = lambda: games
    m._rom_match_cache = {}
    m._rom_match_games = None
    m._rom_id_for_launch_alias = lambda a, b: None
    m._rom_id_for_title_id = lambda t: None
    return m


def main():
    save = Path('/saves/Disc One.srm')
    for label, category, want in (
            ('a game file names the save', 'game', 7),
            ('an uncategorised file still names it', None, 7),
            ('a dlc file does not', 'dlc', None),
            ('an update file does not', 'update', None)):
        m = manager([{'file_name': 'Disc One.bin', 'category': category}])
        check(label, m.find_rom_id_for_save_file(save), want)
    if FAILURES:
        print(f"\nFAILED: {', '.join(FAILURES)}")
        sys.exit(1)
    print("\nall passed")


if __name__ == '__main__':
    main()
