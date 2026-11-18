# Program: magi_pact - cli.py
# Programmer: Ethan-da-Tech-Wizard (written with Claude, an AI assistant)
# Last Modified: 2026-11-18
# Purpose: Command line interface for the Magi Pact 32-seat mesh: initializing meshes, claiming seats, messaging, locks and dataset shards.

"""Command Line Interface for Magi Pact.

================================================================================
DISTRIBUTED SYSTEMS EDUCATIONAL OVERVIEW: THE CLI AS AN AGENT BUS
================================================================================
How Agents and Humans Interact With the Mesh:
--------------------------------------------
In an autonomous multi-agent cluster, agents running on distinct hosts or
sub-shells must coordinate without manual human intervention. The Magi Pact CLI
acts as an accessible, scriptable protocol client:

1. Dynamic Workspace Discovery (`get_herder`):
   Subcommands automatically traverse the filesystem upwards to locate the
   nearest `roster/` or `pact/` directory, allowing agents to execute commands
   from any subdirectory without manually specifying `--dir`.

2. 32-Seat Visual Grid Representation:
   The `status` command renders a visual 4x8 ANSI-colored terminal grid representing
   all 32 seats:
     - [00★] : Host / Primary Arbitrator (Yellow)
     - [XX●] : Active Peer Node with valid lease (Green)
     - [XX▲] : Stale Seat with expired lease > 300s (Red)
     - [XX○] : Pristine Vacant Seat available for allocation

3. Environment Variable Context Integration:
   Commands like `post` inspect the `MAGI_SEAT` environment variable. When an
   autonomous agent is assigned to Seat 04, setting `export MAGI_SEAT=4` allows
   it to post and communicate without repetitively passing `--from-seat 4`.

4. Subcommand Dispatch Pattern:
   Rather than complex if-elif chains, the CLI utilizes Python's dictionary-based
   command dispatch table (`dispatch_map`), mapping subcommand strings directly
   to dedicated handler functions.
"""

# ------------------------------------------------------------------------------
# Standard Library Imports
# ------------------------------------------------------------------------------
import argparse   # Standard Python command-line argument parsing library
import os         # Operating system environment variable inspection
import sys        # System-specific parameters, exits, and standard streams
from pathlib import Path  # Object-oriented filesystem path manipulation

# ------------------------------------------------------------------------------
# Magi Pact Internal Module Imports
# ------------------------------------------------------------------------------
from .herder import PactHerder
from .protocol import (
    KIND_CHAT,
    KIND_TASK_DISPATCH,
    SeatState,
    make_envelope,
)
from .abli import AbliteratedRegistry
from .dataset import (
    export_seat_shard,
    reconcile_mesh_shards,
    generate_language_matrix,
    DOMAINS,
)


# ==============================================================================
# Workspace Discovery Helper
# ==============================================================================

def get_herder(dir_override: str = None) -> PactHerder:
    """Discovers the workspace root and instantiates a configured PactHerder.

    Educational Note on Directory Tree Traversal:
    ---------------------------------------------
    Command-line tools often fail when invoked from deep subdirectories (e.g.,
    running `pact send` from inside `data/datasets/`). This function implements
    an upwards directory crawl: it begins at the current working directory and
    steps upwards through parent folders until it finds evidence of the workspace
    boundary (`roster/` or `pact/` directories).

    Inputs:
        dir_override (Optional[str]): Explicit workspace directory passed by user via `--dir`.

    Outputs:
        PactHerder: Initialized Herder instance bound to the resolved workspace root.

    Step-by-Step Logic:
        1. If `dir_override` is provided, resolve it to an absolute Path and return `PactHerder(root)`.
        2. Otherwise, start at `Path.cwd()` (the current working directory).
        3. Climb parent directories in a while-loop until reaching the filesystem root (`/`).
        4. If a directory containing `roster` or `pact` is detected, return `PactHerder(current)`.
        5. If the search reaches the root without finding a match, fallback to `PactHerder(root)`.
    """
    # 1. Respect explicit directory override if supplied
    root = Path(dir_override).resolve() if dir_override else Path.cwd()

    # 2. Traverse upwards through parent directories
    current = root
    while current != current.parent:
        if (current / "roster").is_dir() or (current / "pact").is_dir():
            return PactHerder(current)
        current = current.parent

    # 3. Fallback to original root
    return PactHerder(root)


