"""save_convert: which downloads need sigil, and the conversion itself."""
import sys
import tempfile
import zipfile
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from romm_sync_engine import save_convert as C  # noqa: E402
from romm_sync_engine import sigil_saves as S  # noqa: E402

failures = []


def check(name, got, want):
    if got != want:
        failures.append(name)
        print(f'FAIL {name}: got={got!r} want={want!r}')


def decisions():
    n = C.needs_conversion
    check('plain srm same core', n('Mario.srm', 'mupen64plus_next', 'n64', 'mupen64plus_next'), False)
    check('srm other libretro core', n('Mario.srm', 'parallel_n64', 'n64', 'mupen64plus_next'), False)
    check('n64 zip unit', n('Mario.zip', 'mupen64plus_next', 'n64', 'mupen64plus_next'), True)
    check('duckstation mcd', n('FF7_1.mcd', 'duckstation', 'psx', 'pcsx_rearmed'), True)
    check('standalone tag', n('Game.srm', 'flycast_standalone', 'dreamcast', 'flycast'), True)
    check('core with suffix', n('Mario.zip', '', 'n64', 'mupen64plus_next_libretro.so'), True)
    check('gba not synced', n('Game.sav', 'mgba', 'gba', 'mgba'), False)
    check('no core', n('Mario.zip', '', 'n64', None), False)


def _n64_unit(d):
    src = d / 'src'
    src.mkdir()
    srm = bytearray(b'\xff' * 0x48800)
    srm[0:0x800] = bytes(0x800)
    srm[0:16] = b'EEPROMDATA123456'
    (src / 'Mario.srm').write_bytes(bytes(srm))
    return S.collect(S.Game(platform='n64'), 'mupen64plus_next', 'Mario.z64', src).data


def n64_zip_becomes_srm():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        unit = _n64_unit(d)
        saves = d / 'saves'
        saves.mkdir()
        dl = saves / 'Mario.zip'
        dl.write_bytes(unit)
        ok = C.convert_into_core(dl, saves / 'Super Mario 64.srm', 'n64',
                                 'parallel_n64', None, log=lambda *_: None)
        check('n64 converted', ok, True)
        check('n64 files', sorted(p.name for p in saves.iterdir()), ['Super Mario 64.srm'])
        check('n64 eeprom', (saves / 'Super Mario 64.srm').read_bytes()[:16],
              b'EEPROMDATA123456')


def refusal_leaves_raw():
    with tempfile.TemporaryDirectory() as d:
        saves = Path(d)
        dl = saves / 'Mario.zip'
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('junk.txt', 'nope')
        dl.write_bytes(buf.getvalue())
        ok = C.convert_into_core(dl, saves / 'Mario.srm', 'n64', 'mupen64plus_next',
                                 None, log=lambda *_: None)
        check('refused', ok, False)
        check('raw kept, nothing else', sorted(p.name for p in saves.iterdir()), ['Mario.zip'])


if __name__ == '__main__':
    decisions()
    if S.available():
        n64_zip_becomes_srm()
        refusal_leaves_raw()
    else:
        print('skip conversion: sigil without collect/restore')
    if failures:
        print(f'{len(failures)} failure(s)')
        sys.exit(1)
    print('ok')
