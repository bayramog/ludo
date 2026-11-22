#!/usr/bin/env python3
"""Run backend pytest with fixture-only roots and explicit platform accounting."""
import argparse
from pathlib import Path
from test_support import run_suite

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('patterns', nargs='*')
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--report-dir', type=Path)
    parser.add_argument('--timeout', type=float, default=300)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    raise SystemExit(run_suite('app', args.patterns, args.native, args.report_dir, args.timeout))
