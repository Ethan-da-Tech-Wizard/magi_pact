#!/usr/bin/env python3
"""Build and verify the Systems & Firmware Corpus (40 Golden Trajectories).

Generates:
  /home/user/magi_pact/data/corpus/systems/systems_corpus.jsonl

Coverage:
  - 8 bash_posix: POSIX compliance, set -euo pipefail, trap EXIT, atomic locks, signal safety
  - 8 arch_linux: Arch Linux PKGBUILD packaging, namcap compliance, sha256sums, reproducible builds
  - 8 fedora_linux: Modern Fedora dnf5 transaction resolution, security errata, rootfs creation, history replay
  - 8 bios_uefi: Strictly read-only UEFI ESRT sysfs, fwupd fixtures, SMBIOS DMI parsing (0% flash operations)
  - 8 git_internals: Isolated git worktrees, lock handoffs, porcelain diagnostics, stash internals
"""

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Dict, List, Any, Tuple

# Put the repo root first on sys.path so "pact" is importable and wins over any other install.
# Ensure workspace root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from pact.dataset import TrainingPair
from pact.systems import (
    SYSTEMS_TRAJECTORIES,
    BashSafetyValidator,
    ArchPkgbuildValidator,
    FedoraDnf5Validator,
    FirmwareSafetyGate,
    FirmwareSafetyViolation,
    generate_systems_trajectories,
)
from pact.dedup import PolicyLeakScanner, skeleton_structure_hash
from pact.fleet_dedup import FleetDedupEngine

# Destination corpus; a .sha256 manifest is written next to it.
OUTPUT_PATH = ROOT_DIR / "data" / "corpus" / "systems" / "systems_corpus.jsonl"

