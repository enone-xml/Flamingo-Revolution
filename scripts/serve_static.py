"""Preview the exported static site like Cloudflare Pages does (/about -> about.html).

docker run --rm -p 127.0.0.1:8090:8090 -v flamingo_revolution_site-export:/export:ro \
  -v "$PWD/scripts:/s" python:3.12-slim python /s/serve_static.py
"""
import http.server
import os

ROOT = "/export/site"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def translate_path(self, path):
        p = super().translate_path(path)
        if not os.path.exists(p) and os.path.exists(p + ".html"):
            return p + ".html"
        return p


http.server.ThreadingHTTPServer(("0.0.0.0", 8090), Handler).serve_forever()
