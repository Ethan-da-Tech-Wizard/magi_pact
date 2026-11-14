"""Herder / Operational Supervisor for Magi Pact.

Manages the operational lifecycle:
- Seat roster allocation (00-31) and heartbeats
- Stale seat reclamation
- Distributed advisory claims (file locks with TTL)
- Message journaling to board and directed inboxes
"""
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .protocol import (
    MAX_SEATS,
    KIND_CHAT,
    KIND_CLAIM_LOCK,
    KIND_HEARTBEAT,
    KIND_RELEASE_LOCK,
    KIND_SEAT_CLAIM,
    KIND_SEAT_RELEASE,
    KIND_TASK_DISPATCH,
    SeatState,
    create_vacant_seat,
    current_iso,
    make_envelope,
    validate_envelope,
)

DEFAULT_HEARTBEAT_TTL_SECONDS = 300  # 5 minutes
DEFAULT_CLAIM_TTL_SECONDS = 1800     # 30 minutes


class PactHerder:
    def __init__(self, root_dir: Path):
        self.root = Path(root_dir).resolve()
        self.roster_dir = self.root / "roster"
        self.board_dir = self.root / "board"
        self.inboxes_dir = self.root / "inboxes"
        self.exchange_dir = self.root / "exchange"
        self.claims_file = self.board_dir / "claims.json"
        self.messages_file = self.board_dir / "messages.jsonl"
        self.brief_file = self.board_dir / "BRIEF.md"

    def initialize_workspace(self, host_occupant: str = "Ethan", host_agent: str = "Magi-Master") -> None:
        """Create directory structure and initialize all 32 seats if not present."""
        self.roster_dir.mkdir(parents=True, exist_ok=True)
        self.board_dir.mkdir(parents=True, exist_ok=True)
        self.inboxes_dir.mkdir(parents=True, exist_ok=True)
        self.exchange_dir.mkdir(parents=True, exist_ok=True)

        # Initialize inboxes
        for i in range(MAX_SEATS):
            (self.inboxes_dir / f"seat_{i:02d}").mkdir(exist_ok=True)

        # Initialize roster
        for i in range(MAX_SEATS):
            seat_file = self.roster_dir / f"seat_{i:02d}.json"
            if not seat_file.exists():
                seat = create_vacant_seat(i)
                if i == 0:
                    seat["status"] = SeatState.ACTIVE
                    seat["occupant"] = host_occupant
                    seat["agent_model"] = host_agent
                    seat["claimed_at"] = current_iso()
                    seat["last_heartbeat"] = current_iso()
                    seat["capabilities"] = ["arbitration", "task-dispatch", "merge-approval"]
                self._write_json(seat_file, seat)

        # Initialize claims file
        if not self.claims_file.exists():
            self._write_json(self.claims_file, {"schema": 1, "claims": {}})

        # Initialize messages journal
        if not self.messages_file.exists():
            self.messages_file.touch()

        # Initialize brief
        if not self.brief_file.exists():
            self.brief_file.write_text(
                "# Production Brief & Active Objectives\n\n"
                f"**Host:** {host_occupant} (Seat 00)\n"
                f"**Initialized:** {current_iso()}\n\n"
                "## Current Mission\n"
                "Awaiting task assignments from Seat 00.\n\n"
                "## Active Conventions\n"
                "- Before modifying files, declare a lock via `magi_pact claim <path>`\n"
                "- Check your inbox in `inboxes/seat_<XX>/` for direct instructions\n",
                encoding="utf-8"
            )

    # --- Seat Operations ---

    def list_seats(self) -> List[Dict[str, Any]]:
        self.reap_stale_seats()
        seats = []
        for i in range(MAX_SEATS):
            path = self.roster_dir / f"seat_{i:02d}.json"
            if path.exists():
                seats.append(self._read_json(path))
            else:
                seats.append(create_vacant_seat(i))
        return seats

    def get_seat(self, seat_id: int) -> Optional[Dict[str, Any]]:
        path = self.roster_dir / f"seat_{seat_id:02d}.json"
        if not path.exists():
            return None
        return self._read_json(path)

    def find_vacant_seat(self) -> Optional[int]:
        self.reap_stale_seats()
        # Seat 0 is host, check 1 to 31
        for i in range(1, MAX_SEATS):
            s = self.get_seat(i)
            if s and s.get("status") == SeatState.VACANT:
                return i
        return None

    def claim_seat(
        self,
        occupant: str,
        agent_model: str,
        seat_id: Optional[int] = None,
        capabilities: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        self.reap_stale_seats()
        target_id = seat_id if seat_id is not None else self.find_vacant_seat()
        if target_id is None or not (0 <= target_id < MAX_SEATS):
            raise RuntimeError("No vacant seats available (all 32 occupied or requested seat invalid)")

        seat_file = self.roster_dir / f"seat_{target_id:02d}.json"
        current = self._read_json(seat_file) if seat_file.exists() else create_vacant_seat(target_id)
        if current.get("status") == SeatState.ACTIVE and target_id != 0:
            raise RuntimeError(f"Seat {target_id:02d} is already actively claimed by {current.get('occupant')}")

        now = current_iso()
        current.update({
            "seat_id": target_id,
            "status": SeatState.ACTIVE,
            "occupant": occupant,
            "agent_model": agent_model,
            "claimed_at": now,
            "last_heartbeat": now,
            "capabilities": capabilities or ["code", "test"]
        })
        self._write_json(seat_file, current)

        # Broadcast claim event
        env = make_envelope(
            kind=KIND_SEAT_CLAIM,
            from_seat=target_id,
            to_seat=None,
            payload={"occupant": occupant, "agent_model": agent_model}
        )
        self.record_message(env)
        return current

    def release_seat(self, seat_id: int, reason: str = "voluntary") -> None:
        if seat_id == 0:
            raise ValueError("Host seat 00 cannot be released via client")
        seat_file = self.roster_dir / f"seat_{seat_id:02d}.json"
        vacant = create_vacant_seat(seat_id)
        self._write_json(seat_file, vacant)

        env = make_envelope(
            kind=KIND_SEAT_RELEASE,
            from_seat=seat_id,
            to_seat=None,
            payload={"reason": reason}
        )
        self.record_message(env)

    def heartbeat(self, seat_id: int) -> None:
        seat_file = self.roster_dir / f"seat_{seat_id:02d}.json"
        if not seat_file.exists():
            return
        seat = self._read_json(seat_file)
        if seat.get("status") == SeatState.ACTIVE:
            seat["last_heartbeat"] = current_iso()
            self._write_json(seat_file, seat)

    def reap_stale_seats(self, ttl_seconds: int = DEFAULT_HEARTBEAT_TTL_SECONDS) -> List[int]:
        """Mark seats as stale/vacant if heartbeat hasn't been updated within TTL."""
        reaped = []
        now = time.time()
        for i in range(1, MAX_SEATS):  # Host seat 0 is never reaped
            seat_file = self.roster_dir / f"seat_{i:02d}.json"
            if not seat_file.exists():
                continue
            seat = self._read_json(seat_file)
            if seat.get("status") != SeatState.ACTIVE:
                continue
            hb_str = seat.get("last_heartbeat")
            if not hb_str:
                continue
            try:
                hb_epoch = time.mktime(time.strptime(hb_str, "%Y-%m-%dT%H:%M:%SZ"))
                if now - hb_epoch > ttl_seconds:
                    seat["status"] = SeatState.STALE
                    self._write_json(seat_file, seat)
                    reaped.append(i)
            except Exception:
                pass
        return reaped

    # --- Messaging & Inboxes ---

    def record_message(self, env: Dict[str, Any]) -> None:
        if not validate_envelope(env):
            raise ValueError("Invalid envelope format")
        line = json.dumps(env, sort_keys=True) + "\n"
        with self.messages_file.open("a", encoding="utf-8") as f:
            f.write(line)

        # Route to recipient inbox if direct message
        to_seat = env.get("to_seat")
        if to_seat is not None and (0 <= to_seat < MAX_SEATS):
            inbox_item = self.inboxes_dir / f"seat_{to_seat:02d}" / f"msg_{env['msg_id']}.json"
            self._write_json(inbox_item, env)

    def get_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.messages_file.exists():
            return []
        lines = self.messages_file.read_text(encoding="utf-8").strip().splitlines()
        results = []
        for line in lines[-limit:]:
            try:
                results.append(json.loads(line))
            except Exception:
                pass
        return results

    def poll_inbox(self, seat_id: int) -> List[Dict[str, Any]]:
        inbox = self.inboxes_dir / f"seat_{seat_id:02d}"
        if not inbox.exists():
            return []
        items = []
        for p in sorted(inbox.glob("*.json")):
            try:
                items.append(self._read_json(p))
            except Exception:
                pass
        return items

    # --- Claims Engine (Distributed Locks) ---

    def acquire_claim(self, seat_id: int, resource_path: str, intent: str, ttl_seconds: int = DEFAULT_CLAIM_TTL_SECONDS) -> bool:
        """Acquire an exclusive advisory lock on a file/path for a seat."""
        data = self._read_json(self.claims_file) if self.claims_file.exists() else {"schema": 1, "claims": {}}
        claims = data.get("claims", {})
        now = time.time()

        # Check existing lock
        if resource_path in claims:
            existing = claims[resource_path]
            expires = existing.get("expires_epoch", 0)
            if now < expires and existing.get("seat_id") != seat_id:
                return False  # Active lock held by someone else

        claims[resource_path] = {
            "seat_id": seat_id,
            "intent": intent,
            "acquired_at": current_iso(),
            "expires_epoch": now + ttl_seconds,
            "ttl_seconds": ttl_seconds,
        }
        data["claims"] = claims
        self._write_json(self.claims_file, data)

        env = make_envelope(
            kind=KIND_CLAIM_LOCK,
            from_seat=seat_id,
            to_seat=None,
            payload={"resource": resource_path, "intent": intent}
        )
        self.record_message(env)
        return True

    def release_claim(self, seat_id: int, resource_path: str) -> bool:
        data = self._read_json(self.claims_file) if self.claims_file.exists() else {"schema": 1, "claims": {}}
        claims = data.get("claims", {})
        if resource_path in claims:
            if claims[resource_path].get("seat_id") != seat_id and seat_id != 0:
                return False  # Only holder or host (seat 0) can release
            del claims[resource_path]
            data["claims"] = claims
            self._write_json(self.claims_file, data)

            env = make_envelope(
                kind=KIND_RELEASE_LOCK,
                from_seat=seat_id,
                to_seat=None,
                payload={"resource": resource_path}
            )
            self.record_message(env)
            return True
        return False

    def list_claims(self) -> Dict[str, Any]:
        if not self.claims_file.exists():
            return {}
        data = self._read_json(self.claims_file)
        claims = data.get("claims", {})
        now = time.time()
        # Filter active
        return {k: v for k, v in claims.items() if v.get("expires_epoch", 0) > now}

    # --- Helpers ---

    def _read_json(self, path: Path) -> Dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp.replace(path)
