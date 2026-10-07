# Песочница для задач с кодом: Python 3.11 + Node.js. Контейнер без сети (network_mode: none), файловая система
# только для чтения, отдельный непривилегированный пользователь, лимиты ресурсов — см. docker-compose.yml.
# Бэкенд обращается к песочнице через Unix-сокет на общем томе /run/sandbox.
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 20001 --create-home --shell /usr/sbin/nologin runner \
    && mkdir -p /run/sandbox && chown runner:runner /run/sandbox
WORKDIR /srv
COPY backend/app/services/sandbox/runner.py sandbox/server.py ./
USER 20001
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SANDBOX_CONTAINER=1 SANDBOX_SOCKET=/run/sandbox/sandbox.sock
HEALTHCHECK --interval=15s --timeout=4s --retries=5 CMD ["python", "server.py", "--health"]
CMD ["python", "server.py"]
