"""Builds and verifies Go and Lua deep datasets to unblock Host-Beta."""
import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
# Make the repo root importable so "pact.*" resolves when this script is run directly (python scripts/...).
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from pact.go_engine import generate_go_corpus
from pact.lua_engine import generate_lua_corpus
from pact.fleet_dedup import FleetDedupEngine

def main():
    """Generate Go/Lua corpora, gate them through the dedup engine, and export the shard plus its SHA-256."""
    root = Path(__file__).resolve().parent.parent
    corpus_dir = root / "data" / "corpus" / "go_lua"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    exchange_dir = root / "exchange"
    exchange_dir.mkdir(parents=True, exist_ok=True)

    # Generate the Go and Lua records in memory using the generators in pact/.
    go_records = generate_go_corpus()
    lua_records = generate_lua_corpus()
    all_records = go_records + lua_records

    # The gate checks raw and skeleton prompt uniqueness ratios and counts policy leaks (see the report fields printed below).
    # 1. Audit for uniqueness & policy leaks
    deduped, report = FleetDedupEngine.deduplicate_and_reconcile(all_records)
    print(f"Go & Lua Dedup Report:")
    print(f" - Total rows: {report.total_rows}")
    print(f" - Raw unique prompts: {report.raw_unique_prompts} (ratio: {report.raw_unique_ratio:.2f})")
    print(f" - Skeleton unique prompts: {report.skeleton_unique_prompts} (ratio: {report.skeleton_unique_ratio:.2f})")
    print(f" - Policy leaks: {report.policy_leaks_found}")
    print(f" - Gate passed: {report.gate_passed}")

    # Hard stop: never publish a shard that failed the uniqueness/leak gate.
    assert report.gate_passed, f"Gate failed: leaks={report.policy_leaks_found}, skel_ratio={report.skeleton_unique_ratio}"

    # Per-language files hold the raw, un-deduplicated records; only the exchange shard below is deduplicated.
    # 2. Write individual corpus files
    go_path = corpus_dir / "go_corpus.jsonl"
    go_lines = [json.dumps(r, sort_keys=True) for r in go_records]
    go_path.write_text("\n".join(go_lines) + "\n", encoding="utf-8")

    lua_path = corpus_dir / "lua_corpus.jsonl"
    lua_lines = [json.dumps(r, sort_keys=True) for r in lua_records]
    lua_path.write_text("\n".join(lua_lines) + "\n", encoding="utf-8")

    # 3. Write unified exchange shard
    # The shard goes in exchange/ (seat 03's output); sort_keys keeps the bytes, and so the hash, stable.
    shard_path = exchange_dir / "seat_03_go_lua.jsonl"
    shard_lines = [json.dumps(r, sort_keys=True) for r in deduped]
    content = "\n".join(shard_lines) + "\n"
    shard_path.write_text(content, encoding="utf-8")

    # Checksum is of the exact bytes written, in "sha256sum" format so it can be verified with standard tools.
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    sha_path = exchange_dir / "seat_03_go_lua.sha256"
    sha_path.write_text(f"{sha}  seat_03_go_lua.jsonl\n")

    print(f"Exported seat_03_go_lua.jsonl ({len(deduped)} rows)")
    print(f"SHA256: {sha}")

if __name__ == "__main__":
    main()
