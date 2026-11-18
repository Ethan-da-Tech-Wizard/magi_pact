#!/usr/bin/env python3
# ==============================================================================
# Program: magi.py
# Programmer: Ethan-da-Tech-Wizard
# Last Modified: November 18, 2026
# Purpose: Direct executable CLI runner and front-door entrypoint for Magi Pact.
#          Allows human developers and autonomous AI agents to interact with
#          the 32-Seat Serverless Consensus Mesh without requiring package
#          installation or system-wide pip registration.
# ==============================================================================

"""Magi CLI Executable Entrypoint and Script Launcher.

================================================================================
DISTRIBUTED SYSTEMS EDUCATIONAL OVERVIEW: ZERO-INSTALL RUNNER
================================================================================
Why Provide a Standalone Executable Runner?
------------------------------------------
In heterogeneous AI agent environments (where agents may spin up inside fresh
Docker containers, ephemeral GitHub Actions runners, or isolated virtualenv
sandboxes), running `pip install .` or `pip install -e .` can introduce unwanted
delays, external network dependencies, or permissions conflicts.

`magi.py` solves this by functioning as a self-contained entrypoint:
1. Dynamic Path Resolution:
   It dynamically inspects its own file location on disk, climbs up to the
   repository root, and injects that directory into Python's `sys.path`.
2. Immediate Execution:
   Any agent or human can immediately execute CLI commands such as:
       python3 pact/magi.py init --host Host-Alpha
       python3 pact/magi.py join --seat auto --name "Node-01"
       python3 pact/magi.py status
       python3 pact/magi.py who
       python3 pact/magi.py send --to 0 --msg "Task #42 complete"
3. Clean Separation of Concerns:
   `magi.py` contains zero business logic; it merely configures the runtime
   environment and delegates control directly to `pact.cli.main()`.
"""

# ------------------------------------------------------------------------------
# Standard Library Imports
# ------------------------------------------------------------------------------
import sys          # Access system-specific parameters and the module search path (sys.path)
from pathlib import Path  # Object-oriented filesystem path manipulation

# ------------------------------------------------------------------------------
# Dynamic sys.path Injection
# ------------------------------------------------------------------------------
# Find the absolute filesystem path of the repository root directory:
# __file__ -> /home/user/magi_pact/pact/magi.py
# .resolve() -> resolves any symlinks to find the true canonical path
# .parent -> /home/user/magi_pact/pact
# .parent -> /home/user/magi_pact (Repository Root)
repo_root = Path(__file__).resolve().parent.parent

# If the repository root is not already present in Python's module search path,
# prepend it to index 0 so that local `pact` package imports take precedence
# over any globally installed versions.
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# ------------------------------------------------------------------------------
# Core CLI Application Import
# ------------------------------------------------------------------------------
# Now that sys.path includes the repo root, we can cleanly import the unified
# command-line interface entrypoint from pact.cli.
from pact.cli import main

# ------------------------------------------------------------------------------
# Main Execution Guard
# ------------------------------------------------------------------------------
# The __name__ == "__main__" idiom ensures that this script only triggers CLI
# execution when invoked directly from the command line, and remains safely
# importable by test suites or wrapper scripts without side effects.
if __name__ == "__main__":
    main()
