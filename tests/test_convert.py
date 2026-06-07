from pathlib import Path

from morning_squid import config, convert


def test_build_recipe_payload():
    cfg = config.DEFAULT_CONFIG
    feeds = [{"name": "yogthos", "url": "https://yogthos.net/feed.xml"}]
    payload = convert.build_recipe_payload(
        cfg, feeds, mark_seen=False, state_path=Path("/tmp/seen.json"), oldest_article=7
    )
    assert payload["title"] == "Daily Feeds"
    assert payload["mark_seen"] is False
    assert payload["oldest_article"] == 7
    assert payload["state_path"] == "/tmp/seen.json"
    assert payload["feeds"][0] == ["yogthos", "https://yogthos.net/feed.xml"]
    assert payload["nav_links"] is True
    assert payload["image_max_height"] == "9cm"
    # Defaults cap images at 300 ppi: column width and 9cm height, in pixels.
    assert payload["scale_news_images"] == [1663, 1063]


def test_css_length_inches():
    assert convert._css_length_inches("9cm") == 9 * convert._UNIT_TO_INCH["cm"]
    assert convert._css_length_inches("90mm") == 90 * convert._UNIT_TO_INCH["mm"]
    assert convert._css_length_inches("1in") == 1.0
    assert convert._css_length_inches("96px") == 1.0
    assert convert._css_length_inches("50%") is None
    assert convert._css_length_inches(None) is None


def test_image_scale_box_respects_ppi_and_geometry():
    cfg = {
        "image_max_height": "9cm",
        "image_max_ppi": 300,
        "pdf": {"custom_size": "157x210", "unit": "millimeter",
                "margin_left": 28, "margin_right": 18},
    }
    # width: (157mm - (28+18)pt) in inches * 300; height: 9cm in inches * 300.
    assert convert.image_scale_box(cfg) == [1663, 1063]
    # Raising the PPI raises the pixel cap proportionally.
    assert convert.image_scale_box({**cfg, "image_max_ppi": 600}) == [3325, 2126]


def test_image_scale_box_disabled_without_ppi():
    cfg = {"image_max_height": "9cm", "pdf": config.DEFAULT_PDF}
    assert convert.image_scale_box({**cfg, "image_max_ppi": 0}) is None
    assert convert.image_scale_box(cfg) is None


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
    assert "--pdf-add-toc" in cmd
    assert any(c.startswith("--pdf-footer-template=") for c in cmd)


def test_build_command_skips_empty_and_appends_extra():
    pdf = {"output_profile": "", "custom_size": None, "extra_args": ["--foo", "--bar=1"]}
    cmd = convert.build_command(Path("r.recipe"), Path("out.pdf"), pdf)
    assert not any("--output-profile" in c for c in cmd)
    # add_toc/footer omitted when not set; extra_args stay last.
    assert not any("--pdf-add-toc" == c for c in cmd)
    assert not any(c.startswith("--pdf-footer-template=") for c in cmd)
    assert cmd[-2:] == ["--foo", "--bar=1"]


def test_dry_run_does_not_invoke(tmp_path, capsys):
    payload = {"title": "T", "feeds": [], "state_path": "x", "wpm": 200,
               "oldest_article": 1, "max_articles_per_feed": 1, "mark_seen": True}
    rc = convert.run(config.DEFAULT_CONFIG, tmp_path / "out.pdf", payload, dry_run=True)
    assert rc == 0
    out = capsys.readouterr().out
    assert "ebook-convert" in out
    assert "MORNING_SQUID_RECIPE=" in out
