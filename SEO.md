# Getting Flamingo Watch found (SEO)

What the site already does for search engines:

- A descriptive `<title>` and meta description on every page, in English and Albanian.
- `canonical` links, plus `hreflang` tags so Google shows the Albanian version to Albanian searchers.
- A `sitemap.xml` listing every page in both languages, linked from `robots.txt`.
- Structured data (schema.org: WebSite, Organization, CollectionPage/AboutPage) that Google can read.
- Social share cards: a branded 1200×630 image for Facebook, X, WhatsApp, Telegram and LinkedIn previews.
- The latest stories are real HTML on the page, refreshed every 10 minutes, so crawlers see fresh content.
- A fast site (Lighthouse 100 on mobile), which Google rewards.
- The `www` and `*.pages.dev` copies are marked `noindex`, so only flamingo-watch.com appears in results.
- A proper 404 page, so broken links don't count as duplicate pages.

## What only you can do (about 15 minutes, all free)

### 1. Google Search Console (the important one)
1. Go to https://search.google.com/search-console and sign in with a Google account.
2. **Add property → Domain**, and type `flamingo-watch.com`.
3. Google shows a **TXT record** (`google-site-verification=...`). In Cloudflare go to
   **flamingo-watch.com → DNS → Records → Add record**, set Type **TXT**, Name **@**, and paste the value as the content. Save.
4. Back in Search Console, click **Verify**. It can take a few minutes.
5. Go to **Sitemaps**, enter `sitemap.xml`, and click **Submit**.
6. Go to **URL inspection**, paste `https://flamingo-watch.com/`, and click **Request indexing**. Do the same for `/sq/`.

### 2. Bing Webmaster Tools (Bing, DuckDuckGo, Yahoo, ChatGPT search)
1. Go to https://www.bing.com/webmasters and sign in.
2. Choose **Import from Google Search Console**. It copies your site and sitemap in one click.

### 3. Cloudflare Crawler Hints (tells Bing and others when news changes)
In Cloudflare go to **flamingo-watch.com → Caching → Configuration → Crawler Hints**, and switch it **On**.

### 4. Links from other sites (the biggest ranking factor)
Search engines trust sites that others link to. Free ways to get links:
- Share the site in Flamingo Revolution groups and pages, and on activist and diaspora social accounts.
- Add it to your GitHub repo description and your social profiles.
- Offer the RSS feed (`/feed.xml`, `/sq/feed.xml`) to journalists and bloggers who cover Albania.
- Ask Albanian civic and environmental organisations to link to it as a news tracker.

### 5. Check your share preview
Paste `https://flamingo-watch.com` into https://www.opengraph.xyz to see how links look when shared.

It usually takes a few days to a couple of weeks before the site appears in Google.
Search Console will show how many people find it and through which words.
