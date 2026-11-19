"""Magi Pact: 32-Seat Multi-Agent Production Coordination Framework."""
# Public API of the package: the protocol constants/enums come from protocol.py,
# and PactHerder (the coordinator class) from herder.py. Importing the package
# therefore imports both modules, so keep these imports free of side effects.
from .protocol import PROTOCOL_VERSION, MAX_SEATS, SeatState
from .herder import PactHerder

# The package version intentionally tracks the wire-protocol version so the two
# can never drift apart.
__version__ = PROTOCOL_VERSION
# Explicit export list: what `from pact import *` exposes.
__all__ = ["PROTOCOL_VERSION", "MAX_SEATS", "SeatState", "PactHerder"]
