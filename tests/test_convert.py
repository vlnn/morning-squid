from pathlib import Path

from morning_squid import config, convert


def test_build_recipe_payload():
    cfg = config.DEFAULT_CONFIG
    payload = convert.build_recipe_payload(
        cfg, mark_seen=False, state_path=Path("/tmp/seen.json"), oldest_article=7
    )
    assert payload["title"] == "Daily Feeds"
    assert payload["mark_seen"] is False
    assert payload["oldest_article"] == 7
    assert payload["state_path"] == "/tmp/seen.json"
    assert payload["feeds"][0] == ["yogthos", "https://yogthos.net/feed.xml"]


def test_build_command_maps_pdf_flags():
    cmd = convert.build_command(Path("r.recipe"), Path("out.pdf"), config.DEFAULT_PDF)
    assert cmd[0] == "ebook-convert"
    assert "r.recipe" in cmd
    assert "out.pdf" in cmd
    assert "--output-profile=generic_eink_hd" in cmd
    assert "--custom-size=157x210" in cmd
    assert "--pdf-page-margin-left=28" in cmd
    assert "--pdf-serif-family=Vollkorn" in cmd
    assert "--pdf-default-font-size=15" in cmd


def test_build_command_skips_empty_and_appends_extra():
    pdf = {"output_profile": "", "custom_size": None, "extra_args": ["--foo", "--bar=1"]}
    cmd = convert.build_command(Path("r.recipe"), Path("out.pdf"), pdf)
    assert not any("--output-profile" in c for c in cmd)
    assert cmd[-2:] == ["--foo", "--bar=1"]


def test_dry_run_does_not_invoke(tmp_path, capsys):
    payload = {"title": "T", "feeds": [], "state_path": "x", "wpm": 200,
               "oldest_article": 1, "max_articles_per_feed": 1, "mark_seen": True}
    rc = convert.run(config.DEFAULT_CONFIG, tmp_path / "out.pdf", payload, dry_run=True)
    assert rc == 0
    out = capsys.readouterr().out
    assert "ebook-convert" in out
    assert "MORNING_SQUID_RECIPE=" in out
