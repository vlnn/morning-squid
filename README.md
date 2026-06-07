# morning-squid 🦑

Pull your RSS/Atom feeds into a single, daily, e-ink-friendly PDF.

`morning-squid` wraps [Calibre](https://calibre-ebook.com/)'s news engine: it
fetches the feeds you configure, drops articles you've already seen, merges
everything into one chronological "issue", prepends a stats page (article count,
sources, reading time) and renders a PDF tuned for e-readers.

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

No third-party Python packages are required.

## Install

```bash
pip install .            # from a checkout
# or, for development:
pip install -e ".[dev]"
```

This installs the `morning-squid` command.

## Quick start

```bash
morning-squid config init      # writes ~/.config/morning-squid/config.toml
morning-squid feeds list       # the default feed set ships ready to go
morning-squid pull             # -> ~/squid/news-YYYY-MM-DD.pdf
```

## Commands

| Command | Description |
| --- | --- |
| `pull` | Fetch new articles and render a PDF. |
| `feeds list` | List configured feeds. |
| `feeds add NAME URL` | Add a feed. |
| `feeds remove NAME` | Remove a feed. |
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

`~/.config/morning-squid/config.toml` (override with `$MORNING_SQUID_CONFIG`):

```toml
title = "Daily Feeds"
output_dir = "~/squid"
wpm = 200                  # words-per-minute for reading-time estimates
oldest_article = 1000      # max age (days) of articles to consider
max_articles_per_feed = 100

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

[[feeds]]
name = "tonsky"
url = "https://tonsky.me/feed.xml"

[[feeds]]
name = "lobste.rs"
url = "https://lobste.rs/top/rss"
```

Everything under `[pdf]` maps directly onto `ebook-convert` flags, so you can
retune the output for a different device. Anything in `extra_args` is passed
through verbatim.

State (seen articles) lives at `~/.local/state/morning-squid/seen.json`
(override with `state_path` in the config or `$XDG_STATE_HOME`).

## Run it as a service (systemd user timer)

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
pip install -e ".[dev]"
pytest
```

The feed-processing helpers in `morning_squid/recipe.py` are unit-tested without
Calibre installed (the Calibre import is guarded), and the config/convert layers
have their own tests.
