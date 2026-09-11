# Быстрые команды проекта.
#
# Команды работают в двух режимах. По умолчанию — локально через uv. Если
# передать DOCKER=1, те же команды выполняются внутри compose: удобно, когда
# окружение поднято контейнерами.

.DEFAULT_GOAL := help
SHELL := /bin/bash

COMPOSE := docker compose
COMPOSE_PROD := docker compose -f docker-compose.prod.yml

ifeq ($(DOCKER),1)
	RUN := $(COMPOSE) run --rm web
	MANAGE := $(COMPOSE) run --rm web python manage.py
else
	RUN := uv run
	MANAGE := uv run python manage.py
endif

.PHONY: help
help:  ## Показать список команд
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# --- Окружение -------------------------------------------------------------

.PHONY: install
install:  ## Установить зависимости и pre-commit
	uv sync --all-groups
	uv run pre-commit install

.PHONY: env
env:  ## Создать .env из шаблона, если его ещё нет
	@test -f .env || (cp .env.example .env && echo "Создан .env — задайте DJANGO_SECRET_KEY")

# --- Разработка ------------------------------------------------------------

.PHONY: up
up: env  ## Поднять окружение разработки в Docker
	$(COMPOSE) up -d --build
	@echo "Сайт: http://127.0.0.1:8000  ·  Админка: http://127.0.0.1:8000/admin/"

.PHONY: down
down:  ## Остановить окружение
	$(COMPOSE) down

.PHONY: clean
clean:  ## Остановить окружение и удалить тома (данные будут потеряны)
	$(COMPOSE) down -v

.PHONY: logs
logs:  ## Смотреть логи приложения
	$(COMPOSE) logs -f web worker

.PHONY: ps
ps:  ## Показать состояние контейнеров
	$(COMPOSE) ps

.PHONY: run
run:  ## Запустить сервер разработки локально
	$(MANAGE) runserver 0.0.0.0:8000

.PHONY: shell
shell:  ## Открыть shell Django
	$(MANAGE) shell

.PHONY: dbshell
dbshell:  ## Открыть psql
	$(MANAGE) dbshell

# --- База данных -----------------------------------------------------------

.PHONY: migrate
migrate:  ## Применить миграции
	$(MANAGE) migrate

.PHONY: makemigrations
makemigrations:  ## Создать миграции
	$(MANAGE) makemigrations

.PHONY: check-migrations
check-migrations:  ## Проверить, что нет забытых миграций
	$(MANAGE) makemigrations --check --dry-run

.PHONY: seed
seed:  ## Наполнить базу демонстрационными данными
	$(MANAGE) seed_demo

.PHONY: superuser
superuser:  ## Создать администратора (интерактивно)
	$(MANAGE) createsuperuser

.PHONY: dev-superuser
dev-superuser:  ## Создать администратора admin/admin для локальной работы
	$(MANAGE) create_dev_superuser

# --- Качество кода ---------------------------------------------------------

.PHONY: lint
lint:  ## Проверить код линтером и форматированием
	$(RUN) ruff check .
	$(RUN) ruff format --check .

.PHONY: format
format:  ## Отформатировать код и починить автоисправимое
	$(RUN) ruff check --fix .
	$(RUN) ruff format .

.PHONY: test
test:  ## Прогнать тесты
	$(RUN) pytest

.PHONY: test-fast
test-fast:  ## Прогнать тесты без замера покрытия
	$(RUN) pytest --no-cov -p no:randomly

.PHONY: cover
cover:  ## Прогнать тесты и собрать HTML-отчёт о покрытии
	$(RUN) pytest --cov-report=html
	@echo "Отчёт: htmlcov/index.html"

.PHONY: security
security:  ## Проверить зависимости и код на известные проблемы
	$(RUN) pip-audit --strict
	$(RUN) bandit -c pyproject.toml -r apps config -q

.PHONY: check-deploy
check-deploy:  ## Проверить настройки production
	DJANGO_SETTINGS_MODULE=config.settings.production \
	DJANGO_ALLOWED_HOSTS=example.com \
	$(RUN) python manage.py check --deploy --fail-level WARNING

.PHONY: ci
ci: lint check-migrations test security  ## Прогнать всё, что проверяет CI

