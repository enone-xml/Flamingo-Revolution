# Feed test results

Tested on 2026-09-28 with `scripts/probe_feeds.py`, which looks for the feed
link each site publishes in its own HTML, downloads it, counts the entries and
checks robots.txt. To re-test, run:

```bash
docker run --rm -i -v "$PWD/scripts:/s" python:3.12-slim sh -c "pip install -q feedparser httpx && python /s/probe_feeds.py" < scripts/candidates.txt
```

## Working (in `sources.yaml`)

| Outlet | Language | Feed | Entries | Latest item |
|---|---|---|---|---|
| ABC News Albania | sq | https://abcnews.al/feed/ | 10 | today |
| Balkanweb | sq | https://www.balkanweb.com/feed/ | 10 | today |
| Citizens Channel | sq | https://citizens.al/feed/ | 100 | today |
| Euronews Albania | sq | https://euronews.al/feed/ | 10 | today |
| Euronews Albania (EN) | en | https://euronews.al/en/feed/ | 10 | today |
| Faktoje | sq | https://faktoje.al/feed/ | 9 | today |
| Gazeta Shqiptare | sq | https://gazetashqiptare.al/feed/ | 10 | today |
| JavaNews | sq | https://javanews.al/feed/ | 10 | today |
| Lajme.al | sq | https://www.lajme.al/feed/ | 10 | yesterday |
| News24 | sq | https://www.news24.al/feed/ | 10 | 2 Sep (slow feed, kept) |
| Panorama | sq | https://www.panorama.com.al/feed/ | 4 | 25 Sep (slow feed, kept) |
| Radio Evropa e Lirë (RFE/RL) | sq | https://www.evropaelire.org/api/ | 20 | today |
| Reporter.al (BIRN Albania) | sq | https://www.reporter.al/feed/ | 10 | today |
| Tirana Times | en | https://www.tiranatimes.com/feed/ | 11 | 24 Sep |
| Vizion Plus | sq | https://www.vizionplus.tv/feed/ | 10 | today |
| Al Jazeera | en | https://www.aljazeera.com/xml/rss/all.xml | 25 | today |
| BBC News Europe | en | https://feeds.bbci.co.uk/news/world/europe/rss.xml | 27 | today |
| DW | en | https://rss.dw.com/rdf/rss-en-all | 132 | today |
| Euronews | en | https://www.euronews.com/rss | 50 | today |
| France 24 (Europe) | en | https://www.france24.com/en/europe/rss | 30 | yesterday |
| Politico Europe | en | https://www.politico.eu/feed/ | 10 | today |
| The Guardian (Albania tag) | en | https://www.theguardian.com/world/albania/rss | 20 | 10 Sep |
| GDELT keyword search (EN + SQ) | both | api.gdeltproject.org | varies | Works, but rate-limits hard; the fetcher backs off when it does |

## Not working or not allowed (left out)

| Outlet / source | Why it's out |
|---|---|
| Google News RSS searches | Its robots.txt disallows automated access to `/rss`. Replaced by GDELT searches. |
| Bing News RSS searches | Works technically, but its terms allow only personal, non-commercial use. |
| Balkan Insight (all feeds) | robots.txt says `Disallow: /` for bots other than big search engines. Its Albanian sister site Reporter.al is included. |
| Exit News | No feed published; `/feed/` returns 404. |
| RTSH | No feed published; `lajme.rtsh.al/rss` doesn't connect. |
| Top Channel | No feed published; `/feed/` returns 403. |
| Reuters, AP | No public RSS feeds any more. Their Albania stories reach us via GDELT. |
| Scan TV, Gazeta Dita | Feed exists but returns 0 entries. |
| Shqiptarja, Syri, Ora News, Politiko, Albanian Daily News, Albanian Post, Koha Jonë, Vox News, Lapsi, Dosja, Klan Kosova, Koha | No feed link on the site, and `/feed` returns 404 or nothing. |
| Fax News | Connection fails. |
| Zëri i Amerikës (VOA Albanian), DW Albanian | No feed link found; VOA's feed URL returns 403. |

Several of the missing outlets still show up through the GDELT searches when
they cover the story.
