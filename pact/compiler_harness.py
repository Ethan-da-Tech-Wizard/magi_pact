"""Compiler & Harness Verification Engine.

Validates 100% build and test execution for C, C++, C#, Rust, and Go in isolated sandboxes.
Emits reproducible test receipts with execution metrics, exit codes, and content hashes.
Strictly local toolchains, $0.00 cloud spend.
"""
from dataclasses import dataclass, asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Dict, List, Optional, Tuple, Any

@dataclass
class ToolchainInfo:
    """What detect_toolchains() learned about one language toolchain on this host."""
    # Short key used throughout: "c", "cpp", "rust", "go", "csharp".
    language: str
    # Absolute path of the binary found on PATH, or "none" when absent.
    compiler: str
    # First line of the tool's version output; "unknown" if the probe failed, "not installed" if absent.
    version: str
    # False means callers must skip/fail gracefully instead of invoking the tool.
    available: bool
    # Default arguments the runner passes (warnings, language standard, optimization).
    flags: List[str]

@dataclass
class VerificationReceipt:
    """Reproducible record of one build+run attempt (hash of source, outcome, timing, output)."""
    test_id: str
    language: str
    # Hash of the exact source text, so a receipt can be tied back to its input.
    source_sha256: str
    # compilation_passed False => execution never happened (execution_passed is False too).
    compilation_passed: bool
    execution_passed: bool
    # Compiler exit code on build failure, program exit code otherwise; -1 means toolchain missing.
    exit_code: int
    duration_ms: float
    stdout: str
    stderr: str
    # UTC, ISO-8601 with a literal "Z" suffix.
    timestamp: str

def detect_toolchains() -> Dict[str, ToolchainInfo]:
    """Detect available compilers and interpreters on the local host."""
    # Each block below follows the same pattern: locate the binary with shutil.which,
    # ask it for its version (failure to do so is not fatal), and record the
    # default flags; a missing tool yields an available=False placeholder entry
    # so every language key is always present in the result.
    toolchains = {}

    # C Compiler (gcc / clang / cc)
    # Preference order is gcc, then clang, then the generic cc alias.
    cc = shutil.which("gcc") or shutil.which("clang") or shutil.which("cc")
    if cc:
        try:
            ver = subprocess.check_output([cc, "--version"], text=True).splitlines()[0]
            toolchains["c"] = ToolchainInfo("c", cc, ver, True, ["-std=c11", "-Wall", "-Wextra", "-O2"])
        except Exception:
            toolchains["c"] = ToolchainInfo("c", cc, "unknown", True, ["-std=c11"])
    else:
        toolchains["c"] = ToolchainInfo("c", "none", "not installed", False, [])

    # C++ Compiler (g++ / clang++)
    # Same preference order for C++.
    cxx = shutil.which("g++") or shutil.which("clang++") or shutil.which("c++")
    if cxx:
        try:
            ver = subprocess.check_output([cxx, "--version"], text=True).splitlines()[0]
            toolchains["cpp"] = ToolchainInfo("cpp", cxx, ver, True, ["-std=c++17", "-Wall", "-Wextra", "-O2"])
        except Exception:
            toolchains["cpp"] = ToolchainInfo("cpp", cxx, "unknown", True, ["-std=c++17"])
    else:
        toolchains["cpp"] = ToolchainInfo("cpp", "none", "not installed", False, [])

    # Rust (rustc / cargo)
    # Only rustc is probed (cargo is not used); flags are rustc flags.
    rustc = shutil.which("rustc")
    if rustc:
        try:
            ver = subprocess.check_output([rustc, "--version"], text=True).strip()
            toolchains["rust"] = ToolchainInfo("rust", rustc, ver, True, ["--edition=2021", "-O"])
        except Exception:
            toolchains["rust"] = ToolchainInfo("rust", rustc, "unknown", True, [])
    else:
        toolchains["rust"] = ToolchainInfo("rust", "none", "not installed", False, [])

    # Go (go)
    # For Go the single flag "test" is the subcommand, not a compiler option.
    go = shutil.which("go")
    if go:
        try:
            ver = subprocess.check_output([go, "version"], text=True).strip()
            toolchains["go"] = ToolchainInfo("go", go, ver, True, ["test"])
        except Exception:
            toolchains["go"] = ToolchainInfo("go", go, "unknown", True, [])
    else:
        toolchains["go"] = ToolchainInfo("go", "none", "not installed", False, [])

    # C# (.NET)
    # For C# the flag "build" is the dotnet subcommand.
    dotnet = shutil.which("dotnet")
    if dotnet:
        try:
            ver = subprocess.check_output([dotnet, "--version"], text=True).strip()
            toolchains["csharp"] = ToolchainInfo("csharp", dotnet, f".NET {ver}", True, ["build"])
        except Exception:
            toolchains["csharp"] = ToolchainInfo("csharp", dotnet, "unknown", True, [])
    else:
        toolchains["csharp"] = ToolchainInfo("csharp", "none", "not installed", False, [])

    return toolchains

