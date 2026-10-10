FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEMO_MODE=true \
    DEMO_ADMIN_KEY=evalforge-demo-secret-key-2026 \
    EVALFORGE_DB_PATH=/app/data/evalforge.db

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir -e .

RUN mkdir -p /app/data && python scripts/seed.py

EXPOSE 8000

CMD ["evalforge", "serve", "--host", "0.0.0.0", "--port", "8000"]
