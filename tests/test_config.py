import tomllib
from pathlib import Path

from morning_squid import config, feeds


def test_dumps_roundtrips_through_tomllib():
    text = config.dumps(config.DEFAULT_CONFIG)
    parsed = tomllib.loads(text)
    assert parsed["title"] == "Daily Feeds"
    assert parsed["wpm"] == 200
    assert parsed["feeds_file"] == "feeds.csv"
    assert parsed["pdf"]["serif_family"] == "Vollkorn"
    assert parsed["pdf"]["margin_left"] == 28
    # Feeds are no longer stored in TOML.
    assert "feeds" not in parsed


def test_escaping_handles_special_chars():
    cfg = {"title": 'a "quoted" \\ name', "pdf": {}}
    parsed = tomllib.loads(config.dumps(cfg))
    assert parsed["title"] == 'a "quoted" \\ name'


def test_load_merges_defaults(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('title = "Custom"\n')
    monkeypatch.setenv("MORNING_SQUID_CONFIG", str(cfg_file))
    loaded = config.load()
    assert loaded["title"] == "Custom"
    # defaults still present for unspecified keys
    assert loaded["wpm"] == 200
    assert loaded["pdf"]["serif_family"] == "Vollkorn"


def test_init_seeds_config_and_feeds(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.toml"
    monkeypatch.setenv("MORNING_SQUID_CONFIG", str(cfg_file))
    assert not config.exists()
    config.init()
    assert config.exists()
    assert config.config_path() == cfg_file

    fp = config.feeds_path(config.load())
    assert fp == tmp_path / "feeds.csv"
    seeded = feeds.load_feeds(fp)
    assert len(seeded) == len(config.DEFAULT_FEEDS)
    assert seeded[0]["name"] == "yogthos"


def test_feeds_path_absolute_and_relative(tmp_path, monkeypatch):
    cfg_file = tmp_path / "sub" / "config.toml"
    monkeypatch.setenv("MORNING_SQUID_CONFIG", str(cfg_file))
    # relative -> resolved against config dir
    assert config.feeds_path({"feeds_file": "feeds.csv"}) == tmp_path / "sub" / "feeds.csv"
    # absolute -> used as-is
    assert config.feeds_path({"feeds_file": "/tmp/other.csv"}) == Path("/tmp/other.csv")
