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

# URL path -> file written. "/about" is served from about.html by static hosts.
PAGES = {
    "/": "index.html",
    "/sq/": "sq/index.html",
    "/about": "about.html",
    "/sq/about": "sq/about.html",
    "/sources": "sources.html",
    "/sq/sources": "sq/sources.html",
    "/feed.xml": "feed.xml",
    "/sq/feed.xml": "sq/feed.xml",
    "/robots.txt": "robots.txt",
    "/sitemap.xml": "sitemap.xml",
}

# Security and caching headers, in Cloudflare Pages' _headers format
# (other hosts ignore this file).
HEADERS = """/*
  Content-Security-Policy: {csp}
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: interest-cohort=(), geolocation=(), camera=(), microphone=()
/static/*
  Cache-Control: public, max-age=604800
/data/*
  Cache-Control: no-cache
/feed.xml
  Content-Type: application/rss+xml; charset=utf-8
/sq/feed.xml
  Content-Type: application/rss+xml; charset=utf-8
https://:project.pages.dev/*
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
        {"key": g["key"], "articles": [_slim(a) for a in g["articles"]]}
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
    for path, out in PAGES.items():
        # The header tells the templates to render the static-site variant.
        resp = client.get(path, headers={"X-Static-Export": "1"})
        resp.raise_for_status()
        target = build / out
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(resp.content)

    # Cloudflare Pages serves 404.html for unknown URLs (with a real 404 status).
    (build / "404.html").write_bytes(client.get("/this-page-does-not-exist", headers={"X-Static-Export": "1"}).content)

    shutil.copytree(Path(main.HERE) / "static", build / "static")
    shutil.copy(Path(main.HERE) / "static" / "favicon.svg", build / "favicon.svg")
    # Only the main domain should appear in search results, not www or *.pages.dev.
    host = config.SITE_URL.split("://", 1)[-1]
    www_rule = "" if host.startswith(("localhost", "www.")) else f"https://www.{host}/*\n  X-Robots-Tag: noindex\n"
    (build / "_headers").write_text(HEADERS.format(csp=main.CSP, www_rule=www_rule))

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
