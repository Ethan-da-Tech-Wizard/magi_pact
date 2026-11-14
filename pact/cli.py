"""Command Line Interface for Magi Pact.

Accessible to humans and coding agents directly.
"""
import argparse
import sys
from pathlib import Path

from .herder import PactHerder
from .protocol import (
    KIND_CHAT,
    KIND_TASK_DISPATCH,
    SeatState,
    make_envelope,
)


def get_herder(dir_override: str = None) -> PactHerder:
    root = Path(dir_override).resolve() if dir_override else Path.cwd()
    # Walk upwards if not in root of magi_pact
    current = root
    while current != current.parent:
        if (current / "roster").is_dir() or (current / "pact").is_dir():
            return PactHerder(current)
        current = current.parent
    return PactHerder(root)


def cmd_init(args):
    herder = PactHerder(Path(args.dir or ".").resolve())
    herder.initialize_workspace(host_occupant=args.host, host_agent=args.agent)
    print(f"✅ Magi Pact workspace initialized at: {herder.root}")
    print(f"   Host: {args.host} (Seat 00) | 32 total seats configured.")


def cmd_status(args):
    herder = get_herder(args.dir)
    seats = herder.list_seats()
    active_claims = herder.list_claims()
    recent_msgs = herder.get_messages(limit=5)

    print("\n" + "=" * 64)
    print(" 🏛️  MAGI PACT: 32-SEAT FEDERATED MESH STATUS")
    print("=" * 64)

    # 32-Seat Visual Grid
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
                badge = f"[\033[93m00★\033[0m]" # Host
            elif status == SeatState.ACTIVE:
                badge = f"[\033[92m{idx:02d}●\033[0m]" # Active
            elif status == SeatState.STALE:
                badge = f"[\033[91m{idx:02d}▲\033[0m]" # Stale
            else:
                badge = f"[{idx:02d}○]"             # Vacant
            row_str += badge + " "
        print(row_str)

    print("\nActive Members:")
    for s in seats:
        if s.get("status") in (SeatState.ACTIVE, SeatState.STALE):
            role_badge = "HOST" if s["seat_id"] == 0 else "PEER"
            st_color = "\033[92mACTIVE\033[0m" if s["status"] == SeatState.ACTIVE else "\033[91mSTALE\033[0m"
            print(f"  • Seat {s['seat_id']:02d} [{role_badge}]: {s.get('occupant', 'anon')} ({s.get('agent_model', 'agent')}) - {st_color} (Heartbeat: {s.get('last_heartbeat')})")

    # Active Claims
    print("\n[ ACTIVE FILE CLAIMS (LOCKS) ]")
    if not active_claims:
        print("  None. All files unlocked.")
    else:
        for path, info in active_claims.items():
            print(f"  🔒 {path} -> Seat {info['seat_id']:02d} (Intent: {info['intent']})")

    # Recent Messages
    print("\n[ RECENT MESSAGES ]")
    if not recent_msgs:
        print("  No messages yet.")
    else:
        for m in recent_msgs:
            to_lbl = f"Seat {m['to_seat']:02d}" if m.get("to_seat") is not None else "ALL"
            print(f"  [{m['timestamp'][11:19]}] Seat {m['from_seat']:02d} -> {to_lbl} [{m['kind']}]: {m['payload']}")
    print("=" * 64 + "\n")


def cmd_take_seat(args):
    herder = get_herder(args.dir)
    res = herder.claim_seat(
        occupant=args.name,
        agent_model=args.model,
        seat_id=args.seat,
        capabilities=args.capabilities.split(",") if args.capabilities else None
    )
    print(f"🎉 Successfully claimed Seat {res['seat_id']:02d} for {res['occupant']} ({res['agent_model']})!")


def cmd_leave_seat(args):
    herder = get_herder(args.dir)
    herder.release_seat(args.seat, reason=args.reason or "voluntary exit")
    print(f"👋 Seat {args.seat:02d} released and marked vacant.")


def cmd_heartbeat(args):
    herder = get_herder(args.dir)
    herder.heartbeat(args.seat)
    print(f"💓 Heartbeat recorded for Seat {args.seat:02d}.")


