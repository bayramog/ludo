"""Regressions for fixtures that previously lost whole Windows suites."""
import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'engine/tests'))
import test_flatpak_launcher_path as launcher
import test_play_sessions as sessions


class FixtureTests(unittest.TestCase):
    def test_launcher_fixture_isolates_windows_home_lookup(self):
        with tempfile.TemporaryDirectory() as temporary:
            inherited = Path(temporary) / 'inherited-profile'
            with patch.dict(os.environ, USERPROFILE=str(inherited)), \
                    patch.object(Path, 'home', side_effect=lambda: Path(os.environ['USERPROFILE'])), \
                    contextlib.redirect_stdout(io.StringIO()):
                launcher.FAILURES.clear()
                self.assertEqual(launcher.main(), 0, launcher.FAILURES)
            self.assertFalse(inherited.exists(), 'fixture wrote outside its own profile')

    def test_session_recovery_fixture_does_not_require_host_boot_identity(self):
        sessions.FAILURES.clear()
        with patch.object(sessions.ps, 'boot_id', return_value=''), \
                contextlib.redirect_stdout(io.StringIO()):
            sessions.test_recovery()
        self.assertEqual(sessions.FAILURES, [])


if __name__ == '__main__':
    unittest.main()
