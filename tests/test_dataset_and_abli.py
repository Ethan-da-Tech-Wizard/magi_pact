"""Unit tests for Multi-Language Dataset Curation and Abliterated Model Registry."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from pact.dataset import (
    DOMAINS,
    generate_language_matrix,
    export_seat_shard,
    reconcile_mesh_shards,
)
from pact.abli import AbliteratedRegistry, DEFAULT_PROFILES


class TestDatasetAndAbli(unittest.TestCase):
    """Tests for the multi-language golden dataset, shard export/reconciliation, and the abliterated-model registry."""
    def setUp(self):
        """Use a fresh temp directory as the project root for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.root = Path(self.test_dir)

    def tearDown(self):
        """Delete the temp project root."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_multi_language_matrix_coverage(self):
        """The language matrix covers every domain in DOMAINS and every pair has non-trivial text and a 64-char sha256."""
        pairs = generate_language_matrix()
        self.assertGreaterEqual(len(pairs), 14)
        domains_present = {p.domain for p in pairs}
        for d in DOMAINS:
            self.assertIn(d, domains_present, f"Domain {d} missing from matrix")

        for p in pairs:
            self.assertTrue(p.id.startswith("TWU_GOLD_"))
            self.assertTrue(len(p.prompt) > 10)
            self.assertTrue(len(p.chosen) > 10)
            self.assertTrue(len(p.rejected) > 5)
            self.assertTrue(len(p.sha256) == 64)

    def test_shard_export_and_non_overwrite_reconciliation(self):
        # 1. Export shard from Seat 01 and Seat 02
        # Two seats export their shards into exchange/; each shard has its own file name and a .sha256 manifest.
        """Seat shards export with checksum manifests and reconcile into one deduplicated master file."""
        s1 = export_seat_shard(1, self.root)
        s2 = export_seat_shard(2, self.root)

        self.assertTrue(s1.exists())
        self.assertTrue(s2.exists())
        self.assertNotEqual(s1.name, s2.name)

        # Verify sha256 checksum manifests exist
        m1 = self.root / "exchange" / "seat_01_corpus.sha256"
        m2 = self.root / "exchange" / "seat_02_corpus.sha256"
        self.assertTrue(m1.exists())
        self.assertTrue(m2.exists())

        # 2. Reconcile both shards without overwriting
        # Both seats export the same 14 base records, so reconciliation must collapse them by content hash instead of doubling the total.
        res = reconcile_mesh_shards(self.root)
        self.assertEqual(res["shards_processed"], 2)
        # Identical records across shards should be deduplicated via content hash
        self.assertEqual(res["total_records"], 14)
        self.assertEqual(res["domains_covered"], 14)

        master = Path(res["master_path"])
        self.assertTrue(master.exists())
        lines = [json.loads(l) for l in master.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(len(lines), 14)

    def test_abliterated_registry_and_hardware_detection(self):
        """The registry reports hardware, lists 3+ profiles with a valid active id, and can switch the active profile."""
        reg = AbliteratedRegistry(self.root)
        hw = reg.detect_hardware()
        self.assertIn("system", hw)
        self.assertIn("machine", hw)
        self.assertIn("flavor", hw)

        profiles_data = reg.list_profiles()
        self.assertTrue(len(profiles_data["profiles"]) >= 3)
        self.assertIn(profiles_data["active_id"], [p["id"] for p in profiles_data["profiles"]])

        # Switch to a different built-in profile and confirm exactly one profile is flagged active.
        # Switch active profile
        new_id = DEFAULT_PROFILES[1].id
        ok = reg.set_active_profile(new_id)
        self.assertTrue(ok)

        updated = reg.list_profiles()
        self.assertEqual(updated["active_id"], new_id)
        for p in updated["profiles"]:
            if p["id"] == new_id:
                self.assertTrue(p["active"])
            else:
                self.assertFalse(p["active"])

    def test_abliterated_profiles_share_golden_corpus_reference(self):
        """All profiles are abliterated and point at the shared golden multilang corpus."""
        reg = AbliteratedRegistry(self.root)
        profiles = reg.list_profiles()["profiles"]
        for p in profiles:
            self.assertTrue(p["abliterated"])
            self.assertEqual(p["training_corpus_id"], "golden_multilang_corpus.jsonl")


if __name__ == "__main__":
    unittest.main()
