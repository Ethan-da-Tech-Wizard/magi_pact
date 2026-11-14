"""Unit tests for Magi Pact protocol, herder, and locking mechanisms."""
import shutil
import tempfile
import unittest
from pathlib import Path

from pact.herder import PactHerder
from pact.protocol import (
    KIND_CHAT,
    KIND_TASK_DISPATCH,
    MAX_SEATS,
    SeatState,
    make_envelope,
    validate_envelope,
)


class TestPactProtocol(unittest.TestCase):
    def test_envelope_validation(self):
        env = make_envelope(
            kind=KIND_CHAT,
            from_seat=1,
            to_seat=0,
            payload={"message": "hello world"}
        )
        self.assertTrue(validate_envelope(env))
        self.assertEqual(env["from_seat"], 1)
        self.assertEqual(env["to_seat"], 0)
        self.assertEqual(env["kind"], KIND_CHAT)

    def test_invalid_seat_bounds(self):
        with self.assertRaises(ValueError):
            make_envelope(kind=KIND_CHAT, from_seat=32, to_seat=0, payload={})


class TestPactHerder(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.herder = PactHerder(self.test_dir)
        self.herder.initialize_workspace(host_occupant="TestHost", host_agent="TestAgent")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_32_seats_initialized(self):
        seats = self.herder.list_seats()
        self.assertEqual(len(seats), MAX_SEATS)
        self.assertEqual(seats[0]["status"], SeatState.ACTIVE)
        self.assertEqual(seats[0]["occupant"], "TestHost")
        self.assertEqual(seats[1]["status"], SeatState.VACANT)

    def test_claim_and_release_seat(self):
        # Claim first vacant (should be seat 1)
        claimed = self.herder.claim_seat(occupant="Alice", agent_model="Claude-Code")
        self.assertEqual(claimed["seat_id"], 1)
        self.assertEqual(claimed["status"], SeatState.ACTIVE)
        self.assertEqual(claimed["occupant"], "Alice")

        # Claim specific seat (e.g. seat 5)
        claimed_5 = self.herder.claim_seat(occupant="Bob", agent_model="Codex", seat_id=5)
        self.assertEqual(claimed_5["seat_id"], 5)
        self.assertEqual(claimed_5["occupant"], "Bob")

        # Verify roster status
        s1 = self.herder.get_seat(1)
        self.assertEqual(s1["status"], SeatState.ACTIVE)

        # Release seat 1
        self.herder.release_seat(1, reason="done")
        s1_after = self.herder.get_seat(1)
        self.assertEqual(s1_after["status"], SeatState.VACANT)

    def test_claims_locking_conflict(self):
        # Seat 1 claims a file
        ok1 = self.herder.acquire_claim(seat_id=1, resource_path="services/auth.py", intent="refactor")
        self.assertTrue(ok1)

        # Seat 2 tries to claim the same file -> should fail
        ok2 = self.herder.acquire_claim(seat_id=2, resource_path="services/auth.py", intent="bugfix")
        self.assertFalse(ok2)

        # Seat 1 releases the claim
        rel = self.herder.release_claim(seat_id=1, resource_path="services/auth.py")
        self.assertTrue(rel)

        # Now Seat 2 can claim it
        ok3 = self.herder.acquire_claim(seat_id=2, resource_path="services/auth.py", intent="bugfix")
        self.assertTrue(ok3)

    def test_inbox_and_messaging(self):
        # Seat 0 dispatches a task to Seat 2
        env = make_envelope(
            kind=KIND_TASK_DISPATCH,
            from_seat=0,
            to_seat=2,
            payload={"title": "Fix bug", "description": "Details here"}
        )
        self.herder.record_message(env)

        # Poll inbox for Seat 2
        inbox_items = self.herder.poll_inbox(2)
        self.assertEqual(len(inbox_items), 1)
        self.assertEqual(inbox_items[0]["kind"], KIND_TASK_DISPATCH)
        self.assertEqual(inbox_items[0]["payload"]["title"], "Fix bug")

        # Poll empty inbox for Seat 3
        self.assertEqual(len(self.herder.poll_inbox(3)), 0)


if __name__ == "__main__":
    unittest.main()
