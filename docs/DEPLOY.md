# Развёртывание на сервере

Инструкция для домашнего сервера `46.181.135.174`, домен `s3raphim-dev.ru`.
Все команды выполняются **на сервере**, а не на машине разработчика.

## Перед началом

Проверьте три вещи — без них выпуск сертификата не пройдёт.

**1. Домен указывает на сервер.** С любой машины вне домашней сети:

```bash
dig +short s3raphim-dev.ru A        # должно вернуть 46.181.135.174
dig +short www.s3raphim-dev.ru A    # если планируете www
```

Если возвращается что-то другое — правьте A-запись у регистратора и ждите
обновления DNS. Кеш может держаться до суток.

**2. Порты 80 и 443 доступны снаружи.** Проверять нужно именно снаружи:
из домашней сети запрос может уходить в обход. Воспользуйтесь мобильным
интернетом или любым внешним сервисом проверки портов.

Порт 80 нужен не только для сайта: по нему Let's Encrypt проверяет, что домен
ваш. Часть домашних провайдеров его блокирует — тогда сертификат по этой схеме
не выпустится, и нужен способ с подтверждением через DNS.

**3. На сервере есть Docker и плагин compose.**

```bash
docker --version && docker compose version
```

## Установка

```bash
git clone <адрес репозитория> modern-machinery
cd modern-machinery
cp .env.example .env
```

### Настройка окружения

Откройте `.env` и задайте значения.

**Обязательно смените ключ приложения.** В шаблоне лежит заглушка, а не ключ:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

Полученную строку впишите в `DJANGO_SECRET_KEY`.

**Смените пароль базы.** `postgres:postgres` из шаблона годится, только пока
порт базы не опубликован наружу (в production-профиле так и есть). Если
сервер доступен другим людям, поставьте случайный пароль и там.

Проверьте, что домен и почта заполнены:

```
DOMAIN=s3raphim-dev.ru
DOMAIN_ALIAS=www.s3raphim-dev.ru
CERTBOT_EMAIL=ваша@почта
DJANGO_ALLOWED_HOSTS=s3raphim-dev.ru,www.s3raphim-dev.ru
DJANGO_CSRF_TRUSTED_ORIGINS=https://s3raphim-dev.ru,https://www.s3raphim-dev.ru
SITE_URL=https://s3raphim-dev.ru
```

**`DJANGO_SECURE_SSL_REDIRECT` оставьте `True`.** Сайт собирает персональные
данные: по http они пойдут открытым текстом.

### Первый запуск

```bash
make prod-up
```

Стек поднимется, применит миграции и соберёт статику. nginx увидит, что
сертификата ещё нет, и поднимется по http — этого достаточно, чтобы пройти
проверку Let's Encrypt.

Убедитесь, что сайт отвечает:

```bash
curl -I http://s3raphim-dev.ru/healthz/
```

### Выпуск сертификата

Сначала в тестовом режиме — он не тратит лимит Let's Encrypt (5 выпусков на
домен в неделю, исчерпать его на опечатке легко):

```bash
sed -i 's/^CERTBOT_STAGING=.*/CERTBOT_STAGING=1/' .env
make tls-issue
```

Если прошло без ошибок, выпускайте настоящий:

```bash
sed -i 's/^CERTBOT_STAGING=.*/CERTBOT_STAGING=0/' .env
docker compose -f docker-compose.prod.yml run --rm --entrypoint \
  "certbot delete --cert-name s3raphim-dev.ru --non-interactive" certbot
make tls-issue
```

Команда получит сертификат и перезапустит nginx. Тот увидит сертификат и
включит https: весь трафик с 80-го порта пойдёт на 443-й.

```bash
curl -I https://s3raphim-dev.ru/
```

Продление certbot делает сам: проверяет дважды в сутки и обновляет за 30 дней
до истечения. Вручную — `make tls-renew`, посмотреть срок — `make tls-status`.

### Наполнение

```bash
make prod-up                                          # если ещё не запущен
docker compose -f docker-compose.prod.yml exec web \
  python manage.py createsuperuser
```

Демонстрационные данные (88 машин, 240 запчастей, 15 услуг):

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py seed_demo
```

## После запуска

| Что | Где |
|---|---|
| Сайт | `https://s3raphim-dev.ru/` |
| Админка | `https://s3raphim-dev.ru/admin/` |
| Документация API | `https://s3raphim-dev.ru/api/docs/` |
| Проверка живости | `https://s3raphim-dev.ru/healthz/` |
| Логи | `make prod-logs` |

## Что ещё стоит сделать

**Письма по заявкам.** Сейчас `EMAIL_URL=consolemail://` — письмо печатается в
лог контейнера. Заявка сохраняется в базе и видна в админке, но менеджер о ней
не узнает. Для реальной работы пропишите SMTP:

```
EMAIL_URL=smtp://пользователь:пароль@smtp.example.ru:587/?tls=True
```

**Резервные копии.** Ручные команды есть (`make backup`, `make restore`),
автоматики пока нет — план в [`TODO.md`](TODO.md). На домашнем сервере это
важнее, чем на хостинге: там нет ни снапшотов, ни чужого RAID.

**Мониторинг.** Задайте `SENTRY_DSN`, если хотите получать ошибки. Внешняя
проверка `/healthz/` покажет, что сервер жив, — домашний канал пропадает чаще
серверного.

**Автозапуск после перезагрузки.** Контейнеры объявлены с
`restart: unless-stopped`, но сам Docker должен стартовать вместе с системой:

```bash
sudo systemctl enable docker
```

## Если что-то пошло не так

**`make tls-issue` жалуется на проверку домена.** Убедитесь, что снаружи
открывается `http://s3raphim-dev.ru/.well-known/acme-challenge/проба` — создайте
пробный файл:

```bash
docker compose -f docker-compose.prod.yml exec nginx sh -c \
  'echo ok > /var/www/certbot/.well-known/acme-challenge/probe'
curl http://s3raphim-dev.ru/.well-known/acme-challenge/probe
```

Пусто или ошибка — значит запрос до сервера не доходит: смотрите проброс
портов на роутере и блокировку 80-го порта провайдером.

**Сайт отвечает 400.** Домен не перечислен в `DJANGO_ALLOWED_HOSTS`. Django
намеренно отклоняет запросы с посторонним заголовком `Host`.

**Браузер циклически переадресует на https.** nginx не видит сертификата и
работает по http, а Django требует https. Посмотрите `make prod-logs`: в
логах nginx при старте написано, нашёл он сертификат или нет.

**Контейнер `web` не становится healthy.** Смотрите
`docker compose -f docker-compose.prod.yml logs web` — чаще всего это
незаданный `DJANGO_SECRET_KEY` или недоступная база.
