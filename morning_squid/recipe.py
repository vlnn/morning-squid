"""Calibre recipe used by morning-squid.

This module is *not* imported by the rest of the package at runtime; instead the
CLI copies it to a temporary ``*.recipe`` file and hands it to ``ebook-convert``,
which executes it inside Calibre's own Python interpreter.

All per-run configuration (feed list, title, state path, ...) is passed in via a
JSON file whose path lives in the ``MORNING_SQUID_RECIPE`` environment variable.
Keeping the configuration out of the source means the recipe never has to be
rewritten and there are no string-injection / quoting headaches.

The pure helper functions are deliberately free of any Calibre imports so they
can be unit-tested without Calibre installed.
"""

import json
import os
import posixpath
import re
from collections import Counter
from html import escape
from pathlib import Path

try:  # Calibre is only present when run by ebook-convert; tests import helpers.
    from calibre.web.feeds.news import BasicNewsRecipe
except ImportError:  # pragma: no cover - exercised only outside Calibre
    BasicNewsRecipe = object

try:
    from lxml import etree
except ImportError:  # pragma: no cover
    etree = None


INDEX_PAGE = re.compile(r'^feed_\d+/index\.html$')
ARTICLE_PAGE = re.compile(r'^feed_\d+/article_\d+/index\.html$')
FRONT_PAGE = 'index.html'
XHTML_NS = 'http://www.w3.org/1999/xhtml'
NAV_TITLE_MAX = 40

DEFAULTS = {
    'title': 'Daily Feeds',
    'feeds': [],
    'state_path': str(Path.home() / '.local/state/morning-squid/seen.json'),
    'wpm': 200,
    'oldest_article': 1000,
    'max_articles_per_feed': 100,
    'mark_seen': True,
    'nav_links': True,
}

STATS_CSS = '''
    body { margin: 3em 1em; text-align: center; }
    h1 { font-size: 2.6em; margin-bottom: 0.2em; }
    .date { font-size: 1.1em; margin-bottom: 3em; }
    table { margin: 0 auto; border-collapse: collapse; text-align: left; }
    td { padding: 0.3em 0.7em; vertical-align: top; }
    td.k { font-weight: bold; }
'''


def load_config():
    """Load the per-run recipe config from ``$MORNING_SQUID_RECIPE`` (JSON)."""
    cfg = dict(DEFAULTS)
    path = os.environ.get('MORNING_SQUID_RECIPE')
    if path and Path(path).exists():
        cfg.update(json.loads(Path(path).read_text()))
    return cfg


CONFIG = load_config()
STATE_PATH = Path(CONFIG['state_path']).expanduser()


def load_seen():
    if STATE_PATH.exists():
        return set(json.loads(STATE_PATH.read_text()))
    return set()


def save_seen(seen):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(sorted(seen)))


def article_id(article):
    return article.id or article.url


def drop_seen(feeds, seen):
    for feed in feeds:
        feed.articles = [a for a in feed.articles if article_id(a) not in seen]
    return [f for f in feeds if f.articles]


def merge_chronologically(feeds):
    if not feeds:
        return []
    for feed in feeds:
        for article in feed.articles:
            article.author = feed.title
    articles = [a for f in feeds for a in f.articles]
    articles.sort(key=lambda a: (a.utctime, a.title), reverse=True)
    merged = feeds[0]
    merged.title = 'All articles'
    merged.articles = articles
    return [merged]


def collect_stats(articles):
    times = [a.utctime for a in articles]
    return {
        'count': len(articles),
        'start': min(times),
        'end': max(times),
        'sources': Counter(a.author for a in articles),
    }


def reading_time(words, wpm=200):
    minutes = max(1, round(words / wpm))
    hours, rest = divmod(minutes, 60)
    return f'~{hours} h {rest} min' if hours else f'~{rest} min'


def stats_page(title, stats, words, wpm=200):
    sources = ', '.join(f'{name} ({n})' for name, n in stats['sources'].most_common())
    rows = [
        ('Articles', str(stats['count'])),
        ('Period', f"{stats['start']:%d %b %Y} — {stats['end']:%d %b %Y}"),
        ('Sources', sources),
        ('Reading time', f'{reading_time(words, wpm)} ({words:,} words)'),
    ]
    cells = ''.join(f'<tr><td class="k">{k}</td><td>{v}</td></tr>' for k, v in rows)
    return f'''<html xmlns="http://www.w3.org/1999/xhtml"><head><title>{title}</title>
<style>{STATS_CSS}</style></head><body>
<h1>{title}</h1>
<div class="date">{stats['end']:%A, %d %B %Y}</div>
<table>{cells}</table>
</body></html>'''


def article_header(soup, article):
    header = soup.new_tag('div')
    header['class'] = 'article-header'
    title = soup.new_tag('h2')
    title.string = article.title
    meta = soup.new_tag('div')
    meta['class'] = 'article-meta'
    meta.string = ' · '.join(
        part for part in (article.author, article.utctime.strftime('%a, %d %b %Y')) if part
    )
    header.append(title)
    header.append(meta)
    return header


def relative_href(from_href, to_href):
    """Link from one OEB document to another (posix, relative to from's dir)."""
    return posixpath.relpath(to_href, posixpath.dirname(from_href))


