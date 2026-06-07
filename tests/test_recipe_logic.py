import datetime as dt
import types
import xml.etree.ElementTree as ET

from morning_squid import recipe


def article(id=None, url=None, title="t", utctime=None, author=None):
    return types.SimpleNamespace(
        id=id, url=url, title=title,
        utctime=utctime or dt.datetime(2026, 1, 1), author=author,
    )


def feed(title, articles):
    return types.SimpleNamespace(title=title, articles=list(articles))


def test_reading_time():
    assert recipe.reading_time(0) == "~1 min"
    assert recipe.reading_time(200, wpm=200) == "~1 min"
    assert recipe.reading_time(12000, wpm=200) == "~1 h 0 min"
    assert recipe.reading_time(13000, wpm=200) == "~1 h 5 min"


def test_drop_seen_removes_seen_and_empty_feeds():
    f = feed("blog", [article(id="a"), article(id="b")])
    empty_after = feed("only-seen", [article(id="c")])
    result = recipe.drop_seen([f, empty_after], {"b", "c"})
    assert len(result) == 1
    assert [a.id for a in result[0].articles] == ["a"]


def test_merge_chronologically_sorts_and_tags_author():
    f1 = feed("F1", [article(id="1", title="old", utctime=dt.datetime(2026, 1, 1))])
    f2 = feed("F2", [article(id="2", title="new", utctime=dt.datetime(2026, 1, 2))])
    merged = recipe.merge_chronologically([f1, f2])
    assert len(merged) == 1
    arts = merged[0].articles
    assert [a.id for a in arts] == ["2", "1"]  # newest first
    assert arts[0].author == "F2"
    assert merged[0].title == "All articles"


def test_collect_stats():
    arts = [
        article(utctime=dt.datetime(2026, 1, 1), author="A"),
        article(utctime=dt.datetime(2026, 1, 3), author="A"),
        article(utctime=dt.datetime(2026, 1, 2), author="B"),
    ]
    stats = recipe.collect_stats(arts)
    assert stats["count"] == 3
    assert stats["start"] == dt.datetime(2026, 1, 1)
    assert stats["end"] == dt.datetime(2026, 1, 3)
    assert stats["sources"]["A"] == 2


def test_stats_page_contains_key_fields():
    stats = recipe.collect_stats([article(utctime=dt.datetime(2026, 1, 1), author="A")])
    html = recipe.stats_page("My Title", stats, 400, wpm=200)
    assert "My Title" in html
    assert "Reading time" in html
    assert "400 words" in html


def test_article_page_regex():
    assert recipe.ARTICLE_PAGE.match("feed_0/article_2/index.html")
    assert recipe.ARTICLE_PAGE.match("feed_12/article_0/index.html")
    # Not an article entry page:
    assert not recipe.ARTICLE_PAGE.match("feed_0/index.html")
    assert not recipe.ARTICLE_PAGE.match("feed_0/article_2/index1.html")
    assert not recipe.ARTICLE_PAGE.match("index.html")


def test_relative_href():
    base = "feed_0/article_3/index.html"
    assert recipe.relative_href(base, "feed_0/article_4/index.html") == "../article_4/index.html"
    assert recipe.relative_href(base, "index.html") == "../../index.html"


def test_nav_block_first_article_has_no_prev():
    html = recipe.nav_block_html(
        prev=None,
        nxt=("feed_0/article_1/index.html", "Second"),
        contents_href="index.html",
        index=1, total=3,
        from_href="feed_0/article_0/index.html",
    )
    ET.fromstring(html)  # well-formed XML
    assert recipe.XHTML_NS in html
    assert "Article 1 of 3" in html
    assert ">·<" in html  # muted prev placeholder
    assert "Second" in html
    assert 'href="../article_1/index.html"' in html
    assert 'href="../../index.html"' in html  # Contents link


def test_nav_block_last_article_has_no_next():
    html = recipe.nav_block_html(
        prev=("feed_0/article_1/index.html", "Second"),
        nxt=None,
        contents_href="index.html",
        index=3, total=3,
        from_href="feed_0/article_2/index.html",
    )
    ET.fromstring(html)
    assert "Article 3 of 3" in html
    assert "‹ Second" in html
    assert html.count("·") >= 1  # next placeholder dot


def test_extra_css_constrains_images():
    css = recipe.DailyFeeds.extra_css
    assert "img" in css
    assert "max-width: 100%" in css
    assert f"max-height: {recipe.CONFIG['image_max_height']}" in css


def test_nav_block_truncates_long_titles():
    long_title = "x" * 80
    html = recipe.nav_block_html(
        prev=None,
        nxt=("feed_0/article_1/index.html", long_title),
        contents_href="index.html",
        index=1, total=2,
        from_href="feed_0/article_0/index.html",
    )
    assert long_title not in html
    assert "…" in html
