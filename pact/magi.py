#!/usr/bin/env python3
"""Magi CLI executable entrypoint.

Allows direct invocation via:
    python3 pact/magi.py join --seat auto
    python3 pact/magi.py who
    python3 pact/magi.py send --to <seat> --msg <text>
"""
import sys
from pathlib import Path

# Add repository root to sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from pact.cli import main

if __name__ == "__main__":
    main()
