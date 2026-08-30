FROM python:3.11-slim

WORKDIR /app

# System deps for asyncpg + bandit
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Apply migrations before serving. Render may override this with its own
# start command, so the app also bootstraps its schema at startup.
CMD ["sh", "-c", "alembic upgrade head || echo 'alembic failed — falling back to startup schema bootstrap'; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
