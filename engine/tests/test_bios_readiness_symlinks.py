"""BIOS readiness integration: symlinks; portable checks remain separate."""
import sys
import tempfile
from pathlib import Path
from test_bios_readiness import RetroArchInterface, check, FAILURES


def main():
    ra = RetroArchInterface.__new__(RetroArchInterface)
    print("\nPS2 memory cards are found and made per-game")
    saves_root = Path(tempfile.mkdtemp())
    # RetroDECK's real layout: the memcards dir is a symlink, three levels down.
    deep = saves_root / 'ps2' / 'retroarch-core' / 'LRPS2' / 'memcards'
    deep.mkdir(parents=True)
    (deep / 'Mcd001.ps2').write_bytes(b'\x00' * 64)
    (saves_root / 'n64').mkdir()
    (saves_root / 'n64' / 'Game (Europe).srm').write_bytes(b'\x00' * 16)
    linked = saves_root / 'linked'
    linked.symlink_to(deep)

    ra.save_dirs = {'saves': saves_root}
    seen = sorted(f['relative_path'] for f in ra.get_save_files()['saves'])
    check('the deep memory card is discovered',
          any(r.endswith(str(Path('memcards') / 'Mcd001.ps2')) for r in seen), True)
    check('ordinary saves still found',
          any(r.endswith('Game (Europe).srm') for r in seen), True)
    # Followed through the symlink, but the same real file is not listed twice.
    check('a symlinked dir does not duplicate entries',
          len(seen), len(set(seen)))

    # …and it is the REAL path that is reported, not the alias — whichever
    # order the filesystem hands the directories back. This passed by luck for
    # one iterdir order and failed for the other, which is how a green local
    # run and a red CI run came from the same commit.
    real_iterdir = Path.iterdir
    for label, order in (('ascending', sorted),
                         ('descending', lambda xs: sorted(xs, reverse=True))):
        Path.iterdir = (lambda self, _o=order, _f=real_iterdir:
                        iter(_o(list(_f(self)))))
        try:
            paths = [f['relative_path'] for f in ra.get_save_files()['saves']]
        finally:
            Path.iterdir = real_iterdir
        card = [r for r in paths if r.endswith('Mcd001.ps2')]
        check(f'the card is found under its real path ({label})',
              card, [str(Path('ps2/retroarch-core/LRPS2/memcards/Mcd001.ps2'))])

    # A save folder pointed somewhere enormous must not be walked forever.
    depth_root = Path(tempfile.mkdtemp())
    node = depth_root
    for i in range(10):
        node = node / f'level{i}'
        node.mkdir()
    (node / 'Too Deep.srm').write_bytes(b'\x00')
    ra.save_dirs = {'saves': depth_root}
    deep_seen = [f['relative_path'] for f in ra.get_save_files()['saves']]
    check('the walk is depth-bounded', deep_seen, [])

    # A symlink loop must terminate rather than hang.
    loop_root = Path(tempfile.mkdtemp())
    (loop_root / 'sub').mkdir()
    (loop_root / 'sub' / 'back').symlink_to(loop_root)
    ra.save_dirs = {'saves': loop_root}
    check('a symlink loop terminates', ra.get_save_files()['saves'], [])


    return 1 if FAILURES else 0


if __name__ == '__main__':
    sys.exit(main())
