"""Helpers for the "seen articles" state file (shared format with the recipe)."""

from __future__ import annotations

import json
from pathlib import Path


def load_seen(path: Path) -> set[str]:
    if path.exists():
        return set(json.loads(path.read_text()))
    return set()


def count_seen(path: Path) -> int:
    return len(load_seen(path))


def clear_seen(path: Path) -> int:
    """Forget all seen articles. Returns how many were forgotten."""
    n = count_seen(path)
    if path.exists():
        path.unlink()
    return n
