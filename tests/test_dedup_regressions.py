"""Regressions for pact.dedup: wipe-root regex and the reported unique_prompt_ratio."""
import unittest

from pact.dedup import DESTRUCTIVE_CHOSEN_PATTERNS, deduplicate_dataset


class TestWipeRootPattern(unittest.TestCase):
    # The 'wipe-root' pattern flags training answers that teach `rm -rf /`.
    def setUp(self):
        self.rx = DESTRUCTIVE_CHOSEN_PATTERNS["wipe-root"]

    # Each command ends right after the slash, at a space, a glob or a semicolon;
    # the old trailing \b only matched before a word character, so all slipped through.
    def test_matches_at_end_of_string_and_before_separators(self):
        # The old pattern ended in \b, which cannot match after "/" at end of
        # string or before a space, so these were all missed.
        for cmd in ("rm -rf /", "sudo rm -rf / ", "rm -rf /*", "rm -rf /; echo", "rm -rf / --no-preserve-root"):
            self.assertIsNotNone(self.rx.search(cmd), cmd)

    # Negative side: deleting a subdirectory is ordinary and must not be flagged
    # (false positives would delete legitimate training rows).
    def test_does_not_match_ordinary_paths(self):
        for cmd in ("rm -rf /tmp/build", "rm -rf ./out", "rm -rf /home/user/x"):
            self.assertIsNone(self.rx.search(cmd), cmd)


class TestUniquePromptRatio(unittest.TestCase):
    # Two distinct prompts must give a ratio of exactly 1.0, computed over rows that
    # survive dedup rather than the original count.
    def test_ratio_is_computed_from_survivors(self):
        recs = [
            {"id": "a", "domain": "d", "prompt": "Explain topic alpha", "chosen": "x"},
            {"id": "b", "domain": "d", "prompt": "Describe quantum widgets", "chosen": "y"},
        ]
        kept, metrics = deduplicate_dataset(recs)
        self.assertEqual(len(kept), 2)
        self.assertEqual(metrics["unique_prompt_ratio"], 1.0)

    # Empty input must report 0.0 instead of raising ZeroDivisionError.
    def test_empty_input_reports_zero(self):
        _, metrics = deduplicate_dataset([])
        self.assertEqual(metrics["unique_prompt_ratio"], 0.0)


if __name__ == "__main__":
    unittest.main()
