"""Keep the test run out of the real per-user configuration folders.

The backend resolves its config folder when it is imported and opens debug.log
there. Isolate all home/app-data roots before any test module imports it,
including on Windows. Tests that need their own HOME still set one per test.
"""
import os
import tempfile

_test_home = tempfile.mkdtemp(prefix="ludo-tests-home-")
os.environ.update(HOME=_test_home, USERPROFILE=_test_home,
                  LOCALAPPDATA=os.path.join(_test_home, 'AppData', 'Local'),
                  APPDATA=os.path.join(_test_home, 'AppData', 'Roaming'))
