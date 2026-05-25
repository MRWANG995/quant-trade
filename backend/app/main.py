import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.auth_routes import router as auth_router
from app.api.routes import router
from app.api.strategy_routes import router as strategy_router
from app.auth.seed import ensure_admin_user
from app.config import get_settings
from app.database import async_session, engine
from app.seed import seed_instruments, seed_strategies
from app.scheduler.jobs import scheduled_daily_run
from app.ws import websocket_endpoint

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    async with async_session() as session:
        await seed_instruments(session)
        await seed_strategies(session)
        await ensure_admin_user(session)
        # 启动时不再自动拉取行情：yfinance 容易在启动洪流中被限流，
        # 后续整 IP 被封导致美股/期货数据全军覆没。用户需要数据时点
        # 「全量灌库」（POST /api/data/bootstrap）显式触发。

    scheduler = AsyncIOScheduler()
    parts = settings.daily_run_cron.split()
    if len(parts) == 5:
        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        )
        scheduler.add_job(scheduled_daily_run, trigger, id="daily_scan")
    scheduler.start()
    app.state.scheduler = scheduler

    yield

    scheduler.shutdown(wait=False)
    await engine.dispose()


app = FastAPI(title="Quant Trade API", version="0.1.0", lifespan=lifespan)
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(strategy_router)
app.include_router(router)
app.websocket("/ws/live")(websocket_endpoint)


@app.get("/")
async def root():
    """误开 API 端口时跳转到前端。"""
    return RedirectResponse(url=settings.frontend_url, status_code=302)
