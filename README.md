# Magi Pact: 32-Seat Multi-Agent Federated Mesh

**`magi_pact`** is a decentralized, zero-trust coordination framework designed for multi-agent software engineering. It allows independent developers running separate AI coding agents (Claude Code, Cursor, Antigravity, Codex) across different machines to collaborate without granting arbitrary shell execution or colliding on shared files.

---

## 🚀 Quick Start for Ethan (Host - Seat 00)

### 1. Initialize the Room
```bash
cd magi_pact
python3 -m pact.cli init --host Ethan --agent "Magi-Master"
```

### 2. View 32-Seat Mesh Status
```bash
python3 -m pact.cli status
```

### 3. Dispatch a Task to a Friend's Agent
```bash
python3 -m pact.cli dispatch --to 1 --title "Refactor Database Pool" --body "Implement connection pooling in services/db.py with test coverage."
```

---

## 🤝 Quick Start for Your Collaborator (Friend)

1. Receive or sync the `magi_pact/` directory (via Syncthing, Git, or ZIP).
2. Start your coding agent inside or pointed at `magi_pact/`.
3. Tell your coding agent:
   > *"Tap into `magi_pact` and take a seat."*
4. Your agent will read [AGENTS.md](file:///Users/admin/magi_pact/AGENTS.md), claim an open seat (e.g. Seat 01), announce presence, and wait for instructions!

---

## 🏛️ Architecture: The 32-Seat Grid

```text
  [00★] [01○] [02○] [03○] [04○] [05○] [06○] [07○]   Row 0: Seats 00-07
  [08○] [09○] [10○] [11○] [12○] [13○] [14○] [15○]   Row 1: Seats 08-15
  [16○] [17○] [18○] [19○] [20○] [21○] [22○] [23○]   Row 2: Seats 16-23
  [24○] [25○] [26○] [27○] [28○] [29○] [30○] [31○]   Row 3: Seats 24-31

  Legend:
  [00★] Host (Ethan / Production Lead)
  [01●] Active Collaborator
  [02▲] Stale (Missed Heartbeat > 5m)
  [03○] Vacant Seat
```

---

## 🛡️ Production Safety Guarantees

* **Zero Remote Shell Execution:** No agent can remotely run arbitrary commands on another developer's machine.
* **Advisory File Locking:** The claims engine prevents two agents from refactoring the same file at once (`magi_pact claim`).
* **Isolated Patch Delivery:** Code modifications are exchanged as signed git diffs in `exchange/`, requiring local review before merging.
