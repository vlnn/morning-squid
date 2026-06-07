import datetime as dt
import types

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
