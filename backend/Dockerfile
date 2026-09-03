FROM python:3.11-slim

WORKDIR /app

# Unbuffered: a crashing container must not swallow its traceback.
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/start.sh

# start.sh runs migrations, then execs uvicorn on $PORT (default 8000).
CMD ["/app/start.sh"]
