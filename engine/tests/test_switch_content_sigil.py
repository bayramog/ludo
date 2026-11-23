"""The Switch package must retain and load its native Sigil dependency."""
import sys
from pathlib import Path
from test_switch_content import T, check, FAILURES


def main():
    # ── the bundled library is actually bundled ──────────────────────────
    # Two blanket rules nearly dropped it silently, each leaving a tree that
    # looks complete and a build that ships nothing: .gitignore's "*.so", and
    # pyproject shipping no package-data (the desktop AppImage pip-installs the
    # engine rather than importing the tree). Neither failure is visible at
    # runtime -- identification just goes back to reading filenames -- so it is
    # asserted here rather than trusted.
    bundled = (Path(__file__).resolve().parents[1]
               / 'romm_sync_engine' / 'bin' / 'libsigil.so')
    check('the Sigil build is present in the package', bundled.is_file(), True)
    check('and it loads without LUDO_SIGIL_LIB set', T.sigil_available(), True)

    return 1 if FAILURES else 0


if __name__ == '__main__':
    sys.exit(main())
