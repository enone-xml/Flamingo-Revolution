"""Discover and test RSS feeds. Prints one JSON line per candidate.

Candidates come from (a) the outlet's own <link rel="alternate"> tags on its
homepage and (b) feed URLs the outlet publishes (e.g. an RSS page)."""
import json, re, sys, urllib.robotparser
from urllib.parse import urljoin, urlparse
import feedparser, httpx

UA = "FlamingoWatchBot/0.1 (+https://github.com/enone-xml/Flamingo-Revolution)"
client = httpx.Client(headers={"User-Agent": UA}, timeout=20, follow_redirects=True)

def discover(home):
    try:
        html = client.get(home).text
    except Exception as e:
        return []
    out = []
    for tag in re.findall(r"<link[^>]+>", html, re.I):
        if re.search(r"application/(rss|atom)\+xml", tag, re.I):
            m = re.search(r'href=["\']([^"\']+)', tag)
            if m:
                out.append(urljoin(home, m.group(1)))
    return out

def robots_ok(url):
    p = urlparse(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        r = client.get(f"{p.scheme}://{p.netloc}/robots.txt")
        if r.status_code >= 400:
            return True
        rp.parse(r.text.splitlines())
        return rp.can_fetch(UA, url)
    except Exception:
        return True

def test(name, url):
    res = {"name": name, "url": url}
    try:
        r = client.get(url)
        res["status"] = r.status_code
        f = feedparser.parse(r.content)
        res["entries"] = len(f.entries)
        if f.entries:
            e = f.entries[0]
            res["sample"] = e.get("title", "")[:80]
            res["date"] = e.get("published", e.get("updated", ""))
    except Exception as e:
        res["error"] = type(e).__name__
    res["robots_ok"] = robots_ok(url)
    return res

if __name__ == "__main__":
    for line in sys.stdin:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, kind, url = [x.strip() for x in line.split("|")]
        urls = discover(url) if kind == "home" else [url]
        if not urls:
            print(json.dumps({"name": name, "url": url, "error": "no feed link found"}), flush=True)
        for u in dict.fromkeys(urls):
            print(json.dumps(test(name, u), ensure_ascii=False), flush=True)
