#!/usr/bin/env python3
"""Run actual standalone engine scripts with this Python, from the engine cwd.

No pip, network access or interpreter substitution here. Use run.sh for the
legacy dependency/venv bootstrap, or install engine into your chosen Python.
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from test_support import run_suite


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('patterns', nargs='*', help='OR-ed filename substrings (like run.sh)')
    parser.add_argument('--native', action='store_true', help='apply documented Windows exclusions')
    parser.add_argument('--report-dir', type=Path, help='new directory for bounded, structural evidence')
    parser.add_argument('--timeout', type=float, default=300, help='seconds per test script')
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    return run_suite('engine', args.patterns, args.native, args.report_dir, args.timeout)


if __name__ == '__main__':
    raise SystemExit(main())