# ==============================================================================
# Subcommand Handlers
# ==============================================================================

def cmd_init(args: argparse.Namespace) -> None:
    """Initializes a fresh 32-seat Magi Pact workspace on disk.

    Inputs:
        args (argparse.Namespace): Parsed arguments containing `dir`, `host`, and `agent`.

    Outputs:
        None. (Prints success message to stdout).

    Step-by-Step Logic:
        1. Instantiate `PactHerder` pointing to the target directory.
        2. Invoke `herder.initialize_workspace()` with host occupant and model name.
        3. Print confirmation details to console.
    """
    herder = PactHerder(Path(args.dir or ".").resolve())
    herder.initialize_workspace(host_occupant=args.host, host_agent=args.agent)
    print(f"✅ Magi Pact workspace initialized at: {herder.root}")
    print(f"   Host: {args.host} (Seat 00) | 32 total seats configured.")


def cmd_status(args: argparse.Namespace) -> None:
    """Displays visual 32-seat grid, active members, file claims, and recent messages.

    Inputs:
        args (argparse.Namespace): Parsed CLI arguments.

    Outputs:
        None. (Renders dashboard to stdout).

    Step-by-Step Logic:
        1. Query `herder.list_seats()` (which automatically triggers stale reaping).
        2. Query `herder.list_claims()` for active advisory locks.
        3. Query `herder.get_messages(limit=5)` for recent message audit trail.
        4. Render a formatted 4x8 grid representing the 32 seats with ANSI color badges.
        5. List active and stale members with last heartbeat timestamps.
        6. Display active file locks and recent board messages.
    """
    herder = get_herder(args.dir)
    seats = herder.list_seats()
    active_claims = herder.list_claims()
    recent_msgs = herder.get_messages(limit=5)

    print("\n" + "=" * 64)
    print(" 🏛️  MAGI PACT: 32-SEAT FEDERATED MESH STATUS")
    print("=" * 64)

    # 32-Seat Visual Grid (4 rows x 8 columns)
    print("\n[ SEAT ROSTER ]")
    active_count = sum(1 for s in seats if s["status"] == SeatState.ACTIVE)
    print(f"Occupancy: {active_count}/32 seats active\n")

    for row in range(4):
        row_str = "  "
        for col in range(8):
            idx = row * 8 + col
            s = seats[idx]
            status = s.get("status")
            if idx == 0:
                badge = f"[\033[93m00★\033[0m]"  # Seat 00: Host (Yellow Star)
            elif status == SeatState.ACTIVE:
                badge = f"[\033[92m{idx:02d}●\033[0m]"  # Active (Green Circle)
            elif status == SeatState.STALE:
                badge = f"[\033[91m{idx:02d}▲\033[0m]"  # Stale (Red Triangle)
            else:
                badge = f"[{idx:02d}○]"              # Vacant (Normal Circle)
            row_str += badge + " "
        print(row_str)

    # Active Member Roster Details
    print("\nActive Members:")
    for s in seats:
        if s.get("status") in (SeatState.ACTIVE, SeatState.STALE):
            role_badge = "HOST" if s["seat_id"] == 0 else "PEER"
            st_color = "\033[92mACTIVE\033[0m" if s["status"] == SeatState.ACTIVE else "\033[91mSTALE\033[0m"
            print(f"  • Seat {s['seat_id']:02d} [{role_badge}]: {s.get('occupant', 'anon')} ({s.get('agent_model', 'agent')}) - {st_color} (Heartbeat: {s.get('last_heartbeat')})")

    # Active Claims (Advisory File Locks)
    print("\n[ ACTIVE FILE CLAIMS (LOCKS) ]")
    if not active_claims:
        print("  None. All files unlocked.")
    else:
        for path, info in active_claims.items():
            print(f"  🔒 {path} -> Seat {info['seat_id']:02d} (Intent: {info['intent']})")

    # Recent Audit Log Messages
    print("\n[ RECENT MESSAGES ]")
    if not recent_msgs:
        print("  No messages yet.")
    else:
        for m in recent_msgs:
            to_lbl = f"Seat {m['to_seat']:02d}" if m.get("to_seat") is not None else "ALL"
            print(f"  [{m['timestamp'][11:19]}] Seat {m['from_seat']:02d} -> {to_lbl} [{m['kind']}]: {m['payload']}")
    print("=" * 64 + "\n")


