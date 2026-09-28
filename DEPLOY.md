# Deploying Flamingo Watch

This guide takes you from nothing to a live site with HTTPS, a running fetcher,
daily backups and uptime alerts. Each step gives the exact commands and what
you should see.

Prices were checked on the providers' own pages on **2026-09-28**. Check them
again before you buy.

---

## 1. Hosting: which server?

| Option | What you get | Price / month | Notes |
|---|---|---|---|
| **DigitalOcean Basic Droplet** (recommended) | 1 vCPU, 1 GiB RAM, 25 GiB SSD, 1,000 GiB traffic | **$6.00** | A $4 plan (512 MiB) also exists but is tight for Docker + Python. Weekly backups add 20% ($1.20). Frankfurt (FRA1) is closest to Albania. |
| Hetzner Cloud | CX23: 2 vCPU, 4 GB, 40 GB | €5.99 | Listed as **"not available"** on 2026-09-28. The next plan you can actually order (CPX12) costs €11.99, which breaks the budget. |
| Hostinger VPS KVM 1 | 1 vCPU, 4 GB RAM, 50 GB NVMe, 4 TB traffic, free weekly backups, **free .com for 1 year** | $6.49 (24-month term, $155.76 upfront) | Renews at $11.99/mo. A 12-month term is $6.99/mo ($83.88), renewing at $12.99. Monthly billing is $9.99, renewing at $19.49. |
| **Akamai Cloud (Linode) Nanode 1 GB** (cheapest pay-monthly) | 1 vCPU, 1 GB RAM, 25 GB, 1 TB traffic | **$5.00** | Billed by the hour up to $5 a month, with no commitment. Frankfurt, Amsterdam, Milan and others in Europe. |
| Vultr Cloud Compute | Shared CPU | from $5.00 | Pay monthly or hourly, no commitment. Their site lists "starting at just $5/month". |
| OVHcloud VPS-1 | 2 vCores, 4 GB, 40 GB NVMe, daily backup | $4.54 with a 12-month commitment ($54.48 upfront) | Without commitment it's about 15% more, roughly $5.35 a month (my estimate from their stated 15% discount). |
| Render | Web service, 512 MB RAM, <1 CPU, plus 1 GB disk for SQLite | $7.00 + $0.25 | The free tier sleeps when idle and has no persistent disk, so the fetcher can't run. It's also more expensive than a VPS. |

**Recommendation: a DigitalOcean $6 Droplet in Frankfurt.** It fits the ≤ $7
target, it's a normal Ubuntu VM you already know how to run, and Docker + Caddy
gives automatic HTTPS. If Hetzner's CX23 becomes orderable again it's a fine
alternative at the same price with more RAM. Nothing in this guide is
DigitalOcean-specific except step 1.1.

### 1.1 Create the server

1. Sign up at digitalocean.com and add your SSH public key (Settings → Security → SSH keys).
   On your WSL machine, `cat ~/.ssh/id_ed25519.pub` prints it. If that file doesn't
   exist, `ssh-keygen -t ed25519` creates one.
2. Create → Droplets → region **Frankfurt**, image **Ubuntu 24.04 LTS**,
   size **Basic / Regular / $6**, authentication **SSH key**.
   Optionally tick **Backups (weekly)** for +$1.20.
3. Networking → Firewalls → create a firewall that allows inbound
   **TCP 22, 80, 443** and **UDP 443**, and apply it to the droplet.
4. Note the droplet's **public IPv4** (and IPv6 if you enabled it).

### 1.1a Paying month to month (no yearly commitment)

If you'd rather not pay a year upfront, the cheapest option is **Akamai Cloud (Linode) Nanode 1 GB at
$5/month**. It's billed by the hour and capped at $5 a month, and you can delete it any time.

1. Sign up at **cloud.linode.com** and add your SSH key (Profile → SSH Keys).
2. **Create → Linode**, image **Ubuntu 24.04 LTS**, region **Frankfurt, DE**,
   plan **Shared CPU → Nanode 1 GB**, add your SSH key, set a root password.
3. **Create → Cloud Firewall** with inbound **TCP 22, 80, 443** and **UDP 443**, and
   attach it to the Linode.
4. Note the IPv4 address.

