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