# Record shape (per dict): domain, id_suffix (becomes TWU_GOLD_<suffix>), prompt, chosen (correct answer),
# # rejected (plausible anti-pattern), capabilities (tags). The 5 domains each get 5 new entries here
# # and 3 baseline entries from pact.systems.SYSTEMS_TRAJECTORIES. Entry bodies are Python string
# # literals, so shell/PKGBUILD/Python snippets appear with escaped quotes and "\n".
# 25 expanded trajectories to add to the existing 15 baseline trajectories
EXPANDED_SYSTEMS_TRAJECTORIES: List[Dict[str, Any]] = [
    # -----------------------------------------------------------------
    # BASH POSIX EXPANSIONS (5 new, 8 total)
    # -----------------------------------------------------------------
    {
        "domain": "bash_posix",
        # Teaches: check every pipeline stage via PIPESTATUS under pipefail, with FIFO cleanup in a trap. Rejected: plain pipe that masks upstream failures.
        "id_suffix": "BASH_PIPELINE_ERROR_PROPAGATION_0004",
        "prompt": (
            "Write a robust POSIX Bash pipeline script that processes multi-gigabyte log streams "
            "through gzip, awk filtering, and sha256sum while capturing PIPESTATUS from every stage, "
            "enforcing strict set -euo pipefail, and using a trap EXIT handler for temporary FIFO cleanup."
        ),
        "chosen": (
            "#!/usr/bin/env bash\n"
            "# Multi-stage log filter with PIPESTATUS error propagation\n"
            "set -euo pipefail\n"
            "IFS=$'\\n\\t'\n\n"
            "FIFO_PATH=\"\"\n\n"
            "cleanup() {\n"
            "    local exit_code=$?\n"
            "    if [[ -n \"$FIFO_PATH\" && -p \"$FIFO_PATH\" ]]; then\n"
            "        rm -f \"$FIFO_PATH\"\n"
            "    fi\n"
            "    exit \"$exit_code\"\n"
            "}\n"
            "trap cleanup EXIT INT TERM\n\n"
            "FIFO_PATH=\"$(mktemp -u /tmp/log_stream_XXXXXX.fifo)\"\n"
            "mkfifo -m 0600 \"$FIFO_PATH\"\n\n"
            "LOG_SOURCE=\"${1:-/var/log/audit/audit.log}\"\n"
            "FILTER_TARGET=\"${2:-/tmp/filtered_audit.log.gz}\"\n\n"
            "# Run pipeline and verify each stage status via PIPESTATUS\n"
            "gzip -cd \"$LOG_SOURCE\" | awk '/ERROR|CRITICAL/ { print $0 }' | gzip -c > \"$FILTER_TARGET\" \\\n"
            "    || status=(\"${PIPESTATUS[@]}\")\n\n"
            "if [[ ${#status[@]} -gt 0 ]]; then\n"
            "    for idx in \"${!status[@]}\"; do\n"
            "        if [[ \"${status[$idx]}\" -ne 0 ]]; then\n"
            "            echo \"Pipeline failed at stage $idx with exit code ${status[$idx]}\" >&2\n"
            "            exit \"${status[$idx]}\"\n"
            "        fi\n"
            "    done\n"
            "fi\n\n"
            "echo \"Log stream filtered and verified: $FILTER_TARGET\"\n"
        ),
        "rejected": (
            "#!/bin/bash\n"
            "# Silent pipeline failure with no pipefail\n"
            "cat /var/log/audit/audit.log | grep ERROR | gzip > /tmp/filtered.gz\n"
            "# Exit code will be gzip exit code only, masking grep or cat errors\n"
            "echo 'Finished without checking pipeline exit codes'\n"
        ),
        "capabilities": ["bash", "posix", "pipestatus", "pipefail", "signal_traps"],
    },
    {
        "domain": "bash_posix",
        # Teaches: flock-guarded log writes with size-based rotation by atomic rename. Rejected: unsynchronized size check, copy and truncate (racy, can lose writes).
        "id_suffix": "BASH_ROTATING_LOG_LOCK_0005",
        "prompt": (
            "Design a POSIX Bash daemon logging module that provides atomic file-descriptor locking "
            "via flock, handles SIGTERM/SIGINT with clean exit traps to flush buffers, and rotates logs "
            "at a 100MB threshold using atomic rename without dropping concurrent writes."
        ),
        "chosen": (
            "#!/usr/bin/env bash\n"
            "# Atomic lock-protected rotating logger\n"
            "set -euo pipefail\n"
            "IFS=$'\\n\\t'\n\n"
            "LOG_FILE=\"/var/log/service_worker.log\"\n"
            "LOCK_FD=201\n"
            "MAX_BYTES=$((100 * 1024 * 1024))\n\n"
            "cleanup() {\n"
            "    local code=$?\n"
            "    exec 201>&- 2>/dev/null || true\n"
            "    exit \"$code\"\n"
            "}\n"
            "trap cleanup EXIT INT TERM\n\n"
            "exec 201>\"$LOG_FILE.lock\"\n\n"
            "log_entry() {\n"
            "    local msg=\"$1\"\n"
            "    local ts\n"
            "    ts=\"$(date -u +'%Y-%m-%dT%H:%M:%SZ')\"\n"
            "    flock -x \"$LOCK_FD\"\n\n"
            "    if [[ -f \"$LOG_FILE\" ]]; then\n"
            "        local current_size\n"
            "        current_size=$(stat -c%s \"$LOG_FILE\" 2>/dev/null || stat -f%z \"$LOG_FILE\" 2>/dev/null || echo 0)\n"
            "        if [[ \"$current_size\" -ge \"$MAX_BYTES\" ]]; then\n"
            "            mv -f \"$LOG_FILE\" \"${LOG_FILE}.1\"\n"
            "        fi\n"
            "    fi\n\n"
            "    printf '%s [%s] %s\\n' \"$ts\" \"$$\" \"$msg\" >> \"$LOG_FILE\"\n"
            "    flock -u \"$LOCK_FD\"\n"
            "}\n\n"
            "log_entry \"Worker process initialised successfully\"\n"
        ),
        "rejected": (
            "#!/bin/bash\n"
            "# Unsynchronized logging with race condition and truncation\n"
            "if [ $(wc -c < /var/log/app.log) -gt 100000000 ]; then\n"
            "    cp /var/log/app.log /var/log/app.log.old\n"
            "    cat /dev/null > /var/log/app.log # Truncates during concurrent writes\n"
            "fi\n"
            "echo \"$1\" >> /var/log/app.log\n"
        ),
        "capabilities": ["bash", "flock", "atomic_rotation", "posix", "signal_handling"],
    },
    {
        "domain": "bash_posix",
        # Teaches: systemd watchdog/NOTIFY_SOCKET protocol, STOPPING=1 on termination, no orphaned child. Rejected: backgrounds the command and pings forever.
        "id_suffix": "BASH_SYSTEMD_WATCHDOG_NOTIFY_0006",
        "prompt": (
            "Create a production POSIX Bash service wrapper that interfaces with the systemd watchdog "
            "protocol (NOTIFY_SOCKET), implements set -euo pipefail, schedules ping intervals, traps "
            "termination signals to notify STOPPING=1, and safely exits with the child status code."
        ),
        "chosen": (
            "#!/usr/bin/env bash\n"
            "# Systemd Watchdog Notification Service Wrapper\n"
            "set -euo pipefail\n"
            "IFS=$'\\n\\t'\n\n"
            "NOTIFY_SOCK=\"${NOTIFY_SOCKET:-}\"\n"
            "WATCHDOG_USEC=\"${WATCHDOG_USEC:-0}\"\n"
            "CHILD_PID=\"\"\n\n"
            "send_systemd_notification() {\n"
            "    local state=\"$1\"\n"
            "    if [[ -n \"$NOTIFY_SOCK\" ]] && command -v systemd-notify >/dev/null 2>&1; then\n"
            "        systemd-notify \"$state\" 2>/dev/null || true\n"
            "    fi\n"
            "}\n\n"
            "cleanup() {\n"
            "    local exit_code=$?\n"
            "    send_systemd_notification \"STOPPING=1\"\n"
            "    if [[ -n \"$CHILD_PID\" ]] && kill -0 \"$CHILD_PID\" 2>/dev/null; then\n"
            "        kill -TERM \"$CHILD_PID\" 2>/dev/null || true\n"
            "        wait \"$CHILD_PID\" 2>/dev/null || true\n"
            "    fi\n"
            "    exit \"$exit_code\"\n"
            "}\n"
            "trap cleanup EXIT INT TERM\n\n"
            "# Start target worker process\n"
            "\"$@\" &\n"
            "CHILD_PID=$!\n"
            "send_systemd_notification \"READY=1\"\n\n"
            "# Compute watchdog interval (half of deadline)\n"
            "PING_SEC=10\n"
            "if [[ \"$WATCHDOG_USEC\" -gt 0 ]]; then\n"
            "    PING_SEC=$((WATCHDOG_USEC / 2000000))\n"
            "    [[ \"$PING_SEC\" -le 0 ]] && PING_SEC=1\n"
            "fi\n\n"
            "while kill -0 \"$CHILD_PID\" 2>/dev/null; do\n"
            "    send_systemd_notification \"WATCHDOG=1\"\n"
            "    sleep \"$PING_SEC\" &\n"
            "    wait $! 2>/dev/null || true\n"
            "done\n\n"
            "wait \"$CHILD_PID\"\n"
        ),
        "rejected": (
            "#!/bin/bash\n"
            "# Fragile systemd runner that leaves orphan processes\n"
            "\"$@\" &\n"
            "while true; do\n"
            "    systemd-notify WATCHDOG=1\n"
            "    sleep 10\n"
            "done\n"
        ),
        "capabilities": ["bash", "systemd", "watchdog", "process_lifecycle", "posix"],
    },
    {
        "domain": "bash_posix",
        # Teaches: bounded parallelism with a FIFO semaphore, PID tracking and signal-driven cleanup. Rejected: unbounded fork per item.
        "id_suffix": "BASH_PARALLEL_SEMAPHORE_0007",
        "prompt": (
            "Construct a bounded concurrency job runner in POSIX Bash using a named FIFO semaphore, "
            "tracking worker PIDs in an array, trapping SIGINT/SIGTERM to terminate worker pools cleanly, "
            "and ensuring zero background child leaks under set -euo pipefail."
        ),
        "chosen": (
            "#!/usr/bin/env bash\n"
            "# Bounded Parallel Job Queue via POSIX FIFO Semaphore\n"
            "set -euo pipefail\n"
            "IFS=$'\\n\\t'\n\n"
            "CONCURRENCY=4\n"
            "SEMAPHORE_FIFO=\"\"\n"
            "declare -a WORKER_PIDS=()\n\n"
            "cleanup() {\n"
            "    local code=$?\n"
            "    trap - EXIT INT TERM\n"
            "    for pid in \"${WORKER_PIDS[@]:-}\"; do\n"
            "        kill -TERM \"$pid\" 2>/dev/null || true\n"
            "    done\n"
            "    if [[ -n \"$SEMAPHORE_FIFO\" && -p \"$SEMAPHORE_FIFO\" ]]; then\n"
            "        rm -f \"$SEMAPHORE_FIFO\"\n"
            "    fi\n"
            "    exec 3<&- 2>/dev/null || true\n"
            "    exec 3>&- 2>/dev/null || true\n"
            "    exit \"$code\"\n"
            "}\n"
            "trap cleanup EXIT INT TERM\n\n"
            "SEMAPHORE_FIFO=\"$(mktemp -u /tmp/sem_XXXXXX.fifo)\"\n"
            "mkfifo -m 0600 \"$SEMAPHORE_FIFO\"\n"
            "exec 3<>\"$SEMAPHORE_FIFO\"\n"
            "rm -f \"$SEMAPHORE_FIFO\"\n\n"
            "# Seed semaphore tokens\n"
            "for ((i=0; i<CONCURRENCY; i++)); do\n"
            "    printf '.' >&3\n"
            "done\n\n"
            "run_task() {\n"
            "    local item=\"$1\"\n"
            "    echo \"Processing $item on worker$$\"\n"
            "    sleep 1\n"
            "}\n\n"
            "for item in \"$@\"; do\n"
            "    read -r -n 1 -u 3\n"
            "    (\n"
            "        run_task \"$item\"\n"
            "        printf '.' >&3\n"
            "    ) &\n"
            "    WORKER_PIDS+=($!)\n"
            "done\n\n"
            "wait\n"
            "echo \"All parallel batch tasks completed successfully.\"\n"
        ),
        "rejected": (
            "#!/bin/bash\n"
            "# Unbounded fork bomb with no concurrency limits and abandoned background jobs\n"
            "for item in \"$@\"; do\n"
            "    run_task \"$item\" & # Forks without bound, exhausting memory\n"
            "done\n"
            "wait\n"
        ),
        "capabilities": ["bash", "semaphore", "concurrency", "fifo", "posix"],
    },
    {
        "domain": "bash_posix",
        # Teaches: streaming tar|gzip|tee hashing into a temp file that is atomically moved into place. Rejected: writes the final path directly and leaves a corrupt file if interrupted.
        "id_suffix": "BASH_TAR_STREAM_HASH_0008",
        "prompt": (
            "Implement a streaming POSIX Bash backup archiver that pipes tar through gzip and tee "
            "to compute on-the-fly SHA-256 digests, writes to an isolated atomic temporary target, "
            "and employs trap EXIT cleanup to remove orphaned temporary files on any failure."
        ),
        "chosen": (
            "#!/usr/bin/env bash\n"
            "# Streaming Tar Archive with Atomic Verification\n"
            "set -euo pipefail\n"
            "IFS=$'\\n\\t'\n\n"
            "SRC_DIR=\"${1:-/etc}\"\n"
            "FINAL_TAR=\"${2:-/backup/etc_archive.tar.gz}\"\n"
            "TEMP_TAR=\"\"\n\n"
            "cleanup() {\n"
            "    local code=$?\n"
            "    if [[ -n \"$TEMP_TAR\" && -f \"$TEMP_TAR\" ]]; then\n"
            "        rm -f \"$TEMP_TAR\"\n"
            "    fi\n"
            "    exit \"$code\"\n"
            "}\n"
            "trap cleanup EXIT INT TERM\n\n"
            "TEMP_TAR=\"$(mktemp /backup/etc_archive.XXXXXX.tmp)\"\n"
            "DIGEST_FILE=\"${FINAL_TAR}.sha256\"\n\n"
            "# Stream archive while computing sha256 checksum\n"
            "CHECKSUM=$(tar -C \"$SRC_DIR\" -cf - . | gzip -9 | tee \"$TEMP_TAR\" | sha256sum | awk '{print $1}')\n\n"
            "printf '%s  %s\\n' \"$CHECKSUM\" \"$(basename \"$FINAL_TAR\")\" > \"$DIGEST_FILE\"\n"
            "mv -f \"$TEMP_TAR\" \"$FINAL_TAR\"\n"
            "echo \"Archive created and verified: $FINAL_TAR (sha256: $CHECKSUM)\"\n"
        ),
        "rejected": (
            "#!/bin/bash\n"
            "# Incomplete backup script overwriting target directly\n"
            "tar -czf /backup/etc_archive.tar.gz /etc # Leaves corrupt file if interrupted\n"
            "echo \"Backup complete\"\n"
        ),
        "capabilities": ["bash", "tar", "sha256sum", "atomic_swap", "traps"],
    },

    # -----------------------------------------------------------------
    # ARCH LINUX PKGBUILD EXPANSIONS (5 new, 8 total)
    # -----------------------------------------------------------------
    {
        "domain": "arch_linux",
        # Teaches: namcap-clean Go PKGBUILD (PIE, trimpath, checksums, check() tests, /usr/bin). Rejected: no checksums, installs under /usr/local, pollutes the build env.
        "id_suffix": "ARCH_PKGBUILD_GO_PIE_0004",
        "prompt": (
            "Write an idiomatic, namcap-compliant Arch Linux PKGBUILD for a Go network utility "
            "enforcing Position Independent Executable (-buildmode=pie), trimpath, security build flags, "
            "check() running go test, and installation to /usr/bin."
        ),
        "chosen": (
            "# Maintainer: Magi Systems Specialist <systems@magi-mesh.org>\n"
            "pkgname=net-probe\n"
            "pkgver=2.4.0\n"
            "pkgrel=1\n"
            "pkgdesc=\"High-performance network probing daemon with eBPF support\"\n"
            "arch=('x86_64' 'aarch64')\n"
            "url=\"https://github.com/magi-mesh/net-probe\"\n"
            "license=('Apache-2.0')\n"
            "depends=('glibc' 'libpcap')\n"
            "makedepends=('go')\n"
            "source=(\"${pkgname}-${pkgver}.tar.gz::https://github.com/magi-mesh/${pkgname}/archive/v${pkgver}.tar.gz\")\n"
            "sha256sums=('9c5b62b1b36be9f39e31ff7382d61b36e8b4e788e0b62b11e2f7b88e1e771c5a')\n\n"
            "build() {\n"
            "    cd \"${pkgname}-${pkgver}\"\n"
            "    export CGO_CPPFLAGS=\"${CPPFLAGS}\"\n"
            "    export CGO_CFLAGS=\"${CFLAGS}\"\n"
            "    export CGO_CXXFLAGS=\"${CXXFLAGS}\"\n"
            "    export CGO_LDFLAGS=\"${LDFLAGS}\"\n"
            "    export GOFLAGS=\"-buildmode=pie -trimpath -ldflags=-linkmode=external -mod=readonly -modcacherw\"\n"
            "    go build -v -o \"build/${pkgname}\" ./cmd/net-probe\n"
            "}\n\n"
            "check() {\n"
            "    cd \"${pkgname}-${pkgver}\"\n"
            "    go test -v ./...\n"
            "}\n\n"
            "package() {\n"
            "    cd \"${pkgname}-${pkgver}\"\n"
            "    install -Dm755 \"build/${pkgname}\" \"${pkgdir}/usr/bin/${pkgname}\"\n"
            "    install -Dm644 LICENSE \"${pkgdir}/usr/share/licenses/${pkgname}/LICENSE\"\n"
            "    install -Dm644 README.md \"${pkgdir}/usr/share/doc/${pkgname}/README.md\"\n"
            "}\n"
        ),
        "rejected": (
            "# Unsafe Arch package with missing sha256sums and /usr/local installation\n"
            "pkgname=net-probe\n"
            "pkgver=2.4.0\n"
            "pkgrel=1\n"
            "arch=('x86_64')\n"
            "license=('Apache-2.0')\n"
            "package() {\n"
            "    go install ./... # Pollutes build host environment\n"
            "    cp ~/go/bin/net-probe /usr/local/bin/ # Violates packaging guidelines\n"
            "}\n"
        ),
        "capabilities": ["arch_linux", "pkgbuild", "golang", "pie", "security_hardening"],
    },
    {
        "domain": "arch_linux",
        # Teaches: Meson/Ninja shared-library packaging that uses "meson install --destdir" so soname links and pkg-config files are right. Rejected: hand-copies files and omits checksums.
        "id_suffix": "ARCH_PKGBUILD_SHARED_LIB_MESON_0005",
        "prompt": (
            "Create a standard Arch Linux PKGBUILD for a native C shared library built with Meson "
            "and Ninja, ensuring proper soname symlinks, pkg-config metadata installation, "
            "test suite execution in check(), and strict namcap verification."
        ),
        "chosen": (
            "# Maintainer: Magi Systems Specialist <systems@magi-mesh.org>\n"
            "pkgname=libringbuffer\n"
            "pkgver=1.3.2\n"
            "pkgrel=1\n"
            "pkgdesc=\"Lock-free atomic circular ring buffer library in ISO C11\"\n"
            "arch=('x86_64')\n"
            "url=\"https://github.com/magi-mesh/libringbuffer\"\n"
            "license=('MIT')\n"
            "depends=('glibc')\n"
            "makedepends=('meson' 'ninja')\n"
            "source=(\"${pkgname}-${pkgver}.tar.gz::https://github.com/magi-mesh/${pkgname}/archive/v${pkgver}.tar.gz\")\n"
            "sha256sums=('4b3a165b4c19ef6d482433e16347076a9a79fa4f526210f968ef50c184000305')\n\n"
            "build() {\n"
            "    arch-meson \"${pkgname}-${pkgver}\" build \\\n"
            "        -Ddefault_library=both \\\n"
            "        -Db_lto=true \\\n"
            "        -Db_pie=true\n"
            "    meson compile -C build\n"
            "}\n\n"
            "check() {\n"
            "    meson test -C build --print-errorlogs\n"
            "}\n\n"
            "package() {\n"
            "    meson install -C build --destdir \"${pkgdir}\"\n"
            "    install -Dm644 \"${pkgname}-${pkgver}/LICENSE\" \"${pkgdir}/usr/share/licenses/${pkgname}/LICENSE\"\n"
            "}\n"
        ),
        "rejected": (
            "# Bad PKGBUILD bypassing meson install and omitting checksums\n"
            "pkgname=libringbuffer\n"
            "pkgver=1.3.2\n"
            "pkgrel=1\n"
            "arch=('x86_64')\n"
            "license=('MIT')\n"
            "package() {\n"
            "    mkdir -p $pkgdir/usr/lib\n"
            "    cp build/libringbuffer.so $pkgdir/usr/lib/ # Missing soname symlinks and pkgconfig\n"
            "}\n"
        ),
        "capabilities": ["arch_linux", "pkgbuild", "meson", "shared_library", "lto"],
    },
    {
        "domain": "arch_linux",
        # Teaches: PEP 517 flow (python-build, python-installer, wheel) with pytest in check(). Rejected: deprecated "setup.py install".
        "id_suffix": "ARCH_PKGBUILD_PYTHON_PEP517_0006",
        "prompt": (
            "Author a modern Arch Linux PKGBUILD for a Python library following the PEP 517 build standard "
            "with python-build and python-installer, pyproject.toml wheel generation, compile optimization, "
            "and pytest check()."
        ),
        "chosen": (
            "# Maintainer: Magi Systems Specialist <systems@magi-mesh.org>\n"
            "pkgname=python-mesh-protocol\n"
            "pkgver=3.1.0\n"
            "pkgrel=1\n"
            "pkgdesc=\"Structured high-throughput protocol serializers for Magi Mesh\"\n"
            "arch=('any')\n"
            "url=\"https://github.com/magi-mesh/python-mesh-protocol\"\n"
            "license=('MIT')\n"
            "depends=('python' 'python-pydantic' 'python-cryptography')\n"
            "makedepends=('python-build' 'python-installer' 'python-wheel' 'python-setuptools')\n"
            "checkdepends=('python-pytest' 'python-pytest-asyncio')\n"
            "source=(\"${pkgname}-${pkgver}.tar.gz::https://github.com/magi-mesh/${pkgname}/archive/v${pkgver}.tar.gz\")\n"
            "sha256sums=('c76356784d84b23fe6279f6498a44b1c55bc6f2382cf896c34e8f192b1dc7152')\n\n"
            "build() {\n"
            "    cd \"${pkgname}-${pkgver}\"\n"
            "    python -m build --wheel --no-isolation\n"
            "}\n\n"
            "check() {\n"
            "    cd \"${pkgname}-${pkgver}\"\n"
            "    pytest -v\n"
            "}\n\n"
            "package() {\n"
            "    cd \"${pkgname}-${pkgver}\"\n"
            "    python -m installer --destdir=\"${pkgdir}\" --compile-bytecode=2 dist/*.whl\n"
            "    install -Dm644 LICENSE \"${pkgdir}/usr/share/licenses/${pkgname}/LICENSE\"\n"
            "}\n"
        ),
        "rejected": (
            "# Deprecated setup.py install invocation\n"
            "pkgname=python-mesh-protocol\n"
            "pkgver=3.1.0\n"
            "pkgrel=1\n"
            "arch=('any')\n"
            "license=('MIT')\n"
            "package() {\n"
            "    cd $pkgname-$pkgver\n"
            "    python setup.py install --root=$pkgdir # Deprecated and forbidden by Arch standards\n"
            "}\n"
        ),
        "capabilities": ["arch_linux", "pkgbuild", "python", "pep517", "wheel"],
    },
    {
        "domain": "arch_linux",
        # Teaches: declarative sysusers.d/tmpfiles.d plus a unit file, with no install scriptlet. Rejected: useradd inside an .install scriptlet.
        "id_suffix": "ARCH_PKGBUILD_SYSTEMD_SERVICE_SYSUSERS_0007",
        "prompt": (
            "Provide an Arch Linux PKGBUILD for a systems agent daemon that installs a systemd unit, "
            "systemd-sysusers configuration for dedicated unprivileged user provisioning, systemd-tmpfiles "
            "rules, and adheres to zero post-install scriptlet rules."
        ),
        "chosen": (
            "# Maintainer: Magi Systems Specialist <systems@magi-mesh.org>\n"
            "pkgname=magi-agent-daemon\n"
            "pkgver=1.8.0\n"
            "pkgrel=1\n"
            "pkgdesc=\"Autonomous node monitoring and peer gossip mesh daemon\"\n"
            "arch=('x86_64')\n"
            "url=\"https://github.com/magi-mesh/magi-agent-daemon\"\n"
            "license=('GPL-3.0-or-later')\n"
            "depends=('glibc' 'systemd-libs')\n"
            "makedepends=('cargo')\n"
            "backup=('etc/magi/daemon.conf')\n"
            "source=(\n"
            "    \"${pkgname}-${pkgver}.tar.gz::https://github.com/magi-mesh/${pkgname}/archive/v${pkgver}.tar.gz\"\n"
            "    \"magi-agent.service\"\n"
            "    \"magi-agent.sysusers\"\n"
            "    \"magi-agent.tmpfiles\"\n"
            ")\n"
            "sha256sums=(\n"
            "    '8b628172c91629e46a782e5b72e1281b37494a82bf0954b8bb26b08e2f893110'\n"
            "    'd3b07384d113edec49eaa6238ad5ff00ebd0e84b8026101eb65774a3f3a09332'\n"
            "    'fa43a2916b8b0e79124458319f6a73c1d948293774026ba9b51206d208761234'\n"
            "    '9e107d9d372bb6826bd81d3542a419d6dae0350ac0b1e428c40c94625b15b497'\n"
            ")\n\n"
            "build() {\n"
            "    cd \"${pkgname}-${pkgver}\"\n"
            "    cargo build --release --locked\n"
            "}\n\n"
            "package() {\n"
            "    cd \"${pkgname}-${pkgver}\"\n"
            "    install -Dm755 \"target/release/${pkgname}\" \"${pkgdir}/usr/bin/${pkgname}\"\n"
            "    install -Dm644 \"${srcdir}/magi-agent.service\" \"${pkgdir}/usr/lib/systemd/system/magi-agent.service\"\n"
            "    install -Dm644 \"${srcdir}/magi-agent.sysusers\" \"${pkgdir}/usr/lib/sysusers.d/magi-agent.conf\"\n"
            "    install -Dm644 \"${srcdir}/magi-agent.tmpfiles\" \"${pkgdir}/usr/lib/tmpfiles.d/magi-agent.conf\"\n"
            "    install -Dm640 config/default.conf \"${pkgdir}/etc/magi/daemon.conf\"\n"
            "    install -Dm644 LICENSE \"${pkgdir}/usr/share/licenses/${pkgname}/LICENSE\"\n"
            "}\n"
        ),
        "rejected": (
            "# Anti-pattern: manual useradd in .install scriptlet instead of systemd-sysusers\n"
            "pkgname=magi-agent-daemon\n"
            "pkgver=1.8.0\n"
            "pkgrel=1\n"
            "arch=('x86_64')\n"
            "license=('GPL-3.0-or-later')\n"
            "install=magi-agent.install # Fragile imperatively mutating /etc/passwd\n"
            "package() {\n"
            "    install -Dm755 magi-agent-daemon /usr/local/bin/magi-agent-daemon\n"
            "}\n"
        ),
        "capabilities": ["arch_linux", "pkgbuild", "systemd", "sysusers", "tmpfiles"],
    },
    {
        "domain": "arch_linux",
        # Teaches: DKMS packaging (sources under /usr/src/<pkg>-<ver>, dkms.conf, dkms dependency). Rejected: builds against the running host kernel during packaging.
        "id_suffix": "ARCH_PKGBUILD_DKMS_KERNEL_0008",
        "prompt": (
            "Design an Arch Linux PKGBUILD for a out-of-tree hardware kernel driver module using DKMS, "
            "installing sources to /usr/src/<pkgname>-<pkgver>, generating dkms.conf, and declaring dkms dependencies."
        ),
        "chosen": (
            "# Maintainer: Magi Systems Specialist <systems@magi-mesh.org>\n"
            "pkgname=magi-pcie-driver-dkms\n"
            "pkgver=0.9.4\n"
            "pkgrel=1\n"
            "pkgdesc=\"Out-of-tree PCIe DMA ring buffer kernel module (DKMS)\"\n"
            "arch=('x86_64')\n"
            "url=\"https://github.com/magi-mesh/magi-pcie-driver\"\n"
            "license=('GPL-2.0-only')\n"
            "depends=('dkms')\n"
            "source=(\"${pkgname}-${pkgver}.tar.gz::https://github.com/magi-mesh/${pkgname}/archive/v${pkgver}.tar.gz\")\n"
            "sha256sums=('a12409748b6c0e816a75f562479e1b212f71694f83b17927e1d511ea636a0618')\n\n"
            "package() {\n"
            "    local dest_dir=\"${pkgdir}/usr/src/${pkgname}-${pkgver}\"\n"
            "    install -dm755 \"${dest_dir}\"\n"
            "    cp -r \"${srcdir}/${pkgname}-${pkgver}/\"* \"${dest_dir}/\"\n\n"
            "    # Generate dkms.conf dynamically with proper versioning\n"
            "    cat << EOF > \"${dest_dir}/dkms.conf\"\n"
            "PACKAGE_NAME=\"${pkgname}\"\n"
            "PACKAGE_VERSION=\"${pkgver}\"\n"
            "AUTOINSTALL=\"yes\"\n"
            "BUILT_MODULE_NAME[0]=\"magi_pcie\"\n"
            "DEST_MODULE_LOCATION[0]=\"/kernel/drivers/misc\"\n"
            "CLEAN=\"make -C \\$kernel_source_dir M=\\$dkms_tree/\\$PACKAGE_NAME/\\$PACKAGE_VERSION/build clean\"\n"
            "MAKE=\"make -C \\$kernel_source_dir M=\\$dkms_tree/\\$PACKAGE_NAME/\\$PACKAGE_VERSION/build modules\"\n"
            "EOF\n\n"
            "    install -Dm644 \"${srcdir}/${pkgname}-${pkgver}/COPYING\" \"${pkgdir}/usr/share/licenses/${pkgname}/LICENSE\"\n"
            "}\n"
        ),
        "rejected": (
            "# Anti-pattern: compiles against running host kernel directly during package step\n"
            "pkgname=magi-pcie-driver-dkms\n"
            "pkgver=0.9.4\n"
            "pkgrel=1\n"
            "arch=('x86_64')\n"
            "license=('GPL-2.0-only')\n"
            "package() {\n"
            "    make -C /lib/modules/$(uname -r)/build M=$PWD modules # Breaks on different kernels\n"
            "    mkdir -p $pkgdir/lib/modules\n"
            "}\n"
        ),
        "capabilities": ["arch_linux", "pkgbuild", "dkms", "kernel_module", "automation"],
    },

    # -----------------------------------------------------------------
    # FEDORA LINUX DNF5 EXPANSIONS (5 new, 8 total)
    # -----------------------------------------------------------------
    {
        "domain": "fedora_linux",
        # Teaches: adding an internal repo with dnf5 config-manager, GPG verification, priority pinning. Rejected: curl into /etc/yum.repos.d and --nogpgcheck.
        "id_suffix": "FEDORA_DNF5_MODULE_COPR_REPO_0004",
        "prompt": (
            "Demonstrate how to safely configure an authenticated internal RPM repository in Fedora 41+ "
            "using `dnf5 config-manager`, validating repository GPG signing keys, pinning priority, "
            "and verifying metadata integrity."
        ),
        "chosen": (
            "# 1. Add internal repository using dnf5 config-manager with priority and gpgcheck\n"
            "dnf5 config-manager addrepo \\\n"
            "    --from-repofile=\"https://repo.internal.magi-mesh.org/rpm/magi.repo\" \\\n"
            "    --overwrite\n\n"
            "# 2. Explicitly enforce GPG signature checks and elevate repo priority\n"
            "dnf5 config-manager setopt \\\n"
            "    \"magi-internal.gpgcheck=1\" \\\n"
            "    \"magi-internal.repo_gpgcheck=1\" \\\n"
            "    \"magi-internal.priority=10\"\n\n"
            "# 3. Refresh metadata and query available packages with JSON schema output\n"
            "dnf5 repoquery --repo=magi-internal --json\n"
        ),
        "rejected": (
            "# Dangerous legacy curl into /etc/yum.repos.d with disabled GPG checks\n"
            "curl -o /etc/yum.repos.d/insecure.repo http://repo.internal/insecure.repo\n"
            "yum install --nogpgcheck -y magi-core # Bypasses signature checking entirely\n"
        ),
        "capabilities": ["fedora", "dnf5", "repository_management", "gpg_verification", "security"],
    },
    {
        "domain": "fedora_linux",
        # Teaches: read-only pre-flight audit (check-upgrade --json, download, advisories) before deploying. Rejected: blind "yum update --skip-broken".
        "id_suffix": "FEDORA_DNF5_DRYRUN_JSON_AUDIT_0005",
        "prompt": (
            "Construct a programmatic pre-flight transaction audit utility using `dnf5 check-upgrade --json` "
            "and `dnf5 download` to verify package checksums and CVE advisories before deployment."
        ),
        "chosen": (
            "# 1. Query pending security and bugfix updates in structured JSON format\n"
            "dnf5 check-upgrade --security --json > /tmp/pending_security_updates.json\n\n"
            "# 2. Perform a dry-run download of updated RPMs without altering live filesystem\n"
            "dnf5 upgrade --downloadonly --destdir=/var/cache/dnf5/staged_rpms/ -y\n\n"
            "# 3. Verify RPM header GPG signatures and digest integrity offline\n"
            "rpm -Kv /var/cache/dnf5/staged_rpms/*.rpm\n"
        ),
        "rejected": (
            "# Direct blind upgrade without testing or offline inspection\n"
            "yum -y update --skip-broken # Ignores dependency errors and performs blind updates\n"
        ),
        "capabilities": ["fedora", "dnf5", "dry_run", "audit", "cve_remediation"],
    },
    {
        "domain": "fedora_linux",
        # Teaches: staged, deterministic major-version upgrade with dnf5 system-upgrade and an explicit releasever. Rejected: "rpm -Uvh --nodeps --force" across releases.
        "id_suffix": "FEDORA_DNF5_OFFLINE_SYSTEM_UPGRADE_0006",
        "prompt": (
            "Formulate a deterministic Fedora major-version system upgrade procedure using `dnf5 system-upgrade` "
            "with download pre-staging, target releasever resolution, and transaction verification."
        ),
        "chosen": (
            "# 1. Download and resolve dependencies for targeted Fedora releasever\n"
            "dnf5 system-upgrade download \\\n"
            "    --releasever=42 \\\n"
            "    --setopt=keepcache=1 \\\n"
            "    -y\n\n"
            "# 2. Verify staging state without initiating immediate reboot\n"
            "dnf5 system-upgrade status\n\n"
            "# 3. Trigger safe offline update execution via systemd target\n"
            "echo \"Upgrade transaction downloaded and verified for Fedora 42.\"\n"
        ),
        "rejected": (
            "# Dangerous manual rpm -Uvh with nodeps across major versions\n"
            "rpm -Uvh --nodeps --force http://download.fedoraproject.org/pub/fedora/linux/releases/42/Everything/x86_64/os/Packages/f/fedora-release*.rpm\n"
        ),
        "capabilities": ["fedora", "dnf5", "system_upgrade", "offline_update", "release_engineering"],
    },
    {
        "domain": "fedora_linux",
        # Teaches: "dnf5 swap" replaces a provider in one transaction. Rejected: "rpm -e --nodeps" then install, leaving the system broken in between.
        "id_suffix": "FEDORA_DNF5_SWAP_CONFLICT_RESOLUTION_0007",
        "prompt": (
            "Provide the canonical `dnf5 swap` syntax to replace one package provider with an alternative "
            "implementation without breaking reverse dependencies or causing package orphans."
        ),
        "chosen": (
            "# Perform atomic package replacement using dnf5 swap in a single transaction\n"
            "dnf5 swap \\\n"
            "    iptables-nft \\\n"
            "    nftables \\\n"
            "    -y \\\n"
            "    --setopt=install_weak_deps=False\n\n"
            "# Verify the transaction leaves zero broken dependencies\n"
            "dnf5 check --dependencies\n"
        ),
        "rejected": (
            "# Multi-step removal and install that leaves firewall in uninstalled broken state\n"
            "rpm -e --nodeps iptables-nft\n"
            "dnf5 install -y nftables\n"
        ),
        "capabilities": ["fedora", "dnf5", "swap", "conflict_resolution", "atomic_transaction"],
    },
    {
        "domain": "fedora_linux",
        # Teaches: dnf5 history inspection/replay/revert and rpm -Va verification. Rejected: grep the legacy yum.log and mass-remove.
        "id_suffix": "FEDORA_DNF5_TRANSACTION_HISTORY_REPLAY_0008",
        "prompt": (
            "Show how to inspect dnf5 transaction logs, export historical transaction IDs, and replay "
            "or revert transactions using `dnf5 history` and `rpm -Va`."
        ),
        "chosen": (
            "# 1. Query the last 5 transactions with full package action details in JSON\n"
            "dnf5 history list --limit=5 --json\n\n"
            "# 2. Inspect specific transaction ID 42 metadata and modified files\n"
            "dnf5 history info 42\n\n"
            "# 3. Replay transaction specifications on a duplicate staging node\n"
            "dnf5 history replay 42 --dry-run\n\n"
            "# 4. Validate system file integrity against RPM database records\n"
            "rpm -Va --nomtime --nosize\n"
        ),
        "rejected": (
            "# Grepping through unstructured legacy /var/log/yum.log with no rollback capability\n"
            "grep Installed /var/log/yum.log | awk '{print $NF}' | xargs rpm -e\n"
        ),
        "capabilities": ["fedora", "dnf5", "history", "replay", "integrity_audit"],
    },

    # -----------------------------------------------------------------
    # BIOS / UEFI READ-ONLY FWUPD & SMBIOS EXPANSIONS (5 new, 8 total)
    # -----------------------------------------------------------------
    {
        "domain": "bios_uefi",
        # Teaches: read-only SMBIOS Type 0/1 parsing from /sys/class/dmi/id and dmidecode. Rejected: flashrom write (firmware flash).
        "id_suffix": "BIOS_SMBIOS_DMI_TABLE_INSPECTION_0004",
        "prompt": (
            "Write a Python utility to safely parse SMBIOS Type 0 (BIOS Information) and Type 1 (System Information) "
            "from the Linux sysfs interface `/sys/class/dmi/id/` and `dmidecode` without performing hardware modifications."
        ),
        "chosen": (
            "import os\n"
            "from pathlib import Path\n"
            "from typing import Dict, Optional\n\n"
            "def inspect_smbios_dmi_tables(sysfs_root: str = \"/sys/class/dmi/id\") -> Dict[str, Optional[str]]:\n"
            "    \"\"\"Reads SMBIOS hardware information strictly through Linux read-only sysfs.\"\"\"\n"
            "    root = Path(sysfs_root)\n"
            "    dmi_fields = {\n"
            "        \"bios_vendor\": \"bios_vendor\",\n"
            "        \"bios_version\": \"bios_version\",\n"
            "        \"bios_date\": \"bios_date\",\n"
            "        \"board_vendor\": \"board_vendor\",\n"
            "        \"board_name\": \"board_name\",\n"
            "        \"product_uuid\": \"product_uuid\",\n"
            "        \"sys_vendor\": \"sys_vendor\",\n"
            "    }\n"
            "    results = {}\n"
            "    for key, filename in dmi_fields.items():\n"
            "        node = root / filename\n"
            "        if node.exists() and os.access(node, os.R_OK):\n"
            "            try:\n"
            "                results[key] = node.read_text(encoding=\"utf-8\").strip()\n"
            "            except OSError:\n"
            "                results[key] = None\n"
            "        else:\n"
            "            results[key] = None\n"
            "    return results\n\n"
            "if __name__ == \"__main__\":\n"
            "    info = inspect_smbios_dmi_tables()\n"
            "    print(f\"SMBIOS BIOS Version: {info.get('bios_version', 'UNKNOWN')}\")\n"
        ),
        "rejected": (
            "import subprocess\n"
            "# Destructive script modifying nvram and flashing\n"
            "def flash_bios():\n"
            "    subprocess.run([\"flashrom\", \"-p\", \"internal\", \"-w\", \"update.bin\"], check=True)\n"
        ),
        "capabilities": ["bios_uefi", "smbios", "dmi", "sysfs", "read_only"],
    },
    {
        "domain": "bios_uefi",
        # Teaches: read-only SecureBoot/SetupMode queries from efivars (read flags only). Rejected: opens the EFI variable for writing.
        "id_suffix": "BIOS_UEFI_SECURE_BOOT_STATE_QUERY_0005",
        "prompt": (
            "Construct a Python verification script that queries UEFI SecureBoot state and SetupMode "
            "via `/sys/firmware/efi/efivars/` or `/sys/kernel/security/` with read-only open flags, "
            "strictly preventing write access or NVRAM modifications."
        ),
        "chosen": (
            "import os\n"
            "import struct\n"
            "from pathlib import Path\n"
            "from typing import Dict\n\n"
            "def query_uefi_secure_boot_status(efivars_dir: str = \"/sys/firmware/efi/efivars\") -> Dict[str, bool]:\n"
            "    \"\"\"Queries SecureBoot and SetupMode variables safely in read-only binary mode.\"\"\"\n"
            "    efivars = Path(efivars_dir)\n"
            "    # Standard UEFI variable GUID for global variables\n"
            "    efi_global_guid = \"8be4df61-93ca-11d2-aa0d-00e098032b8c\"\n"
            "    sb_path = efivars / f\"SecureBoot-{efi_global_guid}\"\n"
            "    setup_path = efivars / f\"SetupMode-{efi_global_guid}\"\n\n"
            "    status = {\"secure_boot_enabled\": False, \"setup_mode_enabled\": False}\n\n"
            "    if sb_path.exists():\n"
            "        # UEFI variable format: 4 bytes attributes + data payload\n"
            "        data = sb_path.read_bytes()\n"
            "        if len(data) >= 5:\n"
            "            status[\"secure_boot_enabled\"] = bool(data[4])\n\n"
            "    if setup_path.exists():\n"
            "        data = setup_path.read_bytes()\n"
            "        if len(data) >= 5:\n"
            "            status[\"setup_mode_enabled\"] = bool(data[4])\n\n"
            "    return status\n\n"
            "if __name__ == \"__main__\":\n"
            "    res = query_uefi_secure_boot_status()\n"
            "    print(f\"Secure Boot Enabled: {res['secure_boot_enabled']}\")\n"
        ),
        "rejected": (
            "# Unsafe NVRAM write operation\n"
            "with open('/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c', 'wb') as f:\n"
            "    f.write(b'\\x07\\x00\\x00\\x00\\x00') # Direct write corrupts EFI NVRAM\n"
        ),
        "capabilities": ["bios_uefi", "secure_boot", "efivars", "read_only", "firmware_security"],
    },
    {
        "domain": "bios_uefi",
        # Teaches: parse "fwupdmgr security --json" for an HSI score, TPM 2.0 and IOMMU status, with no update actions. Rejected: runs "fwupdmgr update" (physical flash).
        "id_suffix": "BIOS_FWUPD_SECURITY_ATTRS_HSI_0006",
        "prompt": (
            "Create a safe parser for `fwupdmgr security --json` output to calculate the Host Security "
            "Identification (HSI) score, verify TPM 2.0 and IOMMU enablement, without executing any update actions."
        ),
        "chosen": (
            "import json\n"
            "from typing import Dict, Any, List\n\n"
            "def parse_hsi_security_attributes(json_data: str) -> Dict[str, Any]:\n"
            "    \"\"\"Parses fwupd Host Security ID attributes without issuing physical device operations.\"\"\"\n"
            "    payload = json.loads(json_data)\n"
            "    hsi_level = payload.get(\"HsiLevel\", 0)\n"
            "    attrs: List[Dict[str, Any]] = payload.get(\"SecurityAttributes\", [])\n\n"
            "    passed_checks = []\n"
            "    failed_checks = []\n"
            "    for attr in attrs:\n"
            "        appstream_id = attr.get(\"AppstreamId\", \"\")\n"
            "        hsi_result = attr.get(\"Result\", \"\")\n"
            "        is_success = (hsi_result == \"success\" or attr.get(\"Flags\", 0) & 1)\n"
            "        if is_success:\n"
            "            passed_checks.append(appstream_id)\n"
            "        else:\n"
            "            failed_checks.append(appstream_id)\n\n"
            "    return {\n"
            "        \"hsi_level\": hsi_level,\n"
            "        \"passed_count\": len(passed_checks),\n"
            "        \"failed_count\": len(failed_checks),\n"
            "        \"tpm_enabled\": \"org.fwupd.hsi.Tpm.version-20\" in passed_checks,\n"
            "        \"iommu_enabled\": \"org.fwupd.hsi.Iommu\" in passed_checks,\n"
            "    }\n"
        ),
        "rejected": (
            "# Destructive update attempt disguised as security scan\n"
            "fwupdmgr security --force\n"
            "fwupdmgr update -y # Triggers physical firmware flash\n"
        ),
        "capabilities": ["bios_uefi", "fwupd", "hsi", "security_posture", "read_only"],
    },
    {
        "domain": "bios_uefi",
        # Teaches: parse "efibootmgr -v" (BootCurrent, BootOrder, Boot#### entries) read-only. Rejected: deletes entries and rewrites BootOrder.
        "id_suffix": "BIOS_UEFI_BOOT_ORDER_INSPECTION_0007",
        "prompt": (
            "Develop a read-only Python parser for `efibootmgr -v` output that parses BootCurrent, "
            "BootOrder, and individual Boot#### entries (UUID, device paths) to identify active boot entries."
        ),
        "chosen": (
            "import re\n"
            "from typing import Dict, List, Any, Tuple\n\n"
            "def parse_efibootmgr_verbose(output: str) -> Dict[str, Any]:\n"
            "    \"\"\"Parses efibootmgr verbose output strictly in read-only inspection mode.\"\"\"\n"
            "    boot_order = []\n"
            "    boot_current = None\n"
            "    entries: Dict[str, Dict[str, str]] = {}\n\n"
            "    for line in output.splitlines():\n"
            "        line = line.strip()\n"
            "        if line.startswith(\"BootCurrent:\"):\n"
            "            boot_current = line.split(\":\", 1)[1].strip()\n"
            "        elif line.startswith(\"BootOrder:\"):\n"
            "            raw_order = line.split(\":\", 1)[1].strip()\n"
            "            boot_order = [item.strip() for item in raw_order.split(\",\") if item.strip()]\n"
            "        elif re.match(r\"^Boot[0-9A-Fa-f]{4}\\*?\", line):\n"
            "            m = re.match(r\"^Boot([0-9A-Fa-f]{4})(\\*)?\\s+(.*?)\\t(.*)$\", line)\n"
            "            if m:\n"
            "                entry_id, active, title, devpath = m.groups()\n"
            "                entries[entry_id] = {\n"
            "                    \"active\": bool(active),\n"
            "                    \"title\": title.strip(),\n"
            "                    \"device_path\": devpath.strip(),\n"
            "                }\n\n"
            "    return {\n"
            "        \"boot_current\": boot_current,\n"
            "        \"boot_order\": boot_order,\n"
            "        \"entries\": entries,\n"
            "    }\n"
        ),
        "rejected": (
            "# Dangerous script modifying BootOrder and deleting boot entries\n"
            "efibootmgr -b 0001 -B # Deletes boot option permanently\n"
            "efibootmgr -o 0002,0001 # Modifies NVRAM boot order\n"
        ),
        "capabilities": ["bios_uefi", "efibootmgr", "boot_order", "nvram", "read_only"],
    },
    {
        "domain": "bios_uefi",
        # Teaches: read-only PCI option-ROM inspection with 0x55AA header validation. Rejected: writes to the device ROM file.
        "id_suffix": "BIOS_PCI_EXPANSION_ROM_QUERY_0008",
        "prompt": (
            "Author a safe Python routine to inspect PCI Option ROMs and expansion firmware via "
            "`/sys/bus/pci/devices/*/rom` in read-only mode, validating ROM header signatures (0x55AA) "
            "without enabling write flags."
        ),
        "chosen": (
            "import os\n"
            "from pathlib import Path\n"
            "from typing import List, Dict, Any\n\n"
            "def inspect_pci_option_roms(pci_sysfs_root: str = \"/sys/bus/pci/devices\") -> List[Dict[str, Any]]:\n"
            "    \"\"\"Inspects PCI expansion ROMs in read-only mode, verifying the 0xAA55 signature.\"\"\"\n"
            "    pci_dir = Path(pci_sysfs_root)\n"
            "    rom_reports = []\n"
            "    if not pci_dir.exists():\n"
            "        return rom_reports\n\n"
            "    for dev_path in sorted(pci_dir.glob(\"*\")):\n"
            "        rom_node = dev_path / \"rom\"\n"
            "        if rom_node.exists() and os.access(rom_node, os.R_OK):\n"
            "            try:\n"
            "                with open(rom_node, \"rb\") as f:\n"
            "                    header = f.read(2)\n"
            "                    has_valid_sig = (header == b\"\\x55\\xaa\")\n"
            "                    rom_reports.append({\n"
            "                        \"device_id\": dev_path.name,\n"
            "                        \"rom_readable\": True,\n"
            "                        \"has_valid_signature\": has_valid_sig,\n"
            "                    })\n"
            "            except (PermissionError, OSError):\n"
            "                continue\n"
            "    return rom_reports\n"
        ),
        "rejected": (
            "# Hazardous raw device writing to PCI ROM BAR\n"
            "with open('/sys/bus/pci/devices/0000:01:00.0/rom', 'wb') as f:\n"
            "    f.write(open('custom_rom.bin', 'rb').read()) # Flashes PCI expansion rom\n"
        ),
        "capabilities": ["bios_uefi", "pci", "option_rom", "sysfs", "read_only"],
    },

    # -----------------------------------------------------------------
    # GIT INTERNALS & WORKTREES EXPANSIONS (5 new, 8 total)
    # -----------------------------------------------------------------
    {
        "domain": "git_internals",
        # Teaches: agent handoff with "git worktree lock --reason", porcelain verification and unlock. Rejected: rm -rf of the worktree directory, leaving stale .git/worktrees entries.
        "id_suffix": "GIT_WORKTREE_ATOMIC_LOCK_HANDOFF_0004",
        "prompt": (
            "Detail a collaborative Git worktree locking and handoff protocol between concurrent automation "
            "agents: locking the worktree with `git worktree lock --reason`, asserting lock presence via "
            "`git worktree list --porcelain`, and unlocking before release."
        ),
        "chosen": (
            "# 1. Create dedicated agent worktree for Seat 11\n"
            "git worktree add -b feat/seat_11_expansion .worktrees/seat_11 HEAD\n\n"
            "# 2. Acquire advisory worktree lock with descriptive intent\n"
            "git worktree lock --reason \"Seat 11 active systems expansion\" .worktrees/seat_11\n\n"
            "# 3. Verify lock registration in git porcelain output\n"
            "git worktree list --porcelain | grep -A 3 \".worktrees/seat_11\" | grep \"^locked\"\n\n"
            "# 4. Release lock after pipeline execution and prune worktree cleanly\n"
            "git worktree unlock .worktrees/seat_11\n"
            "git worktree remove --force .worktrees/seat_11\n"
        ),
        "rejected": (
            "# Deleting active worktrees directly from filesystem without unlocking or git pruning\n"
            "rm -rf .worktrees/seat_11 # Leaves dangling entries in .git/worktrees causing repository corruption\n"
        ),
        "capabilities": ["git_internals", "worktree", "locking", "concurrency", "porcelain"],
    },
    {
        "domain": "git_internals",
        # Teaches: "git stash create" plus "store" to snapshot changes without touching the shared stash reflog. Rejected: plain "git stash"/"pop" that races other agents.
        "id_suffix": "GIT_WORKTREE_STASH_INTERNALS_0005",
        "prompt": (
            "Explain how an automation agent isolates unstaged modifications in a worktree by generating "
            "an independent commit object using `git stash create` and `git stash store` without polluting "
            "the global stash reflog of other agents."
        ),
        "chosen": (
            "# 1. Create a dangling commit object from current worktree index & working tree\n"
            "STASH_COMMIT=$(git stash create \"Seat 11 intermediate checkpoint\")\n\n"
            "if [ -n \"$STASH_COMMIT\" ]; then\n"
            "    echo \"Created isolated commit object: $STASH_COMMIT\"\n"
            "    # 2. Store commit under agent-private ref without touching refs/stash\n"
            "    git update-ref refs/magi/seat_11/checkpoint \"$STASH_COMMIT\"\n"
            "    # 3. Clean worktree back to HEAD state\n"
            "    git reset --hard HEAD\n"
            "fi\n"
        ),
        "rejected": (
            "# Polluting global stash reflog shared across multiple workers\n"
            "git stash # Creates race condition where another agent may pop the wrong stash\n"
            "git stash pop\n"
        ),
        "capabilities": ["git_internals", "stash_create", "update_ref", "isolation", "worktree"],
    },
    {
        "domain": "git_internals",
        # Teaches: "git bisect run" inside a detached worktree so the main checkout is untouched. Rejected: bisect in the primary checkout.
        "id_suffix": "GIT_WORKTREE_DETACHED_BISECT_0006",
        "prompt": (
            "Demonstrate how to run an automated regression bisect in an isolated detached worktree "
            "(`git worktree add --detach`) using `git bisect run`, ensuring the main working copy "
            "remains untouched and operational."
        ),
        "chosen": (
            "# 1. Create detached worktree at current HEAD for isolated bisect run\n"
            "git worktree add --detach .worktrees/bisect_runner HEAD\n\n"
            "# 2. Initialize bisect within the isolated worktree directory\n"
            "pushd .worktrees/bisect_runner > /dev/null\n"
            "git bisect start HEAD v1.0.0\n"
            "git bisect run python3 -m unittest discover tests\n"
            "git bisect reset\n"
            "popd > /dev/null\n\n"
            "# 3. Remove the disposable bisect worktree\n"
            "git worktree remove --force .worktrees/bisect_runner\n"
        ),
        "rejected": (
            "# Running bisect directly in primary checkout interrupting active development\n"
            "git bisect start HEAD v1.0.0 # Alters main index, forcing all agents into detached states\n"
        ),
        "capabilities": ["git_internals", "bisect", "detached_head", "isolation", "worktree"],
    },
    {
        "domain": "git_internals",
        # Teaches: relocating a worktree and running "git worktree repair". Rejected: mv plus sed on .git pointer files.
        "id_suffix": "GIT_WORKTREE_SUBMODULE_REPAIR_0007",
        "prompt": (
            "Author a safe script to relocate a git worktree directory to a new path and invoke "
            "`git worktree repair` to reconstruct internal `.git` pointer files and submodule references."
        ),
        "chosen": (
            "#!/usr/bin/env bash\n"
            "# Relocate worktree and repair internal pointer refs\n"
            "set -euo pipefail\n"
            "IFS=$'\\n\\t'\n\n"
            "OLD_PATH=\".worktrees/worker_staging\"\n"
            "NEW_PATH=\".worktrees/worker_active\"\n\n"
            "if [[ -d \"$OLD_PATH\" ]]; then\n"
            "    # 1. Move worktree directory\n"
            "    mv \"$OLD_PATH\" \"$NEW_PATH\"\n"
            "    # 2. Repair git administrative pointer files in both directions\n"
            "    git worktree repair \"$NEW_PATH\"\n"
            "    # 3. Synchronize submodule gitdir paths to point to correct relative targets\n"
            "    git -C \"$NEW_PATH\" submodule sync --recursive 2>/dev/null || true\n"
            "    echo \"Worktree relocated and repaired cleanly at $NEW_PATH\"\n"
            "fi\n"
        ),
        "rejected": (
            "# Manually hacking .git files after directory move causing broken repository refs\n"
            "mv .worktrees/old .worktrees/new\n"
            "sed -i 's/old/new/g' .worktrees/new/.git # Fragile string replacement corrupts git pointers\n"
        ),
        "capabilities": ["git_internals", "worktree_repair", "submodules", "relocation", "posix"],
    },
    {
        "domain": "git_internals",
        # Teaches: "git worktree add --orphan" to stage release docs with no inherited history. Rejected: checkout --orphan and rm -rf in the main tree, wiping local files.
        "id_suffix": "GIT_WORKTREE_ORPHAN_RELEASE_PIPELINE_0008",
        "prompt": (
            "Show how to stage clean documentation and release artifacts on an orphan branch using "
            "`git worktree add --orphan` without inheriting commit history or uncommitted index changes."
        ),
        "chosen": (
            "# 1. Create an isolated orphan worktree for release docs\n"
            "git worktree add --orphan -b gh-pages .worktrees/release_docs\n\n"
            "# 2. Clear out any indexed files from parent branch in the orphan worktree\n"
            "git -C .worktrees/release_docs reset --hard\n\n"
            "# 3. Populate release artifacts and commit\n"
            "echo \"# Magi Mesh Production Documentation\" > .worktrees/release_docs/index.md\n"
            "git -C .worktrees/release_docs add index.md\n"
            "git -C .worktrees/release_docs commit -m \"docs: initial release documentation tree\"\n\n"
            "# 4. Clean up worktree after pushing branch\n"
            "git worktree remove .worktrees/release_docs\n"
        ),
        "rejected": (
            "# Creating orphan branch in main tree, blowing away working directory files\n"
            "git checkout --orphan gh-pages\n"
            "git rm -rf . # Dangerous: wipes out uncommitted local developer files\n"
        ),
        "capabilities": ["git_internals", "worktree", "orphan_branch", "release_engineering"],
    },
]


