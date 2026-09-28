import os

os.environ["RUN_SCHEDULER"] = "0"

import pytest
from fastapi.testclient import TestClient

from app import ai, config, db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    path = str(tmp_path / "web.db")
    monkeypatch.setattr(config, "DB_PATH", path)
    monkeypatch.setattr(config, "RUN_SCHEDULER", False)
    with db.session(path) as conn:
        for i, (title, key) in enumerate([
            ("Protesta në Zvërnec", "zvernec-protest"),
            ("Protesters gather at Zvërnec", "zvernec-protest"),
            ("Rama flet për SHISH", "shish-case"),
        ]):
            conn.execute(
                "INSERT INTO articles(url, title, title_norm, snippet, source, lang, published_at, fetched_at) "
                "VALUES(?, ?, ?, 'x', ?, 'sq', strftime('%Y-%m-%dT%H:%M:%SZ','now', ?), strftime('%Y-%m-%dT%H:%M:%SZ','now'))",
                (f"https://ex.al/{i}", title, title.lower(), f"Src{i}", f"-{i} minutes"),
            )
        db.set_meta(conn, "last_fetch_at", "2026-09-28T10:00:00Z")
    # Give them AI fields, but with story keys from the fixture (fake mode derives its own).
    ai.process_pending(path, backend=ai.FakeBackend())
    with db.session(path) as conn:
        conn.execute("UPDATE articles SET story_key = 'zvernec-protest', tags = '[\"protests\"]' WHERE id IN (1, 2)")
        conn.execute("UPDATE articles SET story_key = 'shish-case' WHERE id = 3")
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_home_pages_render(client):
    for path in ("/", "/sq/", "/about", "/sq/about", "/sources", "/sq/sources"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "Content-Security-Policy" in r.headers
    assert 'lang="sq"' in client.get("/sq/").text


def test_api_groups_by_story(client):
    data = client.get("/api/articles").json()
    assert data["total_groups"] == 2
    grouped = [g for g in data["groups"] if g["key"] == "zvernec-protest"][0]
    assert len(grouped["articles"]) == 2
    assert client.get("/api/articles?tag=protests").json()["total_groups"] == 1
    assert client.get("/api/articles?since_id=1").json()["new_since"] >= 1


def test_rss_is_valid_xml(client):
    import xml.etree.ElementTree as ET

    r = client.get("/feed.xml")
    assert r.headers["content-type"].startswith("application/rss+xml")
    root = ET.fromstring(r.content)
    assert len(root.findall("./channel/item")) == 3


def test_health_flags_stale_fetcher(client):
    from app import db as dbm
    with dbm.session() as conn:
        dbm.set_meta(conn, "last_fetch_at", "2020-01-01T00:00:00Z")
    assert client.get("/health").status_code == 503
    with dbm.session() as conn:
        from datetime import datetime, timezone
        dbm.set_meta(conn, "last_fetch_at", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    assert client.get("/health").status_code == 200


def test_seo_basics(client):
    home = client.get("/").text
    assert '<link rel="canonical"' in home and 'hreflang="x-default"' in home
    assert 'application/ld+json' in home and 'og:image' in home
    assert client.get("/sq/").text.count('lang="sq"') >= 1
    sm = client.get("/sitemap.xml")
    assert sm.status_code == 200 and sm.text.count("<url>") == 6
    assert "Sitemap:" in client.get("/robots.txt").text
    missing = client.get("/no-such-page")
    assert missing.status_code == 404 and "noindex" in missing.text


def test_same_story_key_days_apart_is_two_groups(client):
    from app import db as dbm, feed
    with dbm.session() as conn:
        conn.execute("INSERT INTO articles(url, title, title_norm, source, lang, published_at, fetched_at, ai_status, relevant, story_key, tags) "
                     "VALUES('https://ex.al/old', 'Protesta e vjetër', 'protesta e vjeter', 'Old', 'sq', strftime('%Y-%m-%dT%H:%M:%SZ','now','-6 days'), "
                     "strftime('%Y-%m-%dT%H:%M:%SZ','now'), 'done', 1, 'zvernec-protest', '[]')")
        data = feed.query_groups(conn, "en", rng="30d")
    keys = [g["key"] for g in data["groups"]]
    assert "zvernec-protest" in keys and any(k.startswith("zvernec-protest@") for k in keys)


def test_clean_result_without_story_key_does_not_group():
    from app import ai
    assert ai.clean_result({"relevant": False, "story_key": ""})["story_key"] is None
