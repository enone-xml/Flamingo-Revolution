"""Queries for the website: filtered, grouped articles and site stats."""
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TIRANA = ZoneInfo("Europe/Tirane")
GROUP_SPAN = timedelta(days=3)  # a story key only groups articles this close together

RANGES = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
VISIBLE = "(a.relevant = 1 OR a.ai_status IN ('keyword_only', 'failed'))"


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _age_gap(newest: dict, older: dict) -> timedelta:
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return datetime.strptime(newest["published_at"], fmt) - datetime.strptime(older["published_at"], fmt)


def article_dict(row, lang: str) -> dict:
    """One article, with title/summary in the reader's language when we have it."""
    has_ai = row["ai_status"] == "done"
    title = (row["title_sq"] if lang == "sq" else row["title_en"]) if has_ai else None
    summary = None
    if has_ai:  # prefer the reader's language, else the other one rather than nothing
        first, second = ("summary_sq", "summary_en") if lang == "sq" else ("summary_en", "summary_sq")
        summary = row[first] or row[second] or None
    return {
        "id": row["id"],
        "url": row["url"],
        "source": row["source"],
        "published_at": row["published_at"],
        "lang": row["lang"],
        "title": title or row["title"],
        "original_title": row["title"],
        "summary": summary or None,
        "title_en": row["title_en"],
        "title_sq": row["title_sq"],
        "summary_en": row["summary_en"],
        "summary_sq": row["summary_sq"],
        "tags": json.loads(row["tags"]) if row["tags"] else [],
        "story_key": row["story_key"],
        "ai": has_ai,
    }


def query_groups(conn, lang="en", tag=None, source=None, src_lang=None, rng="7d",
                 page=1, per_page=20, since_id=None, max_rows=2000) -> dict:
    """Return story groups, newest first. Articles sharing a story_key are one group."""
    where, args = [VISIBLE], []
    if rng in RANGES:
        where.append("a.published_at >= ?")
        args.append(_iso(datetime.now(timezone.utc) - RANGES[rng]))
    if tag:
        where.append("EXISTS (SELECT 1 FROM json_each(a.tags) WHERE json_each.value = ?)")
        args.append(tag)
    if source:
        where.append("a.source = ?")
        args.append(source)
    if src_lang in ("en", "sq"):
        where.append("a.lang = ?")
        args.append(src_lang)
    rows = conn.execute(
        f"SELECT a.* FROM articles a WHERE {' AND '.join(where)} "
        "ORDER BY a.published_at DESC LIMIT ?",
        (*args, max_rows),
    ).fetchall()

    groups, index = [], {}
    for row in rows:
        art = article_dict(row, lang)
        key = art["story_key"] or f"id-{art['id']}"
        if key in index and _age_gap(groups[index[key]]["articles"][0], art) > GROUP_SPAN:
            key = f"{key}@{art['published_at'][:10]}"  # same slug, different event days apart
        if key in index:
            groups[index[key]]["articles"].append(art)
        else:
            index[key] = len(groups)
            groups.append({"key": key, "articles": [art]})
    for g in groups:
        lead = g["articles"][0]
        g["lead"] = lead
        g["max_id"] = max(a["id"] for a in g["articles"])
        g["sources"] = sorted({a["source"] for a in g["articles"]})
        g["tags"] = sorted({t for a in g["articles"] for t in a["tags"]})

    total = len(groups)
    new_count = sum(1 for g in groups if since_id and g["max_id"] > since_id) if since_id else 0
    start = (max(page, 1) - 1) * per_page
    return {
        "groups": groups[start:start + per_page],
        "page": page,
        "per_page": per_page,
        "total_groups": total,
        "has_more": start + per_page < total,
        "new_since": new_count,
    }


def stats(conn, source_count: int) -> dict:
    # "Today" as people in Albania count it, not UTC.
    midnight = datetime.now(TIRANA).replace(hour=0, minute=0, second=0, microsecond=0)
    today = _iso(midnight.astimezone(timezone.utc))
    today_count = conn.execute(
        f"SELECT COUNT(*) FROM articles a WHERE {VISIBLE} AND a.published_at >= ?", (today,)
    ).fetchone()[0]
    last = conn.execute("SELECT value FROM meta WHERE key = 'last_fetch_at'").fetchone()
    max_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM articles").fetchone()[0]
    return {
        "articles_today": today_count,
        "sources": source_count,
        "last_updated": last["value"] if last else None,
        "max_id": max_id,
    }


def latest(conn, lang: str, n: int = 5) -> list[dict]:
    rows = conn.execute(
        f"SELECT a.* FROM articles a WHERE {VISIBLE} ORDER BY a.published_at DESC LIMIT ?", (n,)
    ).fetchall()
    return [article_dict(r, lang) for r in rows]


def source_names(conn) -> list[str]:
    return [r[0] for r in conn.execute(
        f"SELECT DISTINCT a.source FROM articles a WHERE {VISIBLE} ORDER BY a.source"
    ).fetchall()]