def cmd_take_seat(args: argparse.Namespace) -> None:
    """Claims a specific or automatically selected open seat for an agent.

    Inputs:
        args (argparse.Namespace): Arguments containing `name`, `model`, `seat`, `capabilities`.

    Outputs:
        None. (Prints confirmation to stdout).

    Step-by-Step Logic:
        1. Parse seat target: if numeric, use integer; if 'auto', leave as None.
        2. Call `herder.claim_seat()` with occupant, model, and capabilities.
        3. Print successful seat allocation details.
    """
    herder = get_herder(args.dir)
    target_seat = None
    if getattr(args, "seat", None) is not None:
        if str(args.seat).lower() != "auto":
            try:
                target_seat = int(args.seat)
            except ValueError:
                target_seat = None
    name = getattr(args, "name", None) or "Node-Agent"
    model = getattr(args, "model", None) or "Coding-Agent"
    caps = getattr(args, "capabilities", None)
    res = herder.claim_seat(
        occupant=name,
        agent_model=model,
        seat_id=target_seat,
        capabilities=caps.split(",") if caps else None
    )
    print(f"🎉 Successfully claimed Seat {res['seat_id']:02d} for {res['occupant']} ({res['agent_model']})!")


def cmd_who(args: argparse.Namespace) -> None:
    """Prints a concise, tabular summary of active members currently in the mesh.

    Inputs:
        args (argparse.Namespace): Parsed CLI arguments.

    Outputs:
        None. (Prints active roster to stdout).

    Step-by-Step Logic:
        1. Retrieve seats via `herder.list_seats()`.
        2. Filter for seats that are ACTIVE or STALE.
        3. Print details for each occupied seat.
    """
    herder = get_herder(args.dir)
    seats = herder.list_seats()
    active = [s for s in seats if s.get("status") in (SeatState.ACTIVE, SeatState.STALE)]
    print("\n" + "=" * 64)
    print(" 👥 MAGI PACT ACTIVE MESH ROSTER")
    print("=" * 64)
    if not active:
        print("  No active seats in mesh.")
    else:
        for s in active:
            role = "HOST" if s["seat_id"] == 0 else "PEER"
            st_color = "\033[92mACTIVE\033[0m" if s["status"] == SeatState.ACTIVE else "\033[91mSTALE\033[0m"
            print(f"  • Seat {s['seat_id']:02d} [{role}]: {s.get('occupant', 'anon')} ({s.get('agent_model', 'agent')}) - {st_color} (Heartbeat: {s.get('last_heartbeat')})")
    print("=" * 64 + "\n")


def cmd_leave_seat(args: argparse.Namespace) -> None:
    """Vacates a seat gracefully and resets its status to VACANT.

    Inputs:
        args (argparse.Namespace): Arguments containing `seat` and optional `reason`.

    Outputs:
        None.

    Step-by-Step Logic:
        1. Obtain herder instance.
        2. Invoke `herder.release_seat(args.seat, reason)`.
        3. Print confirmation message.
    """
    herder = get_herder(args.dir)
    herder.release_seat(args.seat, reason=args.reason or "voluntary exit")
    print(f"👋 Seat {args.seat:02d} released and marked vacant.")


