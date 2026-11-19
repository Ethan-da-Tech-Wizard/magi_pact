"""Regression: a compiled test that never terminates must yield a failing receipt.

Before the fix, subprocess.TimeoutExpired escaped run_c_test and crashed callers.
"""
import shutil
import unittest
from pathlib import Path
import tempfile

from pact import compiler_harness


@unittest.skipUnless(shutil.which("cc") or shutil.which("gcc") or shutil.which("clang"), "no C compiler")
# Skipped on hosts with no C compiler, because the scenario needs a real binary.
class TestExecTimeout(unittest.TestCase):
    def test_infinite_loop_returns_failed_receipt(self):
        # Shrink the limit so the test takes ~1s instead of 10s.
        # Patch the module-level timeout down to 1s and restore it in `finally`, so a
        # failure cannot leak the short limit into other tests.
        original = compiler_harness.EXEC_TIMEOUT_S
        compiler_harness.EXEC_TIMEOUT_S = 1
        try:
            with tempfile.TemporaryDirectory() as ws:
                runner = compiler_harness.IsolatedSandboxRunner(Path(ws))
                receipt = runner.run_c_test("loop", "int main(void){ for(;;){} return 0; }")
        finally:
            compiler_harness.EXEC_TIMEOUT_S = original
        # A broken toolchain is an environment problem, not a regression: skip rather than fail.
        if not receipt.compilation_passed:
            self.skipTest("C toolchain unusable: " + receipt.stderr[:80])
        self.assertFalse(receipt.execution_passed)
        # 124 is the convention (as in coreutils `timeout`) for 'killed for taking too long'.
        self.assertEqual(receipt.exit_code, 124)
        self.assertIn("timed out", receipt.stderr)


if __name__ == "__main__":
    unittest.main()
