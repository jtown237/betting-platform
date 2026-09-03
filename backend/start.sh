#!/bin/sh
set -e

# Wait for the database before migrating. Railway's private network is
# IPv6-only and is not guaranteed to be up the instant the container starts,
# so a bare "alembic upgrade" can hang on connect with no diagnostic at all.
python - <<'PY'
import os
import sys
import time
from urllib.parse import urlsplit

import psycopg2

raw = os.environ.get("DATABASE_URL", "").strip()
if not raw:
    sys.exit("DATABASE_URL: <EMPTY> -- the Railway variable reference did not resolve")

p = urlsplit(raw)
print(f"DATABASE_URL: {p.scheme}://{p.hostname}:{p.port or '(default)'}{p.path}")

deadline = time.monotonic() + 60
attempt = 0
while True:
    attempt += 1
    try:
        psycopg2.connect(raw, connect_timeout=5).close()
        print(f"database reachable on attempt {attempt}")
        break
    except Exception as exc:
        detail = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
        if time.monotonic() >= deadline:
            sys.exit(f"database unreachable after {attempt} attempts: {detail}")
        print(f"attempt {attempt}: {detail} -- retrying in 2s")
        time.sleep(2)
PY

echo "Running database migrations..."
alembic upgrade head

echo "Starting API on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
