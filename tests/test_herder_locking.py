"""Regression: PactHerder read-modify-write cycles must be serialized.

Each worker uses its own PactHerder instance (separate file descriptors), like
separate processes would, so only the flock - not Python object identity - can
make the outcome deterministic.
"""
import tempfile
import threading
import unittest
from pathlib import Path

from pact.herder import PactHerder


class TestHerderLocking(unittest.TestCase):
    # Fresh temp workspace per test so seat/claim state never carries over.
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        PactHerder(self.root).initialize_workspace()

    def tearDown(self):
        self._tmp.cleanup()

    # Helper: run fn in n threads released together by a barrier (to maximise
    # contention), each with its own PactHerder as a separate process would have.
    # A RuntimeError from the herder is recorded as 'refused'.
    def _race(self, fn, n=12):
        results = []
        barrier = threading.Barrier(n)

        def run(i):
            barrier.wait()
            try:
                results.append(fn(PactHerder(self.root), i))
            except RuntimeError:
                results.append("refused")

        threads = [threading.Thread(target=run, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return results

    # Seat 5 is claimed by 12 agents; exactly one may succeed.
    def test_only_one_claimant_wins_a_seat(self):
        # Without the lock several claimants read VACANT and all succeed.
        results = self._race(lambda h, i: h.claim_seat(f"agent{i}", "m", seat_id=5))
        winners = [r for r in results if r != "refused"]
        self.assertEqual(len(winners), 1, results)

    # 12 seats claim the same file for editing; exactly one gets True. This guards the
    # conflict-avoidance protocol that keeps agents from editing one file at once.
    def test_only_one_seat_wins_a_resource_claim(self):
        results = self._race(lambda h, i: h.acquire_claim(i + 1, "pact/herder.py", "edit"))
        self.assertEqual(results.count(True), 1, results)


if __name__ == "__main__":
    unittest.main()
