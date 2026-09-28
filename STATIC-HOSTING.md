# Run on your PC, publish for free (Cloudflare Pages)

In this setup your own computer does all the work: fetching the news, AI
summaries and the database. Every 10 minutes it builds the whole site as plain
files and uploads them to **Cloudflare Pages**, which hosts them for free with
HTTPS.

**Trade-off:** the news only updates while your PC is **on, awake, online and
running Docker Desktop**. When it's off, the site stays up but shows the last
published news, and the "Updated X ago" label shows how old it is.

Checked on 2026-09-28. Cloudflare Pages' free plan limits 500 *builds* a month, but
uploads from your PC (Direct Upload) don't count toward that
([Cloudflare community answer](https://community.cloudflare.com/t/does-pages-development-via-direct-uploads-count-towards-the-monthly-build-quota/390920)).
The site is about 1 MB, far below the 20,000-file limit.

---

## 1. Buy the domain at Cloudflare

1. Create a free account at https://dash.cloudflare.com/sign-up.
2. Go to **Domain Registration → Register Domains**, search for your name, and buy the **.com**
   (about **$10.46 a year**, no markup). Cloudflare then manages its DNS automatically.

## 2. Create a Cloudflare API token and find your account ID

1. Go to **My Profile → API Tokens → Create Token → Create Custom Token**.
   - Name: `flamingo-watch-publisher`
   - Permissions: **Account → Cloudflare Pages → Edit** (nothing else)
   - Account resources: your account
   - Click **Continue to summary → Create Token**, and copy the token. It's shown only once.
2. Find your **Account ID** in **Workers & Pages → Overview**, in the right-hand column.
   It's also in the URL: `dash.cloudflare.com/<ACCOUNT_ID>/...`.

## 3. Put the settings in `.env` (on your PC, never in git)

```bash
cd /home/eno/flamingo_revolution && nano .env
```
Opens your local settings file in a text editor (save with Ctrl+O and Enter, exit with Ctrl+X).

Make sure these lines are there and filled in:

```
SITE_URL=https://yourdomain.com
EXPORT_DIR=/export
COMPOSE_PROFILES=publish
CLOUDFLARE_API_TOKEN=paste-your-token
CLOUDFLARE_ACCOUNT_ID=paste-your-account-id
CF_PAGES_PROJECT=flamingo-watch
```

When you have an Anthropic API key, also set `ANTHROPIC_API_KEY=...` and
`AI_MODE=real`. See DEPLOY.md step 5 for how to create the key and set a
**monthly spend limit** in the Console.

## 4. Create the Pages project (once)

```bash
docker compose build publisher && docker compose run --rm publisher wrangler pages project create flamingo-watch --production-branch main
```
Builds the small uploader image, then creates an empty "flamingo-watch" site in your Cloudflare account.

**You should see:** `Successfully created the 'flamingo-watch' project` and a
`flamingo-watch.pages.dev` address.

## 5. Start everything

```bash
docker compose up -d --build
```
Rebuilds and starts the app and the uploader in the background.

```bash
docker compose logs -f publisher
```
Follows the uploader's log. Press Ctrl+C to stop watching; the uploader keeps running.

**You should see** within about 2 minutes (the first fetch takes a moment):

```
publisher: deploying (content 910d336ea3e62a00)
publisher: deployed OK at 13:40:12Z
```

Open **https://flamingo-watch.pages.dev**. That's your live site.

## 6. Connect your domain

1. In Cloudflare go to **Workers & Pages → flamingo-watch → Custom domains → Set up a custom domain**.
2. Enter `yourdomain.com` → **Continue → Activate domain**. Because the domain is
   at Cloudflare, it creates the DNS record and HTTPS certificate for you.
3. Repeat for `www.yourdomain.com`.
4. Wait a few minutes, then open `https://yourdomain.com`.

To check DNS from WSL:

```bash
dig +short yourdomain.com
```
Asks public DNS where your domain points. You should see Cloudflare IP addresses (often starting with 104. or 172.).

**HTTPS** is automatic and renews itself; there's nothing to do.

## 7. Keep your PC publishing

- **Docker Desktop → Settings → General → "Start Docker Desktop when you sign in to your computer"**: turn it on.
  The containers restart by themselves (`restart: unless-stopped`).
- **Windows Settings → System → Power → Screen and sleep**: set "When plugged in, put my
  device to sleep after" to **Never**. The screen can still turn off; that's fine.
- If you shut the PC down, nothing breaks. The site keeps showing the last news, and
  publishing resumes about 10 minutes after Docker Desktop starts again.

## 8. Get an email if publishing stops (free)

1. Create a free account at https://healthchecks.io and click **Add Check**.
2. Set **Period: 1 hour**, **Grace: 1 hour**, and keep email notifications on.
3. Copy the check's ping URL (`https://hc-ping.com/...`) into `.env` as `HEALTHCHECK_URL=`.
4. Run `docker compose up -d` so the uploader picks it up.

The uploader pings that URL after every successful upload, and at least once an
hour. If the pings stop (PC off, Docker stopped, token expired), you get an email.

## 9. See this month's AI spend

```bash
docker compose exec web python -m app.ai spend
```
Prints the number of AI calls and the estimated cost against the $4 budget.

## 10. Backups

The app copies the database every day at 03:00 UTC and keeps the last 14 copies.
It can only do this while the PC is on. To save a copy somewhere safe, for example
a OneDrive folder:

```bash
docker compose cp web:/data/backups /mnt/c/Users/enoku/OneDrive/flamingo-backups
```
Copies the backup folder out of Docker into a Windows folder. Change the path to wherever you want the copies.

To restore one, follow DEPLOY.md step 7 ("Restore a backup").

## 11. Updating

```bash
cd /home/eno/flamingo_revolution && git pull && docker compose up -d --build
```
Gets the latest code from GitHub and restarts with it. The next upload publishes the new version.

## 12. Monthly cost

| Item | Per month |
|---|---|
| Cloudflare Pages hosting + HTTPS | $0 |
| Domain (.com at Cloudflare, $10.46/yr) | $0.87 |
| Anthropic API (hard cap in the app) | ≤ $4.00 |
| healthchecks.io | $0 |
| **Total (worst case)** | **≤ $4.87** |

Your PC's electricity isn't counted.

## Switching to a server later

Nothing is lost if you move to a server later. DEPLOY.md shows how to run the same
app on a $5 Linode, where it updates around the clock. Remove `COMPOSE_PROFILES` and
`EXPORT_DIR` from that server's `.env`, and point your domain's DNS at the server
instead of Pages.
