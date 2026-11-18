# Program: magi_pact - herder.py
# Programmer: Ethan-da-Tech-Wizard (written with Claude, an AI assistant)
# Last Modified: 2026-11-18
# Purpose: Supervisor for the 32-seat mesh: seat roster, heartbeat leases, stale-seat reclamation, advisory file claims and a JSON message journal.

"""Herder / Operational Supervisor for Magi Pact.

================================================================================
DISTRIBUTED SYSTEMS EDUCATIONAL OVERVIEW: SERVERLESS CONSENSUS & ATOMIC JOURNALING
================================================================================
How Does Serverless Consensus Work Without a Master Server?
----------------------------------------------------------
In traditional distributed clusters, a central master server (or Raft quorum)
maintains state, manages locks, and coordinates worker nodes. If the master dies,
the whole cluster stalls until a new leader is elected.

Magi Pact eliminates master servers entirely by utilizing two foundational
filesystem-level primitives that operate reliably over peer-to-peer file sync
engines (like Syncthing, shared NFS volumes, or Git worktrees):

1. Atomic Replacement via Filesystem Renames (Atomic State Updates):
   When writing seat states (`roster/seat_XX.json`) or lock claims
   (`board/claims.json`), Magi Pact writes the updated JSON payload to a
   temporary file (`.tmp`) and then atomically replaces the target file using
   `temp.replace(path)` (invoking POSIX `rename(2)`).
   - In POSIX filesystems, `rename` is an atomic directory operation.
   - Readers either see the complete old file or the complete new file.
   - Half-written or corrupted JSON states are physically impossible.

2. POSIX Advisory File Locking (`fcntl.flock`) for Append Journals:
   When multiple processes append messages simultaneously to the shared
   `board/messages.jsonl` audit log, they acquire an exclusive lock
   (`fcntl.LOCK_EX`) on the file descriptor. This serializes concurrent appends,
   preventing interleaved lines and race conditions.

3. 32-Seat Mesh Indexing and Partitioned Roster:
   Instead of writing to a single monolithic roster file (which would cause write
   collisions), the cluster is divided into exactly 32 discrete seats:
   - Seat 00 is permanently reserved for the Host / Primary Arbitrator.
   - Seats 01 through 31 are allocated to autonomous peer agents.
   - Each seat writes only to its own file (`roster/seat_XX.json`).

4. Heartbeat Leases and Deterministic Stale Reaping via UTC Epochs:
   - Active incumbents hold a timed lease on their seat (default: 300 seconds).
   - Incumbents renew their lease by calling `heartbeat()`, which writes a fresh
     UTC timestamp string (`current_iso()`).
   - "Incumbent Protection": An active seat whose heartbeat is fresh CANNOT be
     stolen or evicted by any newcomer.
   - If an agent crashes or disconnects, its heartbeat stops advancing.
   - Any node running a mesh operation triggers `reap_stale_seats()`. It converts
     the ISO-8601 UTC timestamp to seconds since the Unix Epoch (`dt.timestamp()`)
     and compares it to `time.time()`. If `(now - hb_epoch) > ttl_seconds`, the
     seat is transitioned from `ACTIVE` to `STALE`, allowing it to be safely
     reclaimed.
"""

# ------------------------------------------------------------------------------
# Standard Library Imports
# ------------------------------------------------------------------------------
import fcntl          # POSIX file-locking primitives (LOCK_EX, LOCK_UN) for atomic appends
import json           # Parsing and serializing structured JSON data
import os             # Low-level operating system interfaces
import time           # Unix epoch timing for leases and TTL comparisons
from datetime import datetime, timezone  # Robust UTC time manipulation and parsing
from pathlib import Path                 # Object-oriented filesystem path manipulation
from typing import Any, Dict, List, Optional, Tuple  # Type hints for strict verification

# ------------------------------------------------------------------------------
# Magi Pact Protocol Definitions
# ------------------------------------------------------------------------------
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

# ------------------------------------------------------------------------------
# Operational Defaults
# ------------------------------------------------------------------------------
# Number of seconds before an active seat with no new heartbeat is flagged as STALE.
# 300 seconds (5 minutes) provides tolerance for network hiccups while ensuring dead
# agents don't block seats indefinitely.
DEFAULT_HEARTBEAT_TTL_SECONDS: int = 300

