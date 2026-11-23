from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..deps import get_current_user
from ..ledger import commission_for, get_balance, slot_cost
from ..models import (
    Completion,
    CompletionStatus,
    LedgerEntry,
    LedgerType,
    Task,
    TaskStatus,
    User,
)
from ..schemas import CompletionOut, SubmitProof, TaskCreate, TaskOut

router = APIRouter(tags=["tasks"])


# ---------- список и создание заданий ----------


@router.get("/tasks", response_model=list[TaskOut])
async def list_tasks(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    """Доступные исполнителю задания: активные, со свободными слотами, не свои и ещё не взятые."""
    taken = select(Completion.task_id).where(Completion.worker_id == user.id)
    result = await session.execute(
        select(Task)
        .where(
            Task.status == TaskStatus.active.value,
            Task.remaining > 0,
            Task.owner_id != user.id,
            Task.id.not_in(taken),
        )
        .order_by(Task.created_at.desc())
        .limit(100)
    )
    return result.scalars().all()


@router.get("/tasks/mine", response_model=list[TaskOut])
async def my_tasks(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(Task).where(Task.owner_id == user.id).order_by(Task.created_at.desc())
    )
    return result.scalars().all()


@router.post("/tasks", response_model=TaskOut, status_code=201)
async def create_task(
    body: TaskCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    total = slot_cost(body.reward) * body.quantity

    # блокируем строку пользователя, чтобы два параллельных запроса не потратили один баланс дважды
    await session.execute(select(User.id).where(User.id == user.id).with_for_update())
    if await get_balance(session, user.id) < total:
        raise HTTPException(status_code=402, detail=f"not enough balance, need {total}")

    task = Task(
        owner_id=user.id,
        platform=body.platform.value,
        action=body.action.value,
        title=body.title,
        url=str(body.url),
        description=body.description,
        reward=body.reward,
        quantity=body.quantity,
        remaining=body.quantity,
    )
    session.add(task)
    await session.flush()
    session.add(
        LedgerEntry(
            user_id=user.id, type=LedgerType.task_freeze.value, amount=-total, task_id=task.id
        )
    )
    await session.commit()
    return task


# ---------- исполнитель ----------


@router.post("/tasks/{task_id}/take", response_model=CompletionOut, status_code=201)
async def take_task(
    task_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    if task.owner_id == user.id:
        raise HTTPException(status_code=400, detail="cannot take your own task")

    # атомарно занимаем слот: если слотов не осталось, rowcount будет 0
    claimed = await session.execute(
        update(Task)
        .where(
            Task.id == task_id,
            Task.status == TaskStatus.active.value,
            Task.remaining > 0,
        )
        .values(remaining=Task.remaining - 1)
    )
    if claimed.rowcount == 0:
        await session.rollback()
        raise HTTPException(status_code=409, detail="no free slots")

    completion = Completion(task_id=task_id, worker_id=user.id)
    session.add(completion)
    try:
        await session.commit()  # уникальный (task_id, worker_id): повторно взять нельзя
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="already taken")
    return completion


@router.post("/completions/{completion_id}/submit", response_model=CompletionOut)
async def submit_proof(
    completion_id: int,
    body: SubmitProof,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    completion = await session.get(Completion, completion_id)
    if completion is None or completion.worker_id != user.id:
        raise HTTPException(status_code=404, detail="completion not found")
    if completion.status != CompletionStatus.pending.value:
        raise HTTPException(status_code=409, detail="already submitted")
    completion.proof = body.proof
    completion.status = CompletionStatus.submitted.value
    await session.commit()
    return completion


@router.get("/completions/mine", response_model=list[CompletionOut])
async def my_completions(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(Completion)
        .where(Completion.worker_id == user.id)
        .order_by(Completion.created_at.desc())
    )
    return result.scalars().all()


# ---------- заказчик: проверка выполнений ----------


async def _owned_completion(session: AsyncSession, completion_id: int, user: User):
    completion = await session.get(Completion, completion_id)
    if completion is None:
        raise HTTPException(status_code=404, detail="completion not found")
    task = await session.get(Task, completion.task_id)
    if task is None or task.owner_id != user.id:
        raise HTTPException(status_code=404, detail="completion not found")
    return completion, task


@router.get("/tasks/{task_id}/completions", response_model=list[CompletionOut])
async def task_completions(
    task_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    task = await session.get(Task, task_id)
    if task is None or task.owner_id != user.id:
        raise HTTPException(status_code=404, detail="task not found")
    result = await session.execute(
        select(Completion).where(Completion.task_id == task_id).order_by(Completion.id)
    )
    return result.scalars().all()


@router.post("/completions/{completion_id}/approve", response_model=CompletionOut)
async def approve(
    completion_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    completion, task = await _owned_completion(session, completion_id, user)

    # переход submitted -> approved делаем одним UPDATE, чтобы награда не выплатилась дважды
    moved = await session.execute(
        update(Completion)
        .where(
            Completion.id == completion_id,
            Completion.status == CompletionStatus.submitted.value,
        )
        .values(status=CompletionStatus.approved.value)
    )
    if moved.rowcount == 0:
        await session.rollback()
        raise HTTPException(status_code=409, detail="completion is not awaiting review")

    session.add(
        LedgerEntry(
            user_id=completion.worker_id,
            type=LedgerType.reward.value,
            amount=task.reward,
            task_id=task.id,
            completion_id=completion.id,
        )
    )
    session.add(
        LedgerEntry(
            user_id=None,  # комиссия платформы
            type=LedgerType.commission.value,
            amount=commission_for(task.reward),
            task_id=task.id,
            completion_id=completion.id,
        )
    )
    await session.commit()
    await session.refresh(completion)
    return completion


@router.post("/completions/{completion_id}/reject", response_model=CompletionOut)
async def reject(
    completion_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    completion, task = await _owned_completion(session, completion_id, user)

    moved = await session.execute(
        update(Completion)
        .where(
            Completion.id == completion_id,
            Completion.status == CompletionStatus.submitted.value,
        )
        .values(status=CompletionStatus.rejected.value)
    )
    if moved.rowcount == 0:
        await session.rollback()
        raise HTTPException(status_code=409, detail="completion is not awaiting review")

    # слот возвращается в задание, чтобы его мог взять другой исполнитель
    await session.execute(
        update(Task).where(Task.id == task.id).values(remaining=Task.remaining + 1)
    )
    await session.commit()
    await session.refresh(completion)
    return completion
