#!/usr/bin/env bash
# Публичный стенд «ФСП Карьера» на виртуальном сервере одной командой.
# Сервер: Ubuntu 22.04/24.04, 2 vCPU, 4 ГБ RAM, открыты порты 80 и 443. Запуск от root или пользователя с sudo:
#
#   curl -fsSL https://raw.githubusercontent.com/andercat2/fsp-career/main/deploy/deploy.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/andercat2/fsp-career/main/deploy/deploy.sh | bash -s -- career.example.ru
#
# Без аргумента адрес стенда — https://<IP сервера>.sslip.io (свой домен не нужен). Повторный запуск обновляет код и
# пересобирает стенд; данные и .env сохраняются.
set -euo pipefail

REPO=https://github.com/andercat2/fsp-career.git
DIR=${FSP_DIR:-/opt/fsp-career}
SUDO=$([ "$(id -u)" = 0 ] && echo "" || echo sudo)

command -v git >/dev/null || { $SUDO apt-get update -q && $SUDO apt-get install -y -q git; }
command -v docker >/dev/null || curl -fsSL https://get.docker.com | $SUDO sh

if [ -d "$DIR/.git" ]; then
  $SUDO git -C "$DIR" pull --ff-only
else
  $SUDO git clone "$REPO" "$DIR"
fi
cd "$DIR"

IP=$(curl -fsS https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')
DOMAIN=${1:-${DOMAIN:-$IP.sslip.io}}
if [ ! -f .env ]; then
  rnd() { openssl rand -hex 24; }
  $SUDO tee .env >/dev/null <<EOF
DOMAIN=$DOMAIN
PUBLIC_URL=https://$DOMAIN
FSP_PUBLIC_ISSUER=https://id.$DOMAIN/realms/fsp
SECRET_KEY=$(rnd)
POSTGRES_PASSWORD=$(rnd)
FSP_CLIENT_SECRET=$(rnd)
FSP_REGISTRY_API_KEY=$(rnd)
SANDBOX_TOKEN=$(rnd)
# Демо-стенд для проверки: код подтверждения e-mail показывается на экране, вход «без регистрации» включён.
# Для продуктива: EMAIL_DEV_MODE=false, реальный SMTP, GUEST_MODE=false.
EMAIL_DEV_MODE=true
GUEST_MODE=true
# Черновики заданий от LLM: без модели на сервере — демо-режим с заранее подготовленными черновиками
LLM_BASE_URL=
EOF
  $SUDO chmod 600 .env
  echo ".env создан: адрес https://$DOMAIN, секреты сгенерированы"
fi
DOMAIN=$($SUDO grep '^DOMAIN=' .env | cut -d= -f2)

COMPOSE="$SUDO docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml"
$COMPOSE up -d --build
echo "Сборка завершена, бэкенд наполняет демо-данные…"
for _ in $(seq 1 120); do
  if curl -fsS -o /dev/null "https://$DOMAIN/api/v1/public/stats" 2>/dev/null; then
    echo "Готово: https://$DOMAIN · Swagger: https://$DOMAIN/docs · проверка подбора: https://$DOMAIN/evaluate"
    echo "ФСП ID (mock): https://id.$DOMAIN · демо-аккаунты — на странице входа (пароль demo12345)"
    exit 0
  fi
  $COMPOSE up -d >/dev/null 2>&1  # фронтенд стартует, когда бэкенд закончит наполнение
  sleep 5
done
echo "Стенд не ответил за 10 минут — логи: $COMPOSE logs --tail 50 backend caddy" >&2
exit 1
