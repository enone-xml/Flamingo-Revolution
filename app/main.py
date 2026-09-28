"""Web app: pages (English at /..., Albanian at /sq/...), RSS feeds, sitemap and JSON API."""
import hashlib
import inspect
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

import yaml
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import ai, config, db, digest, feed, fetcher, i18n, scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
for noisy in ("httpx", "httpx2"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
HERE = Path(__file__).parent
ISO = "%Y-%m-%dT%H:%M:%SZ"


@asynccontextmanager
async def lifespan(app: FastAPI):
    sched = scheduler.start() if config.RUN_SCHEDULER else None
    yield
    if sched:
        sched.shutdown(wait=False)


app = FastAPI(title="Flamingo Watch", lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(GZipMiddleware, minimum_size=800)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")
# Changes whenever any static file changes, so browsers never use a stale cached copy.
ASSET_VERSION = hashlib.sha1(
    b"".join(p.read_bytes() for p in sorted((HERE / "static").rglob("*")) if p.is_file())
).hexdigest()[:10]

CSP = (
    "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; "
    "script-src 'self' 'inline-speculation-rules'; font-src 'self'; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'"
)
# Shared by the live app and the static export (_headers), so both send the same.
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "interest-cohort=(), browsing-topics=(), geolocation=(), camera=(), microphone=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


@app.middleware("http")
async def headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.update(SECURITY_HEADERS)
    if request.url.path.startswith("/static/"):
        # Every static URL carries ?v=<hash of the files>, so it can be cached for a year.
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp


# ---------------------------------------------------------------- helpers

def source_list() -> list[dict]:
    sources, _ = fetcher.load_sources()
    return sources


def parse_iso(iso: str) -> datetime:
    return datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def time_ago(iso: str | None, lang: str) -> str:
    if not iso:
        return i18n.t(lang, "updated_never")
    mins = int((datetime.now(timezone.utc) - parse_iso(iso)).total_seconds() // 60)
    if mins < 1:
        return i18n.t(lang, "just_now")
    if mins < 60:
        return i18n.t(lang, "min_ago", n=mins)
    if mins < 60 * 24:
        return i18n.t(lang, "h_ago", n=mins // 60)
    return i18n.t(lang, "d_ago", n=mins // 1440)


def lang_url(lang: str, path: str = "/") -> str:
    """'/about' -> '/about' (English) or '/sq/about' (Albanian)."""
    return path if lang == "en" else "/sq" + path


def dmy(iso: str | None) -> str:
    """'2026-09-28...' -> '28.09.2026' (the date style used on the site and in images)."""
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}" if iso else ""


templates.env.filters["dmy"] = dmy


def page_context(lang: str, page: str, path: str, static: bool) -> dict:
    """Everything the base template needs."""
    other = "sq" if lang == "en" else "en"
    return {
        "lang": lang,
        "page": page,
        "t": lambda key, **kw: i18n.t(lang, key, **kw),
        "tag_label": lambda tag: i18n.tag_label(lang, tag),
        "ago": lambda iso: time_ago(iso, lang),
        "url": lambda p="/": lang_url(lang, p),
        "switch_url": lang_url(other, path),
        "site_url": config.SITE_URL,
        "path": path,
        "v": ASSET_VERSION,
        "static": static,
        "rss_url": lang_url(lang, "/feed.xml"),
        "tag_labels": {tag: i18n.tag_label(lang, tag) for tag in ai.TAGS},
    }


def render(request: Request, name: str, lang: str, page: str, path: str, **ctx):
    base = page_context(lang, page, path, request.headers.get("x-static-export") == "1")
    if "ticker" not in ctx:
        with db.session() as conn:
            ctx["ticker"] = feed.latest(conn, lang, 5)
    return templates.TemplateResponse(request, name, {**base, **ctx})


def bilingual(path: str):
    """Register a GET endpoint in both languages: `path` (English) and `/sq{path}`.

    The decorated function takes `ui` (the interface language) plus any normal
    FastAPI parameters; `ui` is filled in per route, never read from the URL.
    """
    def decorator(fn):
        sig = inspect.signature(fn)
        params = [p for name, p in sig.parameters.items() if name != "ui"]
        for ui in i18n.LANGS:
            def endpoint(*args, _ui=ui, **kwargs):
                return fn(*args, ui=_ui, **kwargs)
            endpoint.__signature__ = sig.replace(parameters=params)
            endpoint.__name__ = f"{fn.__name__}_{ui}"
            app.add_api_route(lang_url(ui, path), endpoint, methods=["GET"], name=endpoint.__name__)
        return fn
    return decorator


# Pages that exist in both languages. The static export writes every one of them,
# and the sitemap lists those marked True.
PAGES = {"/": True, "/timeline": True, "/digest": True, "/about": True, "/sources": True, "/status": False}


def clean_filters(tag, source, src_lang, rng):
    tag = tag if tag in ai.TAGS else None
    rng = rng if rng in ("24h", "7d", "30d", "all") else "7d"
    src_lang = src_lang if src_lang in ("en", "sq") else None
    return tag, (source or None), src_lang, rng


def clean_query(q: str | None) -> str | None:
    return (q or "").strip()[:100] or None


# ---------------------------------------------------------------- pages

def home(request: Request, ui: str, tag=None, source=None, src_lang=None, rng="7d", page=1, q=None):
    tag, source, src_lang, rng = clean_filters(tag, source, src_lang, rng)
    q = clean_query(q)
    with db.session() as conn:
        data = feed.query_groups(conn, ui, tag, source, src_lang, rng, page=page, q=q)
        latest_digest = next(iter(digest.recent(conn, 1)), None)
        st = feed.stats(conn, len(source_list()))
        ticker = feed.latest(conn, ui, 5)
        sources = feed.source_names(conn)
    if page > 1 and not data["groups"]:
        raise HTTPException(status_code=404)  # past the last page
    filtered = bool(tag or source or src_lang or q or rng != "7d")
    path = "/" if page == 1 or filtered else f"/page/{page}"
    return render(
        request, "index.html", ui, "home", path,
        data=data, stats=st, ticker=ticker, sources=sources, tags=ai.TAGS, latest_digest=latest_digest,
        protest_day=feed.protest_day(), protest_start=config.PROTEST_START, filtered=filtered,
        max_feed_pages=config.MAX_FEED_PAGES,
        filters={"tag": tag, "source": source, "lang": src_lang, "range": rng, "q": q},
    )


@bilingual("/")
def home_page(request: Request, ui: str, tag: str | None = None, source: str | None = None,
              lang: str | None = None, range: str = "7d", page: int = Query(1, ge=1, le=500),
              q: str | None = None):
    return home(request, ui, tag, source, lang, range, page, q)


@bilingual("/page/{n}")
def home_paged(request: Request, ui: str, n: int):
    """Older stories without JavaScript or query strings (also exported as static pages)."""
    if n < 2 or n > 500:
        raise HTTPException(status_code=404)
    return home(request, ui, page=n)


@app.get("/sq")
def sq_redirect():
    return RedirectResponse("/sq/", status_code=301)


@bilingual("/about")
def about_page(request: Request, ui: str):
    return render(request, "about.html", ui, "about", "/about",
                  interval=config.FETCH_INTERVAL_MINUTES, n_sources=len(source_list()))


def feed_states(conn) -> list[dict]:
    """Every configured source with its current health (shared by Sources and Status)."""
    rows = {r["source"]: r for r in conn.execute("SELECT * FROM feed_status").fetchall()}
    out = []
    for s in source_list():
        r = rows.get(s["name"])
        state = "waiting"
        if r and r["last_ok_at"] and (not r["last_error_at"] or r["last_ok_at"] >= r["last_error_at"]):
            state = "ok"
        elif r and r["last_error_at"]:
            state = "err"
        out.append({**s, "state": state, "ok": state == "ok", "checked": r is not None,
                    "last_ok": r["last_ok_at"] if r else None,
                    "every": int(s.get("every") or config.FETCH_INTERVAL_MINUTES),
                    "home": "https://" + s["url"].split("/")[2]})
    return out


@bilingual("/sources")
def sources_page(request: Request, ui: str):
    with db.session() as conn:
        rows = feed_states(conn)
    return render(request, "sources.html", ui, "sources", "/sources", rows=rows)


def story_context(g: dict, lang: str) -> dict:
    lead = g["lead"]
    return {"story": g, "first": g["articles"][-1], "n": len(g["sources"]),
            "desc": i18n.t(lang, "seo_desc_story", title=lead["title"][:90], n=len(g["sources"]))}


@bilingual("/story/{slug}")
def story_page(request: Request, ui: str, slug: str):
    with db.session() as conn:
        g = feed.find_story(conn, ui, slug)
    if not g:
        raise HTTPException(status_code=404)
    return render(request, "story.html", ui, "story", f"/story/{slug}", **story_context(g, ui))


def status_context(conn) -> dict:
    """Everything the public status page shows. No money figures, just states."""
    now = datetime.now(timezone.utc)
    feeds = feed_states(conn)
    skip = db.get_meta(conn, "gdelt_skip_until") or ""
    paused = db.get_meta(conn, "ai_paused_until") or ""
    if config.AI_MODE == "off" or (config.AI_MODE == "real" and not config.ANTHROPIC_API_KEY):
        ai_state = "off"
    elif paused > now.isoformat():
        ai_state = "paused"
    elif db.get_meta(conn, "ai_budget_hit") == ai.month_now():
        ai_state = "budget"
    else:
        ai_state = "on"
    last_digest = next(iter(digest.recent(conn, 1)), None)
    return {
        "st": feed.stats(conn, len(feeds)),
        "feeds": feeds, "ok_count": sum(1 for f in feeds if f["state"] == "ok"),
        "search_paused": skip > now.strftime(ISO),
        "ai_state": ai_state,
        "last_digest": last_digest["day"] if last_digest else None,
        "generated": now.strftime(ISO),
        "interval": config.FETCH_INTERVAL_MINUTES,
    }


@bilingual("/status")
def status_page(request: Request, ui: str):
    with db.session() as conn:
        ctx = status_context(conn)
    return render(request, "status.html", ui, "status", "/status", **ctx)


def load_milestones() -> list[dict]:
    try:
        with open(config.TIMELINE_FILE, encoding="utf-8") as f:
            return (yaml.safe_load(f) or {}).get("milestones") or []
    except FileNotFoundError:
        return []


@bilingual("/timeline")
def timeline_page(request: Request, ui: str):
    with db.session() as conn:
        months = feed.timeline(conn, ui, load_milestones())
    return render(request, "timeline.html", ui, "timeline", "/timeline",
                  months=months, min_sources=feed.TIMELINE_MIN_SOURCES)


@bilingual("/digest")
def digest_page(request: Request, ui: str):
    with db.session() as conn:
        items = digest.recent(conn, 14)
    return render(request, "digest.html", ui, "digest", "/digest", digests=items)


# ---------------------------------------------------------------- RSS

def rss_response(lang: str, title: str, page_path: str, feed_path: str, description: str,
                 items: list[dict]) -> Response:
    """RSS 2.0. Items: title, link, guid, description, pub (datetime), optional source."""
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>',
        f"<title>{escape(title)}</title>",
        f"<link>{escape(config.SITE_URL + lang_url(lang, page_path))}</link>",
        f"<description>{escape(description)}</description>",
        f"<language>{lang}</language>",
        f'<atom:link href="{escape(config.SITE_URL + lang_url(lang, feed_path))}" rel="self" type="application/rss+xml"/>',
    ]
    for it in items:
        source = f'<source url="{escape(it["link"])}">{escape(it["source"])}</source>' if it.get("source") else ""
        out.append(
            f"<item><title>{escape(it['title'])}</title><link>{escape(it['link'])}</link>"
            f'<guid isPermaLink="false">{escape(it["guid"])}</guid>'
            f"<description>{escape(it['description'])}</description>{source}"
            f"<pubDate>{format_datetime(it['pub'])}</pubDate></item>"
        )
    out.append("</channel></rss>")
    return Response("".join(out), media_type="application/rss+xml; charset=utf-8",
                    headers={"Cache-Control": "public, max-age=300"})


def news_rss(lang: str) -> Response:
    lang = lang if lang in i18n.LANGS else "en"
    with db.session() as conn:
        latest = feed.latest(conn, lang, 50)
    items = [{
        "title": a["title"], "link": a["url"], "guid": f"flamingo-watch-{a['id']}",
        "description": ((a["summary"] or "") + f" ({a['source']})").strip(),
        "source": a["source"], "pub": parse_iso(a["published_at"]),
    } for a in latest]
    return rss_response(lang, i18n.t(lang, "site_name"), "/", "/feed.xml", i18n.t(lang, "tagline"), items)


@app.get("/feed.xml")
def rss_en(lang: str = "en"):  # ?lang=sq still works for early subscribers
    return news_rss(lang)


@app.get("/sq/feed.xml")
def rss_sq():
    return news_rss("sq")


@bilingual("/digest.xml")
def digest_rss(ui: str):
    with db.session() as conn:
        days = digest.recent(conn, 14)
    page = config.SITE_URL + lang_url(ui, "/digest")
    items = [{
        "title": f"{i18n.t(ui, 'digest_title')} · {d['day']}", "link": f"{page}#d-{d['day']}",
        "guid": f"flamingo-watch-digest-{d['day']}-{ui}",
        "description": " ".join(f"• {p[ui]}" for p in d["points"]), "pub": parse_iso(d["created_at"]),
    } for d in days]
    return rss_response(ui, f"{i18n.t(ui, 'site_name')} · {i18n.t(ui, 'digest_title')}", "/digest",
                        "/digest.xml", i18n.t(ui, "seo_desc_digest"), items)


# ---------------------------------------------------------------- data, SEO, health

@app.get("/api/articles")
def api_articles(page: int = Query(1, ge=1, le=500), per_page: int = Query(20, ge=1, le=50),
                 ui: str = "en", tag: str | None = None, source: str | None = None,
                 lang: str | None = None, range: str = "7d", since_id: int | None = None,
                 q: str | None = None):
    """Story groups, newest first. `ui` picks the language of titles and summaries;
    `q` searches headlines and summaries (accents ignored)."""
    ui = ui if ui in i18n.LANGS else "en"
    tag, source, lang, range = clean_filters(tag, source, lang, range)
    with db.session() as conn:
        data = feed.query_groups(conn, ui, tag, source, lang, range, page, per_page, since_id, q=clean_query(q))
        data["stats"] = feed.stats(conn, len(source_list()))
    return JSONResponse(data, headers={"Cache-Control": "public, max-age=30"})


@app.get("/api/stats")
def api_stats():
    with db.session() as conn:
        return feed.stats(conn, len(source_list()))


@app.get("/robots.txt")
def robots():
    return Response(f"User-agent: *\nAllow: /\n\nSitemap: {config.SITE_URL}/sitemap.xml\n",
                    media_type="text/plain")


def sitemap_urls(path: str, lastmod: str, changefreq: str | None = None) -> list[str]:
    """One <url> per language, each listing both language versions (hreflang)."""
    alts = "".join(
        f'<xhtml:link rel="alternate" hreflang="{hl}" href="{escape(config.SITE_URL + lang_url(lang, path))}"/>'
        for hl, lang in (("en", "en"), ("sq", "sq"), ("x-default", "en"))
    )
    freq = f"<changefreq>{changefreq}</changefreq>" if changefreq else ""
    return [f"<url><loc>{escape(config.SITE_URL + lang_url(lang, path))}</loc>"
            f"<lastmod>{lastmod}</lastmod>{freq}{alts}</url>" for lang in i18n.LANGS]


@app.get("/sitemap.xml")
def sitemap():
    """Every page in both languages, plus a page per story covered by 2+ outlets."""
    with db.session() as conn:
        last = db.get_meta(conn, "last_fetch_at") or datetime.now(timezone.utc).strftime(ISO)
        stories = feed.story_groups(conn, "en")
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for path, listed in PAGES.items():
        if listed:
            out += sitemap_urls(path, last if path == "/" else last[:10], "hourly" if path == "/" else "monthly")
    for g in stories:
        out += sitemap_urls(f"/story/{g['slug']}", g["lead"]["published_at"][:10])
    out.append("</urlset>")
    return Response("".join(out), media_type="application/xml")


@app.exception_handler(404)
async def not_found(request: Request, exc):
    lang = "sq" if request.url.path.startswith("/sq") else "en"
    resp = render(request, "404.html", lang, "404", "/")
    resp.status_code = 404
    return resp


@app.get("/health")
def health():
    """200 when the site is up and the fetcher ran recently; 503 otherwise,
    so an uptime monitor also notices a stuck scheduler."""
    with db.session() as conn:
        last = db.get_meta(conn, "last_fetch_at")
        count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    stale = bool(last) and (datetime.now(timezone.utc) - parse_iso(last)).total_seconds() \
        > max(45, 3 * config.FETCH_INTERVAL_MINUTES) * 60
    return JSONResponse({"ok": not stale, "last_fetch_at": last, "articles": count},
                        status_code=503 if stale else 200)