def _truncate(text, limit=NAV_TITLE_MAX):
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + '…'


def _nav_cell(side, target, from_href):
    """One side cell: a link to ``target`` (an (href, title) pair) or a muted dot."""
    if not target:
        return f'<td class="ms-nav-{side}">·</td>'
    href, title = target
    rel = escape(relative_href(from_href, href), quote=True)
    label = escape(_truncate(title))
    text = f'‹ {label}' if side == 'prev' else f'{label} ›'
    return f'<td class="ms-nav-{side}"><a href="{rel}">{text}</a></td>'


def nav_block_html(*, prev, nxt, contents_href, index, total, from_href):
    """Build the XHTML for one Prev · Contents · Next navigation block.

    ``prev``/``nxt`` are ``(href, title)`` tuples or ``None``. Returns a string
    in the XHTML namespace so Calibre renders it as part of the article.
    """
    contents_rel = escape(relative_href(from_href, contents_href), quote=True)
    center = (
        f'<a href="{contents_rel}">Contents</a>'
        f' · Article {index} of {total}'
    )
    return (
        f'<table xmlns="{XHTML_NS}" class="ms-nav"><tr>'
        + _nav_cell('prev', prev, from_href)
        + f'<td class="ms-nav-mid">{center}</td>'
        + _nav_cell('next', nxt, from_href)
        + '</tr></table>'
    )


class DailyFeeds(BasicNewsRecipe):
    title = CONFIG['title']
    oldest_article = CONFIG['oldest_article']
    max_articles_per_feed = CONFIG['max_articles_per_feed']
    auto_cleanup = True
    use_embedded_content = False
    remove_empty_feeds = True
    extra_css = '''
        .article-header h2 { margin: 0 0 0.1em 0; }
        .article-meta { font-size: 0.75em; color: #444; margin-bottom: 1em; }
        table.ms-nav { width: 100%; border-collapse: collapse;
            font-size: 0.7em; color: #666; margin: 1.5em 0 0.5em 0;
            border-top: 1px solid #ccc; }
        table.ms-nav td { padding: 0.4em 0; vertical-align: top; }
        .ms-nav a { text-decoration: none; color: #666; }
        .ms-nav-prev { text-align: left; }
        .ms-nav-mid { text-align: center; white-space: nowrap; }
        .ms-nav-next { text-align: right; }
    '''
    feeds = [tuple(f) for f in CONFIG['feeds']]

    def parse_feeds(self):
        feeds = drop_seen(super().parse_feeds(), load_seen())
        self.pending_ids = {article_id(a) for f in feeds for a in f.articles}
        merged = merge_chronologically(feeds)
        self.issue_stats = collect_stats(merged[0].articles) if merged else None
        self.issue_words = 0
        return merged

    def populate_article_metadata(self, article, soup, first):
        self.issue_words += len(soup.get_text(' ').split())
        if not first:
            return
        body = soup.find('body')
        if body is not None:
            body.insert(0, article_header(soup, article))

    def default_cover(self, cover_file):
        return False

    def cleanup(self):
        if CONFIG.get('mark_seen', True):
            save_seen(load_seen() | self.pending_ids)

    def postprocess_book(self, oeb, opts, log):
        for item in [i for i in oeb.spine if INDEX_PAGE.match(i.href)]:
            oeb.spine.remove(item)
            oeb.manifest.remove(item)
        for item in oeb.spine:
            if item.href == FRONT_PAGE:
                item.data = etree.fromstring(
                    stats_page(self.title, self.issue_stats, self.issue_words, CONFIG['wpm'])
                )
            for nav in item.data.xpath('//*[contains(@class, "calibre_navbar")]'):
                nav.getparent().remove(nav)
        if CONFIG.get('nav_links', True):
            self.insert_nav_links(oeb)

    @staticmethod
    def _item_title(item):
        """The article title, from the inserted header h2, falling back to <title>."""
        ns = {'x': XHTML_NS}
        for query in ('//x:div[contains(@class, "article-header")]//x:h2', '//x:title'):
            found = item.data.xpath(query, namespaces=ns)
            if found and found[0].text and found[0].text.strip():
                return found[0].text.strip()
        return 'article'

    def insert_nav_links(self, oeb):
        """Add a Prev · Contents · Next block to the top and bottom of each article."""
        articles = [i for i in oeb.spine if ARTICLE_PAGE.match(i.href)]
        total = len(articles)
        if not total:
            return
        titles = {item.href: self._item_title(item) for item in articles}
        ns = {'x': XHTML_NS}
        for idx, item in enumerate(articles, start=1):
            prev_item = articles[idx - 2] if idx > 1 else None
            next_item = articles[idx] if idx < total else None
            prev = (prev_item.href, titles[prev_item.href]) if prev_item else None
            nxt = (next_item.href, titles[next_item.href]) if next_item else None
            bodies = item.data.xpath('//x:body', namespaces=ns) or item.data.xpath('//body')
            if not bodies:
                continue
            body = bodies[0]
            html = nav_block_html(
                prev=prev, nxt=nxt, contents_href=FRONT_PAGE,
                index=idx, total=total, from_href=item.href,
            )
            body.insert(0, etree.fromstring(html))  # top, above the header
            body.append(etree.fromstring(html))      # bottom
