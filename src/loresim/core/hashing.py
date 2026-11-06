"""Deterministic canonical SHA-256 hashing for world events, facts, and epistemic states."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(data: Any) -> str:
    """Serialize arbitrary nested data into deterministic canonical JSON."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(payload: str | bytes) -> str:
    """Compute a 64-character hex SHA-256 digest."""
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    return hashlib.sha256(raw).hexdigest()


def compute_fact_id(subject: str, predicate: str, obj: str, objective_truth: bool = True) -> str:
    """Compute a deterministic fact ID for a canonical proposition `(subject, predicate, object)`."""
    _ = objective_truth
    digest = sha256_hex(
        canonical_json(
            {
                "s": subject.strip().lower(),
                "p": predicate.strip().lower(),
                "o": obj.strip().lower(),
            }
        )
    )[:12]
    return f"fact_{digest}"


def compute_event_digest(event_dict: dict[str, Any]) -> str:
    """Compute a deterministic digest for a world event."""
    return sha256_hex(canonical_json(event_dict))[:16]
