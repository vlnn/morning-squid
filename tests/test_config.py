import tomllib

from morning_squid import config


def test_dumps_roundtrips_through_tomllib():
    text = config.dumps(config.DEFAULT_CONFIG)
    parsed = tomllib.loads(text)
    assert parsed["title"] == "Daily Feeds"
    assert parsed["wpm"] == 200
    assert parsed["pdf"]["serif_family"] == "Vollkorn"
    assert parsed["pdf"]["margin_left"] == 28
    assert len(parsed["feeds"]) == len(config.DEFAULT_FEEDS)
    assert parsed["feeds"][0]["name"] == "yogthos"


def test_escaping_handles_special_chars():
    cfg = {"title": 'a "quoted" \\ name', "feeds": [], "pdf": {}}
    parsed = tomllib.loads(config.dumps(cfg))
    assert parsed["title"] == 'a "quoted" \\ name'


def test_load_merges_defaults(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('title = "Custom"\n[[feeds]]\nname = "x"\nurl = "http://x"\n')
    monkeypatch.setenv("MORNING_SQUID_CONFIG", str(cfg_file))
    loaded = config.load()
    assert loaded["title"] == "Custom"
    # defaults still present for unspecified keys
    assert loaded["wpm"] == 200
    assert loaded["pdf"]["serif_family"] == "Vollkorn"
    assert loaded["feeds"] == [{"name": "x", "url": "http://x"}]


def test_init_and_path(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.toml"
    monkeypatch.setenv("MORNING_SQUID_CONFIG", str(cfg_file))
    assert not config.exists()
    config.init()
    assert config.exists()
    assert config.config_path() == cfg_file
