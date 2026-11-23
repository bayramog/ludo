"""Portable native-loader fallback, filename and failure-message contracts."""
import sys
from test_switch_nsz import test_contracts, FAILURES


if __name__ == '__main__':
    test_contracts()
    sys.exit(1 if FAILURES else 0)
