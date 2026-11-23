"""Keep real Linux boot identity coverage alongside synthetic recovery cases."""
import sys
from pathlib import Path
from test_play_sessions import ps, check, FAILURES


def main():
    expected = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    check('the kernel supplies a boot identity', bool(expected), True)
    check('session recovery reads the real boot identity', ps.boot_id(), expected)
    return 1 if FAILURES else 0


if __name__ == '__main__':
    sys.exit(main())
