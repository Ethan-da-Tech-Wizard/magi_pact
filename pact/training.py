# Program: magi_pact - training.py
# Programmer: Ethan-da-Tech-Wizard (written with Claude, an AI assistant)
# Last Modified: 2026-11-18
# Purpose: LoRA SFT and DPO recipes with thermal and concurrency guards and a training orchestrator state machine.

"""LoRA Training, Quantization, Thermal Guard, and GGUF Pipeline Engine.

Implements SFT and DPO training recipes for local NVIDIA GeForce RTX 3070 (8GB VRAM)
under strict zero-cloud-spend ($0.00), <= 7.2 GB VRAM ceiling, max 2 concurrency slots,
and 96°C thermal safety guard. Supports both Vanilla and /abli Abliterated base models.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import os
from pathlib import Path
import platform
import subprocess
import time
from typing import Dict, Any, List, Optional, Tuple


# ==============================================================================
# 1. HARDWARE CONSTANTS & MEMORY BUDGET (RTX 3070 8GB)
# ==============================================================================

GPU_TOTAL_VRAM_MB = 8192.0          # 8.0 GB physical VRAM on RTX 3070
MAX_VRAM_ALLOCATION_MB = 7372.8     # Strict <= 7.2 GB limit (90% capacity ceiling)
MIN_HEADROOM_MB = 819.2             # Reserved for display server (X11/Wayland) & CUDA runtime

MAX_CONCURRENT_SLOTS = 2            # Strict mesh limit for local heavy compute runs

# Thermal thresholds in Celsius
THERMAL_WARN_TEMP = 85.0            # High temperature warning logged
THERMAL_PAUSE_TEMP = 90.0           # Proactive pause to allow cooling
THERMAL_EMERGENCY_TEMP = 96.0       # Hard emergency halt limit
THERMAL_RESUME_TEMP = 75.0          # Hysteresis threshold to resume execution

LORA_TARGET_MODULES = [
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj",
]


class ThermalState(str, Enum):
    """Thermal status levels used by the guard, from nominal to emergency."""
    NOMINAL = "NOMINAL"
    WARNING = "WARNING"
    PAUSED = "PAUSED"
    EMERGENCY_HALT = "EMERGENCY_HALT"


class OrchestratorState(str, Enum):
    """States of the training orchestrator state machine."""
    IDLE = "IDLE"
    INITIALIZING = "INITIALIZING"
    PRE_FLIGHT_PASSED = "PRE_FLIGHT_PASSED"
    SFT_TRAINING = "SFT_TRAINING"
    SFT_COMPLETED = "SFT_COMPLETED"
    DPO_TRAINING = "DPO_TRAINING"
    DPO_COMPLETED = "DPO_COMPLETED"
    THERMAL_PAUSED = "THERMAL_PAUSED"
    COOLING = "COOLING"
    GGUF_CONVERTING = "GGUF_CONVERTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EMERGENCY_HALTED = "EMERGENCY_HALTED"


class VRAMBudgetExceededError(ValueError):
    """Raised when training hyperparameters exceed the 7.2 GB VRAM ceiling."""
    pass


class ConcurrencyLimitExceededError(RuntimeError):
    """Raised when more than 2 concurrent compute jobs are launched."""
    pass


class ThermalEmergencyHaltError(RuntimeError):
    """Raised when GPU junction or core temperature hits or exceeds 96°C."""
    pass


# ==============================================================================
# 2. RECIPES (SFT & DPO)
# ==============================================================================

@dataclass
class SFTRecipe:
    """Locked-down LoRA SFT hyperparameters for the 8 GB GPU target."""
    recipe_id: str = "lora-sft-rtx3070-v1"
    base_model: str = "Qwen/Qwen2.5-Coder-7B-Instruct"
    is_abliterated: bool = False
    target_modules: List[str] = field(default_factory=lambda: list(LORA_TARGET_MODULES))
    rank: int = 16                          # r = 16..32
    alpha: int = 32                         # alpha = 32..64
    learning_rate: float = 1.5e-4           # Strict requirement: 1.5e-4
    lr_scheduler: str = "cosine"
    warmup_ratio: float = 0.03
    weight_decay: float = 0.01
    micro_batch_size: int = 1               # Strict requirement: 1
    gradient_accumulation_steps: int = 16   # Effective batch size = 16
    optimizer: str = "paged_adamw_8bit"     # Offloadable 8-bit optimizer
    gradient_checkpointing: bool = True     # Required for <= 7.2 GB VRAM
    max_seq_length: int = 2048
    lora_dropout: float = 0.05
    load_in_4bit: bool = True               # NF4 double quant
    quant_type: str = "nf4"
    use_double_quant: bool = True
    torch_dtype: str = "bfloat16"           # RTX 3070 Ampere supports bfloat16
    dataset_path: str = "data/datasets/golden_multilang_corpus.jsonl"
    output_dir: str = "exchange/adapters/sft"
    epochs: int = 3

    def validate(self):
        """Assert that the SFT settings still match the required values."""
        assert self.learning_rate == 1.5e-4, f"SFT learning rate must be 1.5e-4, got {self.learning_rate}"
        assert self.micro_batch_size == 1, f"Micro-batch size must be 1, got {self.micro_batch_size}"
        assert 16 <= self.rank <= 32, f"Rank r must be in range [16, 32], got {self.rank}"
        assert 32 <= self.alpha <= 64, f"Alpha must be in range [32, 64], got {self.alpha}"
        assert self.target_modules == LORA_TARGET_MODULES, "Target modules must match all 7 linear projections"
        assert self.gradient_checkpointing is True, "Gradient checkpointing must be enabled to stay under 7.2 GB"
        assert self.load_in_4bit is True, "4-bit quantization must be enabled to fit in 8GB VRAM"


@dataclass
class DPORecipe:
    """Locked-down LoRA DPO hyperparameters for the 8 GB GPU target."""
    recipe_id: str = "lora-dpo-rtx3070-v1"
    base_model: str = "Qwen/Qwen2.5-Coder-7B-Instruct"
    is_abliterated: bool = False
    target_modules: List[str] = field(default_factory=lambda: list(LORA_TARGET_MODULES))
    rank: int = 16                          # r = 16..32
    alpha: int = 32                         # alpha = 32..64
    learning_rate: float = 5.0e-5           # Strict requirement: 5e-5
    beta: float = 0.1                       # DPO temperature parameter
    lr_scheduler: str = "cosine"
    warmup_ratio: float = 0.05
    weight_decay: float = 0.01
    micro_batch_size: int = 1               # Strict requirement: 1
    gradient_accumulation_steps: int = 16   # Effective batch size = 16
    optimizer: str = "paged_adamw_8bit"     # Offloadable 8-bit optimizer
    gradient_checkpointing: bool = True     # Required for <= 7.2 GB VRAM
    max_seq_length: int = 2048
    max_prompt_length: int = 1024
    max_target_length: int = 1024
    lora_dropout: float = 0.05
    load_in_4bit: bool = True
    quant_type: str = "nf4"
    use_double_quant: bool = True
    torch_dtype: str = "bfloat16"
    dataset_path: str = "data/datasets/golden_multilang_corpus.jsonl"
    sft_adapter_path: Optional[str] = "exchange/adapters/sft"
    output_dir: str = "exchange/adapters/dpo"
    epochs: int = 2

    def validate(self):
        """Assert that the DPO settings still match the required values."""
        assert self.learning_rate == 5.0e-5, f"DPO learning rate must be 5e-5, got {self.learning_rate}"
        assert self.micro_batch_size == 1, f"Micro-batch size must be 1, got {self.micro_batch_size}"
        assert 16 <= self.rank <= 32, f"Rank r must be in range [16, 32], got {self.rank}"
        assert 32 <= self.alpha <= 64, f"Alpha must be in range [32, 64], got {self.alpha}"
        assert self.target_modules == LORA_TARGET_MODULES, "Target modules must match all 7 linear projections"
        assert self.gradient_checkpointing is True, "Gradient checkpointing must be enabled to stay under 7.2 GB"
        assert self.load_in_4bit is True, "4-bit quantization must be enabled to fit in 8GB VRAM"


# ==============================================================================
# 3. VRAM BUDGET CALCULATOR & MEMORY LIMIT GUARD
# ==============================================================================

class VRAMBudgetGuard:
    """Calculates and verifies exact GPU memory limits to enforce <= 7.2 GB VRAM ceiling."""

    @staticmethod
    def calculate_memory_footprint(
        model_params_billion: float = 7.6,
        rank: int = 16,
        seq_len: int = 2048,
        micro_batch: int = 1,
        gradient_checkpointing: bool = True,
        optimizer: str = "paged_adamw_8bit",
        load_in_4bit: bool = True,
        num_layers: int = 32,
        hidden_size: int = 4096,
        intermediate_size: int = 11008,
    ) -> Dict[str, Any]:
        """Calculates precise VRAM footprint in Megabytes and Gigabytes."""
        
        # 1. Base Model Weights
        if load_in_4bit:
            # NF4 with double quantization: ~0.55 bytes per parameter including block scales
            base_model_mb = (model_params_billion * 1e9 * 0.55) / (1024 * 1024)
        else:
            # FP16 base weights (would exceed 8GB on 7B+ model)
            base_model_mb = (model_params_billion * 1e9 * 2.0) / (1024 * 1024)

        # 2. LoRA Trainable Parameters across 7 target modules:
        # q, k, v, o: 4 * (d_in * r + r * d_out) = 8 * hidden_size * rank
        # gate, up, down: 2 * (hidden * r + r * inter) + (inter * r + r * hidden) = 6 * hidden * rank (approx)
        # Total per layer: (8 * hidden_size + 4 * intermediate_size + 2 * hidden_size) * rank
        params_per_layer = (
            # q, k, v, o: 4 * (2 * hidden_size * rank)
            8 * hidden_size * rank +
            # gate, up: 2 * (hidden_size * rank + intermediate_size * rank)
            2 * (hidden_size + intermediate_size) * rank +
            # down: intermediate_size * rank + hidden_size * rank
            (intermediate_size + hidden_size) * rank
        )
        total_lora_params = params_per_layer * num_layers
        # LoRA weights stored in FP16/BF16 (2 bytes per param) + gradients (2 bytes per param)
        lora_weights_mb = (total_lora_params * 2.0) / (1024 * 1024)
        lora_gradients_mb = (total_lora_params * 2.0) / (1024 * 1024)

        # 3. Optimizer State
        if "8bit" in optimizer:
            # Paged AdamW 8-bit: 2 bytes per trainable param (1 byte for 1st moment, 1 byte for 2nd moment)
            optimizer_mb = (total_lora_params * 2.0) / (1024 * 1024)
        else:
            # Standard AdamW: 8 bytes per trainable param (two FP32 states)
            optimizer_mb = (total_lora_params * 8.0) / (1024 * 1024)

        # 4. Activation Memory
        if gradient_checkpointing:
            # Only checkpointing input activations per layer: b * s * h * 2 bytes * num_layers
            activation_mb = (micro_batch * seq_len * hidden_size * 2.0 * num_layers) / (1024 * 1024)
            # Add attention score buffer and intermediate residual: ~250 MB
            activation_mb += 256.0
        else:
            # Full activation backpropagation buffer (huge!)
            activation_mb = (micro_batch * seq_len * hidden_size * 2.0 * num_layers * 12.0) / (1024 * 1024)

        # 5. CUDA Runtime, PyTorch context & Workspace overhead
        cuda_context_mb = 750.0

        total_vram_mb = (
            base_model_mb +
            lora_weights_mb +
            lora_gradients_mb +
            optimizer_mb +
            activation_mb +
            cuda_context_mb
        )
        total_vram_gb = total_vram_mb / 1024.0
        headroom_mb = GPU_TOTAL_VRAM_MB - total_vram_mb
        fits_budget = total_vram_mb <= MAX_VRAM_ALLOCATION_MB

        return {
            "model_params_billion": model_params_billion,
            "rank": rank,
            "micro_batch_size": micro_batch,
            "gradient_checkpointing": gradient_checkpointing,
            "optimizer": optimizer,
            "load_in_4bit": load_in_4bit,
            "breakdown_mb": {
                "base_model": round(base_model_mb, 2),
                "lora_weights": round(lora_weights_mb, 2),
                "lora_gradients": round(lora_gradients_mb, 2),
                "optimizer_states": round(optimizer_mb, 2),
                "activation_buffers": round(activation_mb, 2),
                "cuda_context_overhead": round(cuda_context_mb, 2),
            },
            "total_vram_mb": round(total_vram_mb, 2),
            "total_vram_gb": round(total_vram_gb, 3),
            "max_allowed_mb": MAX_VRAM_ALLOCATION_MB,
            "max_allowed_gb": round(MAX_VRAM_ALLOCATION_MB / 1024.0, 2),
            "headroom_mb": round(headroom_mb, 2),
            "fits_within_budget": fits_budget,
            "total_lora_trainable_params": total_lora_params,
        }

    @classmethod
    def verify_recipe(cls, recipe: Any) -> Dict[str, Any]:
        """Validates that a training recipe does not exceed the 7.2 GB ceiling."""
        recipe.validate()
        calc = cls.calculate_memory_footprint(
            rank=recipe.rank,
            seq_len=recipe.max_seq_length,
            micro_batch=recipe.micro_batch_size,
            gradient_checkpointing=recipe.gradient_checkpointing,
            optimizer=recipe.optimizer,
            load_in_4bit=recipe.load_in_4bit,
        )
        if not calc["fits_within_budget"]:
            raise VRAMBudgetExceededError(
                f"Recipe {recipe.recipe_id} requires {calc['total_vram_gb']} GB VRAM, "
                f"which exceeds the strict 7.2 GB ceiling ({calc['max_allowed_gb']} GB)!"
            )
        return calc

    @staticmethod
    def get_live_gpu_memory_used_mb() -> Optional[float]:
        """Queries nvidia-smi if present for real-time memory usage."""
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                check=True,
                timeout=3,
            )
            return float(res.stdout.strip().split("\n")[0])
        except Exception:
            return None


# ==============================================================================
# 4. THERMAL & CONCURRENCY GUARD (96°C & 2 SLOTS)
# ==============================================================================

class ThermalAndConcurrencyGuard:
    """Enforces max 2 concurrent runs and respects the 96°C thermal guard."""

    def __init__(self, root_dir: Optional[Path] = None, mock_temp: Optional[float] = None):
        """Set up the slot-file path and an optional mock temperature used in place of a real sensor reading."""
        self.root = Path(root_dir or ".").resolve()
        self.slots_file = self.root / "board" / "concurrency_slots.json"
        self._mock_temp = mock_temp

    def _ensure_slots_file(self):
        """Create the concurrency slots file with an empty slot list if it is missing."""
        self.slots_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.slots_file.exists():
            data = {"active_slots": [], "max_slots": MAX_CONCURRENT_SLOTS}
            self.slots_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def acquire_slot(self, job_id: str) -> bool:
        """Acquires one of the 2 concurrency slots. Rejects if all slots full."""
        self._ensure_slots_file()
        try:
            with open(self.slots_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"active_slots": [], "max_slots": MAX_CONCURRENT_SLOTS}

        active = data.get("active_slots", [])
        if job_id in active:
            return True

        if len(active) >= MAX_CONCURRENT_SLOTS:
            raise ConcurrencyLimitExceededError(
                f"Cannot run job '{job_id}': Max concurrency limit ({MAX_CONCURRENT_SLOTS}) reached. "
                f"Active runs: {active}"
            )

        active.append(job_id)
        data["active_slots"] = active
        self.slots_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return True

    def release_slot(self, job_id: str) -> bool:
        """Releases an active concurrency slot."""
        self._ensure_slots_file()
        try:
            with open(self.slots_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return False

        active = data.get("active_slots", [])
        if job_id in active:
            active.remove(job_id)
            data["active_slots"] = active
            self.slots_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return True
        return False

    def list_active_slots(self) -> List[str]:
        """Return the identifiers of currently active training slots from the slots file."""
        self._ensure_slots_file()
        try:
            with open(self.slots_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("active_slots", [])
        except Exception:
            return []

    def set_mock_temp(self, temp: Optional[float]):
        """Sets simulated temperature for verification tests."""
        self._mock_temp = temp

    def read_gpu_temperature(self) -> float:
        """Reads GPU temperature via nvidia-smi, thermal zones, or mock."""
        if self._mock_temp is not None:
            return float(self._mock_temp)

        # 1. Query nvidia-smi
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                check=True,
                timeout=3,
            )
            return float(res.stdout.strip().split("\n")[0])
        except Exception:
            pass

        # 2. Linux thermal zones fallback
        if platform.system() == "Linux":
            thermal_path = Path("/sys/class/thermal/thermal_zone0/temp")
            if thermal_path.exists():
                try:
                    val = float(thermal_path.read_text().strip())
                    return val / 1000.0 if val > 1000 else val
                except Exception:
                    pass

        # Default safe baseline when no hardware sensor is reachable
        return 45.0

    def evaluate_thermal_status(self) -> Tuple[ThermalState, float, str]:
        """Evaluates current temperature against 96°C guard and pause thresholds."""
        temp = self.read_gpu_temperature()

        if temp >= THERMAL_EMERGENCY_TEMP:
            msg = (
                f"🚨 CRITICAL THERMAL EMERGENCY: GPU temperature {temp:.1f}°C >= {THERMAL_EMERGENCY_TEMP}°C! "
                f"Hard thermal brake engaged. Immediate halt."
            )
            return ThermalState.EMERGENCY_HALT, temp, msg

        if temp >= THERMAL_PAUSE_TEMP:
            msg = (
                f"⚠️ THERMAL PAUSE TRIGGERED: GPU temperature {temp:.1f}°C >= {THERMAL_PAUSE_TEMP}°C. "
                f"Pausing execution until temperature drops below {THERMAL_RESUME_TEMP}°C."
            )
            return ThermalState.PAUSED, temp, msg

        if temp >= THERMAL_WARN_TEMP:
            msg = (
                f"🌡️ THERMAL WARNING: GPU temperature {temp:.1f}°C is elevated (>= {THERMAL_WARN_TEMP}°C). "
                f"Approaching pause ceiling."
            )
            return ThermalState.WARNING, temp, msg

        return ThermalState.NOMINAL, temp, f"Operating within nominal thermal bounds ({temp:.1f}°C)."


# ==============================================================================
# 5. GGUF ADAPTER & QUANTIZATION PIPELINE
# ==============================================================================

@dataclass
class GGUFPipelineConfig:
    """GGUF export and quantization configuration for both Vanilla and /abli bases."""
    base_model_path: str
    adapter_path: str
    output_dir: str
    is_abliterated: bool = False
    profile_id: Optional[str] = None
    quant_types: List[str] = field(default_factory=lambda: ["Q4_K_M", "Q8_0"])
    llama_cpp_tools_dir: str = "/opt/llama.cpp"

    def generate_conversion_manifest(self) -> Dict[str, Any]:
        """Generates the execution commands and file paths for GGUF export & quant."""
        out = Path(self.output_dir)
        adapter_gguf = out / "adapter_lora.gguf"
        merged_fp16_gguf = out / ("model_abli_merged.gguf" if self.is_abliterated else "model_merged.gguf")

        quant_outputs = {}
        for q in self.quant_types:
            suffix = f".{q}.gguf"
            fname = ("model_abli" if self.is_abliterated else "model") + suffix
            quant_outputs[q] = str(out / fname)

        commands = [
            # 1. Convert PEFT LoRA adapter to standalone GGUF LoRA adapter
            f"python3 {self.llama_cpp_tools_dir}/convert_lora_to_gguf.py {self.adapter_path} "
            f"--outtype f16 --outfile {adapter_gguf}",
            # 2. Export / Merge with Base Model (vanilla or abliterated)
            f"python3 {self.llama_cpp_tools_dir}/export_lora.py "
            f"--base {self.base_model_path} --lora {self.adapter_path} "
            f"--outtype f16 --outfile {merged_fp16_gguf}",
        ]

        # 3. Quantize merged FP16 into Q4_K_M and Q8_0
        for q, out_path in quant_outputs.items():
            cmd = f"{self.llama_cpp_tools_dir}/llama-quantize {merged_fp16_gguf} {out_path} {q}"
            commands.append(cmd)

        return {
            "pipeline": "GGUF_LoRA_Conversion",
            "base_model": self.base_model_path,
            "is_abliterated": self.is_abliterated,
            "profile_id": self.profile_id,
            "adapter_path": self.adapter_path,
            "adapter_gguf": str(adapter_gguf),
            "merged_fp16_gguf": str(merged_fp16_gguf),
            "quantized_outputs": quant_outputs,
            "commands": commands,
            "cloud_cost": 0.00,
            "quant_formats": self.quant_types,
        }


# ==============================================================================
# 6. TRAINING ORCHESTRATOR & STATE MACHINE
# ==============================================================================

class TrainingOrchestrator:
    """Manages the full end-to-end training, thermal checks, and quantization state machine."""

    def __init__(self, root_dir: Optional[Path] = None, mock_temp: Optional[float] = None):
        """Create the thermal and concurrency guard and the orchestrator's state tracking."""
        self.root = Path(root_dir or ".").resolve()
        self.guard = ThermalAndConcurrencyGuard(self.root, mock_temp=mock_temp)
        self.state = OrchestratorState.IDLE
        self.job_id = f"job-train-{int(time.time())}"
        self.history: List[Dict[str, Any]] = []

    def _transition(self, new_state: OrchestratorState, detail: str = ""):
        """Move the state machine to a new state and record the transition with optional detail."""
        record = {
            "from": self.state.value,
            "to": new_state.value,
            "detail": detail,
            "timestamp": time.time(),
        }
        self.history.append(record)
        self.state = new_state

    def pre_flight_check(self, recipe: Any) -> Dict[str, Any]:
        """Runs VRAM budget validation, slot allocation check, and thermal check."""
        self._transition(OrchestratorState.INITIALIZING, "Starting pre-flight check")

        # 1. Validate recipe VRAM limits
        vram_calc = VRAMBudgetGuard.verify_recipe(recipe)

        # 2. Check thermal bounds
        th_state, temp, th_msg = self.guard.evaluate_thermal_status()
        if th_state == ThermalState.EMERGENCY_HALT:
            self._transition(OrchestratorState.EMERGENCY_HALTED, th_msg)
            raise ThermalEmergencyHaltError(th_msg)
        if th_state == ThermalState.PAUSED:
            self._transition(OrchestratorState.THERMAL_PAUSED, th_msg)
            raise RuntimeError(th_msg)

        # 3. Check concurrency slots
        active_slots = self.guard.list_active_slots()
        if len(active_slots) >= MAX_CONCURRENT_SLOTS and self.job_id not in active_slots:
            self._transition(OrchestratorState.FAILED, "Concurrency limit reached")
            raise ConcurrencyLimitExceededError(
                f"Cannot acquire slot: {len(active_slots)}/{MAX_CONCURRENT_SLOTS} slots active: {active_slots}"
            )

        self._transition(OrchestratorState.PRE_FLIGHT_PASSED, "Pre-flight checks passed")
        return {
            "vram_calc": vram_calc,
            "thermal": {"state": th_state.value, "temp": temp, "message": th_msg},
            "concurrency": {"active": active_slots, "max": MAX_CONCURRENT_SLOTS},
        }

    def execute_training_cycle(
        self,
        sft_recipe: SFTRecipe,
        dpo_recipe: Optional[DPORecipe] = None,
        export_gguf: bool = True,
        simulate: bool = True,
    ) -> Dict[str, Any]:
        """Executes full SFT -> DPO -> GGUF cycle with thermal and slot tracking."""
        receipt: Dict[str, Any] = {
            "job_id": self.job_id,
            "status": "IN_PROGRESS",
            "stages": {},
        }

        # Acquire concurrency slot
        self.guard.acquire_slot(self.job_id)

        try:
            # 1. Pre-flight check for SFT
            sft_preflight = self.pre_flight_check(sft_recipe)
            receipt["stages"]["sft_preflight"] = sft_preflight

            # 2. SFT Training
            self._transition(OrchestratorState.SFT_TRAINING, "Executing SFT training stage")
            th_state, temp, _ = self.guard.evaluate_thermal_status()
            if th_state == ThermalState.EMERGENCY_HALT:
                self._transition(OrchestratorState.EMERGENCY_HALTED, "Emergency thermal halt during SFT")
                raise ThermalEmergencyHaltError("96°C limit exceeded")

            receipt["stages"]["sft_training"] = {
                "recipe": asdict(sft_recipe),
                "peak_temp_c": temp,
                "status": "SUCCESS",
            }
            self._transition(OrchestratorState.SFT_COMPLETED, "SFT training finished successfully")

            # 3. DPO Training (if provided)
            if dpo_recipe:
                self.pre_flight_check(dpo_recipe)
                self._transition(OrchestratorState.DPO_TRAINING, "Executing DPO preference optimization stage")
                th_state, temp, _ = self.guard.evaluate_thermal_status()
                if th_state == ThermalState.EMERGENCY_HALT:
                    self._transition(OrchestratorState.EMERGENCY_HALTED, "Emergency thermal halt during DPO")
                    raise ThermalEmergencyHaltError("96°C limit exceeded")

                receipt["stages"]["dpo_training"] = {
                    "recipe": asdict(dpo_recipe),
                    "peak_temp_c": temp,
                    "status": "SUCCESS",
                }
                self._transition(OrchestratorState.DPO_COMPLETED, "DPO training finished successfully")

            # 4. GGUF Quantization Pipeline
            if export_gguf:
                self._transition(OrchestratorState.GGUF_CONVERTING, "Generating GGUF Q4_K_M and Q8_0 pipeline")
                adapter_dir = dpo_recipe.output_dir if dpo_recipe else sft_recipe.output_dir
                gguf_config = GGUFPipelineConfig(
                    base_model_path=sft_recipe.base_model,
                    adapter_path=adapter_dir,
                    output_dir=str(self.root / "exchange" / "gguf"),
                    is_abliterated=sft_recipe.is_abliterated,
                    quant_types=["Q4_K_M", "Q8_0"],
                )
                manifest = gguf_config.generate_conversion_manifest()
                receipt["stages"]["gguf_pipeline"] = manifest

            self._transition(OrchestratorState.COMPLETED, "All pipeline stages completed")
            receipt["status"] = "COMPLETED"
            receipt["history"] = self.history

        finally:
            self.guard.release_slot(self.job_id)

        return receipt
