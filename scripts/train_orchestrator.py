#!/usr/bin/env python3
# Program: magi_pact - train_orchestrator.py
# Programmer: Ethan-da-Tech-Wizard (written with Claude, an AI assistant)
# Last Modified: 2026-11-18
# Purpose: Orchestrates local LoRA SFT/DPO training and GGUF quantization under VRAM, concurrency and thermal limits.
"""Magi Pact: LoRA SFT/DPO Training & GGUF Quantization Orchestrator.

Enforces:
1. Zero cloud spend ($0.00) on local RTX 3070 8GB VRAM.
2. Strict VRAM allocation <= 7.2 GB ceiling (819.2 MB safety headroom).
3. Max 2 concurrency compute slots.
4. Thermal protection: 85°C warn, 90°C pause, 96°C hard emergency halt.
5. SFT & DPO recipes with 7 linear projection targets (q, k, v, o, gate, up, down).
6. GGUF Q4_K_M & Q8_0 adapter conversion pipeline for vanilla and /abli models.
"""

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

# Ensure pact is in sys.path
# Repo root is one level above scripts/.
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pact.training import (
    SFTRecipe,
    DPORecipe,
    VRAMBudgetGuard,
    ThermalAndConcurrencyGuard,
    GGUFPipelineConfig,
    TrainingOrchestrator,
    LORA_TARGET_MODULES,
    MAX_VRAM_ALLOCATION_MB,
    GPU_TOTAL_VRAM_MB,
    MAX_CONCURRENT_SLOTS,
    THERMAL_EMERGENCY_TEMP,
    THERMAL_PAUSE_TEMP,
)
from pact.abli import AbliteratedRegistry


def cmd_budget(args):
    """Calculates and reports exact VRAM memory breakdown."""
    # Fall back to the default LoRA rank when none is given.
    rank = args.rank or 16
    res = VRAMBudgetGuard.calculate_memory_footprint(
        model_params_billion=args.params_b,
        rank=rank,
        seq_len=args.seq_len,
        micro_batch=args.micro_batch,
        gradient_checkpointing=not args.no_grad_ckpt,
        optimizer=args.optimizer,
        load_in_4bit=not args.no_4bit,
    )

    print("\n" + "=" * 70)
    print(" ⚡ RTX 3070 (8GB) VRAM ALLOCATION & SAFETY BUDGET")
    print("=" * 70)
    print(f"Hardware Target       : NVIDIA GeForce RTX 3070 (Laptop/Desktop)")
    print(f"Total Physical VRAM   : {GPU_TOTAL_VRAM_MB:.1f} MB (8.00 GB)")
    print(f"Strict Safety Ceiling : {MAX_VRAM_ALLOCATION_MB:.1f} MB (7.20 GB)")
    print(f"Guaranteed Headroom   : {GPU_TOTAL_VRAM_MB - MAX_VRAM_ALLOCATION_MB:.1f} MB (Reserved for OS/CUDA context)")
    print("-" * 70)
    print(f"Parameters Tested     : {args.params_b} Billion | Rank r={rank} | Micro-Batch={args.micro_batch}")
    print(f"Gradient Checkpoint   : {'ENABLED (Activation Checkpointing)' if not args.no_grad_ckpt else 'DISABLED'}")
    print(f"Quantization          : {'4-bit NF4 Double Quant' if not args.no_4bit else '16-bit Full Weights'}")
    print(f"Optimizer             : {args.optimizer}")
    print("-" * 70)
    print("Component Footprint Breakdown:")
    for comp, mb in res["breakdown_mb"].items():
        print(f"  • {comp.ljust(24)}: {mb:>8.2f} MB ({mb/1024.0:.3f} GB)")
    print("-" * 70)
    print(f"Total Estimated VRAM  : {res['total_vram_mb']:>8.2f} MB ({res['total_vram_gb']:.3f} GB)")
    print(f"Remaining Margin      : {res['headroom_mb']:>8.2f} MB ({res['headroom_mb']/1024.0:.3f} GB)")

    if res["fits_within_budget"]:
        print(f"\n✅ PASS: Configuration fits strictly within <= 7.2 GB VRAM budget.")
    else:
        print(f"\n❌ FAIL: Configuration exceeds 7.2 GB ceiling by {res['total_vram_mb'] - MAX_VRAM_ALLOCATION_MB:.2f} MB!")
        sys.exit(1)


def cmd_thermal(args):
    """Queries real-time GPU thermal state and checks concurrency slots."""
    guard = ThermalAndConcurrencyGuard(ROOT_DIR, mock_temp=args.mock_temp)
    state, temp, msg = guard.evaluate_thermal_status()
    slots = guard.list_active_slots()

    print("\n" + "=" * 70)
    print(" 🌡️  RTX 3070 THERMAL & CONCURRENCY GUARD STATUS")
    print("=" * 70)
    print(f"Current GPU Temperature : {temp:.1f}°C")
    print(f"Thermal State           : {state.value}")
    print(f"Evaluation              : {msg}")
    print(f"Safety Thresholds       : 85°C (Warn) | {THERMAL_PAUSE_TEMP}°C (Pause) | {THERMAL_EMERGENCY_TEMP}°C (Hard Halt)")
    print("-" * 70)
    print(f"Concurrency Allocation  : {len(slots)}/{MAX_CONCURRENT_SLOTS} slots occupied")
    if slots:
        print(f"Active Job IDs          : {', '.join(slots)}")
    else:
        print("Active Job IDs          : None (All slots free)")
    print("=" * 70 + "\n")