Buy the domain separately at **Cloudflare Registrar** (step 2). Every registrar charges
for domains by the year, so that's a one-off $10.46 a year.
DigitalOcean at $6/month (step 1.1) is the same kind of month-to-month deal.

### 1.1b Or: buy the server and domain at Hostinger

If you prefer Hostinger, this is the cheapest way to buy there (prices as of 2026-09-28; hPanel menu names can differ slightly):

1. Go to **hostinger.com → VPS hosting**, and under **KVM 1** click **Choose plan**.
   KVM 1 is plenty: the app uses well under 1 GB of RAM.
2. In the cart, set **Period: 24 months** ($6.49/mo, $155.76 paid upfront).
   The cart confirms "You get a FREE domain for 1 year with this order."
   A 12-month term ($6.99/mo, $83.88) is fine if you'd rather pay less upfront.
   Avoid 1 month: it costs $9.99 and renews at $19.49.
3. **Leave "Daily auto-backup" ($3/mo) unticked.** Weekly VPS backups are
   already free, and the app makes its own daily database backups (step 7).
4. **Server location:** pick **Germany**, or whichever European location the cart
   shows with the lowest latency.
5. **What to install:** choose **Plain OS → Ubuntu 24.04**. Don't pick the Docker
   or panel templates; step 1.2 installs Docker for you.
6. Click **Continue**, create your account, and pay. VAT may be added at
   checkout depending on your country. Don't pay for extras such as email,
   SSL or site builders: Caddy gives free HTTPS.
7. After payment, hPanel asks you to **set a root password** and offers to
   **add an SSH key**. Add your key (`cat ~/.ssh/id_ed25519.pub` on WSL; create one
   with `ssh-keygen -t ed25519` if needed).
8. **Claim the free domain:** in hPanel go to **Domains** and use the free-domain
   voucher to register your **.com**. Turn on the free WHOIS privacy protection if it
   isn't already on.
9. **Firewall:** in hPanel go to **VPS → Security → Firewall**, create a rule set that
   allows **TCP 22, 80, 443** and **UDP 443**, and drop everything else.
10. Note the VPS **IPv4 address** (and IPv6) from the VPS overview page.

**About the domain renewal:** the free .com renews at **$19.99/year** at Hostinger.
Cloudflare charges $10.46. Before the first year ends, you can transfer the domain
to Cloudflare Registrar. The transfer includes one more year at $10.46, which saves
about $9.50 a year. Or you can just let Hostinger renew it; the total stays under budget
either way (see step 10).

Then continue with step 1.2. It's the same on any Ubuntu server.

### 1.2 Prepare the server

```bash
ssh root@YOUR_SERVER_IP
```
Logs you into the new server as root.

```bash
apt update && apt -y upgrade && apt -y install docker.io docker-compose-v2 git sqlite3
```
Installs Docker, the Compose plugin, git and the sqlite3 tool from Ubuntu's own packages.

```bash
fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab
```
Adds 1 GB of swap so a Docker build can't run out of memory on the 1 GB server.

```bash
adduser --disabled-password --gecos "" flamingo && usermod -aG docker flamingo && mkdir -p /opt/flamingo && chown flamingo:flamingo /opt/flamingo
```
Creates a normal user that can run Docker and owns the app folder.

```bash
rsync --archive --chown=flamingo:flamingo ~/.ssh /home/flamingo
```
Lets you SSH in as `flamingo` with the same key.

From now on, log in as that user: `ssh flamingo@YOUR_SERVER_IP`.

### 1.3 Get the code (private repo → deploy key)

```bash
ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -N "" -C flamingo-server && cat ~/.ssh/github_deploy.pub
```
Creates a key that only this server uses and prints its public half.

On GitHub: repo **Settings → Deploy keys → Add deploy key**. Paste it, and
leave "Allow write access" **off**.

```bash
printf 'Host github.com\n  IdentityFile ~/.ssh/github_deploy\n' >> ~/.ssh/config && git clone git@github.com:enone-xml/Flamingo-Revolution.git /opt/flamingo
```
Tells SSH to use that key for GitHub, then downloads the code into `/opt/flamingo`.

**You should see:** `Cloning into '/opt/flamingo'...` and no errors.

---

