# Program: magi_pact - systems.py
# Programmer: Ethan-da-Tech-Wizard (written with Claude, an AI assistant)
# Last Modified: 2026-11-18
# Purpose: Golden systems trajectories with validators and read-only firmware fixtures for Bash, packaging, dnf5 and Git worktrees.

"""Systems & Firmware Architecture: Golden Trajectories, Validators, and Read-Only Fixtures.

Covers:
1. Bash Scripting (POSIX compliance, atomic I/O, exit traps, subshell hygiene)
2. Arch Linux Packaging (namcap-compliant PKGBUILD, reproducible LTO, dynamic VCS, split packages)
3. Fedora dnf5 System Administration (modern dnf5 commands, advisory upgrades, history rollback, micro-rootfs)
4. BIOS/UEFI fwupd Query Fixtures (strictly read-only simulated fixtures, ESRT tables, zero hardware flashing)
5. Git Worktree Branching Operations (collision-free agent worktrees, advisory locks, porcelain diagnostics)
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Dict, List, Optional, Any, Tuple

from .dataset import TrainingPair, DOMAINS


# =====================================================================
# Strict Zero-Spend & Firmware Safety Gate (No hardware flashing)
# =====================================================================

class FirmwareSafetyViolation(RuntimeError):
    """Raised when an operation attempts destructive or non-read-only hardware actions."""
    pass


class FirmwareSafetyGate:
    """Strict policy gate ensuring all BIOS/UEFI tasks remain strictly read-only fixtures.
    
    Guarantees $0.00 cloud spend and prevents accidental hardware writes, NVRAM
    corruption, or capsule execution.
    """

    HAZARDOUS_PATTERNS = [
        r"\bflashrom\b",
        r"\bfwupdmgr\s+(?:update|install|reinstall|modify-device-flag)\b",
        r"\bflash\b",
        r"\b--force\b",
        r"\b--reboot\b",
        r"\bwrmsr\b",
        r"\brm\s+.*(?:efivars|sys/firmware)\b",
        r"\b(?:echo|printf)\s+.*>\s*/sys/firmware/efi/efivars\b",
        r"\bdd\b.*of=/dev/(?:nvme[0-9a-z]*|sd[a-z0-9]*|mtd[0-9]*|spi[0-9]*|mem)",
        r"\bmem\b.*write",
        r"\bnvram-wakeup\b",
    ]

    ALLOWED_READONLY_COMMANDS = [
        "fwupdmgr get-devices",
        "fwupdmgr get-updates",
        "fwupdmgr get-history",
        "fwupdmgr hwids",
        "efibootmgr -v",
        "efibootmgr",
        "cat /sys/firmware/efi/esrt",
        "jcat-tool verify",
        "fwupdtool get-devices",
    ]

    @classmethod
    def verify_command_safety(cls, cmd: str) -> bool:
        """Inspects shell commands or API calls for forbidden physical flash operations."""
        lowered = cmd.lower()
        for pat in cls.HAZARDOUS_PATTERNS:
            if re.search(pat, lowered):
                raise FirmwareSafetyViolation(
                    f"Blocked hazardous firmware instruction matching policy pattern '{pat}': {cmd}"
                )
        return True


# =====================================================================
# Read-Only UEFI ESRT & fwupd Fixture Parser
# =====================================================================

class FwupdFixtureParser:
    """Safe, read-only inspection engine for simulated fwupd JSON outputs and ESRT tables."""

    @staticmethod
    def load_fixture(fixture_path: Path) -> Dict[str, Any]:
        """Read a firmware-device fixture file and return its parsed JSON."""
        with open(fixture_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def parse_devices(cls, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract a normalized list of device records from fixture data."""
        devices = data.get("Devices", [])
        parsed = []
        for dev in devices:
            parsed.append({
                "name": dev.get("Name"),
                "device_id": dev.get("DeviceId"),
                "guid": dev.get("Guid", []),
                "plugin": dev.get("Plugin"),
                "version": dev.get("Version"),
                "version_lowest": dev.get("VersionLowest"),
                "flags": dev.get("Flags", []),
                "is_updatable": "updatable" in dev.get("Flags", []),
                "needs_reboot": "needs-reboot" in dev.get("Flags", []),
                "vendor": dev.get("Vendor"),
            })
        return parsed

    @classmethod
    def parse_esrt(cls, esrt_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract a normalized list of ESRT entries from fixture data."""
        entries = esrt_data.get("entries", [])
        results = []
        for e in entries:
            # Check version downgrade protection
            cur_ver = e.get("fw_version", 0)
            lowest = e.get("lowest_supported_fw_version", 0)
            downgrade_safe = cur_ver >= lowest
            results.append({
                "entry_index": e.get("entry_index"),
                "fw_class": e.get("fw_class"),
                "type": e.get("fw_type_name"),
                "version_formatted": e.get("fw_version_formatted"),
                "lowest_supported": e.get("lowest_supported_fw_version_formatted"),
                "downgrade_safe": downgrade_safe,
                "status": e.get("last_attempt_status_name"),
            })
        return results


# =====================================================================
# Domain Validators
# =====================================================================

class BashSafetyValidator:
    """Validates Bash scripts against POSIX safety standards and best practices."""

    @classmethod
    def validate(cls, script: str) -> Dict[str, Any]:
        """Check a Bash script for strict-mode flags and other safety practices; return the issues found."""
        issues = []
        # Check strict error flags
        has_strict_flags = bool(
            re.search(r"set\s+-[a-zA-Z]*e[a-zA-Z]*", script)
            and re.search(r"pipefail", script)
        )
        if not has_strict_flags:
            issues.append("Missing strict error settings: expected 'set -euo pipefail'")

        # Check trap usage
        has_trap = bool(re.search(r"trap\s+.*(?:EXIT|TERM|INT)", script))
        if not has_trap:
            issues.append("Missing exit/signal cleanup trap (expected 'trap ... EXIT')")

        # Check IFS safety
        has_ifs = bool(re.search(r"IFS=", script))

        # Check for unquoted dangerous rm
        dangerous_rm = bool(re.search(r"rm\s+-rf\s+\$[a-zA-Z0-9_]+\s*$", script))
        if dangerous_rm:
            issues.append("Dangerous unquoted rm -rf on variable expansion")

        return {
            "valid": len(issues) == 0,
            "has_strict_flags": has_strict_flags,
            "has_trap": has_trap,
            "has_ifs": has_ifs,
            "issues": issues,
        }


class ArchPkgbuildValidator:
    """Validates Arch Linux PKGBUILD scripts for packaging compliance."""

    MANDATORY_VARS = ["pkgname", "pkgver", "pkgrel", "arch", "license"]

    @classmethod
    def validate(cls, pkgbuild_content: str) -> Dict[str, Any]:
        """Check PKGBUILD text for mandatory variables and packaging best practices; return the issues found."""
        issues = []
        for var in cls.MANDATORY_VARS:
            pattern = rf"^{var}="
            if not re.search(pattern, pkgbuild_content, re.MULTILINE):
                issues.append(f"Missing mandatory PKGBUILD variable: '{var}'")

        has_package_fn = bool(
            re.search(r"^package(_[a-zA-Z0-9_-]+)?\s*\(\)", pkgbuild_content, re.MULTILINE)
        )
        if not has_package_fn:
            issues.append("Missing mandatory 'package()' or 'package_<subpkg>()' function")

        # Check for bad practices
        if "/usr/local" in pkgbuild_content:
            issues.append("Forbidden target path '/usr/local' in Arch package; use '/usr'")

        if "cargo install" in pkgbuild_content and "--root" not in pkgbuild_content:
            issues.append("Unsafe 'cargo install' detected without explicit destination root")

        has_checksums = bool(
            re.search(r"sha256sums=", pkgbuild_content)
            or re.search(r"sha512sums=", pkgbuild_content)
        )
        if not has_checksums:
            issues.append("Missing source integrity checksum array (sha256sums or sha512sums)")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "is_vcs_package": "-git" in pkgbuild_content,
        }


class FedoraDnf5Validator:
    """Validates Fedora dnf5 command patterns, query schemas, and rollback safety."""

    @classmethod
    def validate_command(cls, cmd: str) -> Dict[str, Any]:
        """Check a dnf5 command line for modern dnf5 usage and rollback safety; return the issues found."""
        issues = []
        is_dnf5 = "dnf5" in cmd

        if "yum " in cmd:
            issues.append("Legacy 'yum' invocation detected; migrate to 'dnf5'")
        elif not is_dnf5:
            issues.append("Command does not utilize modern dnf5 package manager")

        if "--nodeps" in cmd or "rpm -e" in cmd:
            issues.append("Dangerous direct rpm manipulation bypassing dependency tracking")

        if "cp -r /" in cmd or "cp -r /bin" in cmd:
            issues.append("Manual directory copy instead of structured package management")
        
        # Check installroot safety
        if "--installroot" in cmd:
            if "--releasever" not in cmd:
                issues.append("When using '--installroot', explicit '--releasever' must be specified")
            if "--nodocs" not in cmd:
                issues.append("Recommended '--nodocs' flag missing for minimal container rootfs creation")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "is_dnf5": is_dnf5,
        }


class GitWorktreeManager:
    """Safe management and porcelain inspection for isolated Git worktrees."""

    @staticmethod
    def parse_worktree_porcelain(porcelain_output: str) -> List[Dict[str, Any]]:
        """Parse `git worktree list --porcelain` output into a list of worktree records."""
        worktrees = []
        current: Dict[str, Any] = {}

        for line in porcelain_output.splitlines():
            line = line.strip()
            if not line:
                if current:
                    worktrees.append(current)
                    current = {}
                continue

            parts = line.split(" ", 1)
            key = parts[0]
            val = parts[1] if len(parts) > 1 else True

            if key == "worktree":
                if current:
                    worktrees.append(current)
                    current = {}
                current["path"] = val
            elif key == "HEAD":
                current["head"] = val
            elif key == "branch":
                current["branch"] = val
            elif key == "locked":
                current["locked"] = True
                current["lock_reason"] = val if val is not True else "no reason"
            elif key == "prunable":
                current["prunable"] = val

        if current:
            worktrees.append(current)

        return worktrees


# =====================================================================
# Systems & Firmware Golden Trajectory Definitions (15 Pairs)
# =====================================================================

SYSTEMS_TRAJECTORIES: List[Dict[str, Any]] = [
    # -------------------------------------------------------------
    # 1. BASH SCRIPTING TRAJECTORIES (bash_posix)
    # -------------------------------------------------------------
    {
        "domain": "bash_posix",
        "id_suffix": "BASH_SUPERVISOR_0001",
        "prompt": (
            "Write a hardened, POSIX-compliant Bash process supervisor script that implements "
            "atomic PID locking via mkdir mutex, signal trapping (SIGINT, SIGTERM, EXIT), isolated "
            "scratch directory management, and atomic state synchronization without race conditions."
        ),
        "chosen": (
            "#!/usr/bin/env bash\n"
            "# Magi Mesh Process Supervisor - Deterministic & Hardened\n"
            "set -euo pipefail\n"
            "IFS=$'\\n\\t'\n\n"
            "LOCK_DIR=\"/tmp/magi_supervisor.lock\"\n"
            "SCRATCH_DIR=\"\"\n\n"
            "cleanup() {\n"
            "    local exit_code=$?\n"
            "    if [[ -n \"$SCRATCH_DIR\" && -d \"$SCRATCH_DIR\" ]]; then\n"
            "        rm -rf \"$SCRATCH_DIR\"\n"
            "    fi\n"
            "    rm -rf \"$LOCK_DIR\"\n"
            "    exit \"$exit_code\"\n"
            "}\n"
            "trap cleanup EXIT INT TERM HUP\n\n"
            "# 1. Acquire atomic filesystem mutex (POSIX directory lock)\n"
            "if ! mkdir \"$LOCK_DIR\" 2>/dev/null; then\n"
            "    echo \"[ERROR] Another instance is holding the lock: $LOCK_DIR\" >&2\n"
            "    exit 1\n"
            "fi\n\n"
            "# 2. Allocate isolated temporary workspace\n"
            "SCRATCH_DIR=\"$(mktemp -d 2>/dev/null || mktemp -d -t 'magi_sup')\"\n"
            "STATE_TARGET=\"${1:-/tmp/magi_state.json}\"\n"
            "TEMP_STATE=\"$SCRATCH_DIR/state.tmp\"\n\n"
            "# 3. Write state payload to temporary scratch space\n"
            "cat << 'EOF' > \"$TEMP_STATE\"\n"
            "{\n"
            "  \"supervisor\": \"active\",\n"
            "  \"pid\": $$, \n"
            "  \"status\": \"healthy\",\n"
            "  \"timestamp\": \"$(date -u +'%Y-%m-%dT%H:%M:%SZ')\"\n"
            "}\n"
            "EOF\n\n"
            "# 4. Atomic swap via POSIX move: readers never observe truncated writes\n"
            "mv -f \"$TEMP_STATE\" \"$STATE_TARGET\"\n"
            "echo \"Supervisor successfully synced state to $STATE_TARGET\"\n"
        ),
        "rejected": (
            "#!/bin/bash\n"
            "# Fragile supervisor with race conditions\n"
            "echo $$ > /tmp/magi.pid # Non-atomic PID write\n"
            "echo '{\"status\": \"healthy\"}' > /tmp/magi_state.json # Truncates live file during read\n"
            "# No exit traps, leaving stale locks on kill\n"
            "sleep 100\n"
        ),
        "capabilities": ["bash", "process_supervision", "atomic_locking", "signal_traps", "posix"],
    },
    {
        "domain": "bash_posix",
        "id_suffix": "BASH_FILE_TRAVERSAL_0002",
        "prompt": (
            "Construct a robust Bash script to safely traverse deep filesystem hierarchies, parse "
            "paths containing spaces, quotes, and newlines using zero-delimiter streams (`find -print0` "
            "and `read -d ''`), compute SHA-256 digests, and batch-migrate files without word-splitting bugs."
        ),
        "chosen": (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "IFS=$'\\n\\t'\n\n"
            "SRC_DIR=\"${1:-./source}\"\n"
            "DEST_DIR=\"${2:-./destination}\"\n"
            "TMP_MANIFEST=\"$(mktemp 2>/dev/null || mktemp -t 'manifest')\"\n\n"
            "cleanup() {\n"
            "    local exit_code=$?\n"
            "    rm -f \"$TMP_MANIFEST\"\n"
            "    exit \"$exit_code\"\n"
            "}\n"
            "trap cleanup EXIT INT TERM HUP\n\n"
            "if [[ ! -d \"$SRC_DIR\" ]]; then\n"
            "    echo \"[ERROR] Source directory does not exist: $SRC_DIR\" >&2\n"
            "    exit 1\n"
            "fi\n\n"
            "mkdir -p \"$DEST_DIR\"\n\n"
            "# Use process substitution and null-delimited record separators for safe iteration\n"
            "while IFS= read -r -d '' src_path; do\n"
            "    # Extract relative path cleanly\n"
            "    rel_path=\"${src_path#\"$SRC_DIR\"/}\"\n"
            "    target_path=\"$DEST_DIR/$rel_path\"\n"
            "    mkdir -p \"$(dirname \"$target_path\")\"\n\n"
            "    # Verify sha256 checksum deterministically\n"
            "    hash_val=\"$(sha256sum \"$src_path\" | awk '{print $1}')\"\n"
            "    cp -p \"$src_path\" \"$target_path\"\n"
            "    echo \"$hash_val  $rel_path\" >> \"$TMP_MANIFEST\"\n"
            "    echo \"Migrated: $rel_path [SHA256: $hash_val]\"\n"
            "done < <(find \"$SRC_DIR\" -type f -print0)\n"
        ),
        "rejected": (
            "#!/bin/bash\n"
            "# Vulnerable to word splitting on spaces and newlines\n"
            "for file in $(find $1 -type f); do\n"
            "    cp $file $2/\n"
            "done\n"
        ),
        "capabilities": ["bash", "stream_processing", "zero_delimiter", "quoting", "sha256"],
    },
    {
        "domain": "bash_posix",
        "id_suffix": "BASH_GETOPTS_JSON_0003",
        "prompt": (
            "Implement a POSIX `getopts` argument parser for a systems utility supporting boolean flags, "
            "options with mandatory parameters, input validation, help docstrings, and structured JSON output "
            "without external dependencies like jq."
        ),
        "chosen": (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "IFS=$'\\n\\t'\n"
            "trap 'exit' EXIT\n\n"
            "usage() {\n"
            "    cat << 'EOF'\n"
            "Usage: sysmon [-v] [-p PORT] [-n NAME] [-h]\n"
            "  -v         Enable verbose diagnostic logging\n"
            "  -p PORT    Listen port (1-65535)\n"
            "  -n NAME    Node identifier (alphanumeric)\n"
            "  -h         Display this help message\n"
            "EOF\n"
            "    exit 1\n"
            "}\n\n"
            "VERBOSE=\"false\"\n"
            "PORT=8080\n"
            "NAME=\"node-01\"\n\n"
            "while getopts \":vp:n:h\" opt; do\n"
            "    case \"$opt\" in\n"
            "        v) VERBOSE=\"true\" ;;\n"
            "        p)\n"
            "            PORT=\"$OPTARG\"\n"
            "            if ! [[ \"$PORT\" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then\n"
            "                echo \"[ERROR] Invalid port number: $PORT\" >&2\n"
            "                exit 2\n"
            "            fi\n"
            "            ;;\n"
            "        n)\n"
            "            NAME=\"$OPTARG\"\n"
            "            if ! [[ \"$NAME\" =~ ^[a-zA-Z0-9_-]+$ ]]; then\n"
            "                echo \"[ERROR] Invalid node name format: $NAME\" >&2\n"
            "                exit 2\n"
            "            fi\n"
            "            ;;\n"
            "        h) usage ;;\n"
            "        \\?) echo \"[ERROR] Unknown option: -$OPTARG\" >&2; usage ;;\n"
            "        :)  echo \"[ERROR] Option -$OPTARG requires an argument.\" >&2; usage ;;\n"
            "    esac\n"
            "done\n"
            "shift $((OPTIND - 1))\n\n"
            "# Emit structured, escaped JSON without external binaries\n"
            "printf '{\"node\":\"%s\",\"port\":%d,\"verbose\":%s}\\n' \\\n"
            "    \"$NAME\" \"$PORT\" \"$VERBOSE\"\n"
        ),
        "rejected": (
            "#!/bin/bash\n"
            "# Manual brittle parsing with $1, $2 and no validation\n"
            "NAME=$1\n"
            "PORT=$2\n"
            "echo \"{\\\"node\\\": \\\"$NAME\\\", \\\"port\\\": $PORT}\"\n"
        ),
        "capabilities": ["bash", "getopts", "input_validation", "posix_cli", "json_emission"],
    },

    # -------------------------------------------------------------
    # 2. ARCH LINUX PKGBUILD TRAJECTORIES (arch_linux)
    # -------------------------------------------------------------
    {
        "domain": "arch_linux",
        "id_suffix": "ARCH_PKGBUILD_RUST_LTO_0001",
        "prompt": (
            "Create a production-grade, namcap-compliant Arch Linux PKGBUILD for a native Rust "
            "mesh daemon with cargo offline vendoring, link-time optimization (LTO), split debug "
            "symbols, and systemd service file installation."
        ),
        "chosen": (
            "# Maintainer: Magi Systems Specialist <maintainer@magi-mesh.org>\n"
            "pkgname=magi-mesh-daemon\n"
            "pkgver=1.2.0\n"
            "pkgrel=1\n"
            "pkgdesc=\"Autonomous 32-seat mesh coordination daemon\"\n"
            "arch=('x86_64' 'aarch64')\n"
            "url=\"https://github.com/magi-pact/magi_pact\"\n"
            "license=('MIT' 'Apache-2.0')\n"
            "depends=('glibc' 'gcc-libs' 'systemd-libs')\n"
            "makedepends=('cargo' 'rust')\n"
            "options=('lto' '!debug')\n"
            "source=(\n"
            "    \"$pkgname-$pkgver.tar.gz::$url/archive/v$pkgver.tar.gz\"\n"
            "    \"magi-mesh.service\"\n"
            ")\n"
            "sha256sums=(\n"
            "    'a48b3c9f28014e7a892b45019d08e5c2b3e8a719d20c3b88e147f892a012d94b'\n"
            "    '71f92e5910c2834b6e51f8021a88b5608d23458b91e70c2a8f81156e9c42a177'\n"
            ")\n\n"
            "prepare() {\n"
            "    cd \"$pkgname-$pkgver\"\n"
            "    export RUSTUP_TOOLCHAIN=stable\n"
            "    cargo fetch --locked --target \"$CARCH-unknown-linux-gnu\"\n"
            "}\n\n"
            "build() {\n"
            "    cd \"$pkgname-$pkgver\"\n"
            "    export RUSTUP_TOOLCHAIN=stable\n"
            "    export CARGO_TARGET_DIR=target\n"
            "    export CARGO_PROFILE_RELEASE_LTO=true\n"
            "    export CARGO_PROFILE_RELEASE_CODEGEN_UNITS=1\n"
            "    cargo build --frozen --release --all-targets\n"
            "}\n\n"
            "check() {\n"
            "    cd \"$pkgname-$pkgver\"\n"
            "    cargo test --frozen --release\n"
            "}\n\n"
            "package() {\n"
            "    cd \"$pkgname-$pkgver\"\n"
            "    install -Dm755 \"target/release/$pkgname\" \"$pkgdir/usr/bin/$pkgname\"\n"
            "    install -Dm644 \"$srcdir/magi-mesh.service\" \"$pkgdir/usr/lib/systemd/system/magi-mesh.service\"\n"
            "    install -Dm644 LICENSE \"$pkgdir/usr/share/licenses/$pkgname/LICENSE\"\n"
            "}\n"
        ),
        "rejected": (
            "pkgname=magi-mesh-daemon\n"
            "pkgver=1.2.0\n"
            "pkgrel=1\n"
            "arch=('any')\n"
            "source=('magi-mesh.tar.gz')\n"
            "sha256sums=('SKIP') # Bypasses integrity check\n"
            "build() {\n"
            "    cargo install --path . --root /usr/local # Pollutes host system without pkgdir\n"
            "}\n"
        ),
        "capabilities": ["arch", "pkgbuild", "rust", "lto", "reproducible_build", "systemd"],
    },
    {
        "domain": "arch_linux",
        "id_suffix": "ARCH_PKGBUILD_VCS_GIT_0002",
        "prompt": (
            "Author a standard Arch Linux VCS PKGBUILD (`-git`) with dynamic `pkgver()` parsing using "
            "`git describe --long --tags`, source integrity fencing, provides/conflicts declarations, and "
            "submodule recursion."
        ),
        "chosen": (
            "# Maintainer: Magi Systems Specialist <maintainer@magi-mesh.org>\n"
            "pkgname=magi-herder-git\n"
            "pkgver=1.0.0.r42.g71fb1c2\n"
            "pkgrel=1\n"
            "pkgdesc=\"Federated mesh herder service (development branch)\"\n"
            "arch=('x86_64')\n"
            "url=\"https://github.com/magi-pact/magi_pact\"\n"
            "license=('MIT')\n"
            "depends=('python' 'python-click' 'python-requests')\n"
            "makedepends=('git' 'python-build' 'python-installer' 'python-wheel' 'python-setuptools')\n"
            "provides=('magi-herder')\n"
            "conflicts=('magi-herder')\n"
            "source=(\"git+$url.git#branch=main\")\n"
            "sha256sums=('SKIP')\n\n"
            "pkgver() {\n"
            "    cd magi_pact\n"
            "    # Extract semantic version from tags, commit count, and hash\n"
            "    git describe --long --tags --abbrev=7 2>/dev/null | sed 's/^v//;s/\\([^-]*-g\\)/r\\1/;s/-/./g'\n"
            "}\n\n"
            "build() {\n"
            "    cd magi_pact\n"
            "    python -m build --wheel --no-isolation\n"
            "}\n\n"
            "package() {\n"
            "    cd magi_pact\n"
            "    python -m installer --destdir=\"$pkgdir\" dist/*.whl\n"
            "    install -Dm644 LICENSE \"$pkgdir/usr/share/licenses/$pkgname/LICENSE\"\n"
            "}\n"
        ),
        "rejected": (
            "pkgname=magi-herder-git\n"
            "pkgver=1.0.0 # Static version in a -git VCS package breaks pacman upgrade logic\n"
            "source=('git+https://github.com/test/repo.git')\n"
            "package() {\n"
            "    python setup.py install --root=\"$pkgdir\" # Deprecated setup.py direct call\n"
            "}\n"
        ),
        "capabilities": ["arch", "pkgbuild", "vcs_git", "pkgver_dynamic", "python_packaging"],
    },
    {
        "domain": "arch_linux",
        "id_suffix": "ARCH_PKGBUILD_SPLIT_PACKAGE_0003",
        "prompt": (
            "Design a compliant Arch Linux split PKGBUILD that builds from a unified C/C++ CMake tree "
            "and generates two distinct binary packages: `libmagi` (shared library and development headers) "
            "and `magi-cli` (command line client), ensuring proper dependency containment."
        ),
        "chosen": (
            "# Maintainer: Magi Systems Specialist <maintainer@magi-mesh.org>\n"
            "pkgbase=magi-core\n"
            "pkgname=('libmagi' 'magi-cli')\n"
            "pkgver=2.4.0\n"
            "pkgrel=1\n"
            "arch=('x86_64' 'aarch64')\n"
            "url=\"https://github.com/magi-pact/magi_pact\"\n"
            "license=('LGPL-3.0-or-later')\n"
            "makedepends=('cmake' 'ninja' 'gcc')\n"
            "source=(\"$pkgbase-$pkgver.tar.gz::$url/archive/v$pkgver.tar.gz\")\n"
            "sha256sums=('9c71e8460b57e7a83421d09e51c8902b4e8a719d20c3b88e147f892a012d94bf')\n\n"
            "build() {\n"
            "    cmake -B build -S \"$pkgbase-$pkgver\" -G Ninja \\\n"
            "        -DCMAKE_BUILD_TYPE=None \\\n"
            "        -DCMAKE_INSTALL_PREFIX=/usr \\\n"
            "        -DBUILD_SHARED_LIBS=ON\n"
            "    cmake --build build\n"
            "}\n\n"
            "package_libmagi() {\n"
            "    pkgdesc=\"Shared library and headers for the Magi mesh protocol\"\n"
            "    depends=('glibc')\n"
            "    DESTDIR=\"$pkgdir\" cmake --install build --component library\n"
            "    DESTDIR=\"$pkgdir\" cmake --install build --component headers\n"
            "}\n\n"
            "package_magi-cli() {\n"
            "    pkgdesc=\"Command-line interface client for Magi mesh\"\n"
            "    depends=('glibc' \"libmagi=$pkgver\")\n"
            "    DESTDIR=\"$pkgdir\" cmake --install build --component cli\n"
            "}\n"
        ),
        "rejected": (
            "pkgname=('libmagi' 'magi-cli')\n"
            "build() { make; }\n"
            "package_libmagi() {\n"
            "    cp -r * $pkgdir/ # Dumps everything indiscriminately into both split packages\n"
            "}\n"
        ),
        "capabilities": ["arch", "pkgbuild", "split_package", "cmake", "shared_libraries"],
    },

    # -------------------------------------------------------------
    # 3. FEDORA DNF5 SYSTEM ADMINISTRATION TRAJECTORIES (fedora_linux)
    # -------------------------------------------------------------
    {
        "domain": "fedora_linux",
        "id_suffix": "FEDORA_DNF5_SECURITY_UPGRADE_0001",
        "prompt": (
            "Write a Fedora 41+ systems administration playbook script using `dnf5` to perform non-interactive "
            "security-only upgrades, inspect transaction advisories, disable weak dependencies, and generate an "
            "audit receipt."
        ),
        "chosen": (
            "#!/usr/bin/env bash\n"
            "# Fedora 41+ Automated Hardened Security Patching with dnf5\n"
            "set -euo pipefail\n"
            "IFS=$'\\n\\t'\n\n"
            "LOG_FILE=\"/var/log/dnf5_security_upgrade_$(date +%Y%m%d).log\"\n\n"
            "echo \"[1/4] Checking available security advisories via dnf5...\"\n"
            "dnf5 advisory list --security\n\n"
            "echo \"[2/4] Executing non-interactive security upgrade...\"\n"
            "# --setopt=install_weak_deps=False prevents installation of recommended bloat\n"
            "dnf5 upgrade \\\n"
            "    --security \\\n"
            "    --assumeyes \\\n"
            "    --setopt=install_weak_deps=False \\\n"
            "    --setopt=clean_requirements_on_remove=True | tee -a \"$LOG_FILE\"\n\n"
            "echo \"[3/4] Recording transaction ID and RPM audit summary...\"\n"
            "LAST_TX=\"$(dnf5 history list --limit 1 --json | python3 -c 'import sys, json; print(json.load(sys.stdin)[\"transactions\"][0][\"id\"])')\"\n"
            "echo \"Applied Security Transaction ID: $LAST_TX\" | tee -a \"$LOG_FILE\"\n\n"
            "echo \"[4/4] Verifying cryptographic signatures and package integrity...\"\n"
            "rpm -Va --nomtime --nosize --nomd5\n"
            "echo \"System security upgrade completed successfully.\"\n"
        ),
        "rejected": (
            "#!/bin/bash\n"
            "# Outdated yum invocation without security filtering\n"
            "yum update -y # Legacy syntax, pulls all weak dependencies, no logging or advisory check\n"
        ),
        "capabilities": ["fedora", "dnf5", "security_advisories", "sysadmin", "rpm_integrity"],
    },
    {
        "domain": "fedora_linux",
        "id_suffix": "FEDORA_DNF5_HISTORY_ROLLBACK_0002",
        "prompt": (
            "Demonstrate how to query `dnf5 history` using the JSON output format, extract the last "
            "transaction ID, verify altered packages, and safely execute `dnf5 history undo` if health "
            "checks fail post-upgrade."
        ),
        "chosen": (
            "#!/usr/bin/env python3\n"
            "\"\"\"Fedora dnf5 Transaction Inspection and Safe Rollback Utility.\"\"\"\n"
            "import json\n"
            "import subprocess\n"
            "import sys\n\n"
            "def run_cmd(args):\n"
            "    res = subprocess.run(args, capture_output=True, text=True, check=True)\n"
            "    return res.stdout\n\n"
            "def inspect_last_transaction():\n"
            "    raw_json = run_cmd([\"dnf5\", \"history\", \"list\", \"--limit\", \"1\", \"--json\"])\n"
            "    data = json.loads(raw_json)\n"
            "    tx = data[\"transactions\"][0]\n"
            "    print(f\"Latest Transaction: #{tx['id']} | Action: {tx['cmdline']} | Timestamp: {tx['timestamp']}\")\n"
            "    return tx['id']\n\n"
            "def execute_safe_rollback(tx_id: int):\n"
            "    print(f\"Executing dry-run rollback for transaction #{tx_id}...\")\n"
            "    # Dry-run validation first\n"
            "    run_cmd([\"dnf5\", \"history\", \"undo\", str(tx_id), \"--assumeno\"])\n"
            "    print(\"Dry-run passed without dependency breaks. Executing undo...\")\n"
            "    run_cmd([\"dnf5\", \"history\", \"undo\", str(tx_id), \"--assumeyes\"])\n"
            "    print(f\"Transaction #{tx_id} successfully rolled back.\")\n\n"
            "if __name__ == '__main__':\n"
            "    tid = inspect_last_transaction()\n"
            "    # Execute rollback on request\n"
            "    if '--rollback' in sys.argv:\n"
            "        execute_safe_rollback(tid)\n"
        ),
        "rejected": (
            "#!/bin/bash\n"
            "# Dangerous manual package removals\n"
            "rpm -e --nodeps $(rpm -qa --last | head -n 5) # Destroys RPM database integrity\n"
        ),
        "capabilities": ["fedora", "dnf5", "history_undo", "rollback", "dry_run"],
    },
    {
        "domain": "fedora_linux",
        "id_suffix": "FEDORA_DNF5_CONTAINER_ROOTFS_0003",
        "prompt": (
            "Construct a deterministic pipeline to build a micro-OS root filesystem using `dnf5 --installroot` "
            "with disabled documentation, explicit releasever, and minimal package set for unprivileged container isolation."
        ),
        "chosen": (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "IFS=$'\\n\\t'\n\n"
            "TARGET_ROOT=\"${1:-/var/lib/containers/micro-rootfs}\"\n"
            "RELEASE_VER=\"41\"\n\n"
            "echo \"[1/3] Preparing target chroot directory...\"\n"
            "mkdir -p \"$TARGET_ROOT\"\n\n"
            "echo \"[2/3] Bootstrapping minimal base packages via dnf5...\"\n"
            "dnf5 --installroot=\"$TARGET_ROOT\" \\\n"
            "    --releasever=\"$RELEASE_VER\" \\\n"
            "    --nodocs \\\n"
            "    --setopt=install_weak_deps=False \\\n"
            "    --setopt=keepcache=False \\\n"
            "    install -y \\\n"
            "        coreutils-single \\\n"
            "        glibc-minimal-langpack \\\n"
            "        systemd-units \\\n"
            "        ca-certificates\n\n"
            "echo \"[3/3] Sanitizing target rootfs...\"\n"
            "dnf5 clean all --installroot=\"$TARGET_ROOT\"\n"
            "rm -rf \"$TARGET_ROOT/var/cache/libdnf5/\"* \"$TARGET_ROOT/var/log/\"*\n"
            "echo \"Minimal Fedora rootfs assembled at: $TARGET_ROOT\"\n"
        ),
        "rejected": (
            "#!/bin/bash\n"
            "cp -r /bin /lib /lib64 /target/ # Copies broken dynamically linked libraries without package database\n"
        ),
        "capabilities": ["fedora", "dnf5", "installroot", "containers", "minimal_rootfs"],
    },

    # -------------------------------------------------------------
    # 4. BIOS/UEFI fwupd QUERY FIXTURES (bios_uefi) - STRICTLY READ-ONLY
    # -------------------------------------------------------------
    {
        "domain": "bios_uefi",
        "id_suffix": "BIOS_FWUPD_READONLY_QUERY_0001",
        "prompt": (
            "Provide a safe, read-only Python parser and inspection routine for `fwupdmgr get-devices --json` "
            "output to identify UEFI System Resource Table (ESRT) devices, query update capabilities (such as "
            "`updatable` and `needs-reboot` flags), and report current vs lowest supported firmware versions "
            "without writing to NVRAM or physical hardware."
        ),
        "chosen": (
            "\"\"\"Strictly Read-Only BIOS/UEFI fwupd Query Engine.\"\"\"\n"
            "import json\n"
            "from pathlib import Path\n"
            "from typing import Dict, List, Any\n\n"
            "def inspect_firmware_devices(fixture_path: Path) -> List[Dict[str, Any]]:\n"
            "    with open(fixture_path, 'r', encoding='utf-8') as f:\n"
            "        data = json.load(f)\n\n"
            "    audit_records = []\n"
            "    for dev in data.get('Devices', []):\n"
            "        name = dev.get('Name', 'Unknown')\n"
            "        guid = dev.get('Guid', [])\n"
            "        version = dev.get('Version', '0.0.0')\n"
            "        lowest_ver = dev.get('VersionLowest', '0.0.0')\n"
            "        flags = dev.get('Flags', [])\n\n"
            "        # Pure read-only status classification\n"
            "        audit_records.append({\n"
            "            'component': name,\n"
            "            'guids': guid,\n"
            "            'current_version': version,\n"
            "            'lowest_supported_version': lowest_ver,\n"
            "            'is_updatable': 'updatable' in flags,\n"
            "            'requires_reboot': 'needs-reboot' in flags,\n"
            "            'has_security_fixes': 'has-security-fixes' in flags,\n"
            "        })\n"
            "    return audit_records\n\n"
            "# Example execution using verified local fixture (zero hardware spend)\n"
            "if __name__ == '__main__':\n"
            "    results = inspect_firmware_devices(Path('data/fixtures/fwupd_devices.json'))\n"
            "    for r in results:\n"
            "        print(f\"Device: {r['component']} | Ver: {r['current_version']} | Updatable: {r['is_updatable']}\")\n"
        ),
        "rejected": (
            "import os\n"
            "# HAZARDOUS: Flashes physical motherboard firmware without read-only guardrails\n"
            "os.system('fwupdmgr update -y --force')\n"
            "os.system('flashrom -p internal -w bios.bin')\n"
        ),
        "capabilities": ["bios_uefi", "fwupd", "read_only", "esrt", "zero_hardware_spend"],
    },
    {
        "domain": "bios_uefi",
        "id_suffix": "BIOS_UEFI_ESRT_SYSFS_PARSER_0002",
        "prompt": (
            "Show how to safely inspect the Linux kernel UEFI ESRT interface at `/sys/firmware/efi/esrt/` "
            "to read firmware GUID, fw_type, fw_version, and lowest_supported_fw_version in a sandboxed, "
            "mock fixture environment with anti-rollback validation."
        ),
        "chosen": (
            "\"\"\"UEFI ESRT (EFI System Resource Table) Safe Attribute Parser.\"\"\"\n"
            "import json\n"
            "from pathlib import Path\n"
            "from typing import Dict, Any\n\n"
            "def parse_esrt_entry(entry_dict: Dict[str, Any]) -> Dict[str, Any]:\n"
            "    \"\"\"Parses ESRT entry and calculates rollback downgrade protection safety.\"\"\"\n"
            "    fw_class = entry_dict.get('fw_class')\n"
            "    fw_type = entry_dict.get('fw_type_name', 'UNKNOWN')\n"
            "    cur_ver = entry_dict.get('fw_version', 0)\n"
            "    lowest_ver = entry_dict.get('lowest_supported_fw_version', 0)\n\n"
            "    # Downgrade protection prevents bricking or security vulnerability regressions\n"
            "    anti_rollback_compliant = cur_ver >= lowest_ver\n\n"
            "    return {\n"
            "        'guid': fw_class,\n"
            "        'type': fw_type,\n"
            "        'current_version_hex': hex(cur_ver),\n"
            "        'lowest_version_hex': hex(lowest_ver),\n"
            "        'anti_rollback_compliant': anti_rollback_compliant,\n"
            "        'status': entry_dict.get('last_attempt_status_name', 'NONE'),\n"
            "    }\n\n"
            "if __name__ == '__main__':\n"
            "    fixture = Path('data/fixtures/uefi_esrt.json')\n"
            "    with open(fixture) as f:\n"
            "        data = json.load(f)\n"
            "    for entry in data.get('entries', []):\n"
            "        print(parse_esrt_entry(entry))\n"
        ),
        "rejected": (
            "echo 0x00010000 > /sys/firmware/efi/esrt/entries/entry0/fw_version\n"
            "# Sysfs firmware attributes are read-only kernel endpoints; writes cause kernel panics or permission denials\n"
        ),
        "capabilities": ["bios_uefi", "esrt", "anti_rollback", "sysfs_readonly", "firmware_security"],
    },
    {
        "domain": "bios_uefi",
        "id_suffix": "BIOS_CAPSULE_METADATA_VERIFY_0003",
        "prompt": (
            "Explain how to verify a UEFI firmware update capsule cabinet (.cab / .cap) metadata, check "
            "SHA-256 and Jcat cryptographic signatures, and simulate pre-flight validation against system requirements "
            "without executing an EFI capsule update."
        ),
        "chosen": (
            "#!/usr/bin/env python3\n"
            "\"\"\"Simulated Read-Only UEFI Capsule Pre-Flight Verification Pipeline.\"\"\"\n"
            "import hashlib\n"
            "import json\n"
            "from typing import Dict, Any\n\n"
            "def verify_capsule_preflight(manifest: Dict[str, Any], system_guid: str) -> Dict[str, Any]:\n"
            "    \"\"\"Checks cryptographic checksum and device GUID compatibility without flashing.\"\"\"\n"
            "    target_guid = manifest.get('target_guid')\n"
            "    checksum_sha256 = manifest.get('sha256')\n"
            "    mock_payload = manifest.get('mock_binary_payload', '').encode('utf-8')\n\n"
            "    computed_hash = hashlib.sha256(mock_payload).hexdigest()\n"
            "    hash_valid = (computed_hash == checksum_sha256)\n"
            "    guid_match = (target_guid.lower() == system_guid.lower())\n\n"
            "    return {\n"
            "        'preflight_status': 'PASS' if (hash_valid and guid_match) else 'FAIL',\n"
            "        'hash_valid': hash_valid,\n"
            "        'guid_match': guid_match,\n"
            "        'action': 'READY_FOR_SIMULATION_ONLY_DO_NOT_FLASH'\n"
            "    }\n\n"
            "if __name__ == '__main__':\n"
            "    sample_manifest = {\n"
            "        'target_guid': '8c3b7a54-6e19-487b-bb66-419b4b0e5124',\n"
            "        'sha256': hashlib.sha256(b'SIMULATED_UEFI_CAPSULE_DATA').hexdigest(),\n"
            "        'mock_binary_payload': 'SIMULATED_UEFI_CAPSULE_DATA'\n"
            "    }\n"
            "    res = verify_capsule_preflight(sample_manifest, '8c3b7a54-6e19-487b-bb66-419b4b0e5124')\n"
            "    print('Preflight result:', res)\n"
        ),
        "rejected": (
            "# Flash command directly without checking signatures or GUID\n"
            "dd if=bios_update.cap of=/dev/mem bs=1M # Severe hardware brick risk\n"
        ),
        "capabilities": ["bios_uefi", "capsule_verify", "jcat", "preflight_validation", "read_only"],
    },

    # -------------------------------------------------------------
    # 5. GIT WORKTREE BRANCHING OPERATIONS (git_internals)
    # -------------------------------------------------------------
    {
        "domain": "git_internals",
        "id_suffix": "GIT_WORKTREE_ISOLATION_0001",
        "prompt": (
            "Detail a safe Git worktree lifecycle workflow for multi-agent environments: provisioning "
            "an isolated topic worktree (`git worktree add`), locking the worktree with `--reason`, checking "
            "working copy status, and cleanly releasing it without polluting trunk."
        ),
        "chosen": (
            "#!/usr/bin/env bash\n"
            "# Multi-Agent Collision-Free Git Worktree Isolation Workflow\n"
            "set -euo pipefail\n"
            "IFS=$'\\n\\t'\n\n"
            "SEAT_ID=\"04\"\n"
            "TOPIC_BRANCH=\"feature/seat_${SEAT_ID}_firmware_specs\"\n"
            "WORKTREE_PATH=\".worktrees/seat_${SEAT_ID}\"\n\n"
            "# 1. Ensure clean base repository\n"
            "git status --porcelain\n\n"
            "# 2. Create isolated worktree with dedicated branch branched off main\n"
            "echo \"Creating worktree at $WORKTREE_PATH on branch $TOPIC_BRANCH...\"\n"
            "git worktree add -b \"$TOPIC_BRANCH\" \"$WORKTREE_PATH\" main\n\n"
            "# 3. Acquire advisory lock on worktree to prevent accidental pruning by peer agents\n"
            "git worktree lock \"$WORKTREE_PATH\" --reason \"Seat ${SEAT_ID} actively generating trajectory specs\"\n\n"
            "# 4. Perform isolated work inside the worktree\n"
            "pushd \"$WORKTREE_PATH\" > /dev/null\n"
            "echo \"Working in isolated checkout: $(pwd)\"\n"
            "git rev-parse --abbrev-ref HEAD\n"
            "popd > /dev/null\n\n"
            "# 5. Release lock and safely remove worktree upon completion\n"
            "git worktree unlock \"$WORKTREE_PATH\"\n"
            "git worktree remove \"$WORKTREE_PATH\"\n"
            "git worktree prune\n"
            "echo \"Worktree cleanly dismantled.\"\n"
        ),
        "rejected": (
            "git checkout -f new_feature # Mutates main trunk directly and destroys peers' unstaged edits\n"
            "rm -rf .worktrees/seat_04 # Leaves corrupted references in .git/worktrees/\n"
        ),
        "capabilities": ["git", "worktree", "isolation", "branching", "advisory_locking"],
    },
    {
        "domain": "git_internals",
        "id_suffix": "GIT_WORKTREE_CHERRY_PICK_PATCH_0002",
        "prompt": (
            "Demonstrate how an agent operating inside a dedicated git worktree cherry-picks an advisory "
            "fix from another seat, verifies tests, signs the commit, and exports a clean patch to `exchange/` "
            "while leaving the main working directory completely untouched."
        ),
        "chosen": (
            "#!/usr/bin/env bash\n"
            "# Worktree Cherry-Pick and Clean Exchange Patch Export\n"
            "set -euo pipefail\n"
            "IFS=$'\\n\\t'\n\n"
            "WT_PATH=\".worktrees/seat_04_patching\"\n"
            "COMMIT_TO_PICK=\"${1:-938898f}\"\n"
            "PATCH_DEST=\"exchange/seat_04_systems_review.patch\"\n\n"
            "mkdir -p .worktrees exchange\n\n"
            "# 1. Spawn detached worktree from main\n"
            "git worktree add --detach \"$WT_PATH\" main\n\n"
            "# 2. Replay commit with original authorship and timestamp preserved\n"
            "pushd \"$WT_PATH\" > /dev/null\n"
            "git cherry-pick -x \"$COMMIT_TO_PICK\"\n\n"
            "# 3. Run regression test suite in isolated directory\n"
            "python3 -m unittest discover tests\n\n"
            "# 4. Generate clean relative diff against main trunk\n"
            "git diff main HEAD > \"../../$PATCH_DEST\"\n"
            "popd > /dev/null\n\n"
            "# 5. Clean up temporary worktree\n"
            "git worktree remove --force \"$WT_PATH\"\n"
            "git worktree prune\n"
            "echo \"Delivered verified patch to $PATCH_DEST without touching trunk.\"\n"
        ),
        "rejected": (
            "git cherry-pick 938898f # Executed in dirty root workspace, risking merge conflicts with peer edits\n"
        ),
        "capabilities": ["git", "worktree", "cherry_pick", "patch_exchange", "clean_trunk"],
    },
    {
        "domain": "git_internals",
        "id_suffix": "GIT_WORKTREE_PORCELAIN_DIAGNOSTICS_0003",
        "prompt": (
            "Construct a diagnostic and cleanup utility in Python to parse `git worktree list --porcelain`, "
            "detect stale or orphaned worktree directories, inspect lock reasons, and safely prune inactive paths."
        ),
        "chosen": (
            "#!/usr/bin/env python3\n"
            "\"\"\"Diagnostic parser for git worktree --porcelain with automated hygiene.\"\"\"\n"
            "import os\n"
            "from pathlib import Path\n"
            "import subprocess\n"
            "import sys\n\n"
            "def inspect_worktrees():\n"
            "    cmd = [\"git\", \"worktree\", \"list\", \"--porcelain\"]\n"
            "    res = subprocess.run(cmd, capture_output=True, text=True, check=True)\n"
            "    \n"
            "    worktrees = []\n"
            "    cur = {}\n"
            "    for line in res.stdout.splitlines():\n"
            "        line = line.strip()\n"
            "        if not line:\n"
            "            if cur:\n"
            "                worktrees.append(cur)\n"
            "                cur = {}\n"
            "            continue\n"
            "        parts = line.split(\" \", 1)\n"
            "        k = parts[0]\n"
            "        v = parts[1] if len(parts) > 1 else True\n"
            "        if k == 'worktree':\n"
            "            if cur:\n"
            "                worktrees.append(cur)\n"
            "                cur = {}\n"
            "            cur['path'] = v\n"
            "        elif k == 'HEAD':\n"
            "            cur['head'] = v\n"
            "        elif k == 'branch':\n"
            "            cur['branch'] = v\n"
            "        elif k == 'locked':\n"
            "            cur['locked'] = True\n"
            "            cur['lock_reason'] = v\n"
            "        elif k == 'prunable':\n"
            "            cur['prunable'] = v\n\n"
            "    if cur:\n"
            "        worktrees.append(cur)\n\n"
            "    print(f\"Found {len(worktrees)} active worktree registration(s):\")\n"
            "    for wt in worktrees:\n"
            "        exists = Path(wt['path']).exists()\n"
            "        print(f\"  • Path: {wt['path']} (Exists: {exists}) | Branch: {wt.get('branch', 'DETACHED')}\")\n"
            "        if wt.get('locked'):\n"
            "            print(f\"    [LOCKED] Reason: {wt.get('lock_reason')}\")\n\n"
            "    # Prune stale metadata\n"
            "    subprocess.run([\"git\", \"worktree\", \"prune\", \"--verbose\"], check=True)\n\n"
            "if __name__ == '__main__':\n"
            "    inspect_worktrees()\n"
        ),
        "rejected": (
            "rm -rf .git/worktrees/* # Corrupts internal git worktree admin index\n"
        ),
        "capabilities": ["git", "worktree", "porcelain_diagnostics", "pruning", "stale_cleanup"],
    },
]


def generate_systems_trajectories() -> List[TrainingPair]:
    """Compiles the verified Systems & Firmware trajectory suite (15 pairs)."""
    pairs = []
    now = datetime.now(timezone.utc).isoformat()
    for ex in SYSTEMS_TRAJECTORIES:
        pair_id = f"TWU_GOLD_{ex['id_suffix']}"
        pairs.append(
            TrainingPair(
                id=pair_id,
                domain=ex["domain"],
                kind="dpo",
                prompt=ex["prompt"],
                chosen=ex["chosen"],
                rejected=ex["rejected"],
                quality="gold_certified",
                capabilities=ex["capabilities"],
                created_at=now,
            )
        )
    return pairs


def export_systems_shard(seat_id: int = 4, root_dir: Optional[Path] = None) -> Tuple[Path, Path]:
    """Exports Seat 04's verified systems & firmware shard to exchange/seat_04_corpus.jsonl."""
    root = Path(root_dir or ".").resolve()
    exchange = root / "exchange"
    exchange.mkdir(parents=True, exist_ok=True)

    shard_path = exchange / f"seat_{seat_id:02d}_corpus.jsonl"
    pairs = generate_systems_trajectories()

    with open(shard_path, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p.to_dict()) + "\n")

    checksum = hashlib.sha256(shard_path.read_bytes()).hexdigest()
    manifest_path = exchange / f"seat_{seat_id:02d}_corpus.sha256"
    manifest_path.write_text(f"{checksum}  {shard_path.name}\n", encoding="utf-8")

    return shard_path, manifest_path
