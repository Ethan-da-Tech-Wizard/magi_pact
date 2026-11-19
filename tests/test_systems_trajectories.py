"""Comprehensive unit tests for Systems & Firmware Architect Trajectories and Guardrails."""

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from pact.dataset import reconcile_mesh_shards, export_seat_shard
from pact.systems import (
    FirmwareSafetyGate,
    FirmwareSafetyViolation,
    FwupdFixtureParser,
    BashSafetyValidator,
    ArchPkgbuildValidator,
    FedoraDnf5Validator,
    GitWorktreeManager,
    generate_systems_trajectories,
    export_systems_shard,
    SYSTEMS_TRAJECTORIES,
)


class TestSystemsTrajectories(unittest.TestCase):
    """Tests for the systems/firmware trajectories, their safety validators, fixture parsers and shard export."""
    def setUp(self):
        """Make a temp root and copy the JSON fixtures into it."""
        self.test_dir = tempfile.mkdtemp()
        self.root = Path(self.test_dir)
        # Fixtures are copied from ./data/fixtures (relative to the current directory), so run pytest from the repo root.
        # Copy fixtures over to test directory
        src_fixtures = Path("data/fixtures")
        dest_fixtures = self.root / "data" / "fixtures"
        dest_fixtures.mkdir(parents=True, exist_ok=True)
        if src_fixtures.exists():
            for f in src_fixtures.glob("*.json"):
                shutil.copy(f, dest_fixtures / f.name)

    def tearDown(self):
        """Delete the temp root."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_systems_trajectory_generation_and_counts(self):
        """15 baseline trajectories, exactly 3 per domain, all gold-certified DPO pairs with sha256."""
        pairs = generate_systems_trajectories()
        self.assertEqual(len(pairs), 15)

        domains = [p.domain for p in pairs]
        expected_domains = [
            "bash_posix",
            "arch_linux",
            "fedora_linux",
            "bios_uefi",
            "git_internals",
        ]
        for ed in expected_domains:
            count = domains.count(ed)
            self.assertEqual(count, 3, f"Domain {ed} should have exactly 3 verified trajectories, found {count}")

        for p in pairs:
            self.assertTrue(p.id.startswith("TWU_GOLD_"))
            self.assertEqual(p.quality, "gold_certified")
            self.assertEqual(p.kind, "dpo")
            self.assertGreater(len(p.prompt), 20)
            self.assertGreater(len(p.chosen), 30)
            self.assertGreater(len(p.rejected), 10)
            self.assertEqual(len(p.sha256), 64)

    def test_bash_safety_validator_on_trajectories(self):
        """Chosen Bash passes (strict flags, trap); rejected Bash fails."""
        for ex in SYSTEMS_TRAJECTORIES:
            if ex["domain"] == "bash_posix":
                chosen_res = BashSafetyValidator.validate(ex["chosen"])
                self.assertTrue(chosen_res["valid"], f"Chosen script failed validation: {chosen_res['issues']}")
                self.assertTrue(chosen_res["has_strict_flags"])
                self.assertTrue(chosen_res["has_trap"])

                # Each "rejected" example must fail validation too, proving the validators can tell good from bad.
                # Rejected scripts should fail safety checks
                rejected_res = BashSafetyValidator.validate(ex["rejected"])
                self.assertFalse(rejected_res["valid"], "Rejected script should have failed safety validation")

    def test_arch_pkgbuild_validator_on_trajectories(self):
        """Chosen PKGBUILDs pass; rejected PKGBUILDs fail."""
        for ex in SYSTEMS_TRAJECTORIES:
            if ex["domain"] == "arch_linux":
                chosen_res = ArchPkgbuildValidator.validate(ex["chosen"])
                self.assertTrue(chosen_res["valid"], f"Chosen PKGBUILD failed validation: {chosen_res['issues']}")

                # Rejected PKGBUILD should fail validation
                rejected_res = ArchPkgbuildValidator.validate(ex["rejected"])
                self.assertFalse(rejected_res["valid"], "Rejected PKGBUILD should fail validation")

    def test_fedora_dnf5_validator_on_trajectories(self):
        """Rejected Fedora commands fail the dnf5 validator."""
        for ex in SYSTEMS_TRAJECTORIES:
            if ex["domain"] == "fedora_linux":
                rejected_res = FedoraDnf5Validator.validate_command(ex["rejected"])
                self.assertFalse(rejected_res["valid"], "Rejected Fedora command should fail validation")

    def test_firmware_safety_gate_blocks_destructive_hardware_actions(self):
        # Allow-list sample: inspection commands only.
        # Read-only and status inspections must pass
        """The firmware gate allows read-only commands and blocks every destructive one."""
        safe_cmds = [
            "fwupdmgr get-devices --json",
            "fwupdmgr get-updates",
            "fwupdmgr hwids",
            "cat /sys/firmware/efi/esrt/entries/entry0/fw_version",
            "efibootmgr -v",
        ]
        for cmd in safe_cmds:
            self.assertTrue(FirmwareSafetyGate.verify_command_safety(cmd))

        # Deny-list sample: every flash, install, raw write or MSR write must raise FirmwareSafetyViolation.
        # Dangerous flashing and write commands must be strictly rejected
        hazardous_cmds = [
            "flashrom -p internal -w bios.bin",
            "fwupdmgr update -y --force",
            "fwupdmgr install bios.cab --reboot",
            "echo 1 > /sys/firmware/efi/efivars/Boot0001",
            "dd if=fw.bin of=/dev/nvme0n1",
            "wrmsr 0x199 0x0",
        ]
        for cmd in hazardous_cmds:
            with self.assertRaises(FirmwareSafetyViolation, msg=f"Should have blocked: {cmd}"):
                FirmwareSafetyGate.verify_command_safety(cmd)

    def test_fwupd_read_only_device_fixture_parsing(self):
        """fwupd device fixture parses to 4 devices with the expected System Firmware attributes."""
        fixture_path = self.root / "data" / "fixtures" / "fwupd_devices.json"
        self.assertTrue(fixture_path.exists())
        data = FwupdFixtureParser.load_fixture(fixture_path)
        devices = FwupdFixtureParser.parse_devices(data)

        self.assertEqual(len(devices), 4)
        names = [d["name"] for d in devices]
        self.assertIn("System Firmware", names)
        self.assertIn("TPM 2.0", names)
        self.assertIn("Samsung SSD 990 PRO 2TB", names)
        self.assertIn("Embedded Controller", names)

        # Check UEFI System Firmware attributes
        sys_fw = next(d for d in devices if d["name"] == "System Firmware")
        self.assertTrue(sys_fw["is_updatable"])
        self.assertTrue(sys_fw["needs_reboot"])
        self.assertEqual(sys_fw["version"], "0.1.24")
        self.assertEqual(sys_fw["version_lowest"], "0.1.0")

    def test_uefi_esrt_fixture_parsing_and_anti_rollback(self):
        """ESRT fixture parses to 2 entries that are downgrade-safe and SUCCESS."""
        fixture_path = self.root / "data" / "fixtures" / "uefi_esrt.json"
        self.assertTrue(fixture_path.exists())
        data = FwupdFixtureParser.load_fixture(fixture_path)
        entries = FwupdFixtureParser.parse_esrt(data)

        self.assertEqual(len(entries), 2)
        for e in entries:
            self.assertTrue(e["downgrade_safe"])
            self.assertEqual(e["status"], "SUCCESS")

    def test_git_worktree_porcelain_parser(self):
        # Hand-written "git worktree list --porcelain" output: a main worktree and a locked one with a lock reason.
        """The porcelain parser extracts path, branch and lock reason per worktree."""
        mock_porcelain = (
            "worktree /home/user/magi_pact\n"
            "HEAD 938898f5c41d84385102d09c9cb26d26c8a795a0\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /home/user/magi_pact/.worktrees/seat_04\n"
            "HEAD 71fb1c2a4b88e147f892a012d94b3c9f28014e7a\n"
            "branch refs/heads/feature/seat_04_firmware\n"
            "locked Seat 04 actively generating trajectory specs\n"
            "\n"
        )
        worktrees = GitWorktreeManager.parse_worktree_porcelain(mock_porcelain)
        self.assertEqual(len(worktrees), 2)
        self.assertEqual(worktrees[0]["path"], "/home/user/magi_pact")
        self.assertEqual(worktrees[0]["branch"], "refs/heads/main")
        self.assertFalse(worktrees[0].get("locked", False))

        self.assertEqual(worktrees[1]["path"], "/home/user/magi_pact/.worktrees/seat_04")
        self.assertTrue(worktrees[1]["locked"])
        self.assertEqual(worktrees[1]["lock_reason"], "Seat 04 actively generating trajectory specs")

    def test_shard_export_and_multi_seat_reconciliation(self):
        # Seat 03 contributes the 14 base records; seat 04 the 15 systems records (counts asserted below).
        # 1. Export seat 03 baseline shard
        """Two seats' shards reconcile to 29 records across 14 domains, and the manifest hash matches."""
        export_seat_shard(3, self.root)

        # 2. Export seat 04 systems & firmware shard
        shard_path, manifest_path = export_systems_shard(4, self.root)
        self.assertTrue(shard_path.exists())
        self.assertTrue(manifest_path.exists())

        # Verify sha256 checksum in manifest matches actual file content
        content_hash = hashlib.sha256(shard_path.read_bytes()).hexdigest()
        manifest_text = manifest_path.read_text(encoding="utf-8")
        self.assertIn(content_hash, manifest_text)

        # 3. Reconcile mesh shards across seats
        res = reconcile_mesh_shards(self.root)
        self.assertEqual(res["shards_processed"], 2)
        # Seat 03 had 14 records; Seat 04 adds 15 unique verified records = 29 records total
        self.assertEqual(res["total_records"], 29)
        self.assertEqual(res["domains_covered"], 14)

    def test_systems_corpus_dataset_integrity(self):
        # These two tests read the committed corpus using a path relative to the current directory (repo root).
        """The committed systems corpus has 40 rows, 8 per domain, matches its sha256, with no leaks or flash commands."""
        corpus_path = Path("data/corpus/systems/systems_corpus.jsonl")
        self.assertTrue(corpus_path.exists(), "systems_corpus.jsonl must exist")

        manifest_path = Path("data/corpus/systems/systems_corpus.sha256")
        self.assertTrue(manifest_path.exists(), "systems_corpus.sha256 must exist")

        content = corpus_path.read_text(encoding="utf-8")
        computed_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        manifest_text = manifest_path.read_text(encoding="utf-8")
        self.assertIn(computed_sha, manifest_text)

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        self.assertEqual(len(lines), 40, "Should contain exactly 40 golden trajectories")

        from pact.dedup import PolicyLeakScanner
        scanner = PolicyLeakScanner()
        domain_counts = {}

        for line in lines:
            rec = json.loads(line)
            dom = rec["domain"]
            domain_counts[dom] = domain_counts.get(dom, 0) + 1

            # Per-record checks: no policy leaks, and no flash command in BIOS/UEFI prompts or chosen answers.
            # Assert zero policy leaks
            leaks = scanner.scan_record(rec)
            self.assertEqual(len(leaks), 0, f"Policy leak in {rec['id']}: {leaks}")

            # Assert zero destructive firmware flash commands
            if dom == "bios_uefi":
                FirmwareSafetyGate.verify_command_safety(rec["prompt"])
                FirmwareSafetyGate.verify_command_safety(rec["chosen"])

        expected_domains = ["bash_posix", "arch_linux", "fedora_linux", "bios_uefi", "git_internals"]
        for ed in expected_domains:
            self.assertEqual(domain_counts.get(ed, 0), 8, f"Expected 8 trajectories for {ed}")


if __name__ == "__main__":
    unittest.main()
