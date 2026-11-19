# ==============================================================================
# Program: abli.py
# Programmer: Ethan-da-Tech-Wizard
# Last Modified: November 18, 2026
# Purpose: Abliterated Model Registry & Multi-Platform Inference Coordinator.
#          Provides the /abli CLI orchestration layer for un-censored,
#          orthogonalized-weight model variants across Mac (Metal/MLX),
#          Arch Linux (CUDA/Vulkan), and Fedora (ROCm/CPU).
# ==============================================================================

"""Abliterated Model Registry & Multi-Platform Inference Coordinator.

Provides the `/abli` CLI interface and orchestration layer for un-censored,
orthogonalized-weight model variants across Mac (Metal), Arch Linux (CUDA/Vulkan),
and Fedora (ROCm/CPU). Guarantees shared training parity with baseline models.
"""
from dataclasses import dataclass, asdict
import json
import os
from pathlib import Path
import platform
from typing import Dict, Any, Optional

@dataclass
class ModelProfile:
    """One registry entry describing a model variant and where/how to run it.

    Serialized to JSON via dataclasses.asdict, so every field must stay a plain
    JSON-compatible type.
    """
    # Stable unique key used by set_active_profile() and the `active_id` field.
    id: str
    name: str
    # Matches detect_hardware()["target_key"], i.e. "<platform.system()>-<platform.machine()>".
    target_hardware: str
    backend: str  # "mlx" | "llama.cpp" | "vllm" | "ollama"
    # Maximum context window in tokens.
    context_length: int
    # Where the weights live on the target box (may contain "~"; not expanded here).
    weights_path: str
    # True for variants with the refusal direction projected out of the weights.
    abliterated: bool
    # Corpus filename the variant is trained/evaluated against, so all variants share one baseline.
    training_corpus_id: str
    # Mirrors registry-level `active_id`; exactly one profile should be True at a time.
    active: bool

# Seed profiles written to abli_profiles.json the first time the registry is
# created. One per supported machine class (Mac/MLX, Arch/vLLM, Fedora/llama.cpp).
# All three point at the same training corpus to guarantee training parity.
DEFAULT_PROFILES = [
    ModelProfile(
        id="qwen-coder-32b-abli-mac",
        name="Qwen2.5-Coder-32B-Instruct-Abliterated-4bit",
        target_hardware="Darwin-arm64",
        backend="mlx",
        context_length=32768,
        weights_path="~/.cache/models/qwen2.5-coder-32b-abli-mlx",
        abliterated=True,
        training_corpus_id="golden_multilang_corpus.jsonl",
        active=True,
    ),
    ModelProfile(
        id="deepseek-coder-v2-abli-arch",
        name="DeepSeek-Coder-V2-Lite-Abliterated-AWQ",
        target_hardware="Linux-x86_64",
        backend="vllm",
        context_length=65536,
        weights_path="/mnt/models/deepseek-coder-v2-abli-awq",
        abliterated=True,
        training_corpus_id="golden_multilang_corpus.jsonl",
        active=True,
    ),
    ModelProfile(
        id="llama33-70b-abli-fedora",
        name="Llama-3.3-70B-Instruct-Abliterated-GGUF",
        target_hardware="Linux-x86_64",
        backend="llama.cpp",
        context_length=131072,
        weights_path="/var/models/llama-3.3-70b-abli.Q4_K_M.gguf",
        abliterated=True,
        training_corpus_id="golden_multilang_corpus.jsonl",
        active=True,
    ),
]


class AbliteratedRegistry:
    """JSON-file-backed registry of model profiles, stored under <root>/data/models/."""
    def __init__(self, root_dir: Optional[Path] = None):
        """Resolve the config location (defaults to the CWD) and create it if missing."""
        self.root = Path(root_dir or ".").resolve()
        self.config_dir = self.root / "data" / "models"
        self.config_file = self.config_dir / "abli_profiles.json"
        self._ensure_config()

    def _ensure_config(self):
        """Create the config dir and seed the file with DEFAULT_PROFILES; never overwrites an existing file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if not self.config_file.exists():
            # First default profile (the Mac one) is active until the user changes it.
            data = {"profiles": [asdict(p) for p in DEFAULT_PROFILES], "active_id": DEFAULT_PROFILES[0].id}
            self.config_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def detect_hardware(self) -> Dict[str, str]:
        """Describe the current machine: OS, CPU arch, hostname, and Linux flavor."""
        system = platform.system()
        machine = platform.machine()
        node = platform.node()
        # Distro marker files refine the generic "linux" label (no other distros detected).
        os_flavor = "macos" if system == "Darwin" else "linux"
        if os.path.exists("/etc/arch-release"):
            os_flavor = "arch"
        elif os.path.exists("/etc/fedora-release"):
            os_flavor = "fedora"

        return {
            "system": system,
            "machine": machine,
            "node": node,
            "flavor": os_flavor,
            # Same format as ModelProfile.target_hardware, so callers can match profiles to this box.
            "target_key": f"{system}-{machine}",
        }

    def list_profiles(self) -> Dict[str, Any]:
        """Return current hardware info plus the stored profiles and active id."""
        with open(self.config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        hw = self.detect_hardware()
        return {
            "current_hardware": hw,
            "active_id": data.get("active_id"),
            "profiles": data.get("profiles", []),
        }

    def set_active_profile(self, profile_id: str) -> bool:
        """Mark profile_id as the only active profile; returns False (and writes nothing) if it is unknown."""
        with open(self.config_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Single pass: flag the match active and every other profile inactive.
        found = False
        for p in data.get("profiles", []):
            if p["id"] == profile_id:
                p["active"] = True
                found = True
            else:
                p["active"] = False

        # Only persist when the id existed, so a typo cannot deactivate everything.
        if found:
            data["active_id"] = profile_id
            self.config_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return found