## 2. Domain

Buy it at **Cloudflare Registrar**. It charges the registry's price with no
markup. Current prices (from cfdomainpricing.com, which tracks Cloudflare's
price list):

| Extension | First year | Renewal |
|---|---|---|
| **.com** (recommended) | $10.46 | $10.46 |
| .org | $8.50 | $11.20 |
| .net | $11.86 | $11.86 |

Pick **.com**. It's the cheapest to keep long term, and it's what people
type. That works out to about **$0.87 a month**. Cloudflare Registrar domains
must use Cloudflare's DNS, which is free and what step 3 uses.
(Namecheap is a fine alternative, at about $11–14 a year for .com.)

---

## 3. DNS records

In Cloudflare: your domain → **DNS → Records → Add record**:

| Type | Name | Content | Proxy status |
|---|---|---|---|
| A | `@` | YOUR_SERVER_IPv4 | **DNS only** (grey cloud) |
| A | `www` | YOUR_SERVER_IPv4 | DNS only |
| AAAA | `@` | YOUR_SERVER_IPv6 (only if the droplet has one) | DNS only |
| AAAA | `www` | YOUR_SERVER_IPv6 (only if the droplet has one) | DNS only |

**If your domain is at Hostinger:** in hPanel go to **Domains → your domain → DNS / Nameservers →
DNS records**. **Delete** any existing `A` records for `@` and `www`, and any
`CNAME` for `www`, since those point to Hostinger's parking page. Then add the
records above. Hostinger has no proxy, so ignore that column.

Keep them **DNS only** so Caddy can get its certificate directly. You can
switch on the orange-cloud proxy later if you want; if you do, set
SSL/TLS mode to **Full (strict)**.

Check propagation from your WSL machine:

```bash
dig +short yourdomain.com A
```
Asks public DNS for the domain's IPv4 address.

**You should see:** your server's IP. If it's empty, wait a few minutes and try
again. You can also check worldwide at https://dnschecker.org.

---

## 4. HTTPS (automatic)

Caddy runs next to the app (`docker-compose.prod.yml` + `deploy/Caddyfile`).
On first start it gets a free Let's Encrypt certificate for `yourdomain.com`
and `www.yourdomain.com`. It renews the certificate by itself about 30 days
before expiry, with no cron and no manual step. `www` redirects to the bare domain.

---

## 5. Secrets: the Anthropic API key

1. Go to https://console.anthropic.com → **API Keys → Create Key**, and name it
   `flamingo-watch`. Copy it; it's shown only once.
2. **Set a spend limit as a second safety net:** Console → **Settings → Limits**
   → set a monthly limit of **$5**. The app already stops itself at $4
   (`AI_MONTHLY_BUDGET_USD`), so this only matters if something goes wrong.
3. On the server, create the `.env` file (it is never committed to git):

```bash
cd /opt/flamingo && cp .env.example .env && chmod 600 .env && nano .env
```
Copies the template, makes it readable only by you, and opens it for editing.

Set at least:

```
ANTHROPIC_API_KEY=sk-ant-...your key...
AI_MODE=real
SITE_URL=https://yourdomain.com
DOMAIN=yourdomain.com
COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml
```

The `COMPOSE_FILE` line makes every plain `docker compose` command on the server
include Caddy, so you never have to type both file names.

Now start everything:

```bash
docker compose up -d --build
```
Builds the app image and starts the app and Caddy in the background.

**You should see:** `Container flamingo-web-1 Started` and `Container flamingo-caddy-1 Started`.
Then open `https://yourdomain.com`. It should load with a padlock.

---

## 6. Scheduler: is the fetcher alive?

The fetcher and AI step run inside the web container every
`FETCH_INTERVAL_MINUTES` (10 by default), and once right after start.

```bash
docker compose logs --since 30m web | grep -E "fetch finished|AI run"
```
Shows the last half hour of fetch and AI runs.

**You should see** lines like `fetch finished: 4 new articles` and
`AI run: {'done': 4, 'failed': 0, 'keyword_only': 0}` every 10 minutes.

```bash
curl -s https://yourdomain.com/health
```
Asks the site for its health status.

