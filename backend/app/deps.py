from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import get_session
from .models import User
from .security import InitDataError, validate_init_data


async def get_current_user(
    authorization: str | None = Header(default=None),
    x_dev_tg_id: int | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Пользователь из заголовка `Authorization: tma <initData>`.

    В DEV_MODE можно передать `X-Dev-Tg-Id: 123`, чтобы тестировать без Telegram.
    """
    tg_user: dict | None = None

    if settings.dev_mode and x_dev_tg_id:
        tg_user = {"id": x_dev_tg_id, "username": f"dev{x_dev_tg_id}", "first_name": "Dev"}
    elif authorization and authorization.startswith("tma "):
        try:
            tg_user = validate_init_data(
                authorization[4:], settings.bot_token, settings.init_data_max_age
            )
        except InitDataError as e:
            raise HTTPException(status_code=401, detail=str(e))

    if not tg_user or "id" not in tg_user:
        raise HTTPException(status_code=401, detail="unauthorized")

    result = await session.execute(select(User).where(User.tg_id == tg_user["id"]))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            tg_id=tg_user["id"],
            username=tg_user.get("username"),
            first_name=tg_user.get("first_name"),
        )
        session.add(user)
        await session.commit()

    if user.is_banned:
        raise HTTPException(status_code=403, detail="banned")
    return user
