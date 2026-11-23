"""Linux process ownership: live Eden, an unreaped zombie, and SIGTERM."""
import sys
import tempfile
import time
from pathlib import Path
from test_emulator_saves import E, check, FAILURES


def main():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        # --- a zombie is not a running emulator -----------------------
        # Ludo launches Eden with Popen and used not to wait on it, so a
        # finished Eden stayed in the process table as an unreaped child for
        # as long as Ludo lived, with /proc/<pid>/comm still readable. That
        # made eden_is_running() answer True forever: the save-sync boundary
        # never fired and Switch saves only reached the server after a Ludo
        # restart. A real zombie is spawned here because that is the only way
        # to exercise the state that actually shipped.
        import subprocess
        fake = d / 'edenfake'
        # A shell script, not a renamed copy of a binary: the copy exited at
        # once on GitHub's runners. The process name is the script's name.
        fake.write_text('#!/bin/sh\nwhile :; do sleep 1; done\n')
        fake.chmod(0o755)
        proc = subprocess.Popen([str(fake)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            time.sleep(0.5)
            check('a live eden* process reads as running',
                  E.eden_is_running(), True)
            if proc.poll() is not None:
                print(f"    fake Eden exited {proc.returncode}: {proc.stderr.read()!r}")
            proc.kill()
            # Deliberately NOT waited on: this IS the shipped state.
            for _ in range(20):
                time.sleep(0.1)
                state = ''
                for line in Path(f'/proc/{proc.pid}/status').read_text().splitlines():
                    if line.startswith('State:'):
                        state = line.split()[1]
                        break
                if state == 'Z':
                    break
            check('the killed process really is a zombie', state, 'Z')
            check('and a zombie does not read as running',
                  E.eden_is_running(), False)
        finally:
            proc.wait()

        # --- closing Eden so its settings can change --------------------
        # SIGTERM, then wait for it to go. Scoped to the fake alone: a real
        # Eden open on the machine running the tests must not be closed.
        proc = subprocess.Popen([str(fake), '30'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        every_eden = E.eden_pids
        E.eden_pids = lambda: [p for p in every_eden() if p == proc.pid]
        try:
            time.sleep(0.5)
            check('the fake Eden is seen', E.eden_pids(), [proc.pid])
            check('close_eden reports it gone', E.close_eden(timeout=5), True)
            check('and it went by SIGTERM', proc.wait(timeout=5), -15)
        finally:
            E.eden_pids = every_eden
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    return 1 if FAILURES else 0


if __name__ == '__main__':
    sys.exit(main())