def cmd_heartbeat(args: argparse.Namespace) -> None:
    """Emits a keep-alive heartbeat pulse to renew an active seat's lease.

    Inputs:
        args (argparse.Namespace): Arguments containing `seat`.

    Outputs:
        None.

    Step-by-Step Logic:
        1. Call `herder.heartbeat(args.seat)` to refresh the UTC timestamp on disk.
        2. Print confirmation message.
    """
    herder = get_herder(args.dir)
    herder.heartbeat(args.seat)
    print(f"💓 Heartbeat recorded for Seat {args.seat:02d}.")


def cmd_post(args: argparse.Namespace) -> None:
    """Posts a message to the mesh (broadcast to all or direct to a specific seat).

    Educational Note on Environment Variable Integration:
    -----------------------------------------------------
    If `--from-seat` is omitted, the CLI checks `os.environ.get("MAGI_SEAT")`.
    This allows an agent daemon to set `MAGI_SEAT` in its sub-shell environment
    and post messages without hardcoding its seat ID into every command string.

    Inputs:
        args (argparse.Namespace): Arguments containing `from_seat`, `to`, `msg`.

    Outputs:
        None.

    Step-by-Step Logic:
        1. Determine sender seat: use `args.from_seat` if given, else check `MAGI_SEAT`, else default to 0.
        2. Create message envelope using `make_envelope(kind=KIND_CHAT, ...)`.
        3. Append envelope to board log via `herder.record_message(env)`.
        4. Print delivery confirmation and message ID.
    """
    herder = get_herder(args.dir)
    from_seat = getattr(args, "from_seat", None)
    if from_seat is None:
        try:
            from_seat = int(os.environ.get("MAGI_SEAT", 0))
        except (ValueError, TypeError):
            from_seat = 0
    env = make_envelope(
        kind=KIND_CHAT,
        from_seat=from_seat,
        to_seat=args.to,
        payload={"message": args.msg}
    )
    herder.record_message(env)
    print(f"📨 Message recorded (ID: {env['msg_id']}) to {'ALL' if args.to is None else f'Seat {args.to:02d}'}")


def cmd_dispatch(args: argparse.Namespace) -> None:
    """Dispatches a formal structured task from Host Seat 00 to a peer agent.

    Inputs:
        args (argparse.Namespace): Arguments containing `from_seat`, `to`, `title`, `body`.

    Outputs:
        None.

    Step-by-Step Logic:
        1. Construct envelope with `KIND_TASK_DISPATCH`.
        2. Route message to the destination inbox and board log via `herder.record_message()`.
        3. Print confirmation of task dispatch.
    """
    herder = get_herder(args.dir)
    env = make_envelope(
        kind=KIND_TASK_DISPATCH,
        from_seat=args.from_seat,
        to_seat=args.to,
        payload={"title": args.title, "description": args.body}
    )
    herder.record_message(env)
    print(f"🚀 Task dispatched to Seat {args.to:02d}: '{args.title}'")


def cmd_inbox(args: argparse.Namespace) -> None:
    """Inspects and displays direct messages delivered to an agent's individual inbox.

    Inputs:
        args (argparse.Namespace): Arguments containing `seat`.

    Outputs:
        None. (Prints inbox contents to stdout).

    Step-by-Step Logic:
        1. Call `herder.poll_inbox(args.seat)`.
        2. Format and display each received message timestamp, sender, and payload.
    """
    herder = get_herder(args.dir)
    items = herder.poll_inbox(args.seat)
    print(f"\n📬 Inbox for Seat {args.seat:02d} ({len(items)} messages):\n")
    if not items:
        print("  Inbox is empty.")
    for item in items:
        print(f"  • [{item['timestamp']}] From Seat {item['from_seat']:02d} [{item['kind']}]: {item['payload']}")
    print()


