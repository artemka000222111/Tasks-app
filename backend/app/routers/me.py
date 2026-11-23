from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_session
from ..deps import get_current_user
from ..ledger import get_balance
from ..models import LedgerEntry, LedgerType, User
from ..schemas import MeOut, TopUp

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return MeOut(
        id=user.id,
        tg_id=user.tg_id,
        username=user.username,
        balance=await get_balance(session, user.id),
    )


@router.post("/dev/topup", response_model=MeOut)
async def dev_topup(
    body: TopUp,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Тестовое пополнение. Работает только при DEV_MODE=true."""
    if not settings.dev_mode:
        raise HTTPException(status_code=404, detail="not found")
    session.add(LedgerEntry(user_id=user.id, type=LedgerType.deposit.value, amount=body.amount))
    await session.commit()
    return MeOut(
        id=user.id,
        tg_id=user.tg_id,
        username=user.username,
        balance=await get_balance(session, user.id),
    )
