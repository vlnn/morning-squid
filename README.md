# morning-squid 🦑

Pull your RSS/Atom feeds into a single, daily, e-ink-friendly PDF.

`morning-squid` wraps [Calibre](https://calibre-ebook.com/)'s news engine: it
fetches the feeds you configure, drops articles you've already seen, merges
everything into one chronological "issue", prepends a stats page (article count,
sources, reading time) and renders a PDF tuned for e-readers. Each article gets
a small clickable `‹ Prev · Contents · Next ›` bar at its top and bottom so you
can hop between articles (or skip one) on the device.

It started life as a single Calibre recipe plus a `pull.sh` one-liner. This is
the same idea, turned into a proper configurable CLI (and an optional systemd
service).

## How it works

```
your feeds ──▶ morning-squid pull ──▶ generates recipe + config ──▶ ebook-convert ──▶ news-YYYY-MM-DD.pdf
                                          (Calibre does the fetching & rendering)
```

Already-seen articles are remembered in a small state file, so each run only
contains what's new since last time.

## Requirements

- Python 3.11+
- **Calibre** (provides `ebook-convert`) on your `PATH` —
  <https://calibre-ebook.com/download>

No third-party Python packages are required. The project is managed with
[uv](https://docs.astral.sh/uv/).

## Install

Install it as a tool so the `morning-squid` command is on your `PATH`:

```bash
uv tool install .          # from a checkout
# or straight from git:
# uv tool install git+https://github.com/vlnn/morning-squid
```

Or run it without installing, from a checkout:

```bash
uv run morning-squid --help
```

## Quick start

```bash
morning-squid config init      # writes config.toml + a starter feeds.csv
morning-squid feeds list       # the default feed set ships ready to go
morning-squid pull             # -> ~/squid/news-YYYY-MM-DD.pdf
```

(prefix with `uv run` if you didn't `uv tool install`.)

## Commands

| Command | Description |
| --- | --- |
| `pull` | Fetch new articles and render a PDF. |
| `feeds list` | List feeds from the feeds CSV. |
| `feeds add NAME URL` | Add a feed to the CSV. |
| `feeds remove NAME` | Remove a feed from the CSV. |
| `config init [--force]` | Write a default config file. |
| `config path` | Print the config file path. |
| `config edit` | Open the config in `$EDITOR`. |
| `status` | Show config, state and whether Calibre is found. |
| `reset [--yes]` | Forget all "seen" articles (next pull re-includes them). |

### `pull` options

- `-o, --output PATH` — write to a specific path instead of `<output_dir>/news-DATE.pdf`.
- `--since DAYS` — only include articles newer than `DAYS` (overrides `oldest_article`).
- `--no-mark-seen` — don't record fetched articles as seen (handy for testing).
- `--dry-run` — print the `ebook-convert` command and recipe payload without running.

## Configuration

Settings live in `~/.config/morning-squid/config.toml` (override with
`$MORNING_SQUID_CONFIG`):

```toml
title = "Daily Feeds"
output_dir = "~/squid"
wpm = 200                  # words-per-minute for reading-time estimates
oldest_article = 1000      # max age (days) of articles to consider
max_articles_per_feed = 100
nav_links = true           # clickable Prev/Contents/Next bar per article
image_max_height = "9cm"   # cap image height so pictures don't swallow pages
feeds_file = "feeds.csv"   # relative paths resolve against the config dir

[pdf]
output_profile = "generic_eink_hd"
custom_size = "157x210"
unit = "millimeter"
margin_left = 28
margin_right = 18
margin_top = 14
margin_bottom = 14
serif_family = "Vollkorn"
default_font_size = 15
# extra_args = ["--some-other-ebook-convert-flag"]
```

Everything under `[pdf]` maps directly onto `ebook-convert` flags, so you can
retune the output for a different device. Anything in `extra_args` is passed
through verbatim.

### Feeds

Feeds are kept in a separate CSV (`~/.config/morning-squid/feeds.csv` by
default) so the list is easy to edit by hand, diff, or generate elsewhere. It's
a plain two-column file with a header:

```csv
name,url
tonsky,https://tonsky.me/feed.xml
lobste.rs,https://lobste.rs/top/rss
```

Manage it with `morning-squid feeds add/remove/list`, or just edit the CSV
directly. Point `feeds_file` at any path (absolute, `~`, or relative to the
config dir) to keep your feed list wherever you like.

State (seen articles) lives at `~/.local/state/morning-squid/seen.json`
(override with `state_path` in the config or `$XDG_STATE_HOME`).

## Run it as a service (systemd user timer)

`uv tool install .` puts the command at `~/.local/bin/morning-squid`, which is
what the unit calls.

```bash
mkdir -p ~/.config/systemd/user
cp contrib/morning-squid.service contrib/morning-squid.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now morning-squid.timer
```

A fresh PDF will then appear in your `output_dir` every morning. Inspect with
`systemctl --user list-timers` and `journalctl --user -u morning-squid`.

## Development

```bash
uv sync          # create the venv and install dev deps from uv.lock
uv run pytest
```

The feed-processing helpers in `morning_squid/recipe.py` are unit-tested without
Calibre installed (the Calibre import is guarded), and the config/convert layers
have their own tests.
