"""Windows integration of job containment, external probes and owner-pipe loss."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

import psutil

BACKEND = Path(__file__).resolve().parents[1] / 'backend'


class WindowsProcesses(unittest.TestCase):
    def test_owner_exit(self):
        # A sibling with a real emulator basename must remain observable and
        # alive through both a graceful owner stop and a hard termination.
        from romm_sync_engine import emulator_saves as emu, play_sessions

        with tempfile.TemporaryDirectory() as tmp:
            eden = Path(tmp) / 'Eden.exe'
            shutil.copyfile(Path(os.environ['SystemRoot']) / 'System32' / 'ping.exe', eden)
            with subprocess.Popen([eden, '-t', '127.0.0.1'], stdout=subprocess.DEVNULL) as external:
                try:
                    self.assertIn(external.pid, emu.eden_pids())
                    self.assertFalse(emu.close_eden())
                    for mode in ('quit', 'owner-eof', 'forced'):
                        with self.subTest(mode=mode):
                            self.exercise_tree(mode)
                            self.assertIsNone(external.poll())
                finally:
                    external.terminate()
                    external.wait(5)
        self.assertIsNotNone(play_sessions.suspended_seconds())
        current = play_sessions.boot_id()
        self.assertTrue(current)
        self.assertEqual(current, subprocess.check_output([
            sys.executable, '-c', 'from romm_sync_engine.play_sessions import boot_id; print(boot_id())'
        ], text=True).strip())

    def exercise_tree(self, mode):
        # The leaf inherits membership through the intermediate child. None
        # of these identifiers is used to locate processes for termination.
        leaf = "import time; time.sleep(90)"
        middle = ("import subprocess, sys, time; p=subprocess.Popen([sys.executable, '-c', "
                  + repr(leaf) + "]); print(p.pid, flush=True); time.sleep(90)")
        owner = ("import subprocess, sys, time; from windows_lifetime import watch_owner; "
                 "stopping=watch_owner(); p=subprocess.Popen([sys.executable, '-c', "
                 + repr(middle) + "], stdout=subprocess.PIPE); "
                 "print(p.pid, p.stdout.readline().decode().strip(), flush=True); "
                 "stopping.wait(); " + ("time.sleep(90)" if mode == 'owner-eof' else "sys.exit(0)"))
        with subprocess.Popen([sys.executable, '-c', owner], cwd=BACKEND, stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, text=True) as proc:
            try:
                middle_pid, leaf_pid = map(int, proc.stdout.readline().split())
                descendants = [psutil.Process(pid) for pid in (middle_pid, leaf_pid)]
                # Pause and resume a real contained process without changing ownership.
                descendants[0].suspend()
                descendants[0].resume()
                since = time.monotonic()
                if mode == 'forced':
                    proc.kill()  # original Popen handle
                elif mode == 'owner-eof':
                    proc.stdin.close()
                else:
                    proc.stdin.write('Q')
                    proc.stdin.flush()
                self.assertEqual(proc.wait(14), 0 if mode == 'quit' else 1)
                _, remaining = psutil.wait_procs(descendants, timeout=2)
                self.assertFalse(remaining)
                self.assertLess(time.monotonic() - since, 15)
            finally:
                if proc.poll() is None:
                    proc.kill()


if __name__ == '__main__':
    unittest.main(verbosity=2)
