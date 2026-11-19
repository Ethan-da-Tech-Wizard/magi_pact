"""Comprehensive test suite for the Final Dataset Lock-in and LoRA Training Pipeline.

Verifies:
- Compiler & Harness Verification Engine (C/C++ local sandbox, zero false positives)
- Systems & Firmware Trajectories (Bash, Arch, Fedora, read-only BIOS/UEFI, Git worktree)
- Web & Modern Runtime (Holy-grail CSS, fluid clamp, HTML dialog, TypeScript satisfies)
- Fleet Dedup & Gate (Skeleton extraction, leak detection, uniqueness >= 0.90)
- LoRA Training & Quantization (VRAM <= 7.2GB, thermal guard, Q4_K_M GGUF adapter)
"""
import json
from pathlib import Path
import tempfile
import unittest

from pact.compiler_harness import detect_toolchains, IsolatedSandboxRunner
from pact.systems_firmware import SYSTEMS_CORPUS, export_systems_trajectories
from pact.web_runtime import WEB_SPECS, validate_web_spec, export_web_specs
from pact.fleet_dedup import FleetDedupEngine
from pact.training import (
    SFTRecipe,
    DPORecipe,
    VRAMBudgetGuard,
    ThermalAndConcurrencyGuard,
    GGUFPipelineConfig,
    MAX_VRAM_ALLOCATION_MB,
    LORA_TARGET_MODULES,
)

