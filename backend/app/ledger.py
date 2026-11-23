"""Работа с деньгами. Баланс всегда считается суммой записей в леджере."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .models import LedgerEntry


def commission_for(reward: int) -> int:
    """Комиссия платформы за одно выполнение (округление вверх). Платит заказчик сверху."""
    return -(-reward * settings.commission_percent // 100)


def slot_cost(reward: int) -> int:
    """Сколько стоит одно выполнение для заказчика: награда + комиссия."""
    return reward + commission_for(reward)


async def get_balance(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(LedgerEntry.user_id == user_id)
    )
    return int(result.scalar_one())
