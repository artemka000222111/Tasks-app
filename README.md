# Tasks-app

Telegram Mini App: биржа заданий. Заказчики создают задания (подписка, лайк, просмотр, комментарий),
исполнители выполняют их и получают награду.

## Структура

```
backend/            FastAPI + SQLAlchemy (async)
  app/
    main.py         приложение, /health
    config.py       настройки из переменных окружения
    db.py           подключение к БД (Postgres на Railway, sqlite локально)
    models.py       users, tasks, completions, ledger
    ledger.py       баланс и комиссия (баланс = сумма записей леджера)
    security.py     проверка подписи initData из Telegram
    deps.py         текущий пользователь
    routers/        эндпоинты
```

## Как работают деньги

- Баланс не хранится числом, а считается по таблице `ledger`.
- Создание задания замораживает `(награда + комиссия) × количество`.
- Одобрение выполнения: исполнителю `+награда`, платформе `+комиссия`.
- Отклонение: слот возвращается в задание.

## Эндпоинты (первая версия)

| Метод | Путь | Что делает |
|-------|------|-----------|
| GET | `/health` | проверка работы |
| GET | `/me` | профиль и баланс |
| GET | `/tasks` | доступные задания |
| POST | `/tasks` | создать задание |
| GET | `/tasks/mine` | мои задания |
| POST | `/tasks/{id}/take` | взять задание |
| POST | `/completions/{id}/submit` | отправить доказательство |
| GET | `/tasks/{id}/completions` | выполнения моего задания |
| POST | `/completions/{id}/approve` | принять (выплата) |
| POST | `/completions/{id}/reject` | отклонить |

Авторизация: заголовок `Authorization: tma <initData>`.

## Локальный запуск

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env        # поставь DEV_MODE=true для теста без Telegram
uvicorn app.main:app --reload
```

В `DEV_MODE=true` можно слать `X-Dev-Tg-Id: 1` вместо `Authorization` и пополнять баланс через
`POST /dev/topup`. Документация API: `http://localhost:8000/docs`.

## Деплой на Railway

1. New Project → Deploy from GitHub repo → этот репозиторий.
2. Add → Database → PostgreSQL (Railway сам добавит `DATABASE_URL`).
3. В Variables сервиса добавь `BOT_TOKEN` (и `COMMISSION_PERCENT`, если нужно другое значение).
   `DEV_MODE` в проде не включать.

## Что дальше

- Бот на aiogram и автопроверка заданий Telegram/VK
- Фронтенд мини-аппа (React + Telegram WebApp SDK)
- Пополнение и вывод, антифрод, миграции Alembic
