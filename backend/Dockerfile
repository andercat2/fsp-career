FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY validation ./validation
COPY tests ./tests

# Непривилегированный пользователь
RUN useradd --create-home --uid 10001 app && mkdir -p /srv/data && chown -R app:app /srv
USER app

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=4s --start-period=60s --retries=10 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

# Один процесс uvicorn: синхронные эндпоинты обслуживает пул потоков (десятки одновременных пользователей);
# для масштабирования — несколько реплик за балансировщиком (сервис stateless, состояние — в PostgreSQL).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
