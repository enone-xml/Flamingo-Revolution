import time
from types import SimpleNamespace

from app import db, fetcher, keywords


def entry(title, link, summary="", age_s=0):
    t = time.gmtime(time.time() - age_s)
    return {"title": title, "link": link, "summary": summary, "published_parsed": t}


def test_keywords_ignore_diacritics_and_case():
    assert keywords.is_candidate("ZVËRNEC: punimet vazhdojnë", "", "INT")
    assert keywords.is_candidate("Zvernec works continue", "", "INT")
    assert keywords.is_candidate("Revolucioni i Flamingove", "", "INT")


def test_keywords_local_vs_international():
    # "Rama" alone counts for Albanian outlets, not for international ones.
    assert keywords.is_candidate("Rama takon ambasadorin", "", "AL")
    assert not keywords.is_candidate("Rama festival in India", "", "INT")
    assert not keywords.is_candidate("Urime për Ramazan Bajram", "", "AL")
    assert not keywords.is_candidate("Panorama e motit", "", "AL")
    # International needs Albania + a topic word.
    assert keywords.is_candidate("Police clash with protesters in Tirana", "", "INT")
    assert not keywords.is_candidate("Albania beat Serbia 2-0", "", "INT")


def test_normalize_url_strips_tracking():
    a = fetcher.normalize_url("https://Example.com/news/1/?utm_source=x&id=5#top")
    b = fetcher.normalize_url("https://example.com/news/1?id=5")
    assert a == b


def test_store_dedupes_url_and_similar_titles():
    conn = db.connect(":memory:")
    entries = [
        entry("Protesta para Kryeministrisë për Zvërnecin", "https://a.al/1"),
        entry("Protesta para Kryeministrisë për Zvërnecin", "https://a.al/1?utm_medium=rss"),
        entry("Protesta para Kryeministrisë për Zvërnecin!", "https://b.al/2"),
        entry("Sport: ndeshja e së dielës", "https://a.al/3"),
        entry("Zvërnec, lajm i vjetër", "https://a.al/4", age_s=30 * 86400),
    ]
    new, skipped = fetcher.store_entries(conn, entries, "Test", "sq", "AL")
    assert new == 1
    assert skipped == 1
    assert conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 1


def test_one_bad_feed_does_not_stop_others(tmp_path, monkeypatch):
    sources = tmp_path / "s.yaml"
    sources.write_text(
        "sources:\n"
        "  - {name: Bad, url: 'https://bad.invalid/feed', lang: sq, country: AL}\n"
        "  - {name: Good, url: 'https://good.invalid/feed', lang: sq, country: AL}\n"
    )
    rss = (b"<rss><channel><item><title>Rama flet per protesten</title>"
           b"<link>https://good.invalid/a</link></item></channel></rss>")

    def fake_get(self, url, headers=None, min_gap=0):
        if "bad" in url:
            raise fetcher.httpx.ConnectError("boom")
        return SimpleNamespace(status_code=200, content=rss, headers={}, text="")

    monkeypatch.setattr(fetcher.PoliteClient, "get", fake_get)
    monkeypatch.setattr(fetcher.PoliteClient, "allowed", lambda self, url: True)
    dbfile = str(tmp_path / "t.db")
    assert fetcher.run_once(db_path=dbfile, sources_path=str(sources)) == 1
    with db.session(dbfile) as conn:
        bad = conn.execute("SELECT last_error FROM feed_status WHERE source='Bad'").fetchone()
        assert "ConnectError" in bad["last_error"]
