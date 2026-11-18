# ==============================================================================
# Program: protocol.py
# Programmer: Ethan-da-Tech-Wizard
# Course: CIS 156 / Advanced Systems
# Last Modified: November 18, 2026
# Purpose: Defines the core communication protocol, message envelope schemas,
#          deterministic seat state definitions, and cryptographic identifiers
#          for the 32-Seat Magi Pact Serverless Consensus Mesh.
# ==============================================================================

"""Protocol Definitions and Envelopes for Magi Pact (32-Seat Federated Mesh).

================================================================================
DISTRIBUTED SYSTEMS EDUCATIONAL OVERVIEW: SERVERLESS CONSENSUS
================================================================================
What is "Distributed Serverless Consensus"?
------------------------------------------
In traditional distributed computing architectures (such as Apache ZooKeeper,
etcd, or HashiCorp Consul), nodes coordinate by connecting via TCP/IP sockets to
a centralized master cluster that runs election algorithms like Paxos or Raft.
While effective, this requires continuous network connectivity, exposed daemon
ports, TLS certificate provisioning, and a persistent server process.

Magi Pact takes a fundamentally different, "serverless" peer-to-peer approach:
1. The Shared Filesystem is the Network:
   Nodes communicate strictly by reading from and writing to a shared filesystem
   directory tree (synchronized across heterogeneous hosts via tools like
   Syncthing, shared NFS/SMB mounts, or Git branches).
2. Deterministic State Separation:
   Instead of one giant lock file, state is partitioned cleanly across 32
   distinct seats (Seat 00 to Seat 31). Each seat owns its dedicated JSON state
   descriptor (e.g., `roster/seat_04.json`), eliminating write contention
   between different agents.
3. Cryptographic Message Fingerprints:
   Messages are immutable envelopes containing deterministic SHA-256 derived
   identifiers. Peers can verify authenticity and discard duplicate deliveries
   without consulting a central database.
4. Incumbent Protection & Heartbeat Leases:
   A seat is leased to an occupant for a defined Time-To-Live (TTL). As long as
   the incumbent refreshes its lease via periodic UTC heartbeats, no competing
   node may evict or overwrite its seat. If the node crashes, its lease expires,
   allowing other nodes to reap the seat safely.

This module provides the low-level constants, enumerations, validation helpers,
and factory functions that govern packet construction across the mesh.
"""

# ------------------------------------------------------------------------------
# Standard Library Imports
# ------------------------------------------------------------------------------
import hashlib     # For SHA-256 cryptographic message hashing
import json        # For serialization and deserialization of protocol packets
import time        # For high-resolution time measurement and UTC timestamping
from typing import Any, Dict, List, Optional  # Type annotations for static verification

# ------------------------------------------------------------------------------
# Protocol Constants and Versioning
# ------------------------------------------------------------------------------
# Protocol version identifier following Semantic Versioning (SemVer 2.0.0).
# Allows heterogeneous nodes across Linux, macOS, and Windows to verify compatibility.
PROTOCOL_VERSION: str = "1.0.0"

# Total number of seats available in the federated mesh cluster grid.
# Seats are indexed from 0 to 31:
# - Seat 00: Designated Host / Arbitrator / Master Coordinator node.
# - Seats 01 through 31: Peer agent execution nodes (compilers, testers, architects).
MAX_SEATS: int = 32

# ------------------------------------------------------------------------------
# Packet / Event Kinds (Message Types)
# ------------------------------------------------------------------------------
# These string constants identify the specific semantic intent of each envelope.
# Strict validation prevents nodes from processing unrecognized message types.

# Lifecycle & Seat Reservation events:
KIND_SEAT_CLAIM: str = "SEAT_CLAIM"          # Broadcasted when a node joins and claims a seat
KIND_SEAT_RELEASE: str = "SEAT_RELEASE"      # Broadcasted when a node gracefully leaves a seat
KIND_HEARTBEAT: str = "HEARTBEAT"            # Periodic keep-alive lease pulse from an active seat

# Communication & Coordination events:
KIND_CHAT: str = "CHAT"                      # Freeform human or agent chat message (broadcast or DM)
KIND_TASK_DISPATCH: str = "TASK_DISPATCH"    # Formal structured task assignment from Host (Seat 00)
KIND_TASK_ACCEPT: str = "TASK_ACCEPT"        # Peer acknowledgement and acceptance of a dispatched task
KIND_TASK_COMPLETE: str = "TASK_COMPLETE"    # Peer notification that an assigned task has finished
KIND_PATCH_PROPOSAL: str = "PATCH_PROPOSAL"  # Cross-node git patch or artifact submission in exchange/

# Distributed Advisory Locking events:
KIND_CLAIM_LOCK: str = "CLAIM_LOCK"          # Request exclusive advisory lease on a shared file/path
KIND_RELEASE_LOCK: str = "RELEASE_LOCK"      # Relinquish an advisory lock after file mutation is done

