"""Regressions for pact.training: validate() under python -O and slot locking."""
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from pact.training import ConcurrencyLimitExceededError, ThermalAndConcurrencyGuard

# Repo root, used as cwd for the subprocess so `import pact` resolves without install.
REPO = Path(__file__).resolve().parent.parent


class TestValidateSurvivesOptimizeFlag(unittest.TestCase):
    # Pins that validation uses real exceptions: run in a child interpreter with -O
    # (asserts stripped) because the parent test runner cannot switch -O on itself.
    # A rank of 1 is below the recipe's minimum, so validate() must still raise.
    def test_bad_rank_still_raises_under_python_O(self):
        # assert statements vanish under -O; validate() must not rely on them.
        # Child program: build a recipe with an invalid rank and report whether the
        # expected error surfaced. Printing a marker lets the parent assert on stdout.
        code = (
            "from pact.training import SFTRecipe\n"
            "r = SFTRecipe(); r.rank = 1\n"
            "try:\n r.validate()\nexcept AssertionError:\n print('RAISED')\n"
        )
        out = subprocess.run([sys.executable, "-O", "-c", code], cwd=REPO, capture_output=True, text=True)
        self.assertIn("RAISED", out.stdout, out.stderr)


class TestSlotLocking(unittest.TestCase):
    # Concurrency regression for ThermalAndConcurrencyGuard.acquire_slot: the slot
    # list lives in a JSON file, so without a file lock two threads can read the same
    # list and both append. mock_temp=40.0 keeps the thermal check from interfering.
    def test_concurrent_acquire_never_exceeds_limit(self):
        # 24 threads race for 2 slots; the unlocked read-modify-write could let
        # several read the same list and all append, overshooting the cap.
        with tempfile.TemporaryDirectory() as root:
            guard = ThermalAndConcurrencyGuard(Path(root), mock_temp=40.0)
            # Create the slots file up front so the race is only about acquire_slot itself.
            guard._ensure_slots_file()
            wins, losses = [], []

            # Each thread tries once and records win/loss; a loss is the expected refusal.
            def worker(i):
                try:
                    guard.acquire_slot(f"job{i}")
                    wins.append(i)
                except ConcurrencyLimitExceededError:
                    losses.append(i)

            # 24 threads vs a limit of 2: starting them all before joining maximises overlap.
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(24)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            active = json.loads(guard.slots_file.read_text())["active_slots"]
            # Three views must agree: exact winners, persisted slots, and refusals (24 = 2 + 22).
            self.assertEqual(len(wins), 2)
            self.assertEqual(len(active), 2)
            self.assertEqual(len(losses), 22)


if __name__ == "__main__":
    unittest.main()
