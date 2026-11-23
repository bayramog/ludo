"""Shared Switch mod path conformance without native installation locks."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from romm_sync_engine import switch_mods as M
TITLE = '0100F2C0115B6000'


class ModPaths(unittest.TestCase):
    def test_shared_path_conformance(self):
        fixture = Path(__file__).parent / 'fixtures/switch-mod-paths.tsv'
        for line in fixture.read_text().splitlines():
            expected, name = line.split('\t')
            with self.subTest(name=name):
                if expected == 'reject':
                    with self.assertRaises(M.ModError):
                        M._target(name, TITLE)
                else:
                    target = M._target(name, TITLE)
                    self.assertEqual(target is not None, expected == 'install')


if __name__ == '__main__':
    unittest.main()
