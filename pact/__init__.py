# Program: magi_pact - __init__.py
# Programmer: Ethan-da-Tech-Wizard (written with Claude, an AI assistant)
# Last Modified: 2026-11-18
# Purpose: Package entry point that exposes the protocol constants, SeatState and the PactHerder supervisor.

"""Magi Pact: 32-Seat Multi-Agent Production Coordination Framework."""
from .protocol import PROTOCOL_VERSION, MAX_SEATS, SeatState
from .herder import PactHerder

__version__ = PROTOCOL_VERSION
__all__ = ["PROTOCOL_VERSION", "MAX_SEATS", "SeatState", "PactHerder"]