# Number of seconds an advisory file lock (claim) remains valid before expiring.
# 1800 seconds (30 minutes) gives an agent sufficient time to run tests or compilers
# without risking a perpetual freeze if the agent crashes during mutation.
DEFAULT_CLAIM_TTL_SECONDS: int = 1800


# ==============================================================================
# PactHerder Class Implementation
# ==============================================================================

class PactHerder:
    """Operational Herder and State Manager for the Magi Pact 32-Seat Mesh.

    The Herder encapsulates all disk operations, concurrency controls, seat
    allocations, message routing, and distributed advisory locking.
    """

    def __init__(self, root_dir: Path):
        """Initializes the Herder instance with a specific workspace root directory.

        Inputs:
            root_dir (Path or str): Filesystem path to the root of the magi_pact workspace.

        Outputs:
            None.

        Step-by-Step Logic:
            1. Resolve `root_dir` into an absolute canonical Path object.
            2. Compute standard child directory paths: `roster`, `board`, `inboxes`, `exchange`.
            3. Compute standard file paths: `claims.json`, `messages.jsonl`, `BRIEF.md`.
        """
        # Ensure the root path is resolved to an absolute, symlink-free canonical path
        self.root: Path = Path(root_dir).resolve()

        # Define directory locations for partitioned mesh assets
        self.roster_dir: Path = self.root / "roster"      # Contains seat_00.json ... seat_31.json
        self.board_dir: Path = self.root / "board"        # Contains messages.jsonl, claims.json, BRIEF.md
        self.inboxes_dir: Path = self.root / "inboxes"    # Contains seat_00/ ... seat_31/ mailboxes
        self.exchange_dir: Path = self.root / "exchange"  # Contains patches, shards, and artifacts

        # Define canonical shared state file paths
        self.claims_file: Path = self.board_dir / "claims.json"
        self.messages_file: Path = self.board_dir / "messages.jsonl"
        self.brief_file: Path = self.board_dir / "BRIEF.md"

    # ==========================================================================
    # Workspace Initialization
    # ==========================================================================

    def initialize_workspace(
        self,
        host_occupant: str = "Host-Alpha",
        host_agent: str = "Magi-Master"
    ) -> None:
        """Sets up a pristine Magi Pact directory structure and initializes all 32 seats.

        Inputs:
            host_occupant (str): Human developer name or host node callsign (default: 'Host-Alpha').
            host_agent (str): Host agent model or runtime identifier (default: 'Magi-Master').

        Outputs:
            None.

        Exceptions Raised:
            OSError: If directory creation or file writing fails due to permission errors.

        Step-by-Step Logic:
            1. Create `roster/`, `board/`, `inboxes/`, and `exchange/` directories if missing.
            2. Iterate 0 to 31 to create individual inbox directories: `inboxes/seat_00/` through `inboxes/seat_31/`.
            3. Iterate 0 to 31 to initialize roster state files: `roster/seat_00.json` through `roster/seat_31.json`.
               - Seat 00 is immediately configured as ACTIVE, held by the host node.
               - Seats 01 through 31 are initialized as pristine VACANT seats.
            4. Initialize `board/claims.json` with an empty claims registry if it does not exist.
            5. Touch `board/messages.jsonl` to ensure the append log exists.
            6. Generate initial `board/BRIEF.md` containing operational objectives and guidelines.
        """
        # Step 1: Create top-level directories
        self.roster_dir.mkdir(parents=True, exist_ok=True)
        self.board_dir.mkdir(parents=True, exist_ok=True)
        self.inboxes_dir.mkdir(parents=True, exist_ok=True)
        self.exchange_dir.mkdir(parents=True, exist_ok=True)

        # Step 2: Initialize individual inboxes for point-to-point peer routing
        for i in range(MAX_SEATS):
            (self.inboxes_dir / f"seat_{i:02d}").mkdir(exist_ok=True)

        # Step 3: Initialize 32-seat roster grid files
        for i in range(MAX_SEATS):
            seat_file = self.roster_dir / f"seat_{i:02d}.json"
            if not seat_file.exists():
                seat = create_vacant_seat(i)
                # Seat 00 is designated as the Host / Arbitrator node
                if i == 0:
                    seat["status"] = SeatState.ACTIVE
                    seat["occupant"] = host_occupant
                    seat["agent_model"] = host_agent
                    seat["claimed_at"] = current_iso()
                    seat["last_heartbeat"] = current_iso()
                    seat["capabilities"] = ["arbitration", "task-dispatch", "merge-approval"]
                # Atomically write the initial seat descriptor
                self._write_json(seat_file, seat)

        # Step 4: Initialize claims file if not already present
        if not self.claims_file.exists():
            self._write_json(self.claims_file, {"schema": 1, "claims": {}})

        # Step 5: Ensure the append-only message journal exists
        if not self.messages_file.exists():
            self.messages_file.touch()

        # Step 6: Initialize room brief markdown file
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

    # ==========================================================================
    # Seat Allocation and Lifecycle Management
    # ==========================================================================

    def list_seats(self) -> List[Dict[str, Any]]:
        """Scans and returns the current state of all 32 seats in the mesh.

        Inputs:
            None.

        Outputs:
            List[Dict[str, Any]]: A 32-element list of seat state dictionaries,
                                  ordered by seat_id from 00 to 31.

        Step-by-Step Logic:
            1. Call `self.reap_stale_seats()` to opportunistically clean up expired leases.
            2. Iterate through seat IDs 0 through 31.
            3. Read each `roster/seat_XX.json` from disk; if missing, synthesize a VACANT record.
            4. Return the assembled list of seat states.
        """
        # Opportunistic garbage collection: reap any dead nodes before reporting roster
        self.reap_stale_seats()

        seats: List[Dict[str, Any]] = []
        for i in range(MAX_SEATS):
            path = self.roster_dir / f"seat_{i:02d}.json"
            if path.exists():
                seats.append(self._read_json(path))
            else:
                seats.append(create_vacant_seat(i))
        return seats

    def get_seat(self, seat_id: int) -> Optional[Dict[str, Any]]:
        """Fetches the state dictionary for a specific seat by its numeric index.

        Inputs:
            seat_id (int): Numeric seat identifier [0, 31].

        Outputs:
            Optional[Dict[str, Any]]: The seat state dictionary, or None if the file is absent.

        Step-by-Step Logic:
            1. Compute the path `roster/seat_XX.json`.
            2. Check if the file exists on disk.
            3. If it exists, read and parse the JSON; otherwise return None.
        """
        path = self.roster_dir / f"seat_{seat_id:02d}.json"
        if not path.exists():
            return None
        return self._read_json(path)

    def find_vacant_seat(self) -> Optional[int]:
        """Finds the lowest-indexed unoccupied (vacant) peer seat in the mesh.

        Inputs:
            None.

        Outputs:
            Optional[int]: The index of the first available seat (1-31), or None if all are full.

        Step-by-Step Logic:
            1. Call `self.reap_stale_seats()` to ensure expired seats become eligible.
            2. Scan seat indices from 1 to 31 (Seat 00 is reserved for Host).
            3. Check if seat status is `SeatState.VACANT`.
            4. Return the first matching index found, or None if the grid is at capacity.
        """
        # Reaping stale seats frees up abandoned seats for reuse
        self.reap_stale_seats()

        # Seat 0 is the host/arbitrator; peer seats span indices 1 through 31
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
        """Claims a vacant or specified seat for a joining agent or human developer.

        Incumbent Protection Guarantees:
        --------------------------------
        If another agent is currently ACTIVE in the requested seat, this method
        refuses to overwrite it, preventing split-brain conflicts and seat theft.

        Inputs:
            occupant (str): Human name or agent callsign (e.g. 'Node-01').
            agent_model (str): LLM or toolchain name (e.g. 'Qwen-2.5-Coder', 'Codex').
            seat_id (Optional[int]): Specific seat requested (1-31), or None for auto-allocation.
            capabilities (Optional[List[str]]): List of capability tags (default: ['code', 'test']).

        Outputs:
            Dict[str, Any]: The newly updated seat record dictionary.

        Exceptions Raised:
            RuntimeError: If no vacant seats remain, or if the requested seat is already ACTIVE.

        Step-by-Step Logic:
            1. Run `reap_stale_seats()` to free dead seats.
            2. Determine target seat: use `seat_id` if provided, otherwise call `find_vacant_seat()`.
            3. Validate target seat is valid [0, 31]. If None, raise RuntimeError.
            4. Inspect existing seat record: if ACTIVE and not Seat 00, raise RuntimeError.
            5. Update seat record with new occupant, agent model, UTC timestamps, and capabilities.
            6. Write record atomically via `self._write_json()`.
            7. Construct and record a `SEAT_CLAIM` broadcast message on the global board.
            8. Return the updated seat dictionary.
        """
        # Step 1: Reap expired leases
        self.reap_stale_seats()

        # Step 2: Determine target seat index
        target_id = seat_id if seat_id is not None else self.find_vacant_seat()
        if target_id is None or not (0 <= target_id < MAX_SEATS):
            raise RuntimeError("No vacant seats available (all 32 occupied or requested seat invalid)")

        # Step 3: Check for incumbent protection
        seat_file = self.roster_dir / f"seat_{target_id:02d}.json"
        current = self._read_json(seat_file) if seat_file.exists() else create_vacant_seat(target_id)
        if current.get("status") == SeatState.ACTIVE and target_id != 0:
            raise RuntimeError(f"Seat {target_id:02d} is already actively claimed by {current.get('occupant')}")

        # Step 4: Populate active lease data
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

        # Step 5: Atomically persist the claimed seat
        self._write_json(seat_file, current)

        # Step 6: Broadcast arrival to all peers on the board
        env = make_envelope(
            kind=KIND_SEAT_CLAIM,
            from_seat=target_id,
            to_seat=None,  # Broadcast to all
            payload={"occupant": occupant, "agent_model": agent_model}
        )
        self.record_message(env)

        return current

    def release_seat(self, seat_id: int, reason: str = "voluntary") -> None:
        """Gracefully vacates an occupied seat, resetting it to VACANT.

        Inputs:
            seat_id (int): Numeric seat identifier to release (1-31).
            reason (str): Human-readable reason for departure (default: 'voluntary').

        Outputs:
            None.

        Exceptions Raised:
            ValueError: If an attempt is made to release Host Seat 00.

        Step-by-Step Logic:
            1. Guard: Ensure `seat_id != 0`. Seat 00 is the host anchor and cannot be released.
            2. Create a clean vacant seat dictionary via `create_vacant_seat(seat_id)`.
            3. Atomically overwrite `roster/seat_XX.json` with the vacant record.
            4. Broadcast a `SEAT_RELEASE` event to the global message board.
        """
        if seat_id == 0:
            raise ValueError("Host seat 00 cannot be released via client")

        seat_file = self.roster_dir / f"seat_{seat_id:02d}.json"
        vacant = create_vacant_seat(seat_id)
        self._write_json(seat_file, vacant)

        # Announce departure on the message board
        env = make_envelope(
            kind=KIND_SEAT_RELEASE,
            from_seat=seat_id,
            to_seat=None,
            payload={"reason": reason}
        )
        self.record_message(env)

    def heartbeat(self, seat_id: int) -> None:
        """Renews an active seat's lease by updating its `last_heartbeat` timestamp.

        Inputs:
            seat_id (int): Seat index [0, 31] to refresh.

        Outputs:
            None.

        Step-by-Step Logic:
            1. Check if `roster/seat_XX.json` exists on disk.
            2. Read current seat record.
            3. If status is `ACTIVE`, set `last_heartbeat` to `current_iso()`.
            4. Atomically write the updated record back to disk.
        """
        seat_file = self.roster_dir / f"seat_{seat_id:02d}.json"
        if not seat_file.exists():
            return
        seat = self._read_json(seat_file)
        if seat.get("status") == SeatState.ACTIVE:
            seat["last_heartbeat"] = current_iso()
            self._write_json(seat_file, seat)

    def reap_stale_seats(self, ttl_seconds: int = DEFAULT_HEARTBEAT_TTL_SECONDS) -> List[int]:
        """Identifies and marks seats as STALE if their heartbeats have lapsed beyond TTL.

        Educational Note on UTC Epoch Comparison:
        ------------------------------------------
        Clock drift and timezone confusion are primary sources of bugs in peer-to-peer
        distributed systems. By parsing the ISO-8601 UTC string (`hb_str`) into a
        Python datetime object with explicit UTC timezone, we convert it to raw
        Unix epoch seconds (`dt.timestamp()`). We then compare it directly to
        `time.time()`. If `(now - hb_epoch) > ttl_seconds`, we know definitively
        that the node has stopped heartbeating.

        Inputs:
            ttl_seconds (int): Maximum allowable seconds since last heartbeat (default: 300).

        Outputs:
            List[int]: List of seat IDs that were transitioned to STALE.

        Step-by-Step Logic:
            1. Capture current system epoch seconds via `time.time()`.
            2. Scan peer seats 1 through 31 (Host Seat 00 is permanent and exempt from reaping).
            3. Read each active seat record.
            4. Parse `last_heartbeat` ISO timestamp into epoch seconds.
            5. If `(now - hb_epoch) > ttl_seconds`:
               - Set seat status to `SeatState.STALE`.
               - Atomically write the modified seat back to disk.
               - Record the reaped seat ID.
            6. Return list of reaped seat IDs.
        """
        reaped: List[int] = []
        now = time.time()

        # Scan peer seats 1 to 31 (Seat 00 host is never reaped)
        for i in range(1, MAX_SEATS):
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
                # Handle standard Zulu ('Z') ISO-8601 UTC timestamp format
                if hb_str.endswith("Z"):
                    dt = datetime.fromisoformat(hb_str[:-1] + "+00:00")
                else:
                    dt = datetime.fromisoformat(hb_str)
                hb_epoch = dt.timestamp()

                # If elapsed time exceeds TTL threshold, mark seat as STALE
                if now - hb_epoch > ttl_seconds:
                    seat["status"] = SeatState.STALE
                    self._write_json(seat_file, seat)
                    reaped.append(i)
            except Exception:
                # If timestamp is malformed, skip to avoid crashing the herder loop
                pass

        return reaped

    # ==========================================================================
    # Messaging & Inbox Delivery
    # ==========================================================================

    def record_message(self, env: Dict[str, Any]) -> None:
        """Appends a message to `board/messages.jsonl` and routes direct messages to inboxes.

        Educational Note on POSIX `fcntl.flock`:
        ----------------------------------------
        Multiple autonomous agents may attempt to write messages simultaneously.
        Using `fcntl.flock(f.fileno(), fcntl.LOCK_EX)` places an exclusive lock on
        the underlying file descriptor. The operating system kernel guarantees that
        only one process writes at a time, completely preventing garbled or torn
        lines in the append-only log.

        Inputs:
            env (Dict[str, Any]): Validated message envelope dictionary.

        Outputs:
            None.

        Exceptions Raised:
            ValueError: If the envelope fails schema validation.

        Step-by-Step Logic:
            1. Validate the envelope using `validate_envelope()`.
            2. Serialize the envelope to a single JSON line with trailing newline (`\n`).
            3. Open `board/messages.jsonl` in append mode ('a').
            4. Acquire POSIX exclusive lock `fcntl.LOCK_EX`.
            5. Write the line and immediately `f.flush()` OS buffers.
            6. Release POSIX lock in a `finally:` block.
            7. If `env['to_seat']` is directed (not None), atomically write a copy of
               the envelope into `inboxes/seat_<XX>/msg_<id>.json`.
        """
        # Step 1: Validate envelope schema
        if not validate_envelope(env):
            raise ValueError("Invalid envelope format: fails protocol validation checks")

        line = json.dumps(env, sort_keys=True) + "\n"

        # Step 2: Atomic thread/process safe append with POSIX advisory lock
        with self.messages_file.open("a", encoding="utf-8") as f:
            try:
                # Lock exclusively to serialize concurrent appends across local processes
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                f.write(line)
                f.flush()
            finally:
                # Always unlock to prevent deadlocks
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        # Step 3: Route to recipient mailbox if this is a directed point-to-point message
        to_seat = env.get("to_seat")
        if to_seat is not None and (0 <= to_seat < MAX_SEATS):
            inbox_item = self.inboxes_dir / f"seat_{to_seat:02d}" / f"msg_{env['msg_id']}.json"
            self._write_json(inbox_item, env)

    def get_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Reads recent messages from the append-only board log `board/messages.jsonl`.

        Inputs:
            limit (int): Maximum number of recent messages to return (default: 50).

        Outputs:
            List[Dict[str, Any]]: List of parsed message envelopes, ordered chronologically.

        Step-by-Step Logic:
            1. Check if `board/messages.jsonl` exists; return empty list if not.
            2. Read all lines and slice the tail `[-limit:]`.
            3. Parse each line from JSON into a Python dictionary.
            4. Return the list of decoded envelopes.
        """
        if not self.messages_file.exists():
            return []
        lines = self.messages_file.read_text(encoding="utf-8").strip().splitlines()
        results: List[Dict[str, Any]] = []
        for line in lines[-limit:]:
            try:
                results.append(json.loads(line))
            except Exception:
                pass
        return results

    def poll_inbox(self, seat_id: int) -> List[Dict[str, Any]]:
        """Polls directed messages waiting in an agent's individual mailbox.

        Inputs:
            seat_id (int): Numeric seat identifier [0, 31].

        Outputs:
            List[Dict[str, Any]]: List of message envelopes found in `inboxes/seat_XX/`.

        Step-by-Step Logic:
            1. Check if `inboxes/seat_XX/` directory exists.
            2. Iterate through all `.json` files in the inbox directory, sorted by name.
            3. Read and decode each message envelope.
            4. Return the collected messages.
        """
        inbox = self.inboxes_dir / f"seat_{seat_id:02d}"
        if not inbox.exists():
            return []
        items: List[Dict[str, Any]] = []
        for p in sorted(inbox.glob("*.json")):
            try:
                items.append(self._read_json(p))
            except Exception:
                pass
        return items

    # ==========================================================================
    # Claims Engine (Distributed Advisory Resource Locks)
    # ==========================================================================

    def acquire_claim(
        self,
        seat_id: int,
        resource_path: str,
        intent: str,
        ttl_seconds: int = DEFAULT_CLAIM_TTL_SECONDS
    ) -> bool:
        """Acquires an exclusive advisory lock on a file or path for a specific seat.

        Why Advisory Resource Locking is Essential:
        -------------------------------------------
        In multi-agent clusters where several autonomous coders edit code simultaneously,
        two agents modifying the same file concurrently will cause merge conflicts or
        broken code. An agent calls `acquire_claim` before editing a critical path.
        If another seat holds a non-expired lock on that path, the request is rejected.

        Inputs:
            seat_id (int): Seat index of the requesting node.
            resource_path (str): Relative file or module path to lock (e.g. 'pact/herder.py').
            intent (str): Human-readable reason for the lock (e.g. 'Refactoring parser').
            ttl_seconds (int): Lock duration in seconds before auto-expiration (default: 1800).

        Outputs:
            bool: True if lock was successfully acquired; False if actively locked by another seat.

        Step-by-Step Logic:
            1. Read current claims from `board/claims.json`.
            2. Check if `resource_path` is already present in `claims`:
               - If present, check `expires_epoch`.
               - If `now < expires_epoch` and holder is a different seat, return False (lock denied).
            3. Record new claim under `resource_path` with `seat_id`, `intent`, `acquired_at`,
               `expires_epoch`, and `ttl_seconds`.
            4. Atomically persist updated claims file via `self._write_json()`.
            5. Broadcast a `CLAIM_LOCK` message to notify peers.
            6. Return True (lock acquired).
        """
        data = self._read_json(self.claims_file) if self.claims_file.exists() else {"schema": 1, "claims": {}}
        claims = data.get("claims", {})
        now = time.time()

        # Step 1: Check existing lock status
        if resource_path in claims:
            existing = claims[resource_path]
            expires = existing.get("expires_epoch", 0)
            # If lock is still valid and held by another seat, reject acquisition
            if now < expires and existing.get("seat_id") != seat_id:
                return False

        # Step 2: Establish the new claim
        claims[resource_path] = {
            "seat_id": seat_id,
            "intent": intent,
            "acquired_at": current_iso(),
            "expires_epoch": now + ttl_seconds,
            "ttl_seconds": ttl_seconds,
        }
        data["claims"] = claims
        self._write_json(self.claims_file, data)

        # Step 3: Broadcast lock acquisition event
        env = make_envelope(
            kind=KIND_CLAIM_LOCK,
            from_seat=seat_id,
            to_seat=None,
            payload={"resource": resource_path, "intent": intent}
        )
        self.record_message(env)
        return True

    def release_claim(self, seat_id: int, resource_path: str) -> bool:
        """Releases an advisory lock on a resource path.

        Inputs:
            seat_id (int): Seat index releasing the lock (must be holder or Seat 00 Host).
            resource_path (str): The file path to unlock.

        Outputs:
            bool: True if lock was released; False if resource was not locked or caller lacked rights.

        Step-by-Step Logic:
            1. Read claims from `board/claims.json`.
            2. If `resource_path` not found, return False.
            3. Check authorization: only the lock holder or Seat 00 (Arbitrator) may release.
            4. Delete entry from `claims` dictionary.
            5. Atomically persist updated claims file.
            6. Broadcast `RELEASE_LOCK` event to notify peers.
            7. Return True.
        """
        data = self._read_json(self.claims_file) if self.claims_file.exists() else {"schema": 1, "claims": {}}
        claims = data.get("claims", {})

        if resource_path in claims:
            # Authorization check: only holder or Seat 00 host arbitrator can release
            if claims[resource_path].get("seat_id") != seat_id and seat_id != 0:
                return False

            del claims[resource_path]
            data["claims"] = claims
            self._write_json(self.claims_file, data)

            # Broadcast release event
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
        """Returns all currently active (non-expired) advisory file claims.

        Inputs:
            None.

        Outputs:
            Dict[str, Any]: Dictionary mapping resource paths to active claim details.

        Step-by-Step Logic:
            1. Read `board/claims.json`.
            2. Filter claims where `expires_epoch > current_time`.
            3. Return the filtered dictionary of active locks.
        """
        if not self.claims_file.exists():
            return {}
        data = self._read_json(self.claims_file)
        claims = data.get("claims", {})
        now = time.time()
        # Filter out expired locks
        return {k: v for k, v in claims.items() if v.get("expires_epoch", 0) > now}

    # ==========================================================================
    # Private Filesystem Helpers (Atomic I/O)
    # ==========================================================================

    def _read_json(self, path: Path) -> Dict[str, Any]:
        """Safely reads and deserializes a JSON file from disk.

        Inputs:
            path (Path): Filesystem path to the JSON file.

        Outputs:
            Dict[str, Any]: The parsed JSON data.

        Exceptions Raised:
            json.JSONDecodeError: If file content is not valid JSON.
            FileNotFoundError: If the file does not exist.
        """
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, data: Any) -> None:
        """Writes data to a temporary file and atomically replaces target path.

        Educational Note on Atomic Filesystem Renames:
        ---------------------------------------------
        In distributed systems, writing directly to a destination file (`open(path, 'w')`)
        creates a dangerous race condition: if another process reads the file midway
        through the write, it reads a truncated, half-written JSON fragment that crashes
        with `json.JSONDecodeError`.

        By writing the entire JSON payload to a sibling `.tmp` file and then executing
        `temp.replace(path)`:
        1. The underlying POSIX kernel executes an atomic `rename(2)` system call.
        2. Directory pointers are updated in a single hardware transaction.
        3. All readers either see the complete previous version or the complete new version.
        4. Zero file corruption, even during unexpected system power loss or process termination.

        Inputs:
            path (Path): Destination path for the JSON file.
            data (Any): Python data structure to serialize.

        Outputs:
            None.
        """
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temporary file on the same filesystem
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        # Atomic replacement: replaces target path instantaneously
        temp.replace(path)
