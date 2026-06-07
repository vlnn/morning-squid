"""Configuration handling for morning-squid.

Config lives in a single TOML file (``~/.config/morning-squid/config.toml`` by
default). Reading uses the stdlib :mod:`tomllib`; writing uses a small,
schema-aware TOML emitter so the package has zero runtime dependencies.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from . import feeds as _feeds

APP = "morning-squid"

# Defaults ship with the original feed list and e-ink PDF tuning so the tool
# produces a useful PDF immediately after `morning-squid config init`.
DEFAULT_FEEDS: list[dict[str, str]] = [
    {"name": "yogthos", "url": "https://yogthos.net/feed.xml"},
    {"name": "Zine changelog", "url": "https://zine-ssg.io/log/index.xml"},
    {"name": "hauleth", "url": "https://plan.cat/~hauleth.rss"},
    {"name": "100r.co", "url": "https://100r.ca/links/rss.xml"},
    {"name": "lobste.rs", "url": "https://lobste.rs/top/rss"},
    {"name": "desmond rivet", "url": "https://desmondrivet.com/posts/feed_articles.xml"},
    {"name": "zylstra", "url": "https://www.zylstra.org/blog/feed/"},
    {"name": "zylstras book", "url": "https://www.zylstra.org/blog/category/myreads/feed"},
    {"name": "winny.tech", "url": "https://blog.winny.tech/posts/rss.xml"},
    {"name": "tonsky", "url": "https://tonsky.me/feed.xml"},
    {"name": "Stapelberg", "url": "https://michael.stapelberg.ch/feed.xml"},
    {"name": "Yossarian", "url": "https://blog.yossarian.net/feed.xml"},
    {"name": "simonwillison.com/til", "url": "https://til.simonwillison.net/tils/feed.atom"},
    {"name": "devault", "url": "https://drewdevault.com/blog/index.xml"},
    {"name": "simonwillison.com", "url": "https://simonwillison.net/atom/entries/"},
]

DEFAULT_PDF: dict[str, Any] = {
    "output_profile": "generic_eink_hd",
    "custom_size": "157x210",
    "unit": "millimeter",
    "margin_left": 28,
    "margin_right": 18,
    "margin_top": 14,
    "margin_bottom": 14,
    "serif_family": "Vollkorn",
    "default_font_size": 15,
    # Tappable article list in the PDF outline/bookmarks (reach it from any page).
    "add_toc": True,
    # Running footer on every page: current article title + page number.
    "footer": True,
}

DEFAULT_CONFIG: dict[str, Any] = {
    "title": "Daily Feeds",
    "output_dir": "~/squid",
    "wpm": 200,
    "oldest_article": 1000,
    "max_articles_per_feed": 100,
    # Add clickable Prev/Contents/Next nav at each article's top and bottom.
    "nav_links": True,
    # Cap how much vertical space an image may use (any CSS length). Keeps tall
    # images from swallowing whole pages; aspect ratio is preserved.
    "image_max_height": "9cm",
    # Feeds live in a separate CSV (see feeds.py). Relative paths are resolved
    # against the config directory.
    "feeds_file": "feeds.csv",
    "pdf": dict(DEFAULT_PDF),
}


def _xdg(var: str, default: Path) -> Path:
    value = os.environ.get(var)
    return Path(value) if value else default


def config_path() -> Path:
    """Return the path to the config file (override with ``$MORNING_SQUID_CONFIG``)."""
    override = os.environ.get("MORNING_SQUID_CONFIG")
    if override:
        return Path(override).expanduser()
    base = _xdg("XDG_CONFIG_HOME", Path.home() / ".config")
    return base / APP / "config.toml"


def default_state_path() -> Path:
    base = _xdg("XDG_STATE_HOME", Path.home() / ".local/state")
    return base / APP / "seen.json"


def state_path(cfg: dict[str, Any] | None = None) -> Path:
    cfg = cfg or {}
    custom = cfg.get("state_path")
    if custom:
        return Path(custom).expanduser()
    return default_state_path()


def feeds_path(cfg: dict[str, Any] | None = None) -> Path:
    """Resolve the feeds CSV path.

    Absolute or ``~``-prefixed values are used as-is; relative values are
    resolved against the config file's directory.
    """
    cfg = cfg or {}
    raw = cfg.get("feeds_file", "feeds.csv")
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return config_path().parent / path


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load() -> dict[str, Any]:
    """Load config, falling back to defaults for any missing keys."""
    path = config_path()
    if not path.exists():
        return _merge(DEFAULT_CONFIG, {})
    with path.open("rb") as fh:
        user = tomllib.load(fh)
    return _merge(DEFAULT_CONFIG, user)


def exists() -> bool:
    return config_path().exists()


def save(cfg: dict[str, Any]) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(cfg))
    return path


def init(force: bool = False) -> Path:
    """Write a default config and seed the feeds CSV with the default feeds."""
    path = config_path()
    if path.exists() and not force:
        raise FileExistsError(path)
    save(DEFAULT_CONFIG)
    fp = feeds_path(DEFAULT_CONFIG)
    if force or not fp.exists():
        _feeds.save_feeds(fp, [dict(f) for f in DEFAULT_FEEDS])
    return path


# --- minimal TOML emitter -------------------------------------------------

def _escape(s: str) -> str:
    out = []
    for ch in s:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\r":
            out.append("\\r")
        elif ord(ch) < 0x20:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return "".join(out)


def _fmt(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    return f'"{_escape(str(value))}"'


def dumps(cfg: dict[str, Any]) -> str:
    """Serialize our config schema to TOML.

    Handles scalars and one level of nested tables (e.g. ``[pdf]``) -- the only
    shapes this app's config uses (feeds live in a separate CSV).
    """
    lines: list[str] = ["# morning-squid configuration", ""]

    # Scalars first.
    scalars = {k: v for k, v in cfg.items() if not isinstance(v, dict)}
    for key, value in scalars.items():
        lines.append(f"{key} = {_fmt(value)}")
    if scalars:
        lines.append("")

    # Nested tables.
    for key, value in cfg.items():
        if isinstance(value, dict):
            lines.append(f"[{key}]")
            for sub_key, sub_value in value.items():
                lines.append(f"{sub_key} = {_fmt(sub_value)}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
