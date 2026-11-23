from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401  (регистрирует таблицы)
from .db import Base, engine
from .routers import me, tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Для старта создаём таблицы автоматически. Позже заменим на миграции Alembic.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Tasks Mini App API", lifespan=lifespan)

# Авторизация идёт заголовком, а не cookie, поэтому "*" здесь допустимо.
# Перед продом лучше заменить на домен мини-аппа.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

app.include_router(me.router)
app.include_router(tasks.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
