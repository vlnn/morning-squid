"""Feed list storage.

Feeds live in a simple two-column CSV (``name,url``) kept separate from the
TOML config so the list is easy to edit, diff, version, or generate from
elsewhere. The path is resolved by :func:`morning_squid.config.feeds_path`.
"""

from __future__ import annotations

import csv
from pathlib import Path

FIELDS = ["name", "url"]


def load_feeds(path: Path) -> list[dict[str, str]]:
    """Read feeds from a CSV file. Missing file -> empty list."""
    if not path.exists():
        return []
    feeds: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = (row.get("name") or "").strip()
            url = (row.get("url") or "").strip()
            if name and url:
                feeds.append({"name": name, "url": url})
    return feeds


def save_feeds(path: Path, feeds: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(FIELDS)
        for f in feeds:
            writer.writerow([f["name"], f["url"]])
