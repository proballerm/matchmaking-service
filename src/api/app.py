import asyncio
import os
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from core.engine import MatchmakingEngine
from core.redis_queue import RedisMatchmakingQueue

app = FastAPI(title="Matchmaking Service")


def build_engine() -> MatchmakingEngine:
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return MatchmakingEngine()

    namespace = os.getenv("REDIS_NAMESPACE", "matchmaking")
    queue = RedisMatchmakingQueue.from_url(redis_url, namespace=namespace)
    return MatchmakingEngine(queue=queue)


engine = build_engine()

TICK_INTERVAL_SECONDS = float(os.getenv("TICK_INTERVAL_SECONDS", "1.0"))
ENABLE_BACKGROUND_TICK = os.getenv("ENABLE_BACKGROUND_TICK", "1") == "1"

lock = asyncio.Lock()
stop_event = asyncio.Event()
bg_task: asyncio.Task | None = None


class EnqueueRequest(BaseModel):
    player_id: str = Field(..., min_length=1)
    rating: float = Field(..., ge=0)
    timestamp_utc: Optional[str] = None


class DequeueRequest(BaseModel):
    player_id: str = Field(..., min_length=1)


class TickRequest(BaseModel):
    timestamp_utc: Optional[str] = None


def parse_time(ts: Optional[str]) -> datetime:
    if not ts:
        return datetime.now(timezone.utc)

    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def tick_loop() -> None:
    while not stop_event.is_set():
        try:
            async with lock:
                engine.run_matchmaking_once(utcnow())
        except Exception as exc:
            print(f"[tick_loop] error: {exc}")
        await asyncio.sleep(TICK_INTERVAL_SECONDS)


@app.on_event("startup")
async def on_startup() -> None:
    global bg_task
    if not ENABLE_BACKGROUND_TICK:
        return
    stop_event.clear()
    bg_task = asyncio.create_task(tick_loop())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    stop_event.set()
    if bg_task is not None:
        bg_task.cancel()
        try:
            await bg_task
        except asyncio.CancelledError:
            pass


@app.get("/")
async def root():
    return {
        "service": "matchmaking",
        "docs": "/docs",
        "health": "/health",
        "queue_backend": "redis" if os.getenv("REDIS_URL") else "memory",
    }


@app.get("/health")
async def health():
    return {"ok": True, "queue_backend": "redis" if os.getenv("REDIS_URL") else "memory"}


@app.post("/enqueue")
async def enqueue(req: EnqueueRequest):
    t = parse_time(req.timestamp_utc)
    async with lock:
        ok = engine.enqueue_player(req.player_id, req.rating, t)
    if not ok:
        raise HTTPException(status_code=409, detail="player already queued")
    return {"enqueued": True, "player_id": req.player_id}


@app.post("/dequeue")
async def dequeue(req: DequeueRequest):
    async with lock:
        ok = engine.dequeue_player(req.player_id)
    if not ok:
        raise HTTPException(status_code=404, detail="player not found in queue")
    return {"dequeued": True, "player_id": req.player_id}


@app.post("/tick")
async def tick(req: TickRequest):
    t = parse_time(req.timestamp_utc)
    async with lock:
        engine.run_matchmaking_once(t)
        metrics = engine.get_metrics()
    return {"ticked": True, "metrics": metrics}


@app.get("/matches")
async def matches():
    async with lock:
        out = engine.get_and_clear_matches()
    return {"matches": [asdict(match) for match in out]}


@app.get("/metrics")
async def metrics():
    async with lock:
        return engine.get_metrics()
