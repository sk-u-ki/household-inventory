# Домашний склад

Личный учёт продуктов и закупок. Чек из магазина превращается в приход, склад считается как сумма покупок минус сумма списаний. Неизвестные товары из чека не угадываются — их разбирает человек.

Единицы только `g` / `ml` / `pcs`. FIFO, партии и сроки годности не ведутся.

## Как устроено

- **Product** — наш продукт, который можно заменять (`Куриное филе`). Не SKU магазина.
- **Store + ProductMapping** — SKU магазина привязан к Product. Упаковка переводится в базовую единицу: `package_count × package_quantity`.
- **Purchase** — приход на склад (из чека или вручную).
- **Consumption** — расход. Остаток = `SUM(purchases) − SUM(consumptions)`.
- **Receipt line** со статусом `unmapped` — товар из чека, которого ещё нет в маппинге. После привязки такие же SKU применяются сами.

Магазин подключается адаптером: он приводит свой чек к общему виду. Ядро импорта Lidl не знает.

```
магазин (Lidl, …)
    → adapter.normalize()
    → POST /receipts
    → mapping? Purchase : очередь проверки
```

## Состав

```
frontend/                 PWA (склад, проверка, каталог, приход)
backend/                  FastAPI + SQLAlchemy + Alembic
docker-compose.yml        Postgres 17
.env.example
```

PWA отдаётся бэкендом с того же origin: `/` → `/app/`.

## Запуск

Нужны Docker, Python 3.10+, venv.

```bash
cp .env.example .env          # задай POSTGRES_PASSWORD
docker compose up -d

cd backend
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

- приложение: http://127.0.0.1:8000/app/
- docs: http://127.0.0.1:8000/docs
- health: http://127.0.0.1:8000/health

`.env` в git не коммитить. Если файл уже tracked: `git rm --cached .env`.

## PWA

Четыре вкладки:

| Вкладка   | Что делает                                      |
|-----------|--------------------------------------------------|
| Склад     | остатки, ниже минимума подсвечены                |
| Проверка  | неизвестные SKU: привязать или создать продукт   |
| Продукты  | внутренний каталог                               |
| Приход    | ручное пополнение                                |

На телефоне открой тот же URL и «Добавить на экран Домой». Кэшируется только оболочка, не API.

## Чеки Lidl

Адаптер `lidl` ходит в Lidl Plus по refresh token. Браузерный логин в этот репозиторий не входит.

Токен (по порядку):

1. `LIDL_REFRESH_TOKEN` в `.env`
2. иначе файл `~/.config/lidl-plus/refresh_token`

```bash
curl -X POST http://127.0.0.1:8000/adapters/lidl/sync
```

Забираются только новые `ticket.id`. Уже импортированные пропускаются (`store + external_receipt_id`). Первый sync может подтянуть всю историю.

Если токен протух — 502/503. Обнови файл токена и повтори.

Сырой чек без клиента:

```bash
curl -X POST http://127.0.0.1:8000/adapters/lidl/import \
  -H 'Content-Type: application/json' \
  --data-binary @ticket.json
```

## Другой магазин

1. Класс `StoreAdapter` в `backend/app/adapters/` (`key`, `display_name`, `normalize`).
2. По желанию `list_summaries` / `fetch_raw` для живого опроса.
3. `register(...)` в `backend/app/adapters/__init__.py`.

Дальше тот же импорт и та же вкладка «Проверка». Маппинги разделены по магазину: одно и то же молоко в Lidl и в другом магазине — разные SKU.

## API (коротко)

| Метод | Путь | Зачем |
|-------|------|--------|
| GET | `/inventory` | остатки |
| GET/POST | `/products` | каталог |
| GET/POST | `/purchases` | приходы |
| POST | `/receipts` | канонический чек |
| GET | `/receipt-lines?status=unmapped` | очередь проверки |
| POST | `/receipt-lines/{id}/resolve` | привязать к существующему продукту |
| POST | `/receipt-lines/{id}/create-and-resolve` | создать продукт и привязать |
| GET | `/adapters` | список магазинов |
| POST | `/adapters/{key}/sync` | забрать новые чеки |
| POST | `/adapters/{key}/import` | импорт сырого чека |

## Миграции

Из `backend/`, с активированным venv:

```bash
alembic upgrade head
alembic revision --autogenerate -m "описание"
```
