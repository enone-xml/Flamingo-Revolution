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


def test_foreign_headlines_are_skipped_for_albanian_outlets():
    assert not keywords.is_candidate("Lufta trondit buxhetin e Ukrainës, qeveria shkurton shpenzimet", "", "AL")
    assert not keywords.is_candidate("Protesta në Prishtinë: qytetarët vazhdojnë", "", "AL")
    # Albanian stories still pass, including when Rama is named alongside another country.
    assert keywords.is_candidate("Qeveria miraton paketën e re fiskale", "", "AL")
    assert keywords.is_candidate("Rama takon Trump në Nju Jork", "", "AL")
    assert keywords.is_candidate("VKM-ja që i zhveshi mbrojtjen Nartës dërgohet në Kushtetuese", "", "AL")


def test_etag_kept_after_not_modified(tmp_path):
    from types import SimpleNamespace
    conn = db.connect(str(tmp_path / "e.db"))
    fetcher._record_ok(conn, "S", "u", SimpleNamespace(headers={"etag": "abc", "last-modified": "x"}), 1)
    fetcher._record_ok(conn, "S", "u", SimpleNamespace(headers={}), 0)  # 304 without headers
    row = conn.execute("SELECT etag, modified FROM feed_status").fetchone()
    assert (row["etag"], row["modified"]) == ("abc", "x")


def test_every_minutes_skips_until_due(tmp_path):
    conn = db.connect(str(tmp_path / "d.db"))
    src = {"name": "Big", "url": "u", "every": 30}
    assert fetcher.is_due(conn, src)            # never fetched
    conn.execute("INSERT INTO feed_status(source, last_ok_at) VALUES('Big', strftime('%Y-%m-%dT%H:%M:%SZ','now','-10 minutes'))")
    assert not fetcher.is_due(conn, src)        # fetched 10 min ago
    conn.execute("UPDATE feed_status SET last_ok_at = strftime('%Y-%m-%dT%H:%M:%SZ','now','-31 minutes')")
    assert fetcher.is_due(conn, src)
    assert fetcher.is_due(conn, {"name": "Big", "url": "u"})  # no interval: always


def test_always_source_keeps_series_parts_and_is_in_the_sources_file(tmp_path):
    from datetime import datetime, timezone
    from app import ai, db, fetcher
    assert "Flamingo Revolution" in fetcher.always_shown()
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    entries = [{"title": f"QEVERIA E SYLESHËVE {n}", "link": f"https://flamingorevolution.eu/n/{n}",
                "published": now, "summary": "ese"} for n in ("VI", "VII")]
    with db.session(str(tmp_path / "t.db")) as conn:
        assert fetcher.store_entries(conn, entries, "X", "sq", "AL", keyword_filter=False, fuzzy_dedup=False) == (2, 0)
    assert "movement's own site" in ai.build_prompt({"source": "X", "lang": "sq", "title": "t", "snippet": None}, [], True)
