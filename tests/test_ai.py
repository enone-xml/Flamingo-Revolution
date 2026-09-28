import json

from app import ai, config, db


def add_articles(path, n):
    with db.session(path) as conn:
        for i in range(n):
            conn.execute(
                "INSERT INTO articles(url, title, title_norm, snippet, source, lang, published_at, fetched_at) "
                "VALUES(?, ?, ?, ?, 'Test', 'sq', ?, ?)",
                (f"https://x.al/{i}", f"Protesta nr {i} në Tiranë", f"protesta nr {i}", "snippet",
                 f"2026-09-28T10:{i % 60:02d}:00Z", "2026-09-28T10:00:00Z"),
            )


def test_fake_mode_fills_fields_and_clears_snippet(tmp_path):
    path = str(tmp_path / "t.db")
    add_articles(path, 3)
    stats = ai.process_pending(path, backend=ai.FakeBackend())
    assert stats["done"] == 3
    with db.session(path) as conn:
        row = conn.execute("SELECT * FROM articles LIMIT 1").fetchone()
        assert row["ai_status"] == "done" and row["snippet"] is None
        assert json.loads(row["tags"]) == ["other"]
        assert ai.month_spend(conn) > 0
    # Nothing is processed twice.
    assert ai.process_pending(path, backend=ai.FakeBackend())["done"] == 0


def test_budget_guard_switches_to_keyword_only(tmp_path, monkeypatch):
    path = str(tmp_path / "t.db")
    add_articles(path, 10)
    one_call = ai.cost_of(700, 250)
    monkeypatch.setattr(config, "AI_MONTHLY_BUDGET_USD", one_call * 3.5)
    stats = ai.process_pending(path, backend=ai.FakeBackend())
    assert stats["done"] == 3
    assert stats["keyword_only"] == 7
    assert "YES" in ai.spend_report(path)


def test_failures_retry_then_give_up(tmp_path):
    class Broken:
        def call(self, prompt):
            raise RuntimeError("API down")

    path = str(tmp_path / "t.db")
    add_articles(path, 1)
    for _ in range(3):
        ai.process_pending(path, backend=Broken())
    with db.session(path) as conn:
        row = conn.execute("SELECT ai_status, ai_attempts FROM articles").fetchone()
    assert (row["ai_status"], row["ai_attempts"]) == ("failed", 3)


def test_no_key_means_keyword_only(tmp_path, monkeypatch):
    path = str(tmp_path / "t.db")
    add_articles(path, 2)
    monkeypatch.setattr(config, "AI_MODE", "real")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    assert ai.process_pending(path)["keyword_only"] == 2


def test_clean_result_filters_bad_tags_and_slugifies():
    res = ai.clean_result({"relevant": True, "tags": ["protests", "made-up"], "story_key": "Zvërnec Resort Protest!"})
    assert json.loads(res["tags"]) == ["protests"]
    assert res["story_key"] == "zvernec-resort-protest"


def test_out_of_credit_shows_headlines_and_pauses(tmp_path, monkeypatch):
    import anthropic
    import httpx

    path = str(tmp_path / "t.db")
    add_articles(path, 5)
    calls = []

    def no_credit(self, prompt):
        calls.append(1)
        resp = httpx.Response(400, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
        raise anthropic.BadRequestError(
            "Your credit balance is too low to access the Anthropic API.", response=resp, body=None)

    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(ai.RealBackend, "_call", no_credit)
    stats = ai.process_pending(path, backend=ai.RealBackend())
    assert len(calls) == 1                      # stopped after the first refusal
    assert stats["keyword_only"] == 5           # every article is shown right away
    with db.session(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM articles WHERE ai_status='keyword_only'").fetchone()[0] == 5
    assert "AI paused:      YES" in ai.spend_report(path)

    # While paused, new articles skip the API entirely.
    with db.session(path) as conn:
        conn.execute("INSERT INTO articles(url, title, title_norm, source, lang, published_at, fetched_at) "
                     "VALUES('https://x.al/new', 'Protesta e re', 'protesta e re', 'T', 'sq', '2026-09-28T11:00:00Z', '2026-09-28T11:00:00Z')")
    ai.process_pending(path, backend=ai.RealBackend())
    assert len(calls) == 1

    # After the pause, it tries again (e.g. once credit is topped up).
    with db.session(path) as conn:
        db.set_meta(conn, "ai_paused_until", "2000-01-01T00:00:00+00:00")
        conn.execute("INSERT INTO articles(url, title, title_norm, source, lang, published_at, fetched_at) "
                     "VALUES('https://x.al/new2', 'Protesta tjeter', 'protesta tjeter', 'T', 'sq', '2026-09-28T11:05:00Z', '2026-09-28T11:05:00Z')")
    assert ai.process_pending(path, backend=ai.FakeBackend())["done"] == 1


def test_other_bad_requests_are_not_account_errors(monkeypatch):
    import anthropic
    import httpx

    def bad(self, prompt):
        resp = httpx.Response(400, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
        raise anthropic.BadRequestError("prompt is too long", response=resp, body=None)

    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(ai.RealBackend, "_call", bad)
    try:
        ai.RealBackend().call("x")
    except ai.AccountError:
        raise AssertionError("should be a normal, per-article failure")
    except anthropic.BadRequestError:
        pass
