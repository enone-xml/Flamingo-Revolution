"""Web app: pages, RSS output and JSON API."""
import hashlib
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

from fastapi import FastAPI, Query, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import ai, config, db, feed, fetcher, i18n, scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
HERE = Path(__file__).parent


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
# Changes whenever CSS/JS change, so browsers never use a stale cached copy.
ASSET_VERSION = hashlib.sha1(
    b"".join((HERE / "static" / f).read_bytes() for f in ("css/site.css", "js/site.js"))
).hexdigest()[:10]

CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
    "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


@app.middleware("http")
async def headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["Content-Security-Policy"] = CSP
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "interest-cohort=(), geolocation=(), camera=(), microphone=()"
    if request.url.path.startswith("/static/"):
        resp.headers["Cache-Control"] = "public, max-age=604800"
    return resp


# ---------------------------------------------------------------- helpers

def source_list() -> list[dict]:
    sources, _ = fetcher.load_sources()
    return sources


def time_ago(iso: str | None, lang: str) -> str:
    if not iso:
        return i18n.t(lang, "updated_never")
    then = datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    mins = int((datetime.now(timezone.utc) - then).total_seconds() // 60)
    if mins < 1:
        return i18n.t(lang, "just_now")
    if mins < 60:
        return i18n.t(lang, "min_ago", n=mins)
    if mins < 60 * 24:
        return i18n.t(lang, "h_ago", n=mins // 60)
    return i18n.t(lang, "d_ago", n=mins // 1440)


def lang_url(lang: str, path: str = "/") -> str:
    return path if lang == "en" else "/sq" + path


def render(request: Request, name: str, lang: str, page: str, path: str, **ctx):
    other = "sq" if lang == "en" else "en"
    base = {
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
        "static": request.headers.get("x-static-export") == "1",
        "rss_url": "/feed.xml" if lang == "en" else "/sq/feed.xml",
        "tag_labels": {tag: i18n.tag_label(lang, tag) for tag in ai.TAGS},
    }
    if "ticker" not in ctx:
        with db.session() as conn:
            ctx["ticker"] = feed.latest(conn, lang, 5)
    return templates.TemplateResponse(request, name, {**base, **ctx})


def clean_filters(tag, source, src_lang, rng):
    tag = tag if tag in ai.TAGS else None
    rng = rng if rng in ("24h", "7d", "30d", "all") else "7d"
    src_lang = src_lang if src_lang in ("en", "sq") else None
    return tag, (source or None), src_lang, rng


# ---------------------------------------------------------------- pages

def home(request: Request, lang: str, tag, source, src_lang, rng, page=1):
    tag, source, src_lang, rng = clean_filters(tag, source, src_lang, rng)
    with db.session() as conn:
        data = feed.query_groups(conn, lang, tag, source, src_lang, rng, page=page)
        st = feed.stats(conn, len(source_list()))
        ticker = feed.latest(conn, lang, 5)
        sources = feed.source_names(conn)
    return render(
        request, "index.html", lang, "home", "/",
        data=data, stats=st, ticker=ticker, sources=sources, tags=ai.TAGS,
        filters={"tag": tag, "source": source, "lang": src_lang, "range": rng},
    )


@app.get("/")
def home_en(request: Request, tag: str | None = None, source: str | None = None,
            lang: str | None = None, range: str = "7d", page: int = Query(1, ge=1, le=500)):
    return home(request, "en", tag, source, lang, range, page)


@app.get("/sq/")
def home_sq(request: Request, tag: str | None = None, source: str | None = None,
            lang: str | None = None, range: str = "7d", page: int = Query(1, ge=1, le=500)):
    return home(request, "sq", tag, source, lang, range, page)


@app.get("/sq")
def sq_redirect():
    return RedirectResponse("/sq/", status_code=301)


def about(request: Request, lang: str):
    return render(request, "about.html", lang, "about", "/about",
                  interval=config.FETCH_INTERVAL_MINUTES, n_sources=len(source_list()))


@app.get("/about")
def about_en(request: Request):
    return about(request, "en")


@app.get("/sq/about")
def about_sq(request: Request):
    return about(request, "sq")


def sources_page(request: Request, lang: str):
    with db.session() as conn:
        status = {r["source"]: r for r in conn.execute("SELECT * FROM feed_status").fetchall()}
    rows = []
    for s in source_list():
        st = status.get(s["name"])
        ok = bool(st and st["last_ok_at"] and (not st["last_error_at"] or st["last_ok_at"] >= st["last_error_at"]))
        rows.append({**s, "ok": ok, "checked": st is not None,
                     "home": "https://" + s["url"].split("/")[2]})
    return render(request, "sources.html", lang, "sources", "/sources", rows=rows)


@app.get("/sources")
def sources_en(request: Request):
    return sources_page(request, "en")


@app.get("/sq/sources")
def sources_sq(request: Request):
    return sources_page(request, "sq")


# ---------------------------------------------------------------- data

@app.get("/api/articles")
def api_articles(page: int = Query(1, ge=1, le=500), per_page: int = Query(20, ge=1, le=50),
                 ui: str = "en", tag: str | None = None, source: str | None = None,
                 lang: str | None = None, range: str = "7d", since_id: int | None = None):
    """Story groups, newest first. `ui` picks the language of titles and summaries."""
    ui = ui if ui in i18n.LANGS else "en"
    tag, source, lang, range = clean_filters(tag, source, lang, range)
    with db.session() as conn:
        data = feed.query_groups(conn, ui, tag, source, lang, range, page, per_page, since_id)
        data["stats"] = feed.stats(conn, len(source_list()))
    return JSONResponse(data, headers={"Cache-Control": "public, max-age=30"})


@app.get("/api/stats")
def api_stats():
    with db.session() as conn:
        return feed.stats(conn, len(source_list()))


@app.get("/feed.xml")
def rss(lang: str = "en"):
    return build_rss(lang)


@app.get("/sq/feed.xml")
def rss_sq():
    return build_rss("sq")


def build_rss(lang: str) -> Response:
    lang = lang if lang in i18n.LANGS else "en"
    with db.session() as conn:
        items = feed.latest(conn, lang, 50)
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>',
        f"<title>{escape(i18n.t(lang, 'site_name'))}</title>",
        f"<link>{escape(config.SITE_URL + lang_url(lang))}</link>",
        f"<description>{escape(i18n.t(lang, 'tagline'))}</description>",
        f"<language>{lang}</language>",
        f'<atom:link href="{escape(config.SITE_URL + ("/feed.xml" if lang == "en" else "/sq/feed.xml"))}" rel="self" type="application/rss+xml"/>',
    ]
    for a in items:
        pub = datetime.strptime(a["published_at"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        desc = (a["summary"] or "") + f" ({a['source']})"
        out.append(
            "<item>"
            f"<title>{escape(a['title'])}</title>"
            f"<link>{escape(a['url'])}</link>"
            f'<guid isPermaLink="false">flamingo-watch-{a["id"]}</guid>'
            f"<description>{escape(desc.strip())}</description>"
            f"<source url=\"{escape(a['url'])}\">{escape(a['source'])}</source>"
            f"<pubDate>{format_datetime(pub)}</pubDate>"
            "</item>"
        )
    out.append("</channel></rss>")
    return Response("".join(out), media_type="application/rss+xml; charset=utf-8",
                    headers={"Cache-Control": "public, max-age=300"})


@app.get("/robots.txt")
def robots():
    return Response(f"User-agent: *\nAllow: /\n\nSitemap: {config.SITE_URL}/sitemap.xml\n",
                    media_type="text/plain")


SITEMAP_PATHS = ["/", "/about", "/sources"]


@app.get("/sitemap.xml")
def sitemap():
    """Every page in both languages, with hreflang alternates for search engines."""
    with db.session() as conn:
        last = db.get_meta(conn, "last_fetch_at") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for path in SITEMAP_PATHS:
        alts = "".join(
            f'<xhtml:link rel="alternate" hreflang="{hl}" href="{escape(config.SITE_URL + lang_url(l, path))}"/>'
            for hl, l in (("en", "en"), ("sq", "sq"), ("x-default", "en"))
        )
        for lang in i18n.LANGS:
            freq = "hourly" if path == "/" else "monthly"
            out.append(f"<url><loc>{escape(config.SITE_URL + lang_url(lang, path))}</loc>"
                       f"<lastmod>{last if path == '/' else last[:10]}</lastmod>"
                       f"<changefreq>{freq}</changefreq>{alts}</url>")
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
    stale = False
    if last:
        age = datetime.now(timezone.utc) - datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        stale = age.total_seconds() > max(45, 3 * config.FETCH_INTERVAL_MINUTES) * 60
    body = {"ok": not stale, "last_fetch_at": last, "articles": count}
    return JSONResponse(body, status_code=503 if stale else 200)
