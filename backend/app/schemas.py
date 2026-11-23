from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from .models import Action, Platform


class MeOut(BaseModel):
    id: int
    tg_id: int
    username: str | None
    balance: int


class TaskCreate(BaseModel):
    platform: Platform
    action: Action
    title: str = Field(min_length=3, max_length=200)
    url: HttpUrl
    description: str | None = Field(default=None, max_length=2000)
    reward: int = Field(gt=0, le=100_000)
    quantity: int = Field(gt=0, le=100_000)


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    platform: str
    action: str
    title: str
    url: str
    description: str | None
    reward: int
    quantity: int
    remaining: int
    status: str
    created_at: datetime


class SubmitProof(BaseModel):
    proof: str = Field(min_length=1, max_length=2000)  # ссылка на скриншот или текст


class CompletionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    worker_id: int
    status: str
    proof: str | None
    created_at: datetime


class TopUp(BaseModel):
    amount: int = Field(gt=0, le=1_000_000)
