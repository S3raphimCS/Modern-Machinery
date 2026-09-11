# Развёртывание на сервере

Инструкция для домашнего сервера `46.183.135.174`, домен `s3raphim-dev.ru`.
Все команды выполняются **на сервере**, а не на машине разработчика.

## Перед началом

Проверьте три вещи — без них выпуск сертификата не пройдёт.

**1. Домен указывает на сервер.** С любой машины вне домашней сети:

```bash
dig +short s3raphim-dev.ru A        # должно вернуть 46.183.135.174
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

## Если на сервере уже что-то запущено

Порты 80 и 443 должен занять только этот проект. Пока их держит старый
контейнер или системный веб-сервер, nginx не поднимется, а сертификат не
выпустится.

### Сначала посмотреть, что там есть

Ничего не останавливайте, пока не увидите картину целиком:

```bash
docker ps -a                      # все контейнеры, включая остановленные
docker compose ls                 # проекты compose и их файлы
docker volume ls                  # тома с данными
sudo ss -tulpn | grep -E ':(80|443|5432|6379|8000)\s'   # кто занял порты
```

Последняя команда важнее прочих: она покажет и контейнеры, и системные
службы вроде nginx или apache, установленные мимо Docker.

### Остановить, не потеряв данные

**Если старый проект поднимался через compose**, останавливайте его же
командой — так уйдут и контейнеры, и сеть:

```bash
docker compose -f /путь/к/старому/docker-compose.yml down
```

Без `-v`. Ключ `-v` удаляет тома вместе с базой, и данные не вернуть.

**Если контейнеры запускались поодиночке:**

```bash
docker stop $(docker ps -q)              # остановить все работающие
docker update --restart=no $(docker ps -aq)   # снять автозапуск
```

Вторая команда и есть ответ на «чтобы они не запускались»: без неё Docker
поднимет их обратно после перезагрузки сервера.

**Если порт держит системная служба:**

```bash
sudo systemctl stop nginx && sudo systemctl disable nginx
sudo systemctl stop apache2 && sudo systemctl disable apache2
```

### Проверить, что порты свободны

```bash
sudo ss -tulpn | grep -E ':(80|443)\s' || echo "порты свободны"
```

Пока эта команда что-то выводит, запускать проект рано.

### Как вернуть старое обратно

Контейнеры и тома на месте — ничего не удалялось:

```bash
docker start <имя-контейнера>
docker update --restart=unless-stopped <имя-контейнера>
```

### Освободить место, если его мало

Только после того, как убедились, что старое больше не нужно. Команда не
трогает тома, но удаляет остановленные контейнеры и неиспользуемые образы:

```bash
docker system df                  # сначала посмотреть, сколько занято
docker container prune            # удалить остановленные контейнеры
docker image prune -a             # удалить образы, не привязанные к контейнерам
```

`docker system prune --volumes` не используйте: он удаляет тома, в том числе
с базами данных.

## Установка

```bash
git clone https://github.com/S3raphimCS/Modern-Machinery.git modern-machinery
cd modern-machinery
cp .env.example .env
```

Если репозиторий закрытый, понадобится доступ: либо токен при клонировании по
https, либо ключ на сервере и адрес `git@github.com:S3raphimCS/Modern-Machinery.git`.

`make` на сервере может не оказаться. Тогда либо поставьте его
(`sudo apt install make`), либо используйте команды `docker compose` напрямую —
они приведены ниже рядом с каждой целью.

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
# без make:
# docker compose -f docker-compose.prod.yml up -d --build
```

Стек поднимется, применит миграции и соберёт статику. nginx увидит, что
сертификата ещё нет, и поднимется по http — этого достаточно, чтобы пройти
проверку Let's Encrypt.

Убедитесь, что сайт отвечает:

```bash
curl -I http://s3raphim-dev.ru/healthz/
```

### Если входящий порт 80 закрыт

Проверка Let's Encrypt по HTTP требует, чтобы сервер отвечал на 80-м порту из
интернета. У домашних провайдеров в РФ он часто заблокирован, и тогда
`make tls-issue` завершается так:

```
Type: connection
Detail: Fetching http://домен/.well-known/acme-challenge/...:
        Timeout during connect (likely firewall problem)
```

**Как отличить блокировку от незаданного проброса.** Проверьте порт снаружи,
например через check-host.net. «Connection refused» означает, что пакеты
доходят и отвечает сама машина — тогда дело в настройке. «Timeout» означает,
что пакеты не доходят вовсе: либо порт не проброшен на роутере, либо его режет
провайдер. Если при этом другой порт (скажем, SSH) снаружи открыт, белый адрес
у вас есть и проброс в принципе работает — остаётся блокировка именно 80-го.

**Решение — подтверждение через DNS.** Certbot создаёт временную TXT-запись в
зоне домена, Let's Encrypt читает её и выдаёт сертификат. Открытые порты не
нужны совсем, продление работает так же.

Для доменов на reg.ru:

1. В личном кабинете reg.ru откройте раздел управления API, заведите **пароль
   для API** (не от личного кабинета) и разрешите доступ с адреса сервера.

2. Заполните учётные данные:

   ```bash
   cp secrets/regru.ini.example secrets/regru.ini
   nano secrets/regru.ini
   chmod 600 secrets/regru.ini
   ```

