#!/usr/bin/env python3
# Packaging metadata for the magi-pact distribution (the "pact" package).
# Install in editable mode with "pip install -e ." to get the console commands below.
from setuptools import setup, find_packages

setup(
    name="magi-pact",
    version="1.0.0",
    description="Serverless, decentralized multi-agent consensus and message exchange for heterogeneous AI clusters",
    author="Magi Mesh Developers",
    author_email="maintainer@magi-mesh.org",
    url="https://github.com/magi-pact/magi_pact",
    # Only the pact package (and subpackages) is shipped; scripts/, tests/ and data/ stay out of the distribution.
    packages=find_packages(include=["pact*"]),
    entry_points={
        # Both command names point at the same entry point, pact.cli:main.
        "console_scripts": [
            "magi=pact.cli:main",
            "magi-pact=pact.cli:main",
        ],
    },
)
