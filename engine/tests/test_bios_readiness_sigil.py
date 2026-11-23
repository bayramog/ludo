"""BIOS readiness integration: sigil; portable checks remain separate."""
import sys
import tempfile
from pathlib import Path
from test_bios_readiness import RetroArchInterface, check, FAILURES, make_ps2_iso


def main():
    ra = RetroArchInterface.__new__(RetroArchInterface)
    # A disc whose serial IS readable: the serial outranks everything, because
    # it is what the console's own BIOS checks.
    discs = Path(tempfile.mkdtemp())
    ntsc_u = discs / 'Disc (Europe).iso'      # deliberately mislabelled
    ntsc_u.write_bytes(make_ps2_iso('SCUS_974.90'))
    check('SCUS serial reads as America', ra._ps2_disc_region(ntsc_u), 'A')
    check('the serial beats RomM metadata',
          ra._ps2_disc_region(ntsc_u, ['Europe']), 'A')
    check('the serial beats a wrong filename tag',
          ra._ps2_disc_region(ntsc_u, None), 'A')
    pal = discs / 'Disc2.iso'
    pal.write_bytes(make_ps2_iso('SLES_123.45'))
    check('SLES serial reads as Europe', ra._ps2_disc_region(pal), 'E')
    jp = discs / 'Disc3.iso'
    jp.write_bytes(make_ps2_iso('SLPS_250.88'))
    check('SLPS serial reads as Japan', ra._ps2_disc_region(jp), 'J')

    return 1 if FAILURES else 0


if __name__ == '__main__':
    sys.exit(main())
