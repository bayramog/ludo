#!/usr/bin/env python3
"""RetroArch counts as running when a core renames its main thread (#97).

PPSSPP renames the thread, so the process name stops being 'retroarch', and
our launches put '<app>-launch.cfg' on the command line, which the
own-process filter rejected. The close transition never fired, so a PSP save
stayed local until some other game's save triggered a sync.
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from romm_sync_engine import paths  # noqa: E402
from romm_sync_engine.sync_core import AutoSyncManager  # noqa: E402

paths.set_app_id('ludo')

FAILURES = []


def check(label, got, want):
    ok = got == want
    print(f"{'ok  ' if ok else 'FAIL'} {label}: got={got!r} want={want!r}")
    if not ok:
        FAILURES.append(label)


class Proc:
    def __init__(self, name, cmdline):
        self.info = {'pid': 4242, 'name': name, 'cmdline': cmdline, 'status': 'sleeping'}


def running(procs):
    fake = types.ModuleType('psutil')
    fake.process_iter = lambda attrs: iter(procs)
    for err in ('NoSuchProcess', 'AccessDenied', 'ZombieProcess'):
        setattr(fake, err, type(err, (Exception,), {}))
    sys.modules['psutil'] = fake
    m = AutoSyncManager.__new__(AutoSyncManager)
    return m.is_retroarch_running()


ARGV = ['/app/retrodeck/components/retroarch/bin/retroarch', '-L',
        '/app/retrodeck/components/retroarch/rd_extras/cores/ppsspp_libretro.so',
        '/run/media/ROMM/retrodeck/roms/psp/Pangya.chd', '--appendconfig',
        '/home/deck/.var/app/net.retrodeck.retrodeck/config/retroarch/ludo-launch.cfg']


def main():
    check('plain retroarch process', running([Proc('retroarch', ARGV)]), True)
    check('thread renamed by the core', running([Proc('EmuThread', ARGV)]), True)
    check('our own process is still skipped',
          running([Proc('python3', ['python3', '-m', 'ludo_app', '--retroarch-content'])]),
          False)
    check('nothing running', running([]), False)
    if FAILURES:
        print(f"\nFAILED: {', '.join(FAILURES)}")
        sys.exit(1)
    print("\nall passed")


if __name__ == '__main__':
    main()
