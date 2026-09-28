# Small image that uploads the exported static site to Cloudflare Pages.
FROM node:22-slim
RUN npm install -g wrangler@4 && npm cache clean --force \
 && apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY deploy/publish-loop.sh /usr/local/bin/publish-loop.sh
USER node
WORKDIR /home/node
CMD ["/usr/local/bin/publish-loop.sh"]
