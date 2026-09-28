# Contributing to Flamingo Watch

Thanks for helping! Flamingo Watch is an open, automated news aggregator about
the Flamingo Revolution protests in Albania and Edi Rama's government. It
doesn't fact-check or label outlets, and contributions should keep it that way.

## Good first contributions

- **Add a news source.** Albanian, regional or international outlets with a
  working RSS feed are welcome, from any political leaning. Follow
  "Add a news source" in the [README](README.md): test the feed with
  `scripts/probe_feeds.py`, then add one line to `sources.yaml`.
  Only use real feed URLs the outlet publishes, and only outlets whose
  robots.txt allows it.
- **Improve the keyword filter** in `app/keywords.py`, for example missing Albanian word forms.
- **Translations:** the interface text lives in `app/i18n.py`, in English and Albanian.
- **Design and accessibility** fixes in `app/templates` and `app/static`.
- Bug reports and ideas: open an issue.

## How to run it

```bash
cp .env.example .env
```
Creates local settings. Set `AI_MODE=fake` so no API key is needed.

```bash
docker compose up -d --build
```
Starts the site at http://localhost:8080.

```bash
docker compose run --rm web python -m pytest -q
```
Runs the tests.

## Pull requests

1. Fork the repo, make a branch, and keep each PR focused on one thing.
2. The **tests** check runs automatically on your PR and must pass.
3. A maintainer reviews and merges it. The live site updates itself within about
   10 minutes of a merge, once the tests pass on `main`.

## Rules that keep the project honest

- **Never commit secrets.** API keys and tokens go only in your own `.env`, which git ignores.
- Store and show only what's allowed: headline, source, time, link and our own
  short AI summary. **Never copy full article text.**
- Respect robots.txt and keep request rates gentle.
- No tracking, analytics, cookies or personal data.
- Don't label outlets as biased, and don't add editorial commentary to summaries.