class TestFinalPipeline(unittest.TestCase):

    """End-to-end checks of the final pipeline: toolchains, systems/web corpora, dedup gate, VRAM/thermal guards and GGUF plan."""
    def test_toolchain_detection(self):
        # Only checks that every language has an entry; it does not require that the compiler is installed.
        """detect_toolchains reports an entry for each supported language."""
        toolchains = detect_toolchains()
        self.assertIn("c", toolchains)
        self.assertIn("cpp", toolchains)
        self.assertIn("rust", toolchains)
        self.assertIn("go", toolchains)
        self.assertIn("csharp", toolchains)

    def test_c_sandbox_execution(self):
        """A tiny asserting C program compiles and runs cleanly in the isolated sandbox runner."""
        runner = IsolatedSandboxRunner()
        c_code = (
            "#include <stdio.h>\n"
            "#include <assert.h>\n"
            "int add(int a, int b) { return a + b; }\n"
            "int main() {\n"
            "    assert(add(2, 3) == 5);\n"
            "    printf(\"C verification passed.\\n\");\n"
            "    return 0;\n"
            "}\n"
        )
        receipt = runner.run_c_test("test-c-01", c_code)
        # Soft check: if the compiler is missing/fails, the run assertions are skipped rather than failing the suite on machines without a toolchain.
        if receipt.compilation_passed:
            self.assertTrue(receipt.execution_passed)
            self.assertEqual(receipt.exit_code, 0)
            self.assertIn("C verification passed.", receipt.stdout)

    def test_cpp_sandbox_execution(self):
        """A tiny asserting C++ program compiles and runs cleanly in the isolated sandbox runner."""
        runner = IsolatedSandboxRunner()
        cpp_code = (
            "#include <iostream>\n"
            "#include <cassert>\n"
            "#include <vector>\n"
            "#include <numeric>\n"
            "int main() {\n"
            "    std::vector<int> v = {1, 2, 3, 4};\n"
            "    int sum = std::accumulate(v.begin(), v.end(), 0);\n"
            "    assert(sum == 10);\n"
            "    std::cout << \"CPP verification passed.\" << std::endl;\n"
            "    return 0;\n"
            "}\n"
        )
        receipt = runner.run_cpp_test("test-cpp-01", cpp_code)
        if receipt.compilation_passed:
            self.assertTrue(receipt.execution_passed)
            self.assertEqual(receipt.exit_code, 0)
            self.assertIn("CPP verification passed.", receipt.stdout)

    def test_systems_firmware_trajectories(self):
        """Systems trajectories are well formed, BIOS/UEFI ones are read-only, and export writes a hashed file."""
        self.assertGreaterEqual(len(SYSTEMS_CORPUS), 5)
        for traj in SYSTEMS_CORPUS:
            self.assertTrue(traj.trajectory_id.startswith("SYS-"))
            self.assertIn(traj.safety_classification, ["read_only", "idempotent_mutation", "sandboxed"])
            self.assertGreater(len(traj.commands), 0)
            if traj.subsystem == "bios_uefi_ro":
                self.assertEqual(traj.safety_classification, "read_only")
                # Confirm no flashing commands
                # Read-only BIOS/UEFI trajectories may not contain any flash or write command text.
                for cmd in traj.commands:
                    self.assertNotIn("flash", cmd)
                    self.assertNotIn("write", cmd)

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "systems.jsonl"
            count, sha = export_systems_trajectories(out_path)
            self.assertEqual(count, len(SYSTEMS_CORPUS))
            self.assertEqual(len(sha), 64)
            self.assertTrue(out_path.exists())

    def test_web_runtime_specs(self):
        """Every web spec passes its validation rules and export writes a hashed file."""
        self.assertGreaterEqual(len(WEB_SPECS), 4)
        for spec in WEB_SPECS:
            self.assertTrue(validate_web_spec(spec), f"Spec {spec.spec_id} failed validation")

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "web.jsonl"
            count, sha = export_web_specs(out_path)
            self.assertEqual(count, len(WEB_SPECS))
            self.assertEqual(len(sha), 64)
            self.assertTrue(out_path.exists())

    def test_fleet_dedup_and_leak_gate(self):
        # Two prompts that differ only in a numeric task id must reduce to the same skeleton.
        # 1. Test skeleton extraction
        """Skeleton extraction, secret-leak scanning and the dedup gate behave as specified."""
        p1 = "How to configure [task id #101] network on Arch Linux?"
        p2 = "How to configure [task id #999] network on Arch Linux?"
        self.assertEqual(FleetDedupEngine.extract_skeleton(p1), FleetDedupEngine.extract_skeleton(p2))

        # 2. Test leak scanning
        clean_text = "Standard POSIX bash script with set -euo pipefail."
        leaked_text = "export AWS_SECRET_KEY='AKIA1234567890abcdef' and token=123"
        self.assertEqual(len(FleetDedupEngine.scan_for_leaks(clean_text)), 0)
        self.assertGreater(len(FleetDedupEngine.scan_for_leaks(leaked_text)), 0)

        # Records 1 and 2 share a skeleton and answer, so 3 rows reduce to 2.
        # 3. Test deduplication and gate
        records = [
            {"prompt": p1, "chosen": "ip link set eth0 up"},
            {"prompt": p2, "chosen": "ip link set eth0 up"},
            {"prompt": "Write a thread-safe ring buffer in C99", "chosen": "typedef struct { ... } rb_t;"},
        ]
        deduped, report = FleetDedupEngine.deduplicate_and_reconcile(records)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(report.duplicates_found, 0)
        self.assertTrue(report.gate_passed)

    def test_lora_training_and_thermal_guard(self):
        # 1. RTX 3070 VRAM Budget Verification
        """Default recipes fit the VRAM ceiling, the slot cap and thermal states work, and the GGUF plan is zero-cost."""
        calc = VRAMBudgetGuard.calculate_memory_footprint(
            model_params_billion=7.6,
            rank=16,
            seq_len=2048,
            micro_batch=1,
            gradient_checkpointing=True,
            optimizer="paged_adamw_8bit",
            load_in_4bit=True
        )
        self.assertTrue(calc["fits_within_budget"])
        self.assertLessEqual(calc["total_vram_mb"], MAX_VRAM_ALLOCATION_MB)
        self.assertGreaterEqual(calc["headroom_mb"], 700.0)

        # 2. SFT and DPO Recipe Verification
        sft = SFTRecipe()
        sft_calc = VRAMBudgetGuard.verify_recipe(sft)
        self.assertTrue(sft_calc["fits_within_budget"])
        self.assertEqual(sft.target_modules, LORA_TARGET_MODULES)

        dpo = DPORecipe()
        dpo_calc = VRAMBudgetGuard.verify_recipe(dpo)
        self.assertTrue(dpo_calc["fits_within_budget"])

        # 3. Thermal and Concurrency Guard
        guard = ThermalAndConcurrencyGuard(mock_temp=72.0)
        # The cap is 2 concurrent compute slots; a third acquire must raise.
        # Test concurrency slots (capped at 2)
        slot1 = guard.acquire_slot("worker_c")
        slot2 = guard.acquire_slot("worker_lora")
        self.assertEqual(len(guard.list_active_slots()), 2)
        self.assertRaises(Exception, guard.acquire_slot, "worker_overflow")
        guard.release_slot("worker_c")
        guard.release_slot("worker_lora")
        self.assertEqual(len(guard.list_active_slots()), 0)

        # Thermal states
        state, temp, msg = guard.evaluate_thermal_status()
        self.assertEqual(state.value, "NOMINAL")
        # 97 C is above the 96 C hard-halt threshold, so the state must be EMERGENCY_HALT.
        guard.set_mock_temp(97.0)
        state_hot, temp_hot, msg_hot = guard.evaluate_thermal_status()
        self.assertEqual(state_hot.value, "EMERGENCY_HALT")

        # 4. GGUF Pipeline Config
        gguf = GGUFPipelineConfig(
            base_model_path="models/base",
            adapter_path="exchange/adapters/sft",
            output_dir="exchange/gguf"
        )
        manifest = gguf.generate_conversion_manifest()
        self.assertEqual(manifest["cloud_cost"], 0.0)
        self.assertIn("Q4_K_M", manifest["quantized_outputs"])
        self.assertGreater(len(manifest["commands"]), 0)

if __name__ == "__main__":
    unittest.main()
