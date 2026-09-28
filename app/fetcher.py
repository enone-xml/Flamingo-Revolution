"""Fetch all feeds, keep only likely-relevant articles, and store them.

Run once by hand:   python -m app.fetcher
"""
import calendar
import difflib
import html
import logging
import re
import time
import urllib.robotparser
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

import feedparser
import httpx
import yaml

from . import config, db, keywords

log = logging.getLogger("fetcher")

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_MIN_GAP = 30  # seconds between GDELT requests (they ask for >= 5; in practice they need more)
HOST_MIN_GAP = 1  # seconds between requests to the same host
TRACKING_PARAMS = re.compile(r"^(utm_|fbclid|gclid|mc_|ref$|ref_src$|cmp$)")
MAX_AGE = timedelta(days=7)  # ignore entries older than this


# ---------------------------------------------------------------- helpers

def load_sources(path: str | None = None) -> tuple[list[dict], list[dict]]:
    with open(path or config.SOURCES_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    sources = [s for s in data.get("sources", []) if s.get("enabled", True)]
    searches = [s for s in data.get("searches", []) if s.get("enabled", True)]
    return sources, searches


def normalize_url(url: str) -> str:
    """Drop tracking parameters, fragments and trailing slashes."""
    p = urlparse(url.strip())
    query = [(k, v) for k, v in parse_qsl(p.query) if not TRACKING_PARAMS.match(k)]
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", urlencode(query), ""))


def normalize_title(title: str) -> str:
    text = keywords.normalize(title)
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_text(value: str, limit: int) -> str:
    """Strip HTML tags and extra whitespace; cap the length."""
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def entry_time(entry) -> datetime:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc)
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_duplicate(conn, url: str, title_norm: str, published: datetime) -> bool:
    if conn.execute("SELECT 1 FROM articles WHERE url = ?", (url,)).fetchone():
        return True
    if not title_norm:
        return False
    if conn.execute("SELECT 1 FROM articles WHERE title_norm = ?", (title_norm,)).fetchone():
        return True
    # Near-identical titles from the last few days (e.g. same wire story).
    since = iso(published - timedelta(days=3))
    rows = conn.execute(
        "SELECT title_norm FROM articles WHERE published_at >= ? AND length(title_norm) BETWEEN ? AND ?",
        (since, int(len(title_norm) * 0.8), int(len(title_norm) * 1.2) + 1),
    ).fetchall()
    return any(
        difflib.SequenceMatcher(None, title_norm, r["title_norm"]).ratio() >= 0.92 for r in rows
    )


ROBOTS_TTL = 24 * 3600  # re-check each site's robots.txt once a day
_robots_cache: dict[str, tuple[float, "urllib.robotparser.RobotFileParser | None"]] = {}


class PoliteClient:
    """HTTP client that obeys robots.txt and waits between requests to a host."""

    def __init__(self):
        self.http = httpx.Client(
            headers={"User-Agent": config.USER_AGENT},
            timeout=httpx.Timeout(20.0),
            follow_redirects=True,
        )
        self._last_hit: dict[str, float] = {}

    def allowed(self, url: str) -> bool:
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        cached = _robots_cache.get(base)
        if not cached or time.monotonic() - cached[0] > ROBOTS_TTL:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.http.get(base + "/robots.txt")
                if r.status_code >= 400:
                    rp = None  # no robots.txt: everything allowed
                else:
                    rp.parse(r.text.splitlines())
            except httpx.HTTPError:
                rp = None
            _robots_cache[base] = (time.monotonic(), rp)
        rp = _robots_cache[base][1]
        return rp is None or rp.can_fetch(config.USER_AGENT, url)

    def get(self, url: str, headers: dict | None = None, min_gap: float = HOST_MIN_GAP) -> httpx.Response:
        host = urlparse(url).netloc
        wait = self._last_hit.get(host, 0) + min_gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            return self.http.get(url, headers=headers or {})
        finally:
            self._last_hit[host] = time.monotonic()

    def close(self):
        self.http.close()


# ---------------------------------------------------------------- core

def _record_ok(conn, name, url, resp, new_count):
    conn.execute(
        """INSERT INTO feed_status(source, url, etag, modified, last_ok_at, last_new)
           VALUES(?, ?, ?, ?, ?, ?)
           ON CONFLICT(source) DO UPDATE SET url=excluded.url,
             etag=COALESCE(excluded.etag, feed_status.etag),
             modified=COALESCE(excluded.modified, feed_status.modified),
             last_ok_at=excluded.last_ok_at, last_new=excluded.last_new""",
        (name, url, resp.headers.get("etag"), resp.headers.get("last-modified"),
         iso(datetime.now(timezone.utc)), new_count),
    )


def _record_error(conn, name, url, message):
    log.warning("feed %s failed: %s", name, message)
    conn.execute(
        """INSERT INTO feed_status(source, url, last_error_at, last_error)
           VALUES(?, ?, ?, ?)
           ON CONFLICT(source) DO UPDATE SET url=excluded.url,
             last_error_at=excluded.last_error_at, last_error=excluded.last_error""",
        (name, url, iso(datetime.now(timezone.utc)), message[:500]),
    )


