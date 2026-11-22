#!/usr/bin/env python3
"""A process that loses the auto-sync lock must not break the owner's (#93).

release() used to unlink autosync.lock even in the process that never held
it, and acquire() opened it truncating. A loser's restart then locked a fresh
file while the owner still held the old one: two auto-syncs at once. flock
contends between separate opens in one process, so three instances here
stand in for three processes.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from romm_sync_engine.sync_core import AutoSyncLock  # noqa: E402

FAILURES = []


def check(label, got, want):
    ok = got == want
    print(f"{'ok  ' if ok else 'FAIL'} {label}: got={got!r} want={want!r}")
    if not ok:
        FAILURES.append(label)


def lock_at(path):
    lk = AutoSyncLock.__new__(AutoSyncLock)
    lk.lock_file = path
    lk.lock_fd = None
    return lk


def main():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'autosync.lock'
        a, b, c = lock_at(path), lock_at(path), lock_at(path)
        check('owner acquires', a.acquire('A'), True)
        owner_info = path.read_text()
        check('a second process is refused', b.acquire('B'), False)
        check("the loser leaves the owner's details", path.read_text(), owner_info)
        b.release()
        check('the loser releasing keeps the file', path.exists(), True)
        check('a third process is still refused', c.acquire('C'), False)
        check('the loser restarting is still refused', b.acquire('B'), False)
        a.release()
        check('after the owner leaves, the next one gets it', c.acquire('C'), True)
        c.release()
    if FAILURES:
        print(f"\nFAILED: {', '.join(FAILURES)}")
        sys.exit(1)
    print("\nall passed")


if __name__ == '__main__':
    main()