# --- Production ------------------------------------------------------------

.PHONY: build
build:  ## Собрать production-образ
	docker build --target runtime -t modern-machinery:latest .

.PHONY: prod-up
prod-up:  ## Поднять production-профиль
	$(COMPOSE_PROD) up -d --build

.PHONY: prod-down
prod-down:  ## Остановить production-профиль
	$(COMPOSE_PROD) down

.PHONY: prod-logs
prod-logs:  ## Смотреть логи production
	$(COMPOSE_PROD) logs -f web worker nginx

# --- TLS -------------------------------------------------------------------

.PHONY: tls-issue
tls-issue:  ## Выпустить сертификат Let's Encrypt и включить https
	@test -f .env || (echo "Нет .env — скопируйте из .env.example" && exit 1)
	@set -a && . ./.env && set +a && 	test -n "$$DOMAIN" || (echo "В .env не задан DOMAIN" && exit 1); 	echo "Выпускаю сертификат для $$DOMAIN"; 	$(COMPOSE_PROD) run --rm --entrypoint certbot certbot certonly 		--webroot --webroot-path=/var/www/certbot 		-d "$$DOMAIN" $${DOMAIN_ALIAS:+-d "$$DOMAIN_ALIAS"} 		--email "$$CERTBOT_EMAIL" --agree-tos --no-eff-email 		$${CERTBOT_STAGING:+$$([ "$$CERTBOT_STAGING" = "1" ] && echo --staging)} 		--non-interactive
	$(COMPOSE_PROD) up -d --force-recreate nginx
	@echo "Готово. Проверьте: https://$$(grep '^DOMAIN=' .env | cut -d= -f2)/"

.PHONY: tls-issue-dns
tls-issue-dns:  ## Выпустить сертификат через DNS reg.ru (когда порт 80 закрыт)
	@test -f secrets/regru.ini || (echo "Нет secrets/regru.ini — скопируйте из secrets/regru.ini.example" && exit 1)
	@set -a && . ./.env && set +a && \
	test -n "$$DOMAIN" || (echo "В .env не задан DOMAIN" && exit 1); \
	echo "Выпускаю сертификат для $$DOMAIN через подтверждение в DNS"; \
	$(COMPOSE_PROD) run --rm --entrypoint certbot certbot certonly \
		--authenticator dns-regru \
		--dns-regru-credentials /run/secrets/regru.ini \
		--dns-regru-propagation-seconds 300 \
		-d "$$DOMAIN" $${DOMAIN_ALIAS:+-d "$$DOMAIN_ALIAS"} \
		--email "$$CERTBOT_EMAIL" --agree-tos --no-eff-email \
		$$([ "$$CERTBOT_STAGING" = "1" ] && echo --staging) \
		--non-interactive
	$(COMPOSE_PROD) up -d --force-recreate nginx
	@echo "Готово. Проверьте: https://$$(grep '^DOMAIN=' .env | cut -d= -f2)/"

.PHONY: tls-renew
tls-renew:  ## Продлить сертификат вручную (обычно это делает certbot сам)
	# Способ подтверждения certbot помнит сам, повторять его не нужно.
	$(COMPOSE_PROD) run --rm --entrypoint certbot certbot renew
	$(COMPOSE_PROD) exec nginx nginx -s reload

.PHONY: tls-status
tls-status:  ## Показать срок действия сертификата
	$(COMPOSE_PROD) run --rm --entrypoint certbot certbot certificates

.PHONY: backup
backup:  ## Сделать резервную копию базы
	@mkdir -p backups
	$(COMPOSE_PROD) exec -T db pg_dump -U $${POSTGRES_USER} $${POSTGRES_DB} \
		| gzip > backups/db-$$(date +%Y%m%d-%H%M%S).sql.gz
	@echo "Копия сохранена в backups/"

.PHONY: restore
restore:  ## Восстановить базу из копии: make restore FILE=backups/db-....sql.gz
	@test -n "$(FILE)" || (echo "Укажите файл: make restore FILE=backups/db-....sql.gz" && exit 1)
	gunzip -c $(FILE) | $(COMPOSE_PROD) exec -T db psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}
	@echo "База восстановлена из $(FILE)"
