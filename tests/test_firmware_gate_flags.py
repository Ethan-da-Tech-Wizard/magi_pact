"""Regression: the --force / --reboot deny patterns used "\\b--flag\\b", which never matches.

"\\b" needs a word character on one side, and "-" is not one, so " --force" slipped
through any command that no other pattern happened to catch.
"""
import unittest

from pact.systems import FirmwareSafetyGate, FirmwareSafetyViolation


class TestFirmwareGateFlags(unittest.TestCase):
    def test_flags_after_a_space_are_blocked(self):
        # Neither command contains another hazardous keyword, so only the flag
        # patterns can block them.
        for cmd in ("somecmd --force", "systemctl something --reboot now", "--force"):
            with self.assertRaises(FirmwareSafetyViolation, msg=cmd):
                FirmwareSafetyGate.verify_command_safety(cmd)

    def test_similar_looking_text_is_not_blocked(self):
        # Flag must start a token and end at a boundary: no false positives on
        # longer option names or read-only fwupd queries.
        for cmd in ("fwupdmgr get-devices", "tool --forceful", "tool --rebooting"):
            self.assertTrue(FirmwareSafetyGate.verify_command_safety(cmd), cmd)


if __name__ == "__main__":
    unittest.main()
