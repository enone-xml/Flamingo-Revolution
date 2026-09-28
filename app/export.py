"""Write a complete static copy of the site: pages, JSON data, RSS and assets.

The result can be served by any static host (Cloudflare Pages, GitHub Pages,
shared hosting). Run by hand:  python -m app.export
"""
import hashlib
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from . import config, db, feed

log = logging.getLogger("export")

MAX_STORY_PAGES = 3000  # per language; keeps the site far below Cloudflare's 20,000-file limit
FEEDS = ["/feed.xml", "/digest.xml"]      # in both languages
FILES = ["/robots.txt", "/sitemap.xml"]   # one copy


def out_file(path: str) -> str:
    """URL path -> file name on a static host: '/' -> index.html, '/about' -> about.html,
    '/sq/' -> sq/index.html, '/feed.xml' -> feed.xml."""
    if path.endswith("/"):
        return path.lstrip("/") + "index.html"
    return path.lstrip("/") if "." in path.rsplit("/", 1)[-1] else path.lstrip("/") + ".html"


def headers_file(main) -> str:
    """Cloudflare Pages' _headers format (other hosts ignore it): the same security
    headers as the live app, plus caching rules.

    Note: we tried 'Cache-Control: no-transform' to stop Cloudflare injecting its
    analytics script, but it also switches off Cloudflare's compression (HTML went
    from ~15 KB to 79 KB), so it's not used. Our CSP blocks that script anyway."""
    sec = "".join(f"  {k}: {v}\n" for k, v in main.SECURITY_HEADERS.items())
    rss = "".join(f"{p}\n  Content-Type: application/rss+xml; charset=utf-8\n"
                  for p in ("/feed.xml", "/sq/feed.xml", "/digest.xml", "/sq/digest.xml"))
    return (
        "/*\n" + sec
        + "/static/*\n  Cache-Control: public, max-age=31536000, immutable\n"
        + "/data/*\n  Cache-Control: no-cache\n"
        + rss
    )


HEADERS_EXTRA = """https://:project.pages.dev/*
  X-Robots-Tag: noindex
{www_rule}"""


def _slim(article: dict) -> dict:
    keys = ("id", "url", "source", "published_at", "lang", "title", "summary", "tags", "ai")
    out = {k: article[k] for k in keys}
    if article["original_title"] != article["title"]:
        out["original_title"] = article["original_title"]  # only when it differs: smaller files
    return out


def _articles_json(conn, lang: str, rng: str) -> dict:
    data = feed.query_groups(conn, lang, rng=rng, per_page=100_000, max_rows=50_000)
    groups = [
        {"key": g["key"], "slug": g["slug"], "articles": [_slim(a) for a in g["articles"]]}
        for g in data["groups"]
    ]
    return {"groups": groups}


def _code_hash() -> str:
    """Changes whenever templates, CSS/JS or app code change, so a new version
    of the site gets published even if no new articles arrived."""
    h = hashlib.sha256()
    here = Path(__file__).parent
    for f in sorted(p for p in here.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        h.update(f.relative_to(here).as_posix().encode())
        h.update(f.read_bytes())
    for f in (config.TIMELINE_FILE, config.SOURCES_FILE):  # hand-edited content outside app/
        if Path(f).exists():
            h.update(Path(f).read_bytes())
    return h.hexdigest()[:12]


def run(export_dir: str | None = None) -> Path:
    """Build the site into <export_dir>/site. Returns that path."""
    from fastapi.testclient import TestClient

    from . import main  # imported late: main reads config at import time

    root = Path(export_dir or config.EXPORT_DIR)
    root.mkdir(parents=True, exist_ok=True)
    build = root / ".build"
    shutil.rmtree(build, ignore_errors=True)
    build.mkdir()

    client = TestClient(main.app)  # no "with": the scheduler doesn't start
    with db.session() as conn:
        total = feed.query_groups(conn, "en", per_page=20)["total_groups"]
    feed_pages = [f"/page/{n}" for n in range(2, min(config.MAX_FEED_PAGES, -(-total // 20)) + 1)]
    paths = [main.lang_url(lang, p) for p in [*main.PAGES, *feed_pages, *FEEDS] for lang in ("en", "sq")]
    for path in paths + FILES:
        # The header tells the templates to render the static-site variant.
        resp = client.get(path, headers={"X-Static-Export": "1"})
        resp.raise_for_status()
        target = build / out_file(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(resp.content)

    # One page per story covered by 2+ outlets (last 90 days), rendered straight from the
    # template instead of through the web app, which would re-query for every page.
    story_tpl = main.templates.get_template("story.html")
    with db.session() as conn:
        for lang in ("en", "sq"):
            ticker = feed.latest(conn, lang, 5)
            for g in feed.story_groups(conn, lang)[:MAX_STORY_PAGES]:
                path = f"/story/{g['slug']}"
                ctx = {**main.page_context(lang, "story", path, True), "ticker": ticker,
                       **main.story_context(g, lang)}
                out = build / ("sq" if lang == "sq" else "") / (path.lstrip("/") + ".html")
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(story_tpl.render(ctx), encoding="utf-8")

    # Cloudflare Pages serves 404.html for unknown URLs (with a real 404 status).
    (build / "404.html").write_bytes(client.get("/this-page-does-not-exist", headers={"X-Static-Export": "1"}).content)

    shutil.copytree(Path(main.HERE) / "static", build / "static")
    shutil.copy(Path(main.HERE) / "static" / "favicon.svg", build / "favicon.svg")
    # Only the main domain should appear in search results, not www or *.pages.dev.
    host = config.SITE_URL.split("://", 1)[-1]
    www_rule = "" if host.startswith(("localhost", "www.")) else f"https://www.{host}/*\n  X-Robots-Tag: noindex\n"
    (build / "_headers").write_text(headers_file(main) + HEADERS_EXTRA.format(www_rule=www_rule))

    data_dir = build / "data"
    data_dir.mkdir()
    with db.session() as conn:
        stats = feed.stats(conn, len(main.source_list()))
        # A small 7-day file for the default view (what phones load), and a
        # 30-day file only fetched when someone picks "30 days" or "All".
        articles = {(lang, rng): _articles_json(conn, lang, rng)
                    for lang in ("en", "sq") for rng in ("7d", "30d")}
    content_hash = hashlib.sha256(_code_hash().encode())
    for (lang, rng), payload in articles.items():
        payload["stats"] = stats
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        suffix = "" if rng == "7d" else "-30d"
        (data_dir / f"articles-{lang}{suffix}.json").write_text(body, encoding="utf-8")
        content_hash.update(json.dumps(payload["groups"], sort_keys=True).encode())
    (data_dir / "stats.json").write_text(json.dumps(stats))
    exported_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # The publisher reads this to decide whether a new upload is needed.
    (data_dir / "version.json").write_text(json.dumps({
        "content_hash": content_hash.hexdigest()[:16],
        "exported_at": exported_at,
    }))

    # Swap the finished build into place, so a half-written site is never published.
    site, old = root / "site", root / ".old"
    shutil.rmtree(old, ignore_errors=True)
    if site.exists():
        site.rename(old)
    build.rename(site)
    shutil.rmtree(old, ignore_errors=True)
    log.info("static site exported to %s (%s)", site, exported_at)
    return site


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    print(f"exported: {run(config.EXPORT_DIR or str(config.ROOT / 'data' / 'export'))}")