def cmd_recipes(args):
    """Exports and prints the complete SFT and DPO training configurations."""
    recipes_dir = ROOT_DIR / "data" / "training_recipes"
    recipes_dir.mkdir(parents=True, exist_ok=True)

    # Choose between the vanilla base model and the abliterated variant.
    is_abli = args.abli
    base_model = args.base_model
    if is_abli and not base_model:
        reg = AbliteratedRegistry(ROOT_DIR)
        profiles = reg.list_profiles()
        active_id = profiles.get("active_id")
        base_model = f"abliterated://{active_id}"

    sft = SFTRecipe(
        base_model=base_model or "Qwen/Qwen2.5-Coder-7B-Instruct",
        is_abliterated=is_abli,
        rank=args.rank or 16,
        alpha=args.alpha or 32,
    )
    # validate() checks the recipe against the training rules.
    sft.validate()

    dpo = DPORecipe(
        base_model=base_model or "Qwen/Qwen2.5-Coder-7B-Instruct",
        is_abliterated=is_abli,
        rank=args.rank or 16,
        alpha=args.alpha or 32,
    )
    dpo.validate()

    sft_file = recipes_dir / f"sft_{'abli' if is_abli else 'vanilla'}.json"
    dpo_file = recipes_dir / f"dpo_{'abli' if is_abli else 'vanilla'}.json"

    sft_file.write_text(json.dumps(asdict(sft), indent=2), encoding="utf-8")
    dpo_file.write_text(json.dumps(asdict(dpo), indent=2), encoding="utf-8")

    print("\n" + "=" * 70)
    print(" 📋 FORMULATED SFT & DPO TRAINING RECIPES")
    print("=" * 70)
    print(f"Target Base Model   : {sft.base_model} ({'Abliterated /abli' if is_abli else 'Vanilla'})")
    print(f"Target Modules (7)  : {', '.join(LORA_TARGET_MODULES)}")
    print(f"Rank (r) / Alpha    : r={sft.rank} | alpha={sft.alpha} (Scaling: {sft.alpha / sft.rank}x)")
    print(f"Micro-Batch / Accum : Micro-Batch={sft.micro_batch_size} | Accum={sft.gradient_accumulation_steps} (Effective: 16)")
    print(f"SFT Learning Rate   : {sft.learning_rate:.1e} (Cosine decay, warmup=0.03)")
    print(f"DPO Learning Rate   : {dpo.learning_rate:.1e} (Beta={dpo.beta}, Cosine decay)")
    print(f"Optimizer           : {sft.optimizer} (Paged 8-bit, zero CPU spill latency)")
    print(f"Quantization Base   : 4-bit NF4 double-quant (bitsandbytes)")
    print("-" * 70)
    print(f"Saved SFT Config    : {sft_file}")
    print(f"Saved DPO Config    : {dpo_file}")
    print("=" * 70 + "\n")


def cmd_gguf(args):
    """Generates the GGUF Q4_K_M and Q8_0 export and quantization pipeline."""
    out_dir = ROOT_DIR / "exchange" / "gguf"
    out_dir.mkdir(parents=True, exist_ok=True)

    pipeline = GGUFPipelineConfig(
        base_model_path=args.base_model or "Qwen/Qwen2.5-Coder-7B-Instruct",
        adapter_path=args.adapter_dir or "exchange/adapters/dpo",
        output_dir=str(out_dir),
        is_abliterated=args.abli,
        quant_types=["Q4_K_M", "Q8_0"],
    )
    manifest = pipeline.generate_conversion_manifest()

    manifest_file = out_dir / f"gguf_pipeline_{'abli' if args.abli else 'vanilla'}.json"
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Generate offline executable shell script
    script_file = out_dir / f"convert_{'abli' if args.abli else 'vanilla'}.sh"
    script_content = "#!/usr/bin/env bash\n# Offline GGUF Conversion ($0.00 cloud spend)\nset -euo pipefail\n\n"
    for cmd in manifest["commands"]:
        script_content += f"echo \"==> Running: {cmd}\"\n{cmd}\n\n"
    script_file.write_text(script_content, encoding="utf-8")
    script_file.chmod(0o755)

    print("\n" + "=" * 70)
    print(" 📦 GGUF CONVERSION & QUANTIZATION PIPELINE")
    print("=" * 70)
    print(f"Target Base Model   : {pipeline.base_model_path} ({'Abliterated' if pipeline.is_abliterated else 'Vanilla'})")
    print(f"Input Adapter Path  : {pipeline.adapter_path}")
    print(f"Target Quant Types  : {', '.join(pipeline.quant_types)}")
    print(f"Export Outputs      :")
    print(f"  • Standalone LoRA : {manifest['adapter_gguf']}")
    print(f"  • Merged FP16     : {manifest['merged_fp16_gguf']}")
    for q, p in manifest["quantized_outputs"].items():
        print(f"  • {q.ljust(17)}: {p}")
    print("-" * 70)
    print(f"Pipeline JSON       : {manifest_file}")
    print(f"Offline Run Script  : {script_file}")
    print("=" * 70 + "\n")


