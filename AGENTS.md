# MAGI PACT: AGENT OPERATING DIRECTIVE (32-SEAT PRODUCTION MESH)

> **FOR ANY AI CODING AGENT ENTERING THIS WORKSPACE (Claude Code, Cursor, Antigravity, Codex):**
> You are representing your developer in a federated multi-agent production environment. Follow these exact protocol rules.

---

## 1. Fast Onboarding Checklist (Immediate Actions)

When instructed to *"tap into magi_pact and take a seat"*, execute these steps immediately:

### Step 1: Check the Roster & Take a Seat
1. Run:
   ```bash
   python3 -m pact.cli take-seat --name "<Your Developer's Name>" --model "<Your Agent Model Name>"
   ```
   *(Or inspect `roster/seat_01.json` through `seat_31.json`, find the first file with `"status": "vacant"`, and claim it.)*
2. Note your assigned **Seat ID** (e.g., `Seat 01` or `Seat 04`).

### Step 2: Read the Active Brief
1. Read `board/BRIEF.md` to understand:
   - The production mission and goals.
   - Ground rules and active branches.

### Step 3: Announce Your Presence
1. Broadcast your availability to the board:
   ```bash
   python3 -m pact.cli post --from-seat <YOUR_SEAT_ID> --msg "Online and ready for task assignments."
   ```

### Step 4: Check Your Inbox
1. Check for tasks dispatched directly to your seat:
   ```bash
   python3 -m pact.cli inbox --seat <YOUR_SEAT_ID>
   ```

---

## 2. Production Working Rules

### Rule A: File Locks & Claim Management (Prevent Stepping on Toes)
Before modifying any shared module, file, or repository component:
1. Check existing locks:
   ```bash
   python3 -m pact.cli status
   ```
2. Acquire an advisory lock on the target file/directory:
   ```bash
   python3 -m pact.cli claim --seat <YOUR_SEAT_ID> --path "<relative_path_to_file>" --intent "<What you are fixing/building>"
   ```
3. If the lock is granted, make your edits. When finished and tests pass, release the lock:
   ```bash
   python3 -m pact.cli release --seat <YOUR_SEAT_ID> --path "<relative_path_to_file>"
   ```

### Rule B: Test Receipts & Code Delivery
1. **Never mutate production trunk directly.**
2. Work in isolated worktrees or branches.
3. Export your changes as a clean git patch or pull request into `exchange/`:
   ```bash
   git diff main > exchange/seat_<YOUR_SEAT_ID>_fix.patch
   ```
4. Post completion to the board or directly to Seat 00 (Host):
   ```bash
   python3 -m pact.cli post --from-seat <YOUR_SEAT_ID> --to 0 --msg "Task complete. Patch delivered to exchange/seat_<ID>_fix.patch. All 14 tests passing."
   ```

### Rule C: Heartbeat Maintenance
Keep your seat lease alive during long tasks by emitting a heartbeat every few minutes:
```bash
python3 -m pact.cli heartbeat --seat <YOUR_SEAT_ID>
```
*(Seats with no heartbeat for > 5 minutes are marked STALE by the Herder).*

---

## 3. Reference CLI Commands

```bash
# View full 32-seat grid, locks, and live message stream
python3 -m pact.cli status

# Send direct message to Seat 00 (Host Ethan)
python3 -m pact.cli post --from-seat <ID> --to 0 --msg "<your message>"

# Vacate your seat upon finishing work
python3 -m pact.cli leave-seat --seat <ID> --reason "Work complete"
```
