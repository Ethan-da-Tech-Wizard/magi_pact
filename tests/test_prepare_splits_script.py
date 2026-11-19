"""Regression: prepare_lora_dataset_splits.py printed a fixed 'Cross-Split Overlap: 0'."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class TestPrepareSplitsReport(unittest.TestCase):
    def test_overlap_line_reports_measured_counts(self):
        with tempfile.TemporaryDirectory() as out:
            run = subprocess.run(
                [sys.executable, str(REPO / "scripts" / "prepare_lora_dataset_splits.py"), "--out-dir", out],
                cwd=REPO, capture_output=True, text=True,
            )
        self.assertEqual(run.returncode, 0, run.stderr)
        line = next(l for l in run.stdout.splitlines() if l.startswith("Cross-Split Overlap"))
        # The new line breaks the overlap down per split pair; the old one did not.
        self.assertIn("train/dev 0", line)
        self.assertIn("dev/eval 0", line)


if __name__ == "__main__":
    unittest.main()
