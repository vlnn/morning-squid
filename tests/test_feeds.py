from morning_squid import feeds


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "feeds.csv"
    data = [
        {"name": "tonsky", "url": "https://tonsky.me/feed.xml"},
        {"name": "lobste.rs", "url": "https://lobste.rs/top/rss"},
    ]
    feeds.save_feeds(path, data)
    assert feeds.load_feeds(path) == data
    # Has a header row.
    assert path.read_text().splitlines()[0] == "name,url"


def test_load_missing_returns_empty(tmp_path):
    assert feeds.load_feeds(tmp_path / "nope.csv") == []


def test_load_skips_blank_rows_and_trims(tmp_path):
    path = tmp_path / "feeds.csv"
    path.write_text("name,url\n tonsky , https://tonsky.me/feed.xml \n,\nonlyname,\n")
    assert feeds.load_feeds(path) == [
        {"name": "tonsky", "url": "https://tonsky.me/feed.xml"},
    ]


def test_save_handles_commas_in_names(tmp_path):
    path = tmp_path / "feeds.csv"
    data = [{"name": "a, b", "url": "http://x?q=1,2"}]
    feeds.save_feeds(path, data)
    assert feeds.load_feeds(path) == data