3. Выпустите сертификат — сначала в тестовом режиме:

   ```bash
   sed -i 's/^CERTBOT_STAGING=.*/CERTBOT_STAGING=1/' .env
   make tls-issue-dns
   ```

   Выпуск занимает несколько минут: certbot ждёт, пока новая TXT-запись
   разойдётся по серверам имён.

4. Если прошло — настоящий:

   ```bash
   sed -i 's/^CERTBOT_STAGING=.*/CERTBOT_STAGING=0/' .env
   docker compose -f docker-compose.prod.yml run --rm --entrypoint \
     "certbot delete --cert-name $DOMAIN --non-interactive" certbot
   make tls-issue-dns
   ```

Файл `secrets/regru.ini` не попадает ни в репозиторий, ни в образ.

#### Ошибка `ACCESS_DENIED_FROM_IP`

```
Encountered error adding TXT record:
  {'error_code': 'ACCESS_DENIED_FROM_IP',
   'error_text': 'Access to API from this IP denied'}
```

Это **не** ошибка логина и пароля: они приняты, отказ пришёл на проверке
адреса. API reg.ru отвечает только тем адресам, которые внесены в белый список.

Узнайте, каким адресом сервер выходит наружу:

```bash
curl -s https://api.ipify.org; echo
```

Он может отличаться от адреса, на который указывает домен. Затем в личном
кабинете reg.ru откройте раздел управления API и добавьте этот адрес в список
разрешённых. Изменения применяются не мгновенно — подождите пару минут и
повторите `make tls-issue-dns`.

Если у домашнего подключения динамический адрес, список придётся обновлять при
каждой его смене. Проверить текущий можно той же командой.

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

Демонстрационные данные — 88 машин с характеристиками и изображениями,
240 запчастей, 15 услуг, 8 посадочных подборок:

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py seed_demo
```

Администратор сайта:

```bash
docker compose -f docker-compose.prod.yml exec web \
  python manage.py createsuperuser
```

Команда спросит логин, почту и пароль. Пароль вводится скрыто и в историю
командной строки не попадает — в отличие от способа с аргументами.

Учётка `admin/admin` из `make dev-superuser` в production намеренно не
создаётся: команда отказывается работать при `DEBUG=False`.

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

## Работа за существующим обратным прокси

Если порты 80 и 443 уже занял другой сервер — Caddy, Traefik, системный
nginx — и трогать его нельзя, проект можно поставить позади него. Тогда
сертификатом занимается внешний прокси, а наш nginx слушает только localhost:

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.behind-proxy.yml up -d
```

Наружу ничего не публикуется, поднимается всё кроме certbot. Пример блока для
Caddy — в [`compose/production/Caddyfile.example`](../compose/production/Caddyfile.example).

Внешний прокси обязан передавать `X-Forwarded-Proto`. Без этого заголовка
Django считает соединение незашифрованным и отправляет браузер на https, где
его встречает тот же прокси, — получается бесконечная переадресация. Заголовок
принимается только от соседа по машине или по внутренней сети: из интернета
подделать его нельзя.

## Если что-то пошло не так

**Контейнер `web` падает, а ошибки не видно.** `make prod-up` запускает стек в
фоне, поэтому ошибка остаётся в журнале:

```bash
docker compose -f docker-compose.prod.yml logs web --tail 50
```

Либо запустить на переднем плане и увидеть вывод сразу:

```bash
docker compose -f docker-compose.prod.yml up web
```

Частые причины:

| В журнале | Причина | Что делать |
|---|---|---|
| `Set the DJANGO_SECRET_KEY environment variable` | нет `.env` или в нём пустой ключ | `cp .env.example .env` и задать ключ |
| `ImproperlyConfigured: Set the DJANGO_ALLOWED_HOSTS` | не заполнен список доменов | вписать домен в `.env` |
| `База данных не ответила за 60 секунд` | контейнер базы не поднялся | `docker compose -f docker-compose.prod.yml logs db` |
| `password authentication failed` | `DATABASE_URL` разошёлся с `POSTGRES_USER`/`POSTGRES_PASSWORD` | привести к одним значениям |
| `operator class "gin_trgm_ops" does not exist` | старый образ без исправления миграций | `git pull && make prod-up` |
| `variable is not set` при запуске | не заданы `POSTGRES_*` или `DOMAIN` | заполнить `.env` |
| `Invalid HTTP_HOST header: '127.0.0.1:8000'` | старый образ: проверка живости не представлялась доменом | `git pull && make prod-up` |

**Контейнер «unhealthy», хотя сайт работает.** Проверка живости обращается к
приложению изнутри и представляется доменом из `DOMAIN`. Если он расходится с
`DJANGO_ALLOWED_HOSTS`, Django отвечает 400 и контейнер считается сломанным.
Значения должны совпадать:

```bash
grep -E "^(DOMAIN|DJANGO_ALLOWED_HOSTS)=" .env
```

Посмотреть, что именно вернула последняя проверка:

```bash
docker inspect --format '{{range .State.Health.Log}}{{.Output}}{{end}}' \
  modern-machinery-prod-web-1
```


Проверить, что окружение вообще прочиталось:

```bash
docker compose -f docker-compose.prod.yml config | grep -E "DJANGO_ALLOWED_HOSTS|DATABASE_URL|DOMAIN"
```



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