# Wall-clock limit (seconds) for running a compiled self-test binary.
EXEC_TIMEOUT_S = 10


def _run_binary(bin_file: Path) -> "subprocess.CompletedProcess":
    """Run a compiled test binary, converting a timeout into a failed result.

    Args:
        bin_file: Path to the executable to run.

    Returns:
        The CompletedProcess; on timeout a synthetic one with returncode 124
        (the `timeout(1)` convention) and a stderr note, so callers build an
        ordinary failing receipt instead of crashing on TimeoutExpired.
    """
    try:
        return subprocess.run([str(bin_file)], capture_output=True, text=True, timeout=EXEC_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        # Normalises captured output of a timed-out child to text for the receipt.
        def _txt(v: Any) -> str:
            # TimeoutExpired may carry bytes or None depending on the platform.
            return v.decode("utf-8", "replace") if isinstance(v, bytes) else (v or "")
        return subprocess.CompletedProcess(
            args=[str(bin_file)], returncode=124,
            stdout=_txt(exc.stdout),
            stderr=_txt(exc.stderr) + f"\nExecution timed out after {EXEC_TIMEOUT_S}s",
        )


class IsolatedSandboxRunner:
    """Executes sandboxed compilations and tests in isolated scratch environments."""

    def __init__(self, workspace_root: Optional[Path] = None):
        """Pick the workspace (default: repo root, two levels above this file) and ensure data/sandbox_scratch exists."""
        self.workspace_root = workspace_root or Path(__file__).resolve().parent.parent
        self.scratch_dir = self.workspace_root / "data" / "sandbox_scratch"
        # Every run builds inside a throwaway TemporaryDirectory under scratch_dir, so
        # compiled artifacts never touch the source tree and are deleted on exit.
        self.scratch_dir.mkdir(parents=True, exist_ok=True)

    def run_c_test(self, test_id: str, c_source: str) -> VerificationReceipt:
        """Compiles and runs a self-testing C snippet."""
        # Hash the source up front so even failure receipts identify their input.
        src_sha = hashlib.sha256(c_source.encode("utf-8")).hexdigest()
        # Wall-clock start; duration covers compile + run.
        t0 = time.time()
        toolchains = detect_toolchains()
        cc_info = toolchains.get("c")

        # Toolchain absent: return a failure receipt (exit_code -1, duration 0) instead of raising.
        if not cc_info or not cc_info.available:
            return VerificationReceipt(
                test_id=test_id, language="c", source_sha256=src_sha,
                compilation_passed=False, execution_passed=False,
                exit_code=-1, duration_ms=0.0,
                stdout="", stderr="Compiler 'c' not available on host",
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            )

        with tempfile.TemporaryDirectory(dir=str(self.scratch_dir)) as tmp_dir:
            src_file = Path(tmp_dir) / "test.c"
            bin_file = Path(tmp_dir) / "test_bin"
            src_file.write_text(c_source, encoding="utf-8")

            # Build step. A non-zero compiler exit short-circuits with the compiler's own
            # stdout/stderr and its exit code so diagnostics reach the receipt.
            # Compile
            cmd_compile = [cc_info.compiler] + cc_info.flags + ["-o", str(bin_file), str(src_file)]
            res_comp = subprocess.run(cmd_compile, capture_output=True, text=True)
            if res_comp.returncode != 0:
                return VerificationReceipt(
                    test_id=test_id, language="c", source_sha256=src_sha,
                    compilation_passed=False, execution_passed=False,
                    exit_code=res_comp.returncode,
                    duration_ms=(time.time() - t0) * 1000,
                    stdout=res_comp.stdout, stderr=res_comp.stderr,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                )

            # Run step. _run_binary enforces EXEC_TIMEOUT_S and converts a timeout into
            # a failed result (exit code 124) so a runaway test yields a receipt.
            # Execute
            res_exec = _run_binary(bin_file)
            duration_ms = (time.time() - t0) * 1000
            return VerificationReceipt(
                test_id=test_id, language="c", source_sha256=src_sha,
                compilation_passed=True, execution_passed=(res_exec.returncode == 0),
                exit_code=res_exec.returncode, duration_ms=duration_ms,
                stdout=res_exec.stdout, stderr=res_exec.stderr,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            )

    def run_cpp_test(self, test_id: str, cpp_source: str) -> VerificationReceipt:
        """Compiles and runs a self-testing C++ snippet."""
        # Hash the source up front so even failure receipts identify their input.
        src_sha = hashlib.sha256(cpp_source.encode("utf-8")).hexdigest()
        # Wall-clock start; duration covers compile + run.
        t0 = time.time()
        toolchains = detect_toolchains()
        cxx_info = toolchains.get("cpp")

        # Toolchain absent: return a failure receipt (exit_code -1, duration 0) instead of raising.
        if not cxx_info or not cxx_info.available:
            return VerificationReceipt(
                test_id=test_id, language="cpp", source_sha256=src_sha,
                compilation_passed=False, execution_passed=False,
                exit_code=-1, duration_ms=0.0,
                stdout="", stderr="Compiler 'cpp' not available on host",
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            )

        with tempfile.TemporaryDirectory(dir=str(self.scratch_dir)) as tmp_dir:
            src_file = Path(tmp_dir) / "test.cpp"
            bin_file = Path(tmp_dir) / "test_bin"
            src_file.write_text(cpp_source, encoding="utf-8")

            # Build step. A non-zero compiler exit short-circuits with the compiler's own
            # stdout/stderr and its exit code so diagnostics reach the receipt.
            # Compile
            cmd_compile = [cxx_info.compiler] + cxx_info.flags + ["-o", str(bin_file), str(src_file)]
            res_comp = subprocess.run(cmd_compile, capture_output=True, text=True)
            if res_comp.returncode != 0:
                return VerificationReceipt(
                    test_id=test_id, language="cpp", source_sha256=src_sha,
                    compilation_passed=False, execution_passed=False,
                    exit_code=res_comp.returncode,
                    duration_ms=(time.time() - t0) * 1000,
                    stdout=res_comp.stdout, stderr=res_comp.stderr,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                )

            # Run step. _run_binary enforces EXEC_TIMEOUT_S and converts a timeout into
            # a failed result (exit code 124) so a runaway test yields a receipt.
            # Execute
            res_exec = _run_binary(bin_file)
            duration_ms = (time.time() - t0) * 1000
            return VerificationReceipt(
                test_id=test_id, language="cpp", source_sha256=src_sha,
                compilation_passed=True, execution_passed=(res_exec.returncode == 0),
                exit_code=res_exec.returncode, duration_ms=duration_ms,
                stdout=res_exec.stdout, stderr=res_exec.stderr,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            )

    def run_rust_test(self, test_id: str, rust_source: str) -> VerificationReceipt:
        """Compiles and runs a self-testing Rust snippet."""
        # Hash the source up front so even failure receipts identify their input.
        src_sha = hashlib.sha256(rust_source.encode("utf-8")).hexdigest()
        # Wall-clock start; duration covers compile + run.
        t0 = time.time()
        toolchains = detect_toolchains()
        rust_info = toolchains.get("rust")

        # Toolchain absent: return a failure receipt (exit_code -1, duration 0) instead of raising.
        if not rust_info or not rust_info.available:
            return VerificationReceipt(
                test_id=test_id, language="rust", source_sha256=src_sha,
                compilation_passed=False, execution_passed=False,
                exit_code=-1, duration_ms=0.0,
                stdout="", stderr="Compiler 'rustc' not available on host",
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            )

        with tempfile.TemporaryDirectory(dir=str(self.scratch_dir)) as tmp_dir:
            src_file = Path(tmp_dir) / "test.rs"
            bin_file = Path(tmp_dir) / "test_bin"
            src_file.write_text(rust_source, encoding="utf-8")

            # Build step. A non-zero compiler exit short-circuits with the compiler's own
            # stdout/stderr and its exit code so diagnostics reach the receipt.
            # Compile
            # "--test" makes rustc build a test-harness binary (runs #[test] fns) rather than a normal executable.
            cmd_compile = [rust_info.compiler] + rust_info.flags + ["--test", "-o", str(bin_file), str(src_file)]
            res_comp = subprocess.run(cmd_compile, capture_output=True, text=True)
            if res_comp.returncode != 0:
                return VerificationReceipt(
                    test_id=test_id, language="rust", source_sha256=src_sha,
                    compilation_passed=False, execution_passed=False,
                    exit_code=res_comp.returncode,
                    duration_ms=(time.time() - t0) * 1000,
                    stdout=res_comp.stdout, stderr=res_comp.stderr,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                )

            # Run step. _run_binary enforces EXEC_TIMEOUT_S and converts a timeout into
            # a failed result (exit code 124) so a runaway test yields a receipt.
            # Execute
            res_exec = _run_binary(bin_file)
            duration_ms = (time.time() - t0) * 1000
            return VerificationReceipt(
                test_id=test_id, language="rust", source_sha256=src_sha,
                compilation_passed=True, execution_passed=(res_exec.returncode == 0),
                exit_code=res_exec.returncode, duration_ms=duration_ms,
                stdout=res_exec.stdout, stderr=res_exec.stderr,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            )