def cmd_claim(args: argparse.Namespace) -> None:
    """Acquires an exclusive advisory file lock on a path before modification.

    Inputs:
        args (argparse.Namespace): Arguments containing `seat`, `path`, `intent`.

    Outputs:
        None. (Exits with code 1 if lock acquisition fails).

    Step-by-Step Logic:
        1. Call `herder.acquire_claim(seat_id, path, intent)`.
        2. If successful, print confirmation.
        3. If unsuccessful (already locked), print error and exit with code 1.
    """
    herder = get_herder(args.dir)
    ok = herder.acquire_claim(seat_id=args.seat, resource_path=args.path, intent=args.intent)
    if ok:
        print(f"🔒 Acquired lock on '{args.path}' for Seat {args.seat:02d}.")
    else:
        print(f"❌ FAILED to lock '{args.path}'. It is already actively locked by another seat.")
        sys.exit(1)


def cmd_release(args: argparse.Namespace) -> None:
    """Releases an advisory file lock previously acquired by this seat.

    Inputs:
        args (argparse.Namespace): Arguments containing `seat` and `path`.

    Outputs:
        None. (Exits with code 1 if release is unauthorized or path not locked).

    Step-by-Step Logic:
        1. Call `herder.release_claim(seat_id, path)`.
        2. If successful, print confirmation.
        3. If caller does not own the lock, print error and exit with code 1.
    """
    herder = get_herder(args.dir)
    ok = herder.release_claim(seat_id=args.seat, resource_path=args.path)
    if ok:
        print(f"🔓 Released lock on '{args.path}'.")
    else:
        print(f"❌ Failed to release lock on '{args.path}'. (You must own the lock or be Seat 00)")
        sys.exit(1)


def cmd_abli(args: argparse.Namespace) -> None:
    """Manages abliterated model profiles and hardware-aware routing.

    Inputs:
        args (argparse.Namespace): Arguments containing `--set` or `--list`.

    Outputs:
        None. (Prints hardware profile data to stdout).

    Step-by-Step Logic:
        1. Instantiate `AbliteratedRegistry(herder.root)`.
        2. If `--set <profile_id>` is supplied, activate profile and return.
        3. Otherwise, detect host hardware (Apple Silicon vs Linux CUDA) and display profiles.
    """
    herder = get_herder(args.dir)
    reg = AbliteratedRegistry(herder.root)
    if args.set:
        ok = reg.set_active_profile(args.set)
        if ok:
            print(f"🔥 Successfully activated abliterated profile: {args.set}")
        else:
            print(f"❌ Unknown profile ID: {args.set}")
            sys.exit(1)
        return

    data = reg.list_profiles()
    hw = data["current_hardware"]
    print("\n" + "=" * 64)
    print(" 🔥 ABLITERATED MODEL ORCHESTRATION (/abli)")
    print("=" * 64)
    print(f"Detected Platform : {hw['system']} ({hw['machine']}) | OS Flavor: {hw['flavor']}")
    print(f"Active Profile ID : {data['active_id']}")
    print("\nAvailable Abliterated Profiles:")
    for p in data["profiles"]:
        active_mark = " [ACTIVE ★]" if p.get("active") else ""
        print(f"  • {p['id']}{active_mark}")
        print(f"    Name      : {p['name']}")
        print(f"    Hardware  : {p['target_hardware']} (Backend: {p['backend']})")
        print(f"    Weights   : {p['weights_path']}")
        print(f"    Context   : {p['context_length']:,} tokens")
        print(f"    Corpus ID : {p['training_corpus_id']}")


