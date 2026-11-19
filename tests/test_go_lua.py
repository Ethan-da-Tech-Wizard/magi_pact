"""Unit tests for Go and Lua Language Trajectory Engines.

Verifies:
- Go syntax structures, channel primitives, mutex concurrency, binary packets
- Lua metatables, coroutines, weak memoization, URL pattern parsing
- Zero template duplication and zero policy leaks
"""
import unittest
from pact.go_engine import GO_PROBLEMS, generate_go_corpus
from pact.lua_engine import LUA_PROBLEMS, generate_lua_corpus
from pact.fleet_dedup import FleetDedupEngine

class TestGoLuaEngines(unittest.TestCase):

    """Checks the Go and Lua problem generators in pact/ produce well-formed, unique, leak-free records."""
    def test_go_problems_structure(self):
        """Each Go problem has the expected id, code, test and tags, and no policy leaks."""
        self.assertGreaterEqual(len(GO_PROBLEMS), 4)
        for p in GO_PROBLEMS:
            # Every Go problem must carry the GO- id prefix, both answer variants, a Go test function, and 2+ capability tags.
            self.assertTrue(p.id.startswith("GO-"))
            self.assertIn("package ", p.chosen)
            self.assertIn("package ", p.rejected)
            self.assertIn("func Test", p.test_code)
            self.assertGreaterEqual(len(p.capabilities), 2)
            # Confirm no leaks
            self.assertEqual(len(FleetDedupEngine.scan_for_leaks(p.chosen)), 0)
            self.assertEqual(len(FleetDedupEngine.scan_for_leaks(p.prompt)), 0)

    def test_lua_problems_structure(self):
        """Each Lua problem has the expected id, assert-based test and tags, and no policy leaks."""
        self.assertGreaterEqual(len(LUA_PROBLEMS), 4)
        for p in LUA_PROBLEMS:
            # Same shape check for Lua; its self-test is plain assert() calls instead of a Go test function.
            self.assertTrue(p.id.startswith("LUA-"))
            self.assertIn("assert(", p.test_assertions)
            self.assertGreaterEqual(len(p.capabilities), 2)
            # Confirm no leaks
            self.assertEqual(len(FleetDedupEngine.scan_for_leaks(p.chosen)), 0)
            self.assertEqual(len(FleetDedupEngine.scan_for_leaks(p.prompt)), 0)

    def test_go_lua_corpus_dedup_gate(self):
        """The combined Go+Lua corpus passes the dedup/leak gate unchanged (no rows removed, skeleton ratio 1.0)."""
        go_rec = generate_go_corpus()
        lua_rec = generate_lua_corpus()
        all_rec = go_rec + lua_rec
        # Nothing should be dropped: every Go/Lua record is already structurally unique and leak-free.
        deduped, report = FleetDedupEngine.deduplicate_and_reconcile(all_rec)
        self.assertEqual(len(deduped), len(all_rec))
        self.assertEqual(report.policy_leaks_found, 0)
        self.assertEqual(report.skeleton_unique_ratio, 1.0)
        self.assertTrue(report.gate_passed)

if __name__ == "__main__":
    unittest.main()
