"""Web app. Stage 1 only has a health check; the site comes in stage 3."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import db, scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    sched = scheduler.start()
    yield
    sched.shutdown(wait=False)


app = FastAPI(title="Flamingo Watch", lifespan=lifespan)


@app.get("/health")
def health():
    with db.session() as conn:
        last = db.get_meta(conn, "last_fetch_at")
        count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    return {"ok": True, "last_fetch_at": last, "articles": count}
