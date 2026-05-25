import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import hash_password
from app.config import get_settings
from app.models.entities import User

logger = logging.getLogger(__name__)


async def ensure_admin_user(session: AsyncSession) -> None:
    settings = get_settings()
    if not settings.admin_email or not settings.admin_password:
        return
    count = await session.scalar(select(func.count(User.id)))
    if count:
        return
    email = settings.admin_email.lower().strip()
    user = User(
        email=email,
        hashed_password=hash_password(settings.admin_password),
        display_name="管理员",
        is_admin=True,
    )
    session.add(user)
    await session.commit()
    logger.info("已创建初始管理员: %s", email)
