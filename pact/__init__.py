"""Magi Pact: 32-Seat Multi-Agent Production Coordination Framework."""
from .protocol import PROTOCOL_VERSION, MAX_SEATS, SeatState
from .herder import PactHerder

__version__ = PROTOCOL_VERSION
__all__ = ["PROTOCOL_VERSION", "MAX_SEATS", "SeatState", "PactHerder"]
