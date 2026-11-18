# ==============================================================================
# Program: abli.py
# Programmer: Ethan-da-Tech-Wizard
# Course: CIS 156 / Advanced Systems
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
    id: str
    name: str
    target_hardware: str
    backend: str  # "mlx" | "llama.cpp" | "vllm" | "ollama"
    context_length: int
    weights_path: str
    abliterated: bool
    training_corpus_id: str
    active: bool

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
    def __init__(self, root_dir: Optional[Path] = None):
        self.root = Path(root_dir or ".").resolve()
        self.config_dir = self.root / "data" / "models"
        self.config_file = self.config_dir / "abli_profiles.json"
        self._ensure_config()

    def _ensure_config(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if not self.config_file.exists():
            data = {"profiles": [asdict(p) for p in DEFAULT_PROFILES], "active_id": DEFAULT_PROFILES[0].id}
            self.config_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def detect_hardware(self) -> Dict[str, str]:
        system = platform.system()
        machine = platform.machine()
        node = platform.node()
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
            "target_key": f"{system}-{machine}",
        }

    def list_profiles(self) -> Dict[str, Any]:
        with open(self.config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        hw = self.detect_hardware()
        return {
            "current_hardware": hw,
            "active_id": data.get("active_id"),
            "profiles": data.get("profiles", []),
        }

    def set_active_profile(self, profile_id: str) -> bool:
        with open(self.config_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        found = False
        for p in data.get("profiles", []):
            if p["id"] == profile_id:
                p["active"] = True
                found = True
            else:
                p["active"] = False

        if found:
            data["active_id"] = profile_id
            self.config_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return found
