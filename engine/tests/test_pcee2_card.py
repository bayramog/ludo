#!/usr/bin/env python3
"""PCEE2 gets a card per game, shared with LRPS2's per-content card.

PCEE2 has no per-content card option; its slot 1 option picks a card from
<system>/pcsx2/memcards. Ludo keeps the card where LRPS2 keeps its own and
links it into memcards. Checked here: the link and the per-game options, the
user's own card left alone, a stale link repointed, other cores untouched,
and the RetroDECK 0.11 layout (memcards inside the saves tree) not reporting
the same card twice.
"""
import sys
import tempfile
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from romm_sync_engine import paths  # noqa: E402
paths.set_app_id('ludo')
from romm_sync_engine import ps2_memcard  # noqa: E402
from romm_sync_engine.sync_core import RetroArchInterface as RA  # noqa: E402

FAILURES = []


def check(label, got, want):
    ok = got == want
    print(f"{'ok  ' if ok else 'FAIL'} {label}: got={got!r} want={want!r}")
    if not ok:
        FAILURES.append(label)


def fake_ra(root, system, mode='content'):
    ra = types.SimpleNamespace(
        save_dirs={'saves': root / 'saves', 'states': root / 'states'},
        get_save_subdir_mode=lambda t='saves': mode,
        bios_manager=types.SimpleNamespace(system_dir=str(system)),
        find_retroarch_config_dir=lambda: root, _unconfigured_tree=lambda: None,
        _write_core_option=RA._write_core_option,
        _save_scan_dirs=RA._save_scan_dirs,
        SAVE_SCAN_MAX_DEPTH=RA.SAVE_SCAN_MAX_DEPTH,
        PCEE2_SLOT1_KEY=RA.PCEE2_SLOT1_KEY,
        PCEE2_SLOT2_ENABLE_KEY=RA.PCEE2_SLOT2_ENABLE_KEY)
    for name in ('_pcee2_card_home', '_ps2_option_files', '_ensure_pcee2_card',
                 'get_save_files'):
        setattr(ra, name, types.MethodType(getattr(RA, name), ra))
    return ra


def opts(root, stem):
    f = root / 'config' / 'PCEE2' / f"{stem}.opt"
    return f.read_text() if f.exists() else ''


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        rom = root / 'roms' / 'ps2' / 'Game (USA).iso'
        rom.parent.mkdir(parents=True)
        rom.write_bytes(b'')
        (root / 'saves').mkdir()
        (root / 'states').mkdir()
        system = root / 'bios'
        ra = fake_ra(root, system)
        core = '/cores/pcee2_libretro.so'

        ra._ensure_pcee2_card(str(rom), core)
        card = root / 'saves' / 'ps2' / 'Game (USA).ps2'
        link = system / 'pcsx2' / 'memcards' / 'Game (USA).ps2'
        check('a blank card is made where LRPS2 keeps its own', card.is_file(), True)
        check('the blank card is formatted', card.read_bytes() == ps2_memcard.format_card(), True)
        check('memcards holds a link to it', link.is_symlink() and link.resolve() == card.resolve(), True)
        o = opts(root, 'Game (USA)')
        check('slot 1 names the card', 'pcsx2_memcard_slot1_file = "Game (USA).ps2"' in o, True)
        check('slot 2 is off', 'pcsx2_memcard_slot2_enable = "disabled"' in o, True)

        # A second launch keeps the existing card and link.
        card.write_bytes(b'saved game')
        ra._ensure_pcee2_card(str(rom), core)
        check('a later launch keeps the card', card.read_bytes(), b'saved game')
        check('and the link', link.resolve() == card.resolve(), True)

        # A link left pointing somewhere else is repointed.
        link.unlink()
        link.symlink_to(root / 'elsewhere.ps2')
        ra._ensure_pcee2_card(str(rom), core)
        check('a stale link is repointed', link.resolve() == card.resolve(), True)

        # The user's own card under that name is left alone.
        rom2 = rom.with_name('Other (USA).iso')
        rom2.write_bytes(b'')
        own = system / 'pcsx2' / 'memcards' / 'Other (USA).ps2'
        own.write_bytes(b'mine')
        ra._ensure_pcee2_card(str(rom2), core)
        check("the user's own card is untouched", own.read_bytes(), b'mine')
        check('and no card is made for it', (root / 'saves' / 'ps2' / 'Other (USA).ps2').exists(), False)
        check('and slot 1 is not pointed at it', opts(root, 'Other (USA)'), '')

        # LRPS2 and other cores get none of this.
        rom3 = rom.with_name('Third (USA).iso')
        ra._ensure_pcee2_card(str(rom3), '/cores/pcsx2_libretro.so')
        check('LRPS2 launches make no link', (system / 'pcsx2' / 'memcards' / 'Third (USA).ps2').exists(), False)

    # RetroDECK 0.11: pcsx2/memcards lives inside the saves tree.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        rom = root / 'roms' / 'ps2' / 'Game (USA).iso'
        rom.parent.mkdir(parents=True)
        rom.write_bytes(b'')
        (root / 'states').mkdir()
        memcards = root / 'saves' / 'ps2' / 'pcsx2' / 'memcards'
        memcards.mkdir(parents=True)
        system = root / 'bios'
        (system / 'pcsx2').mkdir(parents=True)
        (system / 'pcsx2' / 'memcards').symlink_to(memcards)
        ra = fake_ra(root, system)
        ra._ensure_pcee2_card(str(rom), '/cores/pcee2_libretro.so')
        found = [e['relative_path'] for e in ra.get_save_files()['saves']]
        check('the card is reported once, under its real path', found, [str(Path('ps2') / 'Game (USA).ps2')])

    if FAILURES:
        print(f"\nFAILED: {', '.join(FAILURES)}")
        sys.exit(1)
    print("\nall passed")


if __name__ == '__main__':
    main()
