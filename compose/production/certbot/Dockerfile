# syntax=docker/dockerfile:1

# Certbot с плагином подтверждения через DNS reg.ru.
#
# Нужен, когда входящий порт 80 закрыт — а у домашних провайдеров в РФ это
# обычное дело. Подтверждение через DNS не требует ни одного открытого порта:
# certbot создаёт временную TXT-запись в зоне домена, Let's Encrypt читает её
# и выдаёт сертификат. Продление работает так же.
FROM certbot/certbot:latest

RUN pip install --no-cache-dir certbot-dns-regru==1.2.0
