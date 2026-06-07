"""Driving Calibre's ``ebook-convert`` to render the recipe into a PDF."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

EBOOK_CONVERT = "ebook-convert"

# Map our [pdf] config keys onto ebook-convert flags. Keys with empty/None
# values are skipped. Anything in cfg["pdf"]["extra_args"] is appended verbatim.
PDF_FLAGS = {
    "output_profile": "--output-profile",
    "custom_size": "--custom-size",
    "unit": "--unit",
    "margin_left": "--pdf-page-margin-left",
    "margin_right": "--pdf-page-margin-right",
    "margin_top": "--pdf-page-margin-top",
    "margin_bottom": "--pdf-page-margin-bottom",
    "serif_family": "--pdf-serif-family",
    "default_font_size": "--pdf-default-font-size",
}

# Running footer on every physical page: current article (_SECTION_) on the left,
# page number on the right. _SECTION_ / _PAGENUM_ are substituted by Calibre.
# (PDF footers are page furniture, so this is for orientation, not tap targets --
#  use the PDF outline/bookmarks, enabled by add_toc, to jump between articles.)
FOOTER_TEMPLATE = (
    '<footer style="font-family:sans-serif; font-size:8px; color:#666;'
    ' width:100%; padding-top:2px; border-top:1px solid #ccc;">'
    '<span>_SECTION_</span>'
    '<span style="float:right">_PAGENUM_</span>'
    '</footer>'
)


def have_calibre() -> bool:
    return shutil.which(EBOOK_CONVERT) is not None


def recipe_source() -> Path:
    return Path(__file__).with_name("recipe.py")


# Conversion factors to inches. Used to turn page geometry / CSS lengths into a
# pixel cap so images never exceed a target PPI at their largest display size.
_UNIT_TO_INCH = {
    "inch": 1.0, "in": 1.0,
    "millimeter": 1 / 25.4, "mm": 1 / 25.4,
    "centimeter": 1 / 2.54, "cm": 1 / 2.54,
    "point": 1 / 72, "pt": 1 / 72,
    "pica": 1 / 6,
    "devicepixel": 1 / 96, "px": 1 / 96,
}


def _css_length_inches(value: Any) -> float | None:
    """Parse a CSS length such as ``9cm`` / ``90mm`` / ``3.5in`` into inches.

    Returns ``None`` for relative/unknown units (e.g. ``%``) we can't resolve.
    """
    if value is None:
        return None
    m = re.match(r"^\s*([0-9.]+)\s*([a-z%]*)\s*$", str(value).lower())
    if not m:
        return None
    factor = _UNIT_TO_INCH.get(m.group(2) or "px")
    return float(m.group(1)) * factor if factor else None


def _content_width_inches(pdf_cfg: dict[str, Any]) -> float | None:
    """Width of the text column in inches: page width (in ``unit``) minus the
    left/right margins (Calibre PDF margins are in points)."""
    size = pdf_cfg.get("custom_size")
    factor = _UNIT_TO_INCH.get(pdf_cfg.get("unit", "inch"))
    if not size or not factor:
        return None
    try:
        page = float(str(size).lower().split("x")[0]) * factor
    except ValueError:
        return None
    margins = float(pdf_cfg.get("margin_left", 0) or 0) + \
        float(pdf_cfg.get("margin_right", 0) or 0)
    return page - margins / 72.0


def image_scale_box(cfg: dict[str, Any]) -> list[int] | None:
    """Pixel ``[width, height]`` cap so images stay at/under ``image_max_ppi``.

    Bounds each dimension by its largest on-page display size (column width and
    ``image_max_height``); Calibre downscales larger images, preserving aspect
    ratio. Returns ``None`` when capping is disabled or geometry is unknown.
    """
    ppi = cfg.get("image_max_ppi")
    if not ppi:
        return None
    h_in = _css_length_inches(cfg.get("image_max_height"))
    w_in = _content_width_inches(cfg.get("pdf", {}))
    # If only one dimension is known, use it for both so resolution is still
    # bounded rather than silently disabled.
    w_in = w_in or h_in
    h_in = h_in or w_in
    if not w_in or not h_in:
        return None
    return [round(w_in * ppi), round(h_in * ppi)]


def build_recipe_payload(cfg: dict[str, Any], feeds: list[dict[str, str]], *,
                         mark_seen: bool, state_path: Path,
                         oldest_article: int | None = None) -> dict[str, Any]:
    """Translate the user config into the JSON the recipe expects."""
    return {
        "title": cfg.get("title", "Daily Feeds"),
        "feeds": [[f["name"], f["url"]] for f in feeds],
        "state_path": str(state_path),
        "wpm": cfg.get("wpm", 200),
        "oldest_article": oldest_article if oldest_article is not None
        else cfg.get("oldest_article", 1000),
        "max_articles_per_feed": cfg.get("max_articles_per_feed", 100),
        "nav_links": cfg.get("nav_links", True),
        "image_max_height": cfg.get("image_max_height", "9cm"),
        "scale_news_images": image_scale_box(cfg),
        "mark_seen": mark_seen,
    }


def build_command(recipe_file: Path, output: Path, pdf_cfg: dict[str, Any]) -> list[str]:
    cmd = [EBOOK_CONVERT, str(recipe_file), str(output)]
    for key, flag in PDF_FLAGS.items():
        value = pdf_cfg.get(key)
        if value is None or value == "":
            continue
        cmd.append(f"{flag}={value}")
    # Boolean toggles.
    if pdf_cfg.get("add_toc"):
        # Tappable table of contents reachable from any page via the reader's
        # outline/bookmarks button.
        cmd.append("--pdf-add-toc")
    if pdf_cfg.get("footer"):
        cmd.append(f"--pdf-footer-template={FOOTER_TEMPLATE}")
    for extra in pdf_cfg.get("extra_args", []):
        cmd.append(str(extra))
    return cmd


def run(cfg: dict[str, Any], output: Path, payload: dict[str, Any],
        *, dry_run: bool = False) -> int:
    """Render the recipe to ``output``. Returns the ebook-convert exit code."""
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="morning-squid-") as tmp:
        tmp_path = Path(tmp)
        payload_file = tmp_path / "recipe.json"
        payload_file.write_text(json.dumps(payload))

        # ebook-convert detects recipes by the .recipe extension, so copy the
        # packaged source into the temp dir under that name.
        recipe_file = tmp_path / "morning-squid.recipe"
        recipe_file.write_text(recipe_source().read_text())

        cmd = build_command(recipe_file, output, cfg.get("pdf", {}))

        if dry_run:
            print("MORNING_SQUID_RECIPE=" + str(payload_file))
            print(json.dumps(payload, indent=2))
            print(" ".join(cmd))
            return 0

        env = dict(os.environ, MORNING_SQUID_RECIPE=str(payload_file))
        proc = subprocess.run(cmd, env=env)
        return proc.returncode
