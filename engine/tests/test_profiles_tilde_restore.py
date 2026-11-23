"""Original Linux tilde-abbreviated overlay restore contract.

The real Windows probe fails this specific case: _same_path_value only accepts
Unix ~/ suffixes, not native ~\\ state paths. Keep it visible under #16 while
all 21 other profile/store/overlay cases run natively on both operating systems.
"""
import unittest
import test_profiles as profiles


class TildeRestore(unittest.TestCase):
    def test_retroarch_saving_the_overlay_on_exit_is_undone(self):
        case = profiles.ProfilesTest()
        case.setUp()
        try:
            case.check_restore_overlay()
        finally:
            case.tearDown()


if __name__ == '__main__':
    unittest.main()
