FROM python:3.11-slim

# MALLOC_ARENA_MAX: без ограничения glibc заводит арену памяти на поток, и многопоточный процесс раздувается
# фрагментацией (нагрузочный тест, loadtest/)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MALLOC_ARENA_MAX=2 \
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
HEALTHCHECK --interval=10s --timeout=4s --start-period=300s --retries=10 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

# WEB_CONCURRENCY процессов uvicorn (в docker-compose — 2): синхронные эндпоинты обслуживает пул потоков каждого
# процесса, несколько процессов используют несколько ядер (loadtest/). Дальше — реплики за балансировщиком: сервис
# stateless, состояние — в PostgreSQL.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips '*' --workers ${WEB_CONCURRENCY:-1}"]