def cmd_dataset(args: argparse.Namespace) -> None:
    """Manages multi-language golden dataset sharding and peer reconciliation.

    Inputs:
        args (argparse.Namespace): Arguments containing `--export-seat`, `--reconcile`, or `--status`.

    Outputs:
        None. (Exports shards or reconciles peer data).

    Step-by-Step Logic:
        1. If `--export-seat <id>` is provided, export collision-free shard into `exchange/`.
        2. If `--reconcile` is provided, deduplicate and merge all peer shards without overwrites.
        3. Otherwise, summarize language matrix domain coverage.
    """
    herder = get_herder(args.dir)
    if args.export_seat is not None:
        p = export_seat_shard(args.export_seat, herder.root)
        print(f"📦 Exported Seat {args.export_seat:02d} golden shard to: {p}")
        return

    if args.reconcile:
        res = reconcile_mesh_shards(herder.root)
        print(f"✨ Reconciled {res['shards_processed']} peer shards into: {res['master_path']}")
        print(f"   Total Unique Records : {res['total_records']}")
        print(f"   Domains Covered      : {res['domains_covered']}")
        return

    pairs = generate_language_matrix()
    print("\n" + "=" * 64)
    print(" 📚 MULTI-LANGUAGE GOLDEN DATASET MATRIX")
    print("=" * 64)
    print(f"Supported Language & System Domains ({len(DOMAINS)} total):")
    for d in DOMAINS:
        count = sum(1 for p in pairs if p.domain == d)
        print(f"  • {d.ljust(20)}: {count} gold verified exemplar(s)")


# ==============================================================================
# Main Parser Setup and Command Dispatch
# ==============================================================================

