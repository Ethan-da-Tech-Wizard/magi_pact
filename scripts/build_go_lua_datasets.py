# Program: magi_pact - build_go_lua_datasets.py
# Programmer: Ethan-da-Tech-Wizard (written with Claude, an AI assistant)
# Last Modified: 2026-11-18
# Purpose: Builds the Go and Lua training datasets, runs fleet de-duplication over them, and writes checksummed output files.
"""Builds and verifies Go and Lua deep datasets to unblock Host-Beta."""
import hashlib
import json
import sys
from pathlib import Path

# Repo root: this file lives in scripts/, so go up one level.
root = Path(__file__).resolve().parent.parent
# Make the 'pact' package importable when run as a plain script.
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

# --- Project imports (need the sys.path fix above) ---
from pact.go_engine import generate_go_corpus
from pact.lua_engine import generate_lua_corpus
from pact.fleet_dedup import FleetDedupEngine

def main():
    """Generate Go and Lua corpora, gate them on dedup/leak checks, and write the corpus files plus a checksummed exchange shard."""
    root = Path(__file__).resolve().parent.parent
    corpus_dir = root / "data" / "corpus" / "go_lua"
    # Create output folders if missing so reruns are safe.
    corpus_dir.mkdir(parents=True, exist_ok=True)
    exchange_dir = root / "exchange"
    exchange_dir.mkdir(parents=True, exist_ok=True)

    # Generate both language corpora, then pool them for one joint audit.
    go_records = generate_go_corpus()
    lua_records = generate_lua_corpus()
    all_records = go_records + lua_records

    # 1. Audit for uniqueness & policy leaks
    # De-duplicate by prompt skeleton and scan for policy leaks.
    deduped, report = FleetDedupEngine.deduplicate_and_reconcile(all_records)
    print(f"Go & Lua Dedup Report:")
    print(f" - Total rows: {report.total_rows}")
    print(f" - Raw unique prompts: {report.raw_unique_prompts} (ratio: {report.raw_unique_ratio:.2f})")
    print(f" - Skeleton unique prompts: {report.skeleton_unique_prompts} (ratio: {report.skeleton_unique_ratio:.2f})")
    print(f" - Policy leaks: {report.policy_leaks_found}")
    print(f" - Gate passed: {report.gate_passed}")

    # Hard stop: never write files if the quality gate failed.
    assert report.gate_passed, f"Gate failed: leaks={report.policy_leaks_found}, skel_ratio={report.skeleton_unique_ratio}"

    # 2. Write individual corpus files
    go_path = corpus_dir / "go_corpus.jsonl"
    # sort_keys gives stable output, so the checksum is reproducible.
    go_lines = [json.dumps(r, sort_keys=True) for r in go_records]
    go_path.write_text("\n".join(go_lines) + "\n", encoding="utf-8")

    lua_path = corpus_dir / "lua_corpus.jsonl"
    lua_lines = [json.dumps(r, sort_keys=True) for r in lua_records]
    lua_path.write_text("\n".join(lua_lines) + "\n", encoding="utf-8")

    # 3. Write unified exchange shard
    shard_path = exchange_dir / "seat_03_go_lua.jsonl"
    shard_lines = [json.dumps(r, sort_keys=True) for r in deduped]
    content = "\n".join(shard_lines) + "\n"
    shard_path.write_text(content, encoding="utf-8")

    # Checksum lets other seats verify the shard was not altered in transit.
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    sha_path = exchange_dir / "seat_03_go_lua.sha256"
    sha_path.write_text(f"{sha}  seat_03_go_lua.jsonl\n")

    print(f"Exported seat_03_go_lua.jsonl ({len(deduped)} rows)")
    print(f"SHA256: {sha}")

if __name__ == "__main__":
    main()
