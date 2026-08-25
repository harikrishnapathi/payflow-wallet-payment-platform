FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "python -m alembic upgrade head && python -m scripts.initialize_system_accounts && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]