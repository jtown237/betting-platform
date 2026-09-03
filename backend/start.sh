#!/bin/sh
set -e

# Report where we are pointed before connecting. Password is never printed:
# an unresolved ${{ Service.VAR }} reference arrives as an empty string, and
# without this the only symptom is an opaque connection error.
python - <<'PY'
import os
from urllib.parse import urlsplit

raw = os.environ.get("DATABASE_URL", "")
if not raw.strip():
    print("DATABASE_URL: <EMPTY> -- the Railway variable reference did not resolve")
else:
    p = urlsplit(raw)
    print(f"DATABASE_URL: {p.scheme}://{p.hostname}:{p.port or '(default)'}{p.path}")
PY

echo "Running database migrations..."
alembic upgrade head

echo "Starting API on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
