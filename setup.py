#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="magi-pact",
    version="1.0.0",
    description="Serverless, decentralized multi-agent consensus and message exchange for heterogeneous AI clusters",
    author="Magi Mesh Developers",
    author_email="maintainer@magi-mesh.org",
    url="https://github.com/magi-pact/magi_pact",
    packages=find_packages(include=["pact*"]),
    entry_points={
        "console_scripts": [
            "magi=pact.cli:main",
            "magi-pact=pact.cli:main",
        ],
    },
)
