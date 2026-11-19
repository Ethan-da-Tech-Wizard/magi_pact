"""Regressions for pact.training: validate() under python -O and slot locking."""
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from pact.training import ConcurrencyLimitExceededError, ThermalAndConcurrencyGuard

REPO = Path(__file__).resolve().parent.parent


class TestValidateSurvivesOptimizeFlag(unittest.TestCase):
    def test_bad_rank_still_raises_under_python_O(self):
        # assert statements vanish under -O; validate() must not rely on them.
        code = (
            "from pact.training import SFTRecipe\n"
            "r = SFTRecipe(); r.rank = 1\n"
            "try:\n r.validate()\nexcept AssertionError:\n print('RAISED')\n"
        )
        out = subprocess.run([sys.executable, "-O", "-c", code], cwd=REPO, capture_output=True, text=True)
        self.assertIn("RAISED", out.stdout, out.stderr)


class TestSlotLocking(unittest.TestCase):
    def test_concurrent_acquire_never_exceeds_limit(self):
        # 24 threads race for 2 slots; the unlocked read-modify-write could let
        # several read the same list and all append, overshooting the cap.
        with tempfile.TemporaryDirectory() as root:
            guard = ThermalAndConcurrencyGuard(Path(root), mock_temp=40.0)
            guard._ensure_slots_file()
            wins, losses = [], []

            def worker(i):
                try:
                    guard.acquire_slot(f"job{i}")
                    wins.append(i)
                except ConcurrencyLimitExceededError:
                    losses.append(i)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(24)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            active = json.loads(guard.slots_file.read_text())["active_slots"]
            self.assertEqual(len(wins), 2)
            self.assertEqual(len(active), 2)
            self.assertEqual(len(losses), 22)


if __name__ == "__main__":
    unittest.main()
