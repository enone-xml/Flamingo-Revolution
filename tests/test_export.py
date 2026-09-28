import json
import os

os.environ["RUN_SCHEDULER"] = "0"

from app import config, export
from tests.test_web import client  # noqa: F401  (reuses the seeded database fixture)


def test_export_writes_complete_static_site(client, tmp_path):  # noqa: F811
    site = export.run(str(tmp_path / "out"))
    for f in ("index.html", "sq/index.html", "about.html", "sq/sources.html",
              "feed.xml", "sq/feed.xml", "_headers", "static/css/site.css",
              "data/articles-en.json", "data/articles-sq-30d.json", "data/stats.json",
              "data/version.json", "sitemap.xml", "404.html"):
        assert (site / f).exists(), f
    html = (site / "index.html").read_text()
    assert 'data-static="1"' in html
    assert "/api/articles" not in html
    data = json.loads((site / "data/articles-sq.json").read_text())
    assert data["stats"]["max_id"] >= 3
    assert sum(len(g["articles"]) for g in data["groups"]) == 3
    assert "snippet" not in json.dumps(data)  # only public fields are published
    assert "<language>sq</language>" in (site / "sq/feed.xml").read_text()


def test_live_pages_are_not_static(client):  # noqa: F811
    assert 'data-static="1"' not in client.get("/").text


def test_export_is_repeatable(client, tmp_path):  # noqa: F811
    a = export.run(str(tmp_path / "out"))
    first = json.loads((a / "data/version.json").read_text())["content_hash"]
    b = export.run(str(tmp_path / "out"))
    assert json.loads((b / "data/version.json").read_text())["content_hash"] == first
    assert not (tmp_path / "out" / ".build").exists()


def test_export_writes_story_and_digest_pages(client, tmp_path):  # noqa: F811
    site = export.run(str(tmp_path / "out2"))
    stories = list((site / "story").glob("*.html"))
    assert len(stories) == 1 and (site / "sq" / "story" / stories[0].name).exists()
    assert 'data-static="1"' in stories[0].read_text()
    for f in ("digest.html", "sq/digest.html", "digest.xml", "sq/digest.xml"):
        assert (site / f).exists(), f
    data = json.loads((site / "data/articles-en.json").read_text())
    assert any(g["slug"] for g in data["groups"])
