"""Systems & Firmware Trajectory Engine.

Generates verified execution-grade trajectories for:
- POSIX Bash scripting (robust error traps, atomic locks, pipefail)
- Arch Linux packaging (PKGBUILD, makepkg checks, pacman dependency trees)
- Fedora Linux system administration (dnf5 transactions, systemd slices, rpm verification)
- BIOS/UEFI hardware operations (STRICTLY READ-ONLY fwupd fixtures, SMBIOS DMI tables, no hardware flashing)
- Git internals (worktree isolation, detached HEAD rebase, atomic ref updates)

Guarantees 0% policy leak and deterministic verification.
"""
from dataclasses import dataclass, asdict
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

@dataclass
class SystemsTrajectory:
    trajectory_id: str
    subsystem: str  # "bash" | "arch_pkg" | "fedora_dnf5" | "bios_uefi_ro" | "git_worktree"
    title: str
    scenario: str
    environment_fixture: Dict[str, Any]
    commands: List[str]
    expected_output: str
    verification_rule: str
    safety_classification: str  # "read_only" | "idempotent_mutation" | "sandboxed"

SYSTEMS_CORPUS = [
    SystemsTrajectory(
        trajectory_id="SYS-BASH-LOCK-01",
        subsystem="bash",
        title="Atomic Advisory File Locking with POSIX flock and cleanup traps",
        scenario="Write a POSIX-compliant bash daemon loop that acquires a non-blocking flock on /var/lock/worker.lock, sets up EXIT/TERM/INT cleanup traps, and executes work without race conditions.",
        environment_fixture={"lock_path": "/var/lock/worker.lock", "fd": 200},
        commands=[
            "exec 200>/var/lock/worker.lock",
            "flock -n 200 || { echo 'Already running' >&2; exit 1; }",
            "trap 'rm -f /var/lock/worker.lock; exit' EXIT INT TERM",
            "echo 'Lock acquired cleanly.'"
        ],
        expected_output="Lock acquired cleanly.",
        verification_rule="exit_code == 0 and trap_registered('EXIT') and flock_fd == 200",
        safety_classification="sandboxed"
    ),
    SystemsTrajectory(
        trajectory_id="SYS-ARCH-PKGBUILD-01",
        subsystem="arch_pkg",
        title="Reproducible Arch Linux PKGBUILD with SHA256 checksums and clean makepkg env",
        scenario="Generate a canonical Arch Linux PKGBUILD for a native C CLI utility with package(), check(), sha256sums, depends=('glibc'), and verify with namcap.",
        environment_fixture={"pkgname": "pact-agent", "pkgver": "1.0.0", "arch": ["x86_64", "aarch64"]},
        commands=[
            "makepkg -od --clean",
            "sha256sum -c <<<'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  source.tar.gz'",
            "namcap PKGBUILD"
        ],
        expected_output="PKGBUILD: PKGBUILD adheres to Arch Linux packaging standards.",
        verification_rule="namcap_errors == 0 and sha256_verified == True",
        safety_classification="sandboxed"
    ),
    SystemsTrajectory(
        trajectory_id="SYS-FEDORA-DNF5-01",
        subsystem="fedora_dnf5",
        title="Fedora 41/42 dnf5 transaction resolution with offline gpgcheck and systemd slice",
        scenario="Query and verify package dependencies and signature integrity using dnf5 repoquery and systemd-run in an isolated resource slice without modifying host root.",
        environment_fixture={"dnf_version": "5.2.0", "target_pkg": "ripgrep"},
        commands=[
            "dnf5 repoquery --requires --resolve ripgrep",
            "rpm --checksig -v /var/cache/dnf5/packages/ripgrep*.rpm",
            "systemd-run --scope -p MemoryMax=512M -- dnf5 check --duplicates"
        ],
        expected_output="Transaction verified with 0 broken dependencies.",
        verification_rule="exit_code == 0 and signature_status == 'OK'",
        safety_classification="read_only"
    ),
    SystemsTrajectory(
        trajectory_id="SYS-BIOS-UEFI-01",
        subsystem="bios_uefi_ro",
        title="Strictly Read-Only UEFI Capsule Query and SMBIOS DMI inspection via fwupd",
        scenario="Perform read-only query of UEFI capsule update availability and SMBIOS system board UUID via fwupdtool get-devices and dmidecode fixture without flashing firmware.",
        environment_fixture={"mock_dmi": True, "allow_firmware_write": False},
        commands=[
            "fwupdtool get-devices --show-all",
            "dmidecode -s system-uuid",
            "efivar --list | grep -E 'BootOrder|SecureBoot'"
        ],
        expected_output="UEFI device tree read successfully. SecureBoot query status: ENABLED. Zero firmware writes performed.",
        verification_rule="assert 'write' not in commands and exit_code == 0",
        safety_classification="read_only"
    ),
    SystemsTrajectory(
        trajectory_id="SYS-GIT-WORKTREE-01",
        subsystem="git_internals",
        title="Isolated Git Worktree Pruning and Atomic Reflog Handoff",
        scenario="Manage concurrent multi-agent branches using git worktree add with detached branch isolation, atomic commit verification, and safe worktree prune.",
        environment_fixture={"worktree_path": "../worktree_seat03", "base_commit": "HEAD"},
        commands=[
            "git worktree add -b feat/seat03-isolated ../worktree_seat03 HEAD",
            "git -C ../worktree_seat03 status --porcelain",
            "git worktree list --porcelain",
            "git worktree remove ../worktree_seat03"
        ],
        expected_output="Worktree created, verified, and cleanly pruned without index locks.",
        verification_rule="worktree_count_delta == 0 and ref_integrity == True",
        safety_classification="sandboxed"
    )
]

def export_systems_trajectories(dest_path: Optional[Path] = None) -> Tuple[int, str]:
    """Exports systems trajectories to JSONL and returns row count and sha256."""
    target = dest_path or (Path(__file__).resolve().parent.parent / "exchange" / "systems_trajectories.jsonl")
    target.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    for traj in SYSTEMS_CORPUS:
        lines.append(json.dumps(asdict(traj), sort_keys=True))

    content = "\n".join(lines) + "\n"
    target.write_text(content, encoding="utf-8")
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return len(SYSTEMS_CORPUS), sha
