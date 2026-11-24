# 🌐 Magi Pact: Multi-Device Node Slot Mesh Manual
**Autonomous Peer-to-Peer Synchronization for Ethan Kilmer (`Ethan-da-Tech-Wizard`) & Zazu (`zazmattaz-debug`)**
*Architectural Blueprint, Operational Manual & Technical Field Guide*
*Author: Ethan-da-Tech-Wizard & Magi Swarm Engineering*

---

## 🏛️ 1. Architecture: The Sovereign Node Slot Mesh

### Why "Node Slots" Instead of a "Primary Host Anchor"?
In traditional client-server designs, one central machine acts as a "primary host." If that computer sleeps, overheats, or loses its internet connection, all other satellite devices (laptops, phones) become stranded. You experience connection lag, spinning reconnect loaders, and data lockouts.

**The Magi Pact Node Slot Mesh** eliminates this bottleneck completely. 

Every access point—whether a mobile iPhone on cellular, a MacBook in a coffee shop, or a desktop workstation at home—operates as an **independent, sovereign node slot** in a distributed 32-seat deterministic grid.

```mermaid
flowchart TD
    subgraph EthanCluster ["Ethan's Ring (Slots 00-04)"]
        Node00["Node Slot 00: Host-Alpha\n(Primary Orchestrator)"]
        Node01["Node Slot 01: Laptop\n(Mobile / Coffee Shop)"]
        Node02["Node Slot 02: Mobile Phone\n(Cellular 5G / Local Wi-Fi)"]
        Node03["Node Slot 03: Primary Desktop\n(Compile / GPU Rig)"]
        Node04["Node Slot 04: Lab Station\n(Workstation Engine)"]

        Node00 <===> Node01
        Node01 <===> Node02
        Node02 <===> Node03
        Node03 <===> Node04
        Node04 <===> Node00
        Node01 <===> Node03
        Node02 <===> Node04
    end

    subgraph ConsensusBus ["Serverless Consensus & Storage Bus"]
        AtomicRoster["roster/seat_00..31.json\n(Atomic LWW Leases)"]
        AppendJournal["board/messages.jsonl\n(POSIX flock Append Log)"]
        AdvisoryClaims["board/claims.json\n(Distributed File Locks & TTL)"]
        DirectInboxes["inboxes/seat_XX/\n(Point-to-Point Mailboxes)"]
        MerkleWAL["comms/.wal/wal.db\n(Write-Ahead Log + Merkle Trees)"]
    end

    subgraph ZazuCluster ["Zazu's Ring (Slots 05-09: zazmattaz-debug)"]
        Zazu05["Node Slot 05: Zazu Host\n(Primary Rig)"]
        Zazu06["Node Slot 06: Zazu Laptop\n(Mobile Node)"]
        Zazu07["Node Slot 07: Zazu Phone\n(Cellular Mobile Hub)"]

        Zazu05 <===> Zazu06
        Zazu06 <===> Zazu07
        Zazu07 <===> Zazu05
    end

    EthanCluster <==== "P2P Tor / LAN / Git Worktrees" ====> ConsensusBus
    ConsensusBus <==== "P2P Tor / LAN / Git Worktrees" ====> ZazuCluster
```

### Core Invariants of the Mesh
1. **Zero Single Point of Failure:** If your desktop is asleep at home, your phone on cellular and your laptop on Wi-Fi communicate seamlessly with Zazu and each other. No machine depends on another machine being awake.
2. **Dynamic Slot Allocation:** Nodes claim slots on demand (`take-seat`), maintain them via lightweight heartbeat leases, and vacate them gracefully (`leave-seat`).
3. **Multi-Transport Zero Lag:**
   - **Local Wi-Fi:** Immediate peer discovery and direct sub-millisecond local synchronization.
   - **Cellular & Remote:** Transparent end-to-end routing over Tor v3 onion services and encrypted WireGuard tunnels without open ports or static IPs.
4. **Zero Data Loss (WAL + Merkle Catch-Up):** If a device is in your backpack without service, the moment it reconnects, it queries the Merkle tree root diff and automatically pulls missing messages and patches.

---

## 🪑 2. The 32-Seat Roster Topology

The mesh organizes coordination across 32 deterministic slots:

```text
  [00★] [01●] [02●] [03●] [04●] [05◆] [06◆] [07◆]   Row 0: Slots 00-07
  [08○] [09○] [10○] [11○] [12○] [13○] [14○] [15○]   Row 1: Slots 08-15
  [16○] [17○] [18○] [19○] [20○] [21○] [22○] [23○]   Row 2: Slots 16-23
  [24○] [25○] [26○] [27○] [28○] [29○] [30○] [31○]   Row 3: Slots 24-31

  Legend:
  [00★] Primary Mesh Orchestrator (Host-Alpha)
  [01●] Ethan's Active Device Slots (Laptop, Phone, Desktop, Lab Station)
  [05◆] Zazu's Active Device Slots (zazmattaz-debug)
  [08▲] Stale Slot (Heartbeat expired > 300s, available for auto-reclaim)
  [09○] Vacant Slot
```

