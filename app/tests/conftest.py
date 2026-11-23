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


import pytest


@pytest.fixture(autouse=True)
def isolated_user_roots(monkeypatch, tmp_path):
    """HOME alone does not isolate Path.home() or settings on Windows."""
    for key, value in {
        'HOME': tmp_path, 'USERPROFILE': tmp_path,
        'LOCALAPPDATA': tmp_path / 'AppData' / 'Local',
        'APPDATA': tmp_path / 'AppData' / 'Roaming',
    }.items():
        monkeypatch.setenv(key, str(value))
