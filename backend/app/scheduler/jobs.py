from datetime import date

from app.database import async_session
from app.engine.live import run_daily_scan
from app.ws import broadcast


async def scheduled_daily_run() -> None:
    async with async_session() as session:
        details = await run_daily_scan(session, date.today())
    await broadcast("daily_run_complete", details)
