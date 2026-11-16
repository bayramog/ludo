"""Keep the test run out of the real ~/.config/ludo.

The backend resolves its config folder from HOME when it is imported and
opens debug.log there, so HOME has to point somewhere else before any test
module imports it. Tests that need their own HOME still set one per test.
"""
import os
import tempfile

_home = tempfile.mkdtemp(prefix="ludo-tests-home-")
os.environ.update(HOME=_home, USERPROFILE=_home,
                  LOCALAPPDATA=os.path.join(_home, 'AppData', 'Local'),
                  APPDATA=os.path.join(_home, 'AppData', 'Roaming'))