def main() -> None:
    """Primary entrypoint for the CLI argument parser and command router.

    Inputs:
        None. (Parses arguments from sys.argv).

    Outputs:
        None.

    Step-by-Step Logic:
        1. Configure top-level argument parser with `--dir` option.
        2. Register all subcommands: init, status, who, take-seat/join, leave-seat/leave,
           heartbeat, post/send, dispatch, inbox, claim, release, abli, dataset.
        3. Parse command-line arguments.
        4. If no subcommand is supplied, display help text and exit cleanly.
        5. Look up matching subcommand handler in `dispatch_map` and execute it.
    """
    parser = argparse.ArgumentParser(
        prog="magi_pact",
        description="Magi Pact: 32-Seat Multi-Agent Federated Consensus Mesh"
    )
    parser.add_argument("--dir", help="Path to magi_pact root directory", default=None)
    sub = parser.add_subparsers(dest="command")

    # init
    p_init = sub.add_parser("init", help="Initialize a fresh Magi Pact directory")
    p_init.add_argument("--host", default="Host-Alpha", help="Host occupant name")
    p_init.add_argument("--agent", default="Magi-Master", help="Host agent model name")

    # status
    sub.add_parser("status", help="Display 32-seat board, active claims, and message log")

    # who (compact active members view)
    sub.add_parser("who", help="List active seats and members in the mesh")

    # take-seat / join
    p_take = sub.add_parser("take-seat", help="Take an open seat")
    p_take.add_argument("--name", default="Node-Agent", help="Human developer name or callsign")
    p_take.add_argument("--model", default="Coding-Agent", help="Agent model (e.g. Claude Code, Codex)")
    p_take.add_argument("--seat", default="auto", help="Seat ID (1-31), or 'auto' for next available")
    p_take.add_argument("--capabilities", default="code,test", help="Comma-separated capabilities")

    p_join = sub.add_parser("join", help="Join the mesh and claim a seat")
    p_join.add_argument("--name", default="Node-Agent", help="Human developer name or callsign")
    p_join.add_argument("--model", default="Coding-Agent", help="Agent model (e.g. Claude Code, Codex)")
    p_join.add_argument("--seat", default="auto", help="Seat ID (1-31), or 'auto' for next available")
    p_join.add_argument("--capabilities", default="code,test", help="Comma-separated capabilities")

    # leave-seat / leave
    p_leave = sub.add_parser("leave-seat", help="Vacate a seat")
    p_leave.add_argument("--seat", type=int, required=True, help="Seat ID to vacate")
    p_leave.add_argument("--reason", default="leaving", help="Reason for departure")

    p_l = sub.add_parser("leave", help="Leave the mesh and vacate a seat")
    p_l.add_argument("--seat", type=int, required=True, help="Seat ID to vacate")
    p_l.add_argument("--reason", default="leaving", help="Reason for departure")

    # heartbeat
    p_hb = sub.add_parser("heartbeat", help="Send a heartbeat to keep a seat active")
    p_hb.add_argument("--seat", type=int, required=True, help="Seat ID")

    # post / send
    p_post = sub.add_parser("post", help="Post a message to the board or a peer")
    p_post.add_argument("--from-seat", type=int, default=None, help="Your seat ID (default: MAGI_SEAT or 0)")
    p_post.add_argument("--to", type=int, default=None, help="Recipient seat ID (omit for ALL)")
    p_post.add_argument("--msg", required=True, help="Message text")

    p_send = sub.add_parser("send", help="Send a message to a peer or broadcast to all")
    p_send.add_argument("--from-seat", type=int, default=None, help="Your seat ID (default: MAGI_SEAT or 0)")
    p_send.add_argument("--to", type=int, default=None, help="Recipient seat ID (omit for ALL)")
    p_send.add_argument("--msg", required=True, help="Message text")

    # dispatch
    p_disp = sub.add_parser("dispatch", help="Host task dispatch")
    p_disp.add_argument("--from-seat", type=int, default=0, help="Your seat ID (default: 0)")
    p_disp.add_argument("--to", type=int, required=True, help="Recipient seat ID")
    p_disp.add_argument("--title", required=True, help="Task title")
    p_disp.add_argument("--body", required=True, help="Task details")

    # inbox
    p_inbox = sub.add_parser("inbox", help="View direct messages for a seat")
    p_inbox.add_argument("--seat", type=int, required=True, help="Seat ID")

    # claim
    p_claim = sub.add_parser("claim", help="Acquire a file lock")
    p_claim.add_argument("--seat", type=int, required=True, help="Your seat ID")
    p_claim.add_argument("--path", required=True, help="File or module path")
    p_claim.add_argument("--intent", required=True, help="Why you are modifying this file")

    # release
    p_rel = sub.add_parser("release", help="Release a file lock")
    p_rel.add_argument("--seat", type=int, required=True, help="Your seat ID")
    p_rel.add_argument("--path", required=True, help="File path to release")

    # abli (/abli)
    p_abli = sub.add_parser("abli", help="Abliterated model profiles and hardware routing (/abli)")
    p_abli.add_argument("--set", help="Set active abliterated profile ID")
    p_abli.add_argument("--list", action="store_true", help="List all abliterated profiles")

    # dataset
    p_ds = sub.add_parser("dataset", help="Multi-language training dataset and shard management")
    p_ds.add_argument("--export-seat", type=int, help="Export golden dataset shard for a seat into exchange/")
    p_ds.add_argument("--reconcile", action="store_true", help="Reconcile all peer shards in exchange/ without overwrites")
    p_ds.add_argument("--status", action="store_true", help="Show language domain coverage")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Command dispatch dictionary mapping subcommand strings to handler functions
    dispatch_map = {
        "init": cmd_init,
        "status": cmd_status,
        "who": cmd_who,
        "take-seat": cmd_take_seat,
        "join": cmd_take_seat,
        "leave-seat": cmd_leave_seat,
        "leave": cmd_leave_seat,
        "heartbeat": cmd_heartbeat,
        "post": cmd_post,
        "send": cmd_post,
        "dispatch": cmd_dispatch,
        "inbox": cmd_inbox,
        "claim": cmd_claim,
        "release": cmd_release,
        "abli": cmd_abli,
        "dataset": cmd_dataset,
    }
    dispatch_map[args.command](args)


if __name__ == "__main__":
    main()
