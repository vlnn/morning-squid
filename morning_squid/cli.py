"""Command-line interface for morning-squid."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

from . import __version__, config, convert, feeds as feeds_mod, state


def _eprint(*args) -> None:
    print(*args, file=sys.stderr)


def _require_config() -> dict:
    if not config.exists():
        _eprint(
            f"No config at {config.config_path()}.\n"
            "Run `morning-squid config init` to create one."
        )
        raise SystemExit(2)
    return config.load()


# --- pull -----------------------------------------------------------------

def cmd_pull(args: argparse.Namespace) -> int:
    cfg = _require_config()

    if not args.dry_run and not convert.have_calibre():
        _eprint(
            "ebook-convert (Calibre) not found on PATH.\n"
            "Install Calibre: https://calibre-ebook.com/download"
        )
        return 127

    feeds = feeds_mod.load_feeds(config.feeds_path(cfg))
    if not feeds:
        _eprint(
            f"No feeds in {config.feeds_path(cfg)}.\n"
            "Add some with `morning-squid feeds add`."
        )
        return 1

    today = dt.date.today().isoformat()
    if args.output:
        output = Path(args.output).expanduser()
    else:
        output_dir = Path(cfg.get("output_dir", "~/squid")).expanduser()
        output = output_dir / f"news-{today}.pdf"

    payload = convert.build_recipe_payload(
        cfg,
        feeds,
        mark_seen=not args.no_mark_seen,
        state_path=config.state_path(cfg),
        oldest_article=args.since,
    )

    rc = convert.run(cfg, output, payload, dry_run=args.dry_run)
    if rc == 0 and not args.dry_run:
        if output.exists():
            size = output.stat().st_size
            print(f"Wrote {output} ({size / 1024:.0f} KiB)")
        else:
            # ebook-convert exits 0 with no output when every article was
            # already seen / no new content was found.
            _eprint("Nothing new to fetch -- no PDF produced.")
    return rc


# --- feeds ----------------------------------------------------------------

def cmd_feeds_list(args: argparse.Namespace) -> int:
    cfg = _require_config()
    path = config.feeds_path(cfg)
    feeds = feeds_mod.load_feeds(path)
    if not feeds:
        print(f"No feeds in {path}.")
        return 0
    width = max(len(f["name"]) for f in feeds)
    for f in feeds:
        print(f"{f['name']:<{width}}  {f['url']}")
    print(f"\n{len(feeds)} feed(s) in {path}")
    return 0


def cmd_feeds_add(args: argparse.Namespace) -> int:
    cfg = _require_config()
    path = config.feeds_path(cfg)
    feeds = feeds_mod.load_feeds(path)
    for f in feeds:
        if f["name"] == args.name:
            _eprint(f"A feed named {args.name!r} already exists.")
            return 1
    feeds.append({"name": args.name, "url": args.url})
    feeds_mod.save_feeds(path, feeds)
    print(f"Added {args.name} -> {args.url}")
    return 0


def cmd_feeds_remove(args: argparse.Namespace) -> int:
    cfg = _require_config()
    path = config.feeds_path(cfg)
    feeds = feeds_mod.load_feeds(path)
    kept = [f for f in feeds if f["name"] != args.name]
    if len(kept) == len(feeds):
        _eprint(f"No feed named {args.name!r}.")
        return 1
    feeds_mod.save_feeds(path, kept)
    print(f"Removed {args.name}")
    return 0


# --- config ---------------------------------------------------------------

def cmd_config_init(args: argparse.Namespace) -> int:
    try:
        path = config.init(force=args.force)
    except FileExistsError as exc:
        _eprint(f"Config already exists at {exc}. Use --force to overwrite.")
        return 1
    print(f"Wrote default config to {path}")
    return 0


def cmd_config_path(args: argparse.Namespace) -> int:
    print(config.config_path())
    return 0


def cmd_config_edit(args: argparse.Namespace) -> int:
    path = config.config_path()
    if not path.exists():
        config.init()
    editor = os.environ.get("EDITOR", "vi")
    return subprocess.run([editor, str(path)]).returncode


# --- status / reset -------------------------------------------------------

def cmd_status(args: argparse.Namespace) -> int:
    cfg = config.load()
    sp = config.state_path(cfg)
    print(f"config       {config.config_path()}"
          f"{'' if config.exists() else '  (missing -- using defaults)'}")
    print(f"state        {sp}")
    print(f"seen         {state.count_seen(sp)} article(s)")
    print(f"output dir   {Path(cfg.get('output_dir', '~/squid')).expanduser()}")
    fp = config.feeds_path(cfg)
    print(f"feeds file   {fp}{'' if fp.exists() else '  (missing)'}")
    print(f"feeds        {len(feeds_mod.load_feeds(fp))}")
    print(f"calibre      {'found' if convert.have_calibre() else 'NOT found on PATH'}")
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    cfg = config.load()
    sp = config.state_path(cfg)
    if not args.yes:
        n = state.count_seen(sp)
        reply = input(f"Forget {n} seen article(s)? The next pull will re-include them. [y/N] ")
        if reply.strip().lower() not in {"y", "yes"}:
            print("Aborted.")
            return 1
    n = state.clear_seen(sp)
    print(f"Cleared {n} seen article(s).")
    return 0


# --- parser ---------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="morning-squid",
        description="Pull your RSS/Atom feeds into a daily e-ink-friendly PDF.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_pull = sub.add_parser("pull", help="fetch new articles and render a PDF")
    p_pull.add_argument("-o", "--output", help="output PDF path (default: <output_dir>/news-DATE.pdf)")
    p_pull.add_argument("--since", type=int, metavar="DAYS",
                        help="only include articles newer than DAYS (overrides oldest_article)")
    p_pull.add_argument("--no-mark-seen", action="store_true",
                        help="don't record fetched articles as seen (useful for testing)")
    p_pull.add_argument("--dry-run", action="store_true",
                        help="print the ebook-convert command instead of running it")
    p_pull.set_defaults(func=cmd_pull)

    p_feeds = sub.add_parser("feeds", help="manage feeds")
    feeds_sub = p_feeds.add_subparsers(dest="feeds_command", required=True)
    feeds_sub.add_parser("list", help="list configured feeds").set_defaults(func=cmd_feeds_list)
    p_add = feeds_sub.add_parser("add", help="add a feed")
    p_add.add_argument("name")
    p_add.add_argument("url")
    p_add.set_defaults(func=cmd_feeds_add)
    p_rm = feeds_sub.add_parser("remove", help="remove a feed by name")
    p_rm.add_argument("name")
    p_rm.set_defaults(func=cmd_feeds_remove)

    p_config = sub.add_parser("config", help="manage configuration")
    config_sub = p_config.add_subparsers(dest="config_command", required=True)
    p_init = config_sub.add_parser("init", help="write a default config file")
    p_init.add_argument("-f", "--force", action="store_true", help="overwrite an existing config")
    p_init.set_defaults(func=cmd_config_init)
    config_sub.add_parser("path", help="print the config file path").set_defaults(func=cmd_config_path)
    config_sub.add_parser("edit", help="open the config in $EDITOR").set_defaults(func=cmd_config_edit)

    sub.add_parser("status", help="show config, state and environment summary").set_defaults(func=cmd_status)

    p_reset = sub.add_parser("reset", help="forget all seen articles")
    p_reset.add_argument("-y", "--yes", action="store_true", help="don't prompt for confirmation")
    p_reset.set_defaults(func=cmd_reset)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
