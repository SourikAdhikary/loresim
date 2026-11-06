"""Typed exceptions and continuity traps for the LoreSim kernel."""

from __future__ import annotations


class LoreSimError(Exception):
    """Base exception for all LoreSim errors."""


class EpistemicLeakTrap(LoreSimError):
    """Raised when an agent references or acts on a secret/fact outside their EpistemicVault."""


class TeleportationViolationError(LoreSimError):
    """Raised when an agent moves between locations faster than minimum Dijkstra travel time."""


class InventoryViolationError(LoreSimError):
    """Raised when a unique item conservation law is violated."""


class DeadActorViolationError(LoreSimError):
    """Raised when a deceased or incapacitated agent performs an active event."""


class AttributeContradictionError(LoreSimError):
    """Raised when an immutable character or world attribute is contradicted."""


class ParadoxError(LoreSimError):
    """Raised on bi-temporal branch or causal timeline paradoxes."""
