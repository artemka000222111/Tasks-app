import enum
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Platform(str, enum.Enum):
    telegram = "telegram"
    vk = "vk"
    youtube = "youtube"
    tiktok = "tiktok"
    instagram = "instagram"


class Action(str, enum.Enum):
    subscribe = "subscribe"
    like = "like"
    view = "view"
    comment = "comment"


class TaskStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    finished = "finished"


class CompletionStatus(str, enum.Enum):
    pending = "pending"  # исполнитель взял задание
    submitted = "submitted"  # прислал доказательство, ждёт проверки
    approved = "approved"  # принято, награда выплачена
    rejected = "rejected"  # отклонено


class LedgerType(str, enum.Enum):
    deposit = "deposit"  # пополнение баланса
    task_freeze = "task_freeze"  # заморозка бюджета при создании задания
    reward = "reward"  # награда исполнителю
    commission = "commission"  # комиссия платформы (user_id = NULL)
    task_refund = "task_refund"  # возврат неиспользованного бюджета


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    is_banned: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    platform: Mapped[str] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    reward: Mapped[int] = mapped_column(Integer)  # за одно выполнение
    quantity: Mapped[int] = mapped_column(Integer)  # сколько выполнений нужно
    remaining: Mapped[int] = mapped_column(Integer)  # сколько ещё свободных слотов
    status: Mapped[str] = mapped_column(String(16), default=TaskStatus.active.value, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Completion(Base):
    __tablename__ = "completions"
    __table_args__ = (UniqueConstraint("task_id", "worker_id", name="uq_task_worker"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default=CompletionStatus.pending.value)
    proof: Mapped[str | None] = mapped_column(Text)  # ссылка на скриншот / текст
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LedgerEntry(Base):
    """Единственный источник правды о деньгах. Баланс = сумма amount по user_id."""

    __tablename__ = "ledger"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(16))
    amount: Mapped[int] = mapped_column(Integer)  # со знаком: расход < 0, приход > 0
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"))
    completion_id: Mapped[int | None] = mapped_column(ForeignKey("completions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
