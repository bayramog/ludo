"""Real disc identity through the bundled Sigil, including zipped fixtures."""
import sys
import tempfile
from pathlib import Path
from test_title_ids import (T, check, FAILURES, make_gamecube, make_iso9660,
                            make_dreamcast, zipped)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        check('sigil is bundled and loads', T.sigil_available(), True)

        # ── Disc-based readers ────────────────────────────────────────────
        # GameCube and Wii report the hex of the game code as title_id; the
        # save name is the ASCII code (GameCube, which Dolphin writes into
        # every .gci name) or its lowercase hex (Wii, Dolphin's title folder).
        melee = T.identify(make_gamecube(d / 'melee.iso'), platform='ngc')
        check('gamecube iso', (melee or {}).get('title_id'), '47414C45')
        check('gamecube save name is the game code', (melee or {}).get('save_id'), 'GALE')
        check('gamecube saves share a prefix', (melee or {}).get('usage'), 'file-prefix')
        brawl = T.identify(make_gamecube(d / 'brawl.iso', b'RSBE01', wii=True),
                           platform='wii')
        check('wii iso', (brawl or {}).get('title_id'), '52534245')
        check('wii save folder is lowercase hex', (brawl or {}).get('save_id'), '52534245'.lower())

        # Six printable bytes at offset 0 are not enough when nothing names
        # the platform; the disc magic is what makes reading an arbitrary .iso
        # safe. (A NAMED platform is taken at its word, upstream's choice, and
        # Ludo only names one from the folder a ROM was downloaded into.)
        (d / 'random.wbfs').write_bytes(b'ABCDEF' + bytes(0x200))
        check('non-disc image is not identified',
              T.title_id_from_rom(d / 'random.wbfs'), None)

        gt4 = make_iso9660(d / 'gt4.iso',
                           {'SYSTEM.CNF;1': b'BOOT2 = cdrom0:\\SCUS_972.68;1\nVER = 1.00\n'})
        check('ps2 serial from SYSTEM.CNF', T.title_id_from_rom(gt4, platform='ps2'),
              'SCUS-97268')
        check('ps2 save folders carry the region prefix',
              (T.identify(gt4, platform='ps2') or {}).get('save_id'), 'BASCUS-97268')
        check('psp serial from UMD_DATA.BIN', T.title_id_from_rom(make_iso9660(
            d / 'gow.iso',
            {'UMD_DATA.BIN;1': b'ULUS10064|0123456789ABCDEF|0001|G'}), platform='psp'),
            'ULUS10064')
        crazy = T.identify(make_dreamcast(d / 'track03.bin'), platform='dc')
        check('dreamcast product number from IP.BIN',
              (crazy or {}).get('title_id'), 'T1401D  50')

        # A bare .iso could be any of five consoles, so with no platform named
        # nothing is guessed -- but a ROM in Ludo's roms/<platform>/ layout
        # names its platform by where it sits, folder of its own or not.
        check('an .iso with no platform is not guessed at',
              T.title_id_from_rom(make_gamecube(d / 'loose.iso')), None)
        nested = d / 'library' / 'gc' / 'Melee (USA)'
        nested.mkdir(parents=True)
        check('the platform folder names the platform',
              T.title_id_from_rom(make_gamecube(nested / 'Melee (USA).iso')), '47414C45')
        (nested / 'Melee (USA).iso').unlink()

        # RomM serves a game zipped; Sigil reads the member in place, so a
        # library left zipped is as identifiable as an extracted one. The
        # inner name is deliberately unlike the archive's.
        check('zipped gamecube',
              T.title_id_from_rom(zipped(make_gamecube(d / 'z_gc.iso'), 'Melee.iso'),
                                  platform='ngc'), '47414C45')
        check('zipped ps2', T.title_id_from_rom(zipped(make_iso9660(
            d / 'z_ps2.iso', {'SYSTEM.CNF;1': b'BOOT2 = cdrom0:\\SLUS_202.02;1\n'})),
            platform='ps2'), 'SLUS-20202')
        check('zipped dreamcast', T.title_id_from_rom(
            zipped(make_dreamcast(d / 'z_dc.bin'), 'Crazy Taxi (USA) (Track 3).bin'),
            platform='dreamcast'), 'T1401D  50')


    return 1 if FAILURES else 0


if __name__ == '__main__':
    sys.exit(main())