def cmd_post(args):
    herder = get_herder(args.dir)
    env = make_envelope(
        kind=KIND_CHAT,
        from_seat=args.from_seat,
        to_seat=args.to,
        payload={"message": args.msg}
    )
    herder.record_message(env)
    print(f"📨 Message recorded (ID: {env['msg_id']}) to {'ALL' if args.to is None else f'Seat {args.to:02d}'}")


def cmd_dispatch(args):
    herder = get_herder(args.dir)
    env = make_envelope(
        kind=KIND_TASK_DISPATCH,
        from_seat=args.from_seat,
        to_seat=args.to,
        payload={"title": args.title, "description": args.body}
    )
    herder.record_message(env)
    print(f"🚀 Task dispatched to Seat {args.to:02d}: '{args.title}'")


def cmd_inbox(args):
    herder = get_herder(args.dir)
    items = herder.poll_inbox(args.seat)
    print(f"\n📬 Inbox for Seat {args.seat:02d} ({len(items)} messages):\n")
    if not items:
        print("  Inbox is empty.")
    for item in items:
        print(f"  • [{item['timestamp']}] From Seat {item['from_seat']:02d} [{item['kind']}]: {item['payload']}")
    print()


def cmd_claim(args):
    herder = get_herder(args.dir)
    ok = herder.acquire_claim(seat_id=args.seat, resource_path=args.path, intent=args.intent)
    if ok:
        print(f"🔒 Acquired lock on '{args.path}' for Seat {args.seat:02d}.")
    else:
        print(f"❌ FAILED to lock '{args.path}'. It is already actively locked by another seat.")
        sys.exit(1)


def cmd_release(args):
    herder = get_herder(args.dir)
    ok = herder.release_claim(seat_id=args.seat, resource_path=args.path)
    if ok:
        print(f"🔓 Released lock on '{args.path}'.")
    else:
        print(f"❌ Failed to release lock on '{args.path}'. (You must own the lock or be Seat 00)")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(prog="magi_pact", description="Magi Pact: 32-Seat Multi-Agent Federated Mesh")
    parser.add_argument("--dir", help="Path to magi_pact root directory", default=None)
    sub = parser.add_subparsers(dest="command")

    # init
    p_init = sub.add_parser("init", help="Initialize a fresh Magi Pact directory")
    p_init.add_argument("--host", default="Ethan", help="Host occupant name")
    p_init.add_argument("--agent", default="Magi-Master", help="Host agent model name")

    # status
    sub.add_parser("status", help="Display 32-seat board, active claims, and message log")

    # take-seat
    p_take = sub.add_parser("take-seat", help="Take an open seat")
    p_take.add_argument("--name", required=True, help="Human developer name or callsign")
    p_take.add_argument("--model", default="Coding-Agent", help="Agent model (e.g. Claude Code, Codex)")
    p_take.add_argument("--seat", type=int, default=None, help="Explicit seat ID (1-31), or next available")
    p_take.add_argument("--capabilities", default="code,test", help="Comma-separated capabilities")

    # leave-seat
    p_leave = sub.add_parser("leave-seat", help="Vacate a seat")
    p_leave.add_argument("--seat", type=int, required=True, help="Seat ID to vacate")
    p_leave.add_argument("--reason", default="leaving", help="Reason for departure")

    # heartbeat
    p_hb = sub.add_parser("heartbeat", help="Send a heartbeat to keep a seat active")
    p_hb.add_argument("--seat", type=int, required=True, help="Seat ID")

    # post
    p_post = sub.add_parser("post", help="Post a message to the board or a peer")
    p_post.add_argument("--from-seat", type=int, required=True, help="Your seat ID")
    p_post.add_argument("--to", type=int, default=None, help="Recipient seat ID (omit for ALL)")
    p_post.add_argument("--msg", required=True, help="Message text")

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

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch_map = {
        "init": cmd_init,
        "status": cmd_status,
        "take-seat": cmd_take_seat,
        "leave-seat": cmd_leave_seat,
        "heartbeat": cmd_heartbeat,
        "post": cmd_post,
        "dispatch": cmd_dispatch,
        "inbox": cmd_inbox,
        "claim": cmd_claim,
        "release": cmd_release,
    }
    dispatch_map[args.command](args)


if __name__ == "__main__":
    main()
