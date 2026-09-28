# Household inventory

Personal stock and grocery tracking. A store receipt becomes a stock-in. On-hand quantity is `SUM(purchases) − SUM(consumptions)`. Unknown receipt SKUs are never guessed — a person maps them.

Units are `g` / `ml` / `pcs` only. No FIFO, batches, or expiry dates.

## How it works

- **Product** — an internal interchangeable item (`Chicken breast`). Not a store SKU.
- **Store + ProductMapping** — a store SKU is bound to a Product. Packs convert to the base unit: `package_count × package_quantity`.
- **Purchase** — stock in (from a receipt or entered by hand).
- **Consumption** — stock out. On-hand = `SUM(purchases) − SUM(consumptions)`.
- **Receipt line** with status `unmapped` — a receipt item with no mapping yet. After you map it, the same SKU applies automatically.

A store is an adapter: it turns a shop-specific receipt into one canonical shape. The import core does not know about Lidl.

```
store (Lidl, …)
    → adapter.normalize()
    → POST /receipts
    → mapping? Purchase : review queue
```

## Layout

```
frontend/                 PWA (stock, review, catalog, stock-in)
backend/                  FastAPI + SQLAlchemy + Alembic
docker-compose.yml        Postgres 17
.env.example
```

The backend serves the PWA from the same origin: `/` → `/app/`.

## Run

You need Docker, Python 3.10+, and a venv.

```bash
cp .env.example .env          # set POSTGRES_PASSWORD
docker compose up -d

cd backend
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

- app: http://127.0.0.1:8000/app/
- docs: http://127.0.0.1:8000/docs
- health: http://127.0.0.1:8000/health

Do not commit `.env`. If it is already tracked: `git rm --cached .env`.

Locally `docker compose up -d` starts only Postgres. The API container is the `app` profile (see Deploy).

## Deploy

One VPS with Docker is enough. The API image includes the PWA and runs migrations on start.

On the server:

```bash
git clone git@github.com:sk-u-ki/household-inventory.git
cd household-inventory
cp .env.example .env
# set POSTGRES_PASSWORD
# set LIDL_REFRESH_TOKEN (or copy the token file into the server)
docker compose --profile app up -d --build
```

Then open `http://SERVER_IP:8000/app/`.

Install-to-home-screen on a phone needs HTTPS. Put Caddy (or nginx) in front:

```caddy
your.domain {
    reverse_proxy 127.0.0.1:8000
}
```

After a code change: `git pull && docker compose --profile app up -d --build`.

Postgres is bound to `127.0.0.1` only. Do not publish `5432` to the internet. The Lidl token lives in `.env` on the server, not in git.

## PWA

Four tabs:

| Tab        | What it does                                              |
|------------|-----------------------------------------------------------|
| Склад      | on-hand stock; below-minimum rows are highlighted         |
| Проверка   | unknown SKUs: map to a product or create one              |
| Продукты   | internal catalog                                          |
| Приход     | manual stock-in                                           |

On a phone, open the same URL and use “Add to Home Screen”. Only the app shell is cached, not the API.

## Lidl receipts

The `lidl` adapter talks to Lidl Plus with a refresh token. Browser login is not part of this repo.

Token lookup order:

1. `LIDL_REFRESH_TOKEN` in `.env`
2. otherwise `~/.config/lidl-plus/refresh_token`

```bash
curl -X POST http://127.0.0.1:8000/adapters/lidl/sync
```

Only new `ticket.id` values from the last 6 months are imported. Older Lidl tickets have no HTML receipt and are skipped. Already stored receipts are skipped (`store + external_receipt_id`).

If the token is expired you get 502/503. Refresh the token file and retry.

Raw receipt without the live client:

```bash
curl -X POST http://127.0.0.1:8000/adapters/lidl/import \
  -H 'Content-Type: application/json' \
  --data-binary @ticket.json
```

## Another store

1. Add a `StoreAdapter` under `backend/app/adapters/` (`key`, `display_name`, `normalize`).
2. Optionally implement `list_summaries` / `fetch_raw` for live polling.
3. `register(...)` in `backend/app/adapters/__init__.py`.

Import and the review tab stay the same. Mappings are per store: the same milk at Lidl and at another shop are different SKUs.

## API (short)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/inventory` | on-hand stock |
| GET/POST | `/products` | catalog |
| GET/POST | `/purchases` | stock-in |
| POST | `/receipts` | canonical receipt |
| GET | `/receipt-lines?status=unmapped` | review queue |
| POST | `/receipt-lines/{id}/resolve` | map to an existing product |
| POST | `/receipt-lines/{id}/create-and-resolve` | create a product and map it |
| GET | `/adapters` | registered stores |
| POST | `/adapters/{key}/sync` | pull new receipts |
| POST | `/adapters/{key}/import` | import a raw receipt |

## Migrations

From `backend/`, with the venv active:

```bash
alembic upgrade head
alembic revision --autogenerate -m "description"
```
