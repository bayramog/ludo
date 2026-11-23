"""Real POSIX executable-bit adoption, split from portable Cemu fixtures."""
import tempfile
from pathlib import Path
from unittest.mock import patch
from test_cemu_standalone import (sync_core, STANDALONE_EMULATORS,
    find_standalone_executable, touch, check, FAILED)


def main():
    spec = STANDALONE_EMULATORS['cemu']
    with tempfile.TemporaryDirectory() as tmp:
        app = touch(Path(tmp) / 'Cemu-2.6-x86_64.AppImage', exec_=True)
        with patch.object(sync_core, '_standalone_appimage_dirs', return_value=[Path(tmp)]), \
                patch.object(sync_core, 'flatpak_app_installed', return_value=False), \
                patch.object(sync_core.shutil, 'which', return_value=None):
            app.chmod(0o644)
            check('non-executable appimage made executable',
                  find_standalone_executable('cemu', spec), str(app))
            check('exec bit added', bool(app.stat().st_mode & 0o100), True)
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