---

## 🛠️ 3. Node Slot Lifecycle & Commands

### 1. Taking a Seat (Joining the Mesh)
Any device or agent claims the next vacant node slot automatically:

```bash
# Auto-claim next available seat
python3 pact/magi.py join --seat auto --name "Ethan-MacBook" --model "Antigravity"

# Or explicitly claim a specific slot
python3 pact/magi.py join --seat 2 --name "Ethan-iPhone" --model "MobileHub"
```

Under the hood:
- The node acquires an exclusive advisory lock on `roster/`.
- Verifies that the requested seat is either `vacant` or has been `stale` past its TTL (300 seconds).
- Writes `roster/seat_XX.json` using atomic temporary file replacement (`temp.replace()`).
- Emits a `SEAT_CLAIM` event to `board/messages.jsonl`.

### 2. Emitting Heartbeats (Lease Maintenance)
While an access point is active, it periodically emits heartbeats to maintain its lease:

```bash
python3 pact/magi.py heartbeat --seat 2
```
*Note: If no heartbeat is received for > 300 seconds, the Herder supervisor shifts the seat status to `stale`, allowing reclamation if the device was abruptly disconnected.*

### 3. Checking Mesh State & Inboxes
View live roster status, active locks, and recent messages:

```bash
# Visual 32-seat grid, file locks, and message feed
python3 pact/magi.py status

# Compact active roster
python3 pact/magi.py who

# Check direct mailbox for your specific node slot
python3 pact/magi.py inbox --seat 2
```

### 4. Advisory File Locking (Conflict-Free Collaboration)
Before editing shared code or generating datasets, a node acquires a timed advisory lock:

```bash
# Acquire lock
python3 pact/magi.py claim --seat 1 --path "pact/herder.py" --intent "Optimize lease resolution"

# Release lock once verified
python3 pact/magi.py release --seat 1 --path "pact/herder.py"
```

### 5. Graceful Departure (Vacating a Slot)
When a device is going offline or a task is finished:

```bash
python3 pact/magi.py leave --seat 2 --reason "Switching off mobile hotspot"
```
*The seat status is reset to `vacant`, and a `SEAT_RELEASE` event is broadcast to all peers.*

---

## 🔄 4. Zero-Friction Sync: Wi-Fi + Cellular Merkle WAL

For data and message consistency across fluctuating networks (Wi-Fi ↔ Cellular), the mesh pairs with the Write-Ahead Log (`briar_magi_bridge.py`):

1. **Monotonic Sequences:** Every message and patch is assigned a strictly increasing integer sequence number per producer (`agent00`, `ethan-phone`, `zazu-laptop`).
2. **Merkle Accumulator:**
   $$\text{Root}_{i} = \text{SHA256}(\text{Root}_{i-1} \parallel \text{SHA256}(\text{Payload}_i))$$
3. **Differential Catch-Up:** When your phone reconnects on cellular:
   - It queries the remote peer's latest Merkle root and sequence number.
   - If the root matches, the phone is fully synchronized.
   - If divergent, it requests only the events since its last recorded consumer cursor (`since_seq`), replaying them in exact order.

---

## 🤝 5. Coordination Protocol with Zazu (`zazmattaz-debug`)

To collaborate smoothly with Zazu on GitHub without stepping on each other's work:

1. **Independent Sovereign Rings:**
   - Ethan uses Slots `00–04`.
   - Zazu uses Slots `05–09`.
2. **Git Branching & Patch Delivery:**
   - Direct pushes to `main` are restricted during active sprints.
   - Work is developed in feature worktrees and proposed via `exchange/`:
     ```bash
     git diff main > exchange/seat_05_zazu_engine_fix.patch
     python3 pact/magi.py send --to 0 --msg "Patch ready in exchange/seat_05_zazu_engine_fix.patch"
     ```
3. **Repository Sync:**
   - Both nodes pull and push cleanly via GitHub remotes (`Ethan-da-Tech-Wizard` and `zazmattaz-debug`).
   - The file bus ensures neither developer overwrites an active file lock held in `board/claims.json`.

---

## 📋 6. Summary Checklist for Any New Device

When adding any new computer or phone to the mesh:
- [ ] Clone or pull latest `magi_pact` from GitHub.
- [ ] Run `python3 pact/magi.py who` to see current occupancy.
- [ ] Run `python3 pact/magi.py join --seat auto --name "<DeviceName>" --model "<AgentModel>"`.
- [ ] Note assigned **Seat ID**.
- [ ] Broadcast readiness: `python3 pact/magi.py send --msg "Node online and ready."`.
- [ ] Check inbox: `python3 pact/magi.py inbox --seat <SeatID>`.
