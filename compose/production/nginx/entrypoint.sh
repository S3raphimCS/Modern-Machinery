#!/bin/sh
# Точка входа nginx.
#
# Конфигурация собирается при старте и зависит от того, выпущен ли уже
# сертификат. Так контейнер поднимается и на чистом сервере, где сертификата
# ещё нет: без этого nginx падал бы при старте на отсутствующем файле
# ssl_certificate, и выпустить сертификат стало бы невозможно — проверка
# Let's Encrypt ходит через тот же nginx.
set -e

: "${DOMAIN:?переменная DOMAIN обязательна}"

SERVER_NAMES="$DOMAIN"
if [ -n "$DOMAIN_ALIAS" ]; then
    SERVER_NAMES="$DOMAIN $DOMAIN_ALIAS"
fi
export DOMAIN SERVER_NAMES

CERT="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"

if [ -f "$CERT" ]; then
    echo "Сертификат для $DOMAIN найден — включаю https."
    TEMPLATE=/etc/nginx/templates/https.conf.template
else
    echo "Сертификата для $DOMAIN нет — поднимаюсь по http для выпуска."
    echo "Выпустить: make tls-issue"
    TEMPLATE=/etc/nginx/templates/http-only.conf.template
fi

cp /etc/nginx/templates/base.conf /etc/nginx/conf.d/00-base.conf
envsubst '${DOMAIN} ${SERVER_NAMES}' < "$TEMPLATE" > /etc/nginx/conf.d/default.conf

nginx -t
exec "$@"