# Set of all valid event kinds used for O(1) membership validation in envelopes
VALID_KINDS: set = {
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


# ==============================================================================
# Helper Functions: Timestamps and Hashing
# ==============================================================================

def current_iso() -> str:
    """Generates a standardized ISO-8601 UTC timestamp string.

    Why UTC is Critical in Distributed Systems:
    -------------------------------------------
    Different agent nodes running on different operating systems (macOS, Arch Linux,
    AWS Cloud VMs) may reside in different local time zones (e.g., EST, PST, CET).
    Relying on local wall-clock time causes severe clock skew and inconsistent
    lease expirations. Using Greenwich Mean Time / UTC with an explicit trailing 'Z'
    guarantees a single, uniform time reference across all cluster peers.

    Inputs:
        None.

    Outputs:
        str: An ISO-8601 formatted timestamp in the format "YYYY-MM-DDTHH:MM:SSZ".

    Step-by-Step Logic:
        1. Obtain the current time in UTC using time.gmtime().
        2. Format the time tuple into the standard ISO-8601 format with strftime.
        3. Append the 'Z' (Zulu time zone indicator) to denote zero UTC offset.
    """
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def compute_sha256(data: str) -> str:
    """Computes the hex-encoded SHA-256 cryptographic digest of a text string.

    Why SHA-256 is Used:
    --------------------
    In serverless consensus, we need universally unique message identifiers (UUIDs)
    that are both collision-resistant and deterministic. By hashing canonical
    message content, identical messages generate identical hashes, which allows
    nodes to detect replay attacks and duplicate message processing without
    consulting a central database.

    Inputs:
        data (str): The raw string data to hash.

    Outputs:
        str: 64-character hexadecimal representation of the SHA-256 hash.

    Step-by-Step Logic:
        1. Encode the input Python string into UTF-8 binary bytes.
        2. Feed the bytes into the hashlib.sha256 engine.
        3. Return the hexadecimal string via .hexdigest().
    """
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


# ==============================================================================
# Seat State Definition
# ==============================================================================

class SeatState:
    """Enumeration representing the three lifecycle states of a mesh seat.

    State Machine Transition Rules:
    -------------------------------
    1. VACANT:
       The seat has no current occupant. Any node may claim this seat via
       `PactHerder.claim_seat()`.
    2. ACTIVE:
       The seat is held by a live occupant whose heartbeat lease has been
       renewed within the TTL threshold (default 300 seconds). Active seats
       cannot be stolen or evicted by other nodes (Incumbent Protection).
    3. STALE:
       The seat was formerly active, but the occupant missed heartbeats beyond
       the TTL threshold. Stale seats are eligible to be reaped and reclaimed
       by new nodes joining the mesh.
    """
    VACANT: str = "vacant"  # Unassigned; available for immediate allocation
    ACTIVE: str = "active"  # Occupied and heartbeating within TTL
    STALE: str = "stale"   # Occupied but heartbeat lease has expired


def create_vacant_seat(seat_id: int) -> Dict[str, Any]:
    """Factory function to generate a pristine, unassigned seat dictionary.

    Inputs:
        seat_id (int): Numeric seat index within the mesh range [0, MAX_SEATS - 1].

    Outputs:
        Dict[str, Any]: A dictionary matching the canonical seat schema ready to
                        be serialized into `roster/seat_XX.json`.

    Exceptions Raised:
        ValueError: If seat_id is outside the valid range [0, 31].

    Step-by-Step Logic:
        1. Validate that seat_id is an integer between 0 and 31.
        2. Assign special role 'host' for Seat 00, or 'peer' for Seats 01 through 31.
        3. Initialize all occupancy, timestamp, and capability fields to blank defaults.
        4. Return the standardized seat descriptor dictionary.
    """
    # Defensive programming: ensure seat index is bounded by mesh capacity
    if not (0 <= seat_id < MAX_SEATS):
        raise ValueError(f"Seat ID must be between 0 and {MAX_SEATS - 1} (received {seat_id})")

    # Construct canonical schema dictionary
    return {
        "seat_id": seat_id,
        "status": SeatState.VACANT,
        "occupant": None,                           # Human name or agent callsign (e.g., 'Node-01')
        "role": "host" if seat_id == 0 else "peer", # Seat 00 is always the host/arbitrator
        "agent_model": None,                        # Underlying LLM or runtime (e.g., 'Qwen-2.5', 'Claude-Code')
        "claimed_at": None,                         # ISO-8601 timestamp of original seat acquisition
        "last_heartbeat": None,                     # ISO-8601 timestamp of most recent heartbeat renewal
        "capabilities": [],                         # Declared capabilities (e.g., ['code', 'test', 'review'])
        "metadata": {}                              # Extensible key-value metadata for custom workloads
    }


# ==============================================================================
# Message Envelope Construction and Validation
# ==============================================================================

def make_envelope(
    kind: str,
    from_seat: int,
    to_seat: Optional[int],
    payload: Dict[str, Any],
    correlation_id: Optional[str] = None
) -> Dict[str, Any]:
    """Constructs and cryptographically fingerprints a validated protocol message envelope.

    How Message Addressing Works:
    -----------------------------
    - Broadcast Messages: When `to_seat` is None, the message is intended for
      the entire mesh. It is appended to `board/messages.jsonl` for all peers to read.
    - Direct Messages (DMs): When `to_seat` is an integer (e.g. 0 to 31), the message
      is also copied into `inboxes/seat_<XX>/msg_<id>.json`, allowing targeted polling.

    Inputs:
        kind (str): Message event kind; must be a member of VALID_KINDS.
        from_seat (int): Seat index of the sender [0, MAX_SEATS - 1].
        to_seat (Optional[int]): Recipient seat index, or None for mesh broadcast.
        payload (Dict[str, Any]): The application-specific data dictionary.
        correlation_id (Optional[str]): Optional ID tracking multi-turn request/reply threads.

    Outputs:
        Dict[str, Any]: Fully populated message envelope with a unique 16-character SHA-256 ID.

    Exceptions Raised:
        ValueError: If kind is invalid or if from_seat/to_seat are out of bounds.

    Step-by-Step Logic:
        1. Validate `kind` against the whitelist in `VALID_KINDS`.
        2. Validate sender seat index `from_seat` is within [0, 31].
        3. If `to_seat` is specified, validate that it is also within [0, 31].
        4. Capture current UTC timestamp string via `current_iso()`.
        5. Build a canonical JSON representation of the core fields (sorted keys)
           to ensure deterministic serialization.
        6. Compute the SHA-256 hash of this canonical JSON and truncate to 16 hex chars
           to create a compact, collision-resistant message ID (`msg_id`).
        7. Assemble and return the complete envelope dictionary.
    """
    # 1. Validate message type
    if kind not in VALID_KINDS:
        raise ValueError(f"Invalid message kind '{kind}'. Must be one of {sorted(VALID_KINDS)}")

    # 2. Validate sender bounds
    if not (0 <= from_seat < MAX_SEATS):
        raise ValueError(f"Invalid from_seat '{from_seat}'. Must be between 0 and {MAX_SEATS - 1}")

    # 3. Validate recipient bounds if not a broadcast
    if to_seat is not None and not (0 <= to_seat < MAX_SEATS):
        raise ValueError(f"Invalid to_seat '{to_seat}'. Must be None (broadcast) or between 0 and {MAX_SEATS - 1}")

    # 4. Generate timestamp
    ts = current_iso()

    # 5. Deterministic hashing: sort_keys=True ensures identical key ordering regardless of Python dict internals
    raw_content = json.dumps(
        {
            "kind": kind,
            "from": from_seat,
            "to": to_seat,
            "ts": ts,
            "payload": payload
        },
        sort_keys=True
    )

    # 6. Generate 16-character cryptographic identifier
    msg_id = compute_sha256(raw_content)[:16]

    # 7. Package complete envelope
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
    """Performs strict structural and type validation on a candidate message envelope.

    Prevents corrupt, malformed, or malicious packets from entering the mesh
    append-only message journal or individual node inboxes.

    Inputs:
        env (Dict[str, Any]): Candidate envelope dictionary to inspect.

    Outputs:
        bool: True if envelope conforms strictly to protocol specification; False otherwise.

    Step-by-Step Logic:
        1. Ensure all mandatory keys ('protocol', 'msg_id', 'timestamp', 'kind',
           'from_seat', 'payload') exist in the envelope dictionary.
        2. Ensure `env['kind']` belongs to the `VALID_KINDS` set.
        3. Ensure `env['from_seat']` is an integer in the range [0, 31].
        4. If `env['to_seat']` is present and not None, ensure it is an integer in range [0, 31].
        5. Return True if all checks pass; return False on the first violation.
    """
    # 1. Check for required keys
    required_keys = ["protocol", "msg_id", "timestamp", "kind", "from_seat", "payload"]
    if not all(k in env for k in required_keys):
        return False

    # 2. Check message kind validity
    if env["kind"] not in VALID_KINDS:
        return False

    # 3. Check sender seat bounds and type
    if not isinstance(env["from_seat"], int) or not (0 <= env["from_seat"] < MAX_SEATS):
        return False

    # 4. Check recipient seat bounds and type (if not broadcast)
    to_seat = env.get("to_seat")
    if to_seat is not None:
        if not isinstance(to_seat, int) or not (0 <= to_seat < MAX_SEATS):
            return False

    # All validations passed
    return True
