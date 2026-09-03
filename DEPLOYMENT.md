# Betting Platform — Deployment

Frontend on Vercel, backend + Postgres on Railway.

- Frontend: https://betting-platform-wheat.vercel.app
- Backend: https://betting-platform-production-ed57.up.railway.app

Health check: `GET /health` returns `{"status":"ok"}` when the backend is up.

---

## How the backend boots

`backend/Dockerfile` runs `backend/start.sh`, which does three things in order:

1. Prints the resolved database host (never the password) and waits up to 60s
   for Postgres, reporting the driver's own error on each retry.
2. Runs `alembic upgrade head`.
3. Starts uvicorn on `$PORT`, defaulting to 8000.

**Railway needs no custom Start Command.** Setting one breaks things: Railway
does not run it through a shell, so `--port $PORT` arrives as the literal
string `$PORT` and uvicorn rejects it. Leave the field empty.

Migrations run on every boot, so there is no manual migration step.

---

## Railway (backend + database)

### Services

The project holds two services: **betting-platform** (the API) and
**postgres**. They are configured separately — check which one you are
editing before changing anything.

> Never set a Start Command on the **postgres** service. Postgres then tries
> to exec a binary that does not exist in its image and dies with
> `ERROR (catatonit:2): failed to exec pid1: No such file or directory`,
> while the dashboard still reports "Online". Every connection then times
> out and the cause is invisible from the API side.

### betting-platform settings

- **Root Directory:** `./backend`
- **Start Command:** *empty*
- **Public Networking:** the generated domain's port must match the port the
  app logs on startup (`Uvicorn running on http://0.0.0.0:8080`). A mismatch
  serves 502 with a perfectly healthy app behind it.

### betting-platform variables

| Variable | Value |
|---|---|
| `DATABASE_URL` | `${{ postgres.DATABASE_URL }}` |
| `JWT_SECRET` | any random 32+ character string |
| `ODDSAPI_KEY` | your OddsAPI key (see `backend/.env`, which is gitignored) |
| `ENVIRONMENT` | `production` |

Set `DATABASE_URL` with Railway's reference picker, not by typing: type `${{`
and choose the service and variable from the menus. Service references are
case-sensitive, and a name that does not match resolves silently to an empty
string rather than erroring.

---

## Vercel (frontend)

- **Root Directory:** `./frontend`
- **Framework Preset:** Next.js
- **Output Directory:** *empty* — leave it blank so Vercel auto-detects.
  Setting it to `public` or `.next` by hand yields 404s on every route even
  though the build log reports success.
- **Environment variable:** `NEXT_PUBLIC_API_URL` = the Railway backend URL.
  The `NEXT_PUBLIC_` prefix is required — the browser makes these calls, so
  the value has to be public. Vercel warns about this; the warning is
  expected here.

Changing a Vercel environment variable needs a redeploy to take effect.

---

## Verifying a deploy

```sh
BACKEND=https://betting-platform-production-ed57.up.railway.app

curl -s $BACKEND/health
# {"status":"ok"}

curl -s -X POST $BACKEND/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"atleast8chars","initial_bankroll":1000}'
# {"user_id":N,"token":"..."}

curl -s $BACKEND/api/odds/NFL
# {"sport":"NFL","games":[],"count":0} until the poller has run
```

Odds poll every 10 minutes, so an empty list right after deploy is normal.

---

## Troubleshooting

Errors actually hit during the first deploy, and what each one means.

| Symptom | Cause |
|---|---|
| `Invalid value for '--port': '$PORT' is not a valid integer` | A custom Start Command is set. Clear it. |
| Backend 502 but logs show `Uvicorn running` | Public domain port does not match the port in the log. |
| `connection to ... postgres.railway.internal ... timeout expired` | Postgres is not actually serving. Check its logs — most likely a Start Command was set on it. |
| `failed to exec pid1: No such file or directory` in postgres logs | A Start Command or image override is set on the postgres service. Remove it. |
| `Could not parse SQLAlchemy URL from string ''` | `DATABASE_URL` resolved to empty; the `${{ }}` reference does not match. Re-pick it from the menu. |
| `column bets.<name> does not exist` | Model changed without a migration. See below. |
| Vercel 404 on every route, build succeeded | Output Directory is set. Clear it and redeploy. |
| Frontend "failed to fetch" | `NEXT_PUBLIC_API_URL` is wrong, or the backend is down — check `/health` first. |

### Schema changes

The deployed schema comes from migrations, but the test suite builds tables
from the models. A model change without a migration passes every test and
fails in production. `tests/test_migrations.py` guards this — it upgrades a
fresh database to head and asserts Alembic finds nothing left to generate.

After changing `app/models.py`:

```sh
cd backend
alembic revision --autogenerate -m "describe the change"
# review the generated file — autogenerate writes a rename as add+drop,
# which discards data; convert it to a real rename where appropriate
python -m pytest tests/test_migrations.py
```

Commit the migration with the model change.

---

## Costs

| Service | Monthly |
|---|---|
| Vercel | $0 |
| Railway | ~$5 (includes Postgres) |
| OddsAPI | $0 on the free tier |
