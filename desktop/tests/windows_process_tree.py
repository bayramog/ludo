"""Windows integration of job containment, external probes and owner-pipe loss."""
import faulthandler
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
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
        with subprocess.Popen([sys.executable, __file__, 'owner', mode], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, text=True) as proc:
            try:
                lines = queue.Queue()
                threading.Thread(target=lambda: lines.put(proc.stdout.readline()),
                                 daemon=True).start()
                ready = lines.get(timeout=8)
                self.assertTrue(ready, 'owner exited before its tree was ready')
                middle_pid, leaf_pid = map(int, ready.split())
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


def fixture_process(role):
    if role == 'owner':
        sys.path.insert(0, str(BACKEND))
        from windows_lifetime import watch_owner
        stopping = watch_owner()
        middle = subprocess.Popen([sys.executable, __file__, 'middle'], stdout=subprocess.PIPE)
        print(middle.pid, middle.stdout.readline().decode().strip(), flush=True)
        stopping.wait()
        if sys.argv[2] == 'owner-eof':
            time.sleep(90)  # exercise the backend watchdog
    elif role == 'middle':
        # Old POSIX launch contract: helper stdin is empty. The Windows
        # backend has a control pipe, but it must keep that pipe private.
        assert sys.stdin.buffer.read(1) == b''
        leaf = subprocess.Popen([sys.executable, __file__, 'leaf'])
        print(leaf.pid, flush=True)
        time.sleep(90)
    else:
        time.sleep(90)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        fixture_process(sys.argv[1])
    else:
        faulthandler.dump_traceback_later(60, exit=True)
        unittest.main(verbosity=2)