**You should see** `{"ok":true,"last_fetch_at":"...","articles":123}`. If the
fetcher hasn't run for 45 minutes, this returns HTTP 503 with `"ok":false`,
and the uptime monitor (step 8) emails you.

Check the month's AI spend at any time:

```bash
docker compose exec web python -m app.ai spend
```
Prints the month, number of AI calls, estimated cost against the $4 budget, and whether the budget was hit.

---

## 7. Backups

The backup command makes a safe copy of the SQLite file while the app runs and
keeps the last 14, in the `flamingo-data` volume under `/data/backups`.

```bash
crontab -e
```
Opens your user's cron table. Add this line, then save:

```
0 3 * * * /opt/flamingo/deploy/backup.sh >> /home/flamingo/backup.log 2>&1
```
Runs a backup every night at 03:00 server time.

Test it now:

```bash
/opt/flamingo/deploy/backup.sh && docker compose exec web ls /data/backups
```
Makes a backup immediately and lists the backup files.

**Off-server copy (recommended):** backups on the same disk don't survive losing
the server. Either tick DigitalOcean's weekly backups (+$1.20), or pull a copy
to your own machine now and then:

```bash
ssh flamingo@YOUR_SERVER_IP "cd /opt/flamingo && docker compose cp web:/data/backups ./backups-copy" && scp -r flamingo@YOUR_SERVER_IP:/opt/flamingo/backups-copy ./flamingo-backups
```
Copies the backup folder out of the container on the server, then down to your machine.

**Restore a backup:**

```bash
cd /opt/flamingo && docker compose stop web
```
Stops the app so nothing writes to the database.

```bash
docker compose run --rm --no-deps web sh -c "cp /data/backups/flamingo-YYYY-MM-DD-HHMM.db /data/flamingo.db && rm -f /data/flamingo.db-wal /data/flamingo.db-shm"
```
Replaces the live database with the backup you chose (use a real file name from the list).

```bash
docker compose start web
```
Starts the app again on the restored data.

---

## 8. Monitoring (free)

1. Sign up at https://uptimerobot.com (free plan).
2. **Add New Monitor** → type **HTTP(s)** → URL `https://yourdomain.com/health`
   → interval **5 minutes** → alert contact: your email.
3. Save. The status turns green within a few minutes.

It emails you if the site is down **or** if the fetcher has stopped (because
`/health` returns 503 then).

---

## 9. Updating the site

After new commits are pushed to GitHub:

```bash
ssh flamingo@YOUR_SERVER_IP /opt/flamingo/deploy/update.sh
```
Logs in, pulls the latest code, rebuilds, restarts, and checks `/health`.

**You should see** the health JSON and `Deployed OK`. The database lives in a
Docker volume, so updates never touch your data.

To add or remove a news source, edit `sources.yaml`, commit, push, and run
the update command.

---

## 10. Monthly cost

| Item | Per month |
|---|---|
| DigitalOcean Droplet (1 GiB, Frankfurt) | $6.00 |
| DigitalOcean weekly backups (optional) | $1.20 |
| Domain (.com at Cloudflare, $10.46/yr) | $0.87 |
| Anthropic API (hard cap in the app) | ≤ $4.00 |
| Caddy / Let's Encrypt certificates | $0 |
| UptimeRobot | $0 |
| **Total (worst case)** | **≤ $12.07** |

That's under the $20 limit even in the worst case, with about $8 to spare.

**If you pay month to month on Akamai/Linode:** $5.00 server + $0.87 domain + at most $4.00 AI
= **at most $9.87 a month**, paid monthly, with the domain paid yearly.

**If you buy at Hostinger instead:**

| Item | Years 1–2 | After renewal |
|---|---|---|
| Hostinger KVM 1 (24-month term) | $6.49 | $11.99 |
| Domain (.com, free year 1, then $19.99/yr) | $0 in year 1, then $1.67 | $1.67 (or $0.87 after moving to Cloudflare) |
| Anthropic API (hard cap) | ≤ $4.00 | ≤ $4.00 |
| Backups, HTTPS, monitoring | $0 | $0 |
| **Total (worst case)** | **≤ $12.16** | **≤ $17.66** |

This stays under $20 even after the renewal price starts.
At about $0.002 per article, the AI cap covers roughly 2,000 new articles a month.