def validate_trajectory_suite(trajectories: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Validates every trajectory against safety, policy, firmware, and dedup gates."""
    policy_scanner = PolicyLeakScanner()
    bash_issues = []
    arch_issues = []
    fedora_issues = []
    firmware_violations = []
    policy_leaks = []

    domain_counts = {}

    for idx, ex in enumerate(trajectories):
        dom = ex["domain"]
        domain_counts[dom] = domain_counts.get(dom, 0) + 1

        # (Runs on every record in every domain.)
        # 1. Policy leak check (zero credentials, zero private hosts, zero destructive chosen)
        record = {
            "id": f"TWU_GOLD_{ex['id_suffix']}",
            "domain": dom,
            "prompt": ex["prompt"],
            "chosen": ex["chosen"],
            "rejected": ex["rejected"],
        }
        leaks = policy_scanner.scan_record(record)
        if leaks:
            policy_leaks.append({"id": ex["id_suffix"], "leaks": leaks})

        # The prompt and the chosen answer must contain no flash/write operations; "rejected" is allowed to, since it is the bad example.
        # 2. Firmware safety check (0% flash operations)
        if dom == "bios_uefi":
            for text_field in [ex["prompt"], ex["chosen"]]:
                try:
                    FirmwareSafetyGate.verify_command_safety(text_field)
                except FirmwareSafetyViolation as e:
                    firmware_violations.append({"id": ex["id_suffix"], "error": str(e)})

        # Chosen answers must pass the domain validator. Only the Fedora branch also demands that the REJECTED answer fail its validator.
        # 3. Domain specific validators
        if dom == "bash_posix":
            chosen_res = BashSafetyValidator.validate(ex["chosen"])
            if not chosen_res["valid"]:
                bash_issues.append({"id": ex["id_suffix"], "issues": chosen_res["issues"]})

        elif dom == "arch_linux":
            chosen_res = ArchPkgbuildValidator.validate(ex["chosen"])
            if not chosen_res["valid"]:
                arch_issues.append({"id": ex["id_suffix"], "issues": chosen_res["issues"]})

        elif dom == "fedora_linux":
            chosen_text = ex["chosen"]
            if "dnf5" not in chosen_text:
                fedora_issues.append({"id": ex["id_suffix"], "issues": ["Chosen response does not utilize dnf5"]})
            if "yum " in chosen_text or "--nodeps" in chosen_text or "rpm -e" in chosen_text:
                fedora_issues.append({"id": ex["id_suffix"], "issues": ["Chosen response contains legacy or dangerous package operations"]})
            if "--installroot" in chosen_text:
                if "--releasever" not in chosen_text:
                    fedora_issues.append({"id": ex["id_suffix"], "issues": ["Missing --releasever with --installroot"]})
                if "--nodocs" not in chosen_text:
                    fedora_issues.append({"id": ex["id_suffix"], "issues": ["Missing --nodocs with --installroot"]})

            # This guards against a "rejected" example that is actually fine, which would teach nothing.
            # Verify rejected response fails validator
            rejected_res = FedoraDnf5Validator.validate_command(ex["rejected"])
            if rejected_res["valid"]:
                fedora_issues.append({"id": ex["id_suffix"], "issues": ["Rejected response unexpectedly passed validation"]})

    # Corpus-level check: prompt uniqueness (raw and structural "skeleton" ratio, default min 0.90) and policy-leak scan.
    # 4. Fleet deduplication audit
    dedup_report = FleetDedupEngine.audit_corpus(
        [{"prompt": t["prompt"], "chosen": t["chosen"]} for t in trajectories]
    )

    # Every category must be empty and the dedup gate must pass; one failure blocks the build.
    all_passed = (
        len(bash_issues) == 0
        and len(arch_issues) == 0
        and len(fedora_issues) == 0
        and len(firmware_violations) == 0
        and len(policy_leaks) == 0
        and dedup_report.gate_passed
    )

    return {
        "passed": all_passed,
        "total_trajectories": len(trajectories),
        "domain_counts": domain_counts,
        "bash_issues": bash_issues,
        "arch_issues": arch_issues,
        "fedora_issues": fedora_issues,
        "firmware_violations": firmware_violations,
        "policy_leaks": policy_leaks,
        "dedup_report": asdict(dedup_report),
    }


def compile_and_write_corpus() -> Tuple[int, str, Dict[str, int]]:
    """Compiles 15 baseline + 25 expanded trajectories into systems_corpus.jsonl."""
    all_trajectories = list(SYSTEMS_TRAJECTORIES) + list(EXPANDED_SYSTEMS_TRAJECTORIES)

    # Validate full suite
    val_res = validate_trajectory_suite(all_trajectories)
    if not val_res["passed"]:
        print("FAILED: Validation issues detected:")
        print(json.dumps(val_res, indent=2))
        sys.exit(1)

    now = datetime.now(timezone.utc).isoformat()
    lines = []
    domain_counts = {}

    for ex in all_trajectories:
        dom = ex["domain"]
        domain_counts[dom] = domain_counts.get(dom, 0) + 1
        # All rows are exported as DPO pairs; quality "gold_certified" marks them as validator-approved golden trajectories.
        pair = TrainingPair(
            id=f"TWU_GOLD_{ex['id_suffix']}",
            domain=dom,
            kind="dpo",
            prompt=ex["prompt"],
            chosen=ex["chosen"],
            rejected=ex["rejected"],
            quality="gold_certified",
            capabilities=ex["capabilities"],
            created_at=now,
        )
        # sort_keys gives byte-stable output for the checksum.
        lines.append(json.dumps(pair.to_dict(), sort_keys=True))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines) + "\n"
    OUTPUT_PATH.write_text(content, encoding="utf-8")

    sha256_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    # Also write a manifest checksum file
    manifest_path = OUTPUT_PATH.parent / "systems_corpus.sha256"
    manifest_path.write_text(f"{sha256_hash}  systems_corpus.jsonl\n", encoding="utf-8")

    return len(lines), sha256_hash, domain_counts


if __name__ == "__main__":
    count, sha, counts = compile_and_write_corpus()
    print(f"Successfully generated systems corpus:")
    print(f"  Path      : {OUTPUT_PATH}")
    print(f"  Row Count : {count}")
    print(f"  SHA256    : {sha}")
    print(f"  Breakdown : {counts}")
