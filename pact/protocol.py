"""Protocol definitions for Magi Pact (32-Seat Federated Mesh).

Provides typed schema validation, seat state representations, message envelopes,
and distributed lock (claims) definitions.
"""
import hashlib
import json
import time
from typing import Any, Dict, List, Optional

PROTOCOL_VERSION = "1.0.0"
MAX_SEATS = 32

# Valid packet / event kinds
KIND_SEAT_CLAIM = "SEAT_CLAIM"
KIND_SEAT_RELEASE = "SEAT_RELEASE"
KIND_HEARTBEAT = "HEARTBEAT"
KIND_CHAT = "CHAT"
KIND_TASK_DISPATCH = "TASK_DISPATCH"
KIND_TASK_ACCEPT = "TASK_ACCEPT"
KIND_TASK_COMPLETE = "TASK_COMPLETE"
KIND_PATCH_PROPOSAL = "PATCH_PROPOSAL"
KIND_CLAIM_LOCK = "CLAIM_LOCK"
KIND_RELEASE_LOCK = "RELEASE_LOCK"

VALID_KINDS = {
    KIND_SEAT_CLAIM,
    KIND_SEAT_RELEASE,
    KIND_HEARTBEAT,
    KIND_CHAT,
    KIND_TASK_DISPATCH,
    KIND_TASK_ACCEPT,
    KIND_TASK_COMPLETE,
    KIND_PATCH_PROPOSAL,
    KIND_CLAIM_LOCK,
    KIND_RELEASE_LOCK,
}


def current_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def compute_sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class SeatState:
    VACANT = "vacant"
    ACTIVE = "active"
    STALE = "stale"


def create_vacant_seat(seat_id: int) -> Dict[str, Any]:
    if not (0 <= seat_id < MAX_SEATS):
        raise ValueError(f"Seat ID must be between 0 and {MAX_SEATS - 1}")
    return {
        "seat_id": seat_id,
        "status": SeatState.VACANT,
        "occupant": None,
        "role": "host" if seat_id == 0 else "peer",
        "agent_model": None,
        "claimed_at": None,
        "last_heartbeat": None,
        "capabilities": [],
        "metadata": {}
    }


def make_envelope(
    kind: str,
    from_seat: int,
    to_seat: Optional[int],  # None means broadcast to all
    payload: Dict[str, Any],
    correlation_id: Optional[str] = None
) -> Dict[str, Any]:
    if kind not in VALID_KINDS:
        raise ValueError(f"Invalid message kind: {kind}")
    if not (0 <= from_seat < MAX_SEATS):
        raise ValueError(f"Invalid from_seat: {from_seat}")
    if to_seat is not None and not (0 <= to_seat < MAX_SEATS):
        raise ValueError(f"Invalid to_seat: {to_seat}")

    ts = current_iso()
    raw_content = json.dumps({"kind": kind, "from": from_seat, "to": to_seat, "ts": ts, "payload": payload}, sort_keys=True)
    msg_id = compute_sha256(raw_content)[:16]

    return {
        "protocol": PROTOCOL_VERSION,
        "msg_id": msg_id,
        "correlation_id": correlation_id,
        "timestamp": ts,
        "kind": kind,
        "from_seat": from_seat,
        "to_seat": to_seat,
        "payload": payload,
    }


def validate_envelope(env: Dict[str, Any]) -> bool:
    required = ["protocol", "msg_id", "timestamp", "kind", "from_seat", "payload"]
    if not all(k in env for k in required):
        return False
    if env["kind"] not in VALID_KINDS:
        return False
    if not isinstance(env["from_seat"], int) or not (0 <= env["from_seat"] < MAX_SEATS):
        return False
    if env.get("to_seat") is not None and (not isinstance(env["to_seat"], int) or not (0 <= env["to_seat"] < MAX_SEATS)):
        return False
    return True
