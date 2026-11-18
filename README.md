# Magi Pact: Decentralized Multi-Agent Consensus Bus

[![License](https://img.shields.io/badge/License-MIT%20%7C%20Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](pyproject.toml)
[![Architecture](https://img.shields.io/badge/Architecture-Serverless%20P2P-orange.svg)](#architecture)
[![Consensus](https://img.shields.io/badge/Consensus-LWW%20%2B%20Incumbent%20Protection-green.svg)](#consensus-and-seat-reservation)

**Magi Pact** is a serverless, zero-trust coordination framework and consensus bus designed for heterogeneous AI agent clusters. It enables autonomous coding and reasoning agents across diverse environments (macOS, Arch Linux, Fedora, Ubuntu, Cloud VMs) to collaborate deterministically without requiring a central coordinator, centralized daemon, or open network listening ports.

By leveraging filesystem-level atomic journaling, advisory distributed locks, and deterministic Last-Write-Wins (LWW) conflict resolution with incumbent protection, Magi Pact provides a single-point-of-failure-free communication layer suitable for peer-to-peer file synchronization engines (such as Syncthing), Git worktrees, and shared network volumes.

---

## Architecture

Magi Pact operates on a partitioned 32-seat deterministic grid. Seat 00 serves as the primary host/arbitrator partition, while Seats 01 through 31 function as peer execution nodes for specialized agents (architects, compilers, runtime engineers, test harnesses).

### Core Architecture Diagram

```mermaid
flowchart TD
    subgraph StorageBus ["Distributed Storage & Sync Bus (Syncthing / Git / Shared Volume)"]
        Roster["roster/seat_00..31.json\n(Node State & Leases)"]
        Board["board/messages.jsonl\n(Append-Only Message Stream)"]
        Claims["board/claims.json\n(Advisory File Locks & TTL)"]
        Inboxes["inboxes/seat_00..31/\n(Directed Peer Mailboxes)"]
        Exchange["exchange/\n(Artifacts & Patches)"]
    end

    subgraph HostNode ["Host Node (Host-Alpha)"]
        HostAgent["Coordinator Agent\n(Seat 00)"]
        HostCLI["Magi CLI / Herder"]
    end

    subgraph PeerA ["Peer Node A (Host-Beta / Linux)"]
        AgentA["Polyglot / Systems Agent\n(Seat 01)"]
        CLIA["Magi CLI / Herder"]
    end

    subgraph PeerB ["Peer Node B (Host-Gamma / Cloud)"]
        AgentB["Verification Agent\n(Seat 02)"]
        CLIB["Magi CLI / Herder"]
    end

    HostAgent <--> HostCLI
    HostCLI <--> StorageBus

    AgentA <--> CLIA
    CLIA <--> StorageBus

    AgentB <--> CLIB
    CLIB <--> StorageBus
```

### Consensus and Seat Reservation

1. **Deterministic Last-Write-Wins (LWW) with Incumbent Protection:**
   - Active incumbents with valid heartbeat leases cannot be preempted or evicted by newcomers.
   - If an agent misses heartbeats beyond the TTL threshold (default: 300 seconds), its seat status shifts to `stale`, allowing reclamation.
2. **Local Mailbox Delivery & Atomic Journaling:**
   - Messages are written using atomic file-locking (`fcntl.flock`) to `board/messages.jsonl` for global auditability.
   - Point-to-point dispatches are routed directly into destination mailboxes (`inboxes/seat_<XX>/msg_<id>.json`), ensuring peers only poll localized state.
3. **Advisory Resource Locking:**
   - Before mutating shared codebases or running exclusive workloads, agents request timed resource claims in `board/claims.json`. Conflicting requests are deterministically rejected until the lock is released or its TTL expires.
4. **Zero Remote Code Execution (RCE):**
   - No node can force arbitrary command execution on another host. All cross-node directives take the form of structured task proposals and verifiable git patches in `exchange/`.

---

## 32-Seat Roster Topology

```text
  [00★] [01○] [02○] [03○] [04○] [05○] [06○] [07○]   Row 0: Seats 00-07
  [08○] [09○] [10○] [11○] [12○] [13○] [14○] [15○]   Row 1: Seats 08-15
  [16○] [17○] [18○] [19○] [20○] [21○] [22○] [23○]   Row 2: Seats 16-23
  [24○] [25○] [26○] [27○] [28○] [29○] [30○] [31○]   Row 3: Seats 24-31

  Legend:
  [00★] Host / Primary Coordinator
  [01●] Active Peer Node
  [02▲] Stale Seat (Heartbeat expired > 5m)
  [03○] Vacant Seat
```

---

## Quickstart Guide

### 1. Installation

Install via pip in editable mode or build from source:

```bash
# Clone the repository
git clone https://github.com/magi-pact/magi_pact.git
cd magi_pact

# Install locally
pip install .
```

Alternatively, you can run directly without installation using the Python entrypoint `pact/magi.py`.

### 2. Initializing a Workspace (Host Only)

```bash
# Initialize a fresh 32-seat mesh with Host-Alpha in Seat 00
python3 pact/magi.py init --host Host-Alpha --agent Magi-Master
```

### 3. Joining the Mesh

Agents or developers can join by claiming an automatic or explicit seat:

```bash
# Auto-allocate the next vacant seat
python3 pact/magi.py join --seat auto --name "Node-01" --model "Codex"

# Or explicitly claim a specific seat
python3 pact/magi.py join --seat 4 --name "FirmwareArchitect" --model "Antigravity"
```

### 4. Viewing Mesh Status and Roster

```bash
# Compact active roster
python3 pact/magi.py who

# Full visual 32-seat grid, file claims, and recent messages
python3 pact/magi.py status
```

### 5. Messaging and Task Dispatch

```bash
# Broadcast a message to all mesh nodes
python3 pact/magi.py send --msg "Node-01 online. Ready for pipeline tasks."

# Send a direct message to Seat 00
python3 pact/magi.py send --to 0 --msg "Task #42 completed. Patch delivered to exchange/."

# Dispatch a formal structured task (Seat 00 only)
python3 pact/magi.py dispatch --to 1 --title "Build Go Shards" --body "Implement worker pools in go_engine.py"
```

### 6. Checking Inboxes

```bash
# Poll directed messages for your seat
python3 pact/magi.py inbox --seat 1
```

### 7. Advisory File Locking

```bash
# Acquire a lock before editing critical paths
python3 pact/magi.py claim --seat 1 --path "pact/herder.py" --intent "Implement monotonic clock TTL"

# Release the lock once edits are verified
python3 pact/magi.py release --seat 1 --path "pact/herder.py"
```

### 8. Emitting Heartbeats and Leaving

```bash
# Refresh lease during long computations
python3 pact/magi.py heartbeat --seat 1

# Gracefully vacate seat upon task completion
python3 pact/magi.py leave --seat 1 --reason "Mission accomplished"
```

---

## Synchronization Layer Integration

Magi Pact is transport-agnostic and relies on standard filesystem semantics. Any synchronization layer that delivers file updates across machines can host the bus:

### Option A: Syncthing (Recommended for Multi-Host P2P)
1. Install [Syncthing](https://syncthing.net/) on all cluster machines (e.g. Mac, Linux workstation, Cloud instance).
2. Share the `magi_pact/` directory across all nodes with **Send & Receive** folder type.
3. Set File Pull Order to *Smallest First* to prioritize heartbeat JSON updates over large exchange artifacts.

### Option B: Git Worktrees
1. Push and pull the mesh state using a dedicated orchestration branch (e.g. `mesh-state`).
2. Agents commit their seat and inbox changes; git hooks handle fast-forward pulls.

### Option C: Shared Network Volumes (NFS / SMB / Ceph)
1. Mount the `magi_pact` directory as a shared network filesystem across your cluster.
2. The built-in POSIX `fcntl` file locking ensures conflict-free concurrent appends.

---

## Directory Layout

```text
magi_pact/
├── pact/                    # Python core package
│   ├── herder.py            # Lifecycle, seat management & advisory claims
│   ├── protocol.py          # Message envelopes & schema validation
│   ├── cli.py               # Unified CLI subcommands
│   ├── magi.py              # Direct executable runner
│   ├── dataset.py           # Multi-language golden dataset matrix
│   ├── splits.py            # Qwen3.5 ChatML formatters & loss masking
│   └── abli.py              # Hardware-aware model routing registry
├── bin/                     # Standalone CLI wrapper
├── roster/                  # Seat state records (seat_00.json ... seat_31.json)
├── inboxes/                 # Directed mailboxes (seat_00/ ... seat_31/)
├── board/                   # Append-only message log & claims
│   ├── messages.jsonl       # Consensus message journal
│   ├── claims.json          # Active file locks
│   └── BRIEF.md             # Active room objectives
├── exchange/                # Patches, checksums, and dataset shards
├── tests/                   # Complete test suite (44 passing tests)
├── pyproject.toml           # Standard PEP 517/518 build metadata
├── setup.py                 # Setuptools installer
├── LICENSE                  # Dual-license notice
├── LICENSE-MIT              # MIT License
└── LICENSE-APACHE           # Apache 2.0 License
```

---

## Verification & Testing

Magi Pact comes with comprehensive test coverage verifying protocol envelope serialization, seat reaping, POSIX file locking, dataset partitioning, and toolchain engines:

```bash
# Run the complete test suite
python3 -m unittest discover tests
```

---

## License

Magi Pact is dual-licensed under both the **MIT License** and the **Apache License (Version 2.0)**. See [LICENSE](LICENSE), [LICENSE-MIT](LICENSE-MIT), and [LICENSE-APACHE](LICENSE-APACHE) for details.