def cmd_run(args):
    """Executes the orchestrator training state machine cycle."""
    orchestrator = TrainingOrchestrator(ROOT_DIR, mock_temp=args.mock_temp)

    sft = SFTRecipe(
        base_model=args.base_model or "Qwen/Qwen2.5-Coder-7B-Instruct",
        is_abliterated=args.abli,
        rank=args.rank or 16,
        alpha=args.alpha or 32,
    )
    dpo = None
    if not args.sft_only:
        dpo = DPORecipe(
            base_model=args.base_model or "Qwen/Qwen2.5-Coder-7B-Instruct",
            is_abliterated=args.abli,
            rank=args.rank or 16,
            alpha=args.alpha or 32,
        )

    receipt = orchestrator.execute_training_cycle(
        sft_recipe=sft,
        dpo_recipe=dpo,
        export_gguf=not args.no_gguf,
        # Simulation mode, as passed by the code: no real training is launched here.
        simulate=True,
    )

    exchange_dir = ROOT_DIR / "exchange"
    exchange_dir.mkdir(parents=True, exist_ok=True)
    receipt_file = exchange_dir / f"training_receipt_{orchestrator.job_id}.json"
    receipt_file.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

    print("\n" + "=" * 70)
    print(f" 🚀 ORCHESTRATOR RUN COMPLETE: {orchestrator.job_id}")
    print("=" * 70)
    print(f"Final State   : {orchestrator.state.value}")
    print(f"Stages Run    : {list(receipt['stages'].keys())}")
    print(f"Receipt File  : {receipt_file}")
    print("=" * 70 + "\n")


def main():
    """Command-line entry point: parse arguments and run the training and quantization orchestration."""
    parser = argparse.ArgumentParser(description="LoRA Training, Thermal Guard & GGUF Pipeline Orchestrator")
    sub = parser.add_subparsers(dest="command")

    # budget
    p_b = sub.add_parser("budget", help="Calculate exact VRAM allocation against 7.2 GB ceiling")
    p_b.add_argument("--params-b", type=float, default=7.6, help="Model parameters in billions (default: 7.6B)")
    p_b.add_argument("--rank", type=int, default=16, help="LoRA rank r (16..32)")
    p_b.add_argument("--seq-len", type=int, default=2048, help="Sequence length (default: 2048)")
    p_b.add_argument("--micro-batch", type=int, default=1, help="Micro-batch size (default: 1)")
    p_b.add_argument("--no-grad-ckpt", action="store_true", help="Disable gradient checkpointing")
    p_b.add_argument("--no-4bit", action="store_true", help="Disable 4-bit NF4 base quantization")
    p_b.add_argument("--optimizer", default="paged_adamw_8bit", help="Optimizer choice")

    # thermal
    p_t = sub.add_parser("thermal", help="Query real-time GPU thermal state & concurrency slots")
    p_t.add_argument("--mock-temp", type=float, default=None, help="Mock temperature in °C for testing")

    # recipes
    p_r = sub.add_parser("recipes", help="Formulate and export reproducible SFT/DPO recipe JSON configs")
    p_r.add_argument("--abli", action="store_true", help="Target /abli abliterated base model")
    p_r.add_argument("--base-model", default=None, help="Base model identifier")
    p_r.add_argument("--rank", type=int, default=16, help="LoRA rank r (16..32)")
    p_r.add_argument("--alpha", type=int, default=32, help="LoRA alpha (32..64)")

    # gguf
    p_g = sub.add_parser("gguf", help="Generate GGUF Q4_K_M and Q8_0 conversion pipeline")
    p_g.add_argument("--base-model", default=None, help="Base model identifier")
    p_g.add_argument("--adapter-dir", default=None, help="Directory containing LoRA adapter")
    p_g.add_argument("--abli", action="store_true", help="Use abliterated base weights")

    # run
    p_run = sub.add_parser("run", help="Execute end-to-end training cycle with state machine")
    p_run.add_argument("--abli", action="store_true", help="Target abliterated base model")
    p_run.add_argument("--base-model", default=None, help="Base model identifier")
    p_run.add_argument("--rank", type=int, default=16, help="LoRA rank r (16..32)")
    p_run.add_argument("--alpha", type=int, default=32, help="LoRA alpha (32..64)")
    p_run.add_argument("--sft-only", action="store_true", help="Run only SFT stage")
    p_run.add_argument("--no-gguf", action="store_true", help="Skip GGUF conversion stage")
    p_run.add_argument("--mock-temp", type=float, default=None, help="Simulate temperature in °C")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Map each subcommand name to its handler function.
    dispatch = {
        "budget": cmd_budget,
        "thermal": cmd_thermal,
        "recipes": cmd_recipes,
        "gguf": cmd_gguf,
        "run": cmd_run,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