def store_entries(conn, entries, source_name: str, lang: str, country: str,
                  source_from_entry: bool = False) -> tuple[int, int]:
    """Filter and insert feed entries. Returns (new, skipped_by_keyword)."""
    now = datetime.now(timezone.utc)
    new = skipped = 0
    for e in entries:
        link = e.get("link")
        title = clean_text(e.get("title", ""), 300)
        if not link or not title:
            continue
        published = min(entry_time(e), now)
        if now - published > MAX_AGE:
            continue
        snippet = clean_text(e.get("summary", ""), 600)
        if country != "SEARCH" and not keywords.is_candidate(title, snippet, country):
            skipped += 1
            continue
        url = normalize_url(link)
        title_norm = normalize_title(title)
        if is_duplicate(conn, url, title_norm, published):
            continue
        name = source_name
        if source_from_entry:
            # GDELT: use the outlet's domain as the source name.
            name = urlparse(url).netloc.removeprefix("www.")
        conn.execute(
            """INSERT OR IGNORE INTO articles
               (url, title, title_norm, snippet, source, lang, published_at, fetched_at)
               VALUES(?, ?, ?, ?, ?, ?, ?, ?)""",
            (url, title, title_norm, snippet, name, lang, iso(published), iso(now)),
        )
        new += 1
    return new, skipped


def fetch_feed(conn, client: PoliteClient, src: dict) -> int:
    name, url = src["name"], src["url"]
    if not client.allowed(url):
        _record_error(conn, name, url, "blocked by robots.txt")
        return 0
    prev = conn.execute("SELECT etag, modified FROM feed_status WHERE source = ?", (name,)).fetchone()
    headers = {}
    if prev and prev["etag"]:
        headers["If-None-Match"] = prev["etag"]
    if prev and prev["modified"]:
        headers["If-Modified-Since"] = prev["modified"]
    try:
        resp = client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        _record_error(conn, name, url, f"{type(exc).__name__}: {exc}")
        return 0
    if resp.status_code == 304:
        _record_ok(conn, name, url, resp, 0)
        return 0
    if resp.status_code != 200:
        _record_error(conn, name, url, f"HTTP {resp.status_code}")
        return 0
    parsed = feedparser.parse(resp.content)
    if not parsed.entries:
        _record_error(conn, name, url, "no entries in feed")
        return 0
    new, skipped = store_entries(conn, parsed.entries, name, src.get("lang", "sq"), src.get("country", "INT"))
    _record_ok(conn, name, url, resp, new)
    log.info("feed %-28s entries=%3d new=%2d filtered_out=%3d", name, len(parsed.entries), new, skipped)
    return new


class RateLimited(Exception):
    pass


def fetch_search(conn, client: PoliteClient, search: dict) -> int:
    name = search["name"]
    params = {
        "query": search["query"], "mode": "ArtList", "format": "rss",
        "maxrecords": "50", "timespan": "1d", "sort": "DateDesc",
    }
    url = GDELT_URL + "?" + urlencode(params, quote_via=quote)
    try:
        resp = client.get(url, min_gap=GDELT_MIN_GAP)
    except httpx.HTTPError as exc:
        _record_error(conn, name, url, f"{type(exc).__name__}: {exc}")
        return 0
    if resp.status_code == 429 or "limit requests" in resp.text[:200]:
        _record_error(conn, name, url, "rate limited by GDELT, skipping searches this run")
        raise RateLimited()
    if resp.status_code != 200:
        _record_error(conn, name, url, f"HTTP {resp.status_code}")
        return 0
    parsed = feedparser.parse(resp.content)
    # Search results already matched our query, so skip the keyword filter.
    new, _ = store_entries(conn, parsed.entries, name, search.get("lang", "en"), "SEARCH",
                           source_from_entry=True)
    _record_ok(conn, name, url, resp, new)
    log.info("search %-26s entries=%3d new=%2d", name, len(parsed.entries), new)
    return new


def run_once(db_path: str | None = None, sources_path: str | None = None) -> int:
    """Fetch every enabled source once. One failing feed never stops the rest."""
    sources, searches = load_sources(sources_path)
    client = PoliteClient()
    total = 0
    try:
        with db.session(db_path) as conn:
            for src in sources:
                try:
                    total += fetch_feed(conn, client, src)
                except Exception as exc:  # keep going whatever happens
                    log.exception("unexpected error in %s", src.get("name"))
                    _record_error(conn, src.get("name", "?"), src.get("url", ""), repr(exc))
                conn.commit()
            # GDELT rate-limits hard, so each run makes one search, taking turns.
            if searches:
                turn = int(db.get_meta(conn, "gdelt_turn", "0") or 0)
                db.set_meta(conn, "gdelt_turn", str(turn + 1))
                searches = [searches[turn % len(searches)]]
            for search in searches:
                try:
                    total += fetch_search(conn, client, search)
                except RateLimited:
                    conn.commit()
                    break  # back off until the next run
                except Exception as exc:
                    log.exception("unexpected error in search %s", search.get("name"))
                    _record_error(conn, search.get("name", "?"), "", repr(exc))
                conn.commit()
            db.set_meta(conn, "last_fetch_at", iso(datetime.now(timezone.utc)))
    finally:
        client.close()
    log.info("fetch finished: %d new articles", total)
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_once()
