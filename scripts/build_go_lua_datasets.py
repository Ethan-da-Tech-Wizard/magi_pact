"""Builds and verifies Go and Lua deep datasets to unblock Host-Beta."""
import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from pact.go_engine import generate_go_corpus
from pact.lua_engine import generate_lua_corpus
from pact.fleet_dedup import FleetDedupEngine

def main():
    root = Path(__file__).resolve().parent.parent
    corpus_dir = root / "data" / "corpus" / "go_lua"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    exchange_dir = root / "exchange"
    exchange_dir.mkdir(parents=True, exist_ok=True)

    go_records = generate_go_corpus()
    lua_records = generate_lua_corpus()
    all_records = go_records + lua_records

    # 1. Audit for uniqueness & policy leaks
    deduped, report = FleetDedupEngine.deduplicate_and_reconcile(all_records)
    print(f"Go & Lua Dedup Report:")
    print(f" - Total rows: {report.total_rows}")
    print(f" - Raw unique prompts: {report.raw_unique_prompts} (ratio: {report.raw_unique_ratio:.2f})")
    print(f" - Skeleton unique prompts: {report.skeleton_unique_prompts} (ratio: {report.skeleton_unique_ratio:.2f})")
    print(f" - Policy leaks: {report.policy_leaks_found}")
    print(f" - Gate passed: {report.gate_passed}")

    assert report.gate_passed, f"Gate failed: leaks={report.policy_leaks_found}, skel_ratio={report.skeleton_unique_ratio}"

    # 2. Write individual corpus files
    go_path = corpus_dir / "go_corpus.jsonl"
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

    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    sha_path = exchange_dir / "seat_03_go_lua.sha256"
    sha_path.write_text(f"{sha}  seat_03_go_lua.jsonl\n")

    print(f"Exported seat_03_go_lua.jsonl ({len(deduped)} rows)")
    print(f"SHA256: {sha}")

if __name__ == "__main__":
    main()
