"""The backend's import-time fixture isolates every user root on each OS."""
from pathlib import Path
import subprocess
import sys


def test_fixture_isolates_user_roots_before_importing_this_checkout():
    root = Path(__file__).resolve().parents[2]
    code = r'''
import os
from pathlib import Path
import runpy
import sys

root = Path(sys.argv[1])
runpy.run_path(str(root / 'app' / 'tests' / 'conftest.py'))
home = Path(os.environ['HOME'])
assert home == Path(os.environ['USERPROFILE']) == Path.home()
assert Path(os.environ['LOCALAPPDATA']) == home / 'AppData' / 'Local'
assert Path(os.environ['APPDATA']) == home / 'AppData' / 'Roaming'
assert len({home, Path(os.environ['LOCALAPPDATA']), Path(os.environ['APPDATA'])}) == 3
sys.path[:0] = [str(root / 'engine'), str(root / 'app')]
from romm_sync_engine import paths, sync_core
from ludo_app import backend
assert Path(paths.__file__).resolve().is_relative_to(root / 'engine')
assert Path(sync_core.__file__).resolve().is_relative_to(root / 'engine')
assert Path(backend.__file__).resolve().is_relative_to(root / 'app')
assert paths.config_dir().is_relative_to(home)
assert paths.machine_dir().is_relative_to(home)
assert paths.library_dir().is_relative_to(home)
'''
    result = subprocess.run([sys.executable, '-c', code, str(root)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
