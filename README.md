# Flamingo Watch

A near-real-time news aggregator about the Flamingo Revolution protests in
Albania and Edi Rama's government. Every 10 minutes it reads Albanian and
international news feeds, keeps what's on topic, has Claude Haiku write short
bilingual (EN/SQ) titles and summaries, and shows everything in one feed.

It doesn't fact-check or label outlets. It stores only the headline, source,
time, link and its own short summary.

Contributions are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md).

## Two ways to host it

- **Run on your PC and publish for free** (no server needed): see [STATIC-HOSTING.md](STATIC-HOSTING.md).
  Your PC fetches the news and uploads a static copy to Cloudflare Pages every 10 minutes.
- **Run on a small server** ($5–6 a month, updates around the clock): see [DEPLOY.md](DEPLOY.md).

## Run it locally

```bash
cp .env.example .env
```
Creates your local settings file. Leave `ANTHROPIC_API_KEY` empty and set `AI_MODE=fake` to try it without an API key.

```bash
docker compose up -d --build
```
Builds and starts the site plus the 10-minute fetcher.

Open http://localhost:8080 (English) or http://localhost:8080/sq/ (Albanian).

```bash
docker compose run --rm web python -m pytest -q
```
Runs the test suite inside the container.

## Check this month's AI spend

```bash
docker compose exec web python -m app.ai spend
```

This prints something like:

```
Month:          2026-09
AI mode:        real (claude-haiku-4-5-20251001)
AI calls:       412
Estimated cost: $0.8123 of $10.00 budget
Budget reached: no
Waiting for AI: 0 articles
```

When the estimate reaches `AI_MONTHLY_BUDGET_USD` ($10 by default), AI calls
stop until the 1st of next month. New articles still appear, with their original
headline and no summary. Also set a monthly limit in the Anthropic Console as
a second safety net (see DEPLOY.md, step 5).

## Add a news source

1. Find the outlet's **real** feed URL. Look for an RSS icon, or for
   `<link rel="alternate" type="application/rss+xml" ...>` in the page source.
2. Test it:

   ```bash
   echo "My Outlet | feed | https://example.al/feed/" | docker run --rm -i -v "$PWD/scripts:/s" python:3.12-slim sh -c "pip install -q feedparser httpx && python /s/probe_feeds.py"
   ```
   Downloads the feed once and prints how many entries it has and whether robots.txt allows it.
   You want `"status": 200`, `"entries"` above 0, and `"robots_ok": true`.
   You can also pass `home` instead of `feed` with the outlet's homepage, and the script finds the feed link for you.

3. Add one line to `sources.yaml`:

   ```yaml
   - {name: My Outlet, url: "https://example.al/feed/", lang: sq, country: AL}
   ```
   Use `lang: sq` or `en`. Use `country: AL` for Albanian outlets (looser keyword filter) or `INT` for international ones (they must mention Albania plus a topic word).

4. Restart locally with `docker compose up -d --build`, or deploy with `deploy/update.sh` on the server.
   The source shows on the Sources page, marked "working" after its first successful fetch.

## Where things are

| Path | What it does |
|---|---|
| `sources.yaml` | The feed list. `SOURCES.md` has the test results, including dropped feeds. |
| `app/fetcher.py` | Fetches feeds (obeys robots.txt, one request per second per host), dedupes, stores in SQLite |
| `app/keywords.py` | Keyword prefilter in English and Albanian (diacritics ignored) |
| `app/ai.py` | Claude Haiku step, budget guard, `spend` command |
| `app/main.py` | Web pages (`@bilingual` registers each page at `/…` and `/sq/…`; `PAGES` lists them for the export and sitemap), RSS, sitemap, `/api/articles`, `/health` |
| `app/templates`, `app/static` | Design: HTML, CSS, JS, fonts, GSAP/Lenis (self-hosted) |
| `app/export.py` | Builds the static copy of the site from `PAGES` (pages, story pages, `/page/N`, JSON, RSS, `_headers`) |
| `deploy/publish-loop.sh` | Uploads that copy to Cloudflare Pages when the news changes |
| `DEPLOY.md` | Step-by-step server deploy, backups, monitoring, costs |
| `STATIC-HOSTING.md` | Step-by-step free static hosting from your PC |

## API

`GET /api/articles?page=1&per_page=20&ui=en&tag=protests&source=Balkanweb&lang=sq&range=7d`

This returns story groups, newest first. Articles about the same event share a
`story_key` and appear in one group. `range` is `24h`, `7d`, `30d` or `all`.
`ui` picks the language of titles and summaries.

`GET /feed.xml?lang=sq` is an RSS feed of the latest 50 items.
