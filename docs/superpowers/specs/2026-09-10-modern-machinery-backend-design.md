# Бэкенд сайта филиала «Модерн Машинери Фар Ист» (Хабаровск) — дизайн-документ

Дата: 2026-09-10
Источники требований: `modern-machinery-plan-stage-0-1.md` (разделы 4, 6, 7), макет
`design/Design/Модерн Машинери - Сайт.dc.html`.

## 1. Цель и рамки

Демонстрационный, но production-grade бэкенд сайта хабаровского филиала: каталог техники
с нормализованными характеристиками и фасетными фильтрами, каталог запчастей, модуль
услуг, контент, приём и маршрутизация заявок с соблюдением 152-ФЗ, SEO-слой.

Объём соответствует разделу 7 плана (сужение до Хабаровска), а не разделу 4
(корпоративный сайт группы).

**Вне объёма:** личный кабинет клиента, интеграция с 1С, онлайн-оплата, телематика,
англоязычная версия, парсер старого сайта (оставлена только точка расширения —
идемпотентная команда импорта из JSON).

## 2. Принятые решения

| Вопрос | Решение |
|---|---|
| Объём | Полный этап 1 по разделу 7 (Хабаровск) |
| Форма бэкенда | DRF API + серверный рендеринг Django-шаблонов с HTMX |
| Данные | Генератор демо-данных `seed_demo` (детерминированный) |
| Инфраструктура | PostgreSQL, Redis + Celery (worker + beat), nginx + gunicorn в prod-профиле |
| Медиа | Локальный том; переключение на S3 через переменные окружения |
| Аутентификация | Кастомная модель `User` с первого дня, сессионный вход в админку. API каталога — публичное чтение, запись только заявки с дросселированием. JWT — задел на этап 2 |
| Шаблоны | Порт макета `Модерн Машинери - Сайт.dc.html`, включая мобильную версию |
| Стили | Рукописный CSS с переменными по токенам макета. Node в проекте не используется |
| Тесты | pytest + pytest-django + factory-boy на реальном PostgreSQL, гейт покрытия 90% |
| CI | ruff, pytest+coverage, проверка миграций и `check --deploy`, pip-audit + bandit + сборка образа |

## 3. Стек

Python 3.13 (через uv), Django 5.2 LTS, DRF 3.16, PostgreSQL 17+ (`pg_trgm`, `unaccent`),
Redis 7, Celery 5.5, drf-spectacular, django-filter, django-treebeard, Pillow,
psycopg[binary], django-environ, gunicorn, WhiteNoise, sentry-sdk (по DSN).
Инструменты: uv (`uv.lock`), ruff (lint + format), pytest, factory-boy, pre-commit.

## 4. Структура проекта

```
config/                 настройки по окружениям, urls, celery
apps/core/              абстрактные модели, миксины, healthcheck
apps/users/             кастомная модель User
apps/catalog/           Brand, Category, MachineType, Machine, MachineImage,
                        MachineDocument, MachineStock
apps/specs/             SpecGroup, SpecKey, SpecOption, MachineSpec, нормализатор
apps/parts/             PartCategory, Part, PartApplicability, PartAnalog, PartStock
apps/services/          ServiceCategory, Service
apps/company/           Branch, Department, Employee, ContactPoint
apps/content/           Page, PageBlock, NewsPost, Vacancy, MenuItem, SiteSettings
apps/leads/             Lead, LeadEvent, ConsentVersion, LeadRoutingRule, TCO
apps/seo/               RedirectRule, NotFoundLog, middleware, sitemaps, JSON-LD
apps/imports/           ImportRun, SourcePage, seed_demo, import_machines
templates/ static/ locale/ compose/ docs/ tests/
```

Внутри приложения: `models/ api/ views/ admin.py services.py tests/ factories.py`.
Тесты лежат рядом с кодом; сквозные — в корневом `tests/`.

## 5. Модель данных

База — раздел 6 плана с сокращениями раздела 7.4: `Region` не создаётся, `Branch`
остаётся (на нём висят сотрудники, контакты, склад), `NewsPost.branches` убран.

Отклонения от плана, продиктованные макетом:

- `Machine.price`, `Machine.price_note`, `Machine.is_price_on_request` — в макете
  карточка показывает цену. По умолчанию цена скрыта («по запросу»).
- `MachineStock` (филиал, статус, количество, срок готовности) по образцу `PartStock` —
  макет показывает «В наличии · 2 ед.» и «Готовность к выдаче».
- `Machine.equipment` — таб «Комплектация».
- `ContactPoint.Kind.WHATSAPP` — кнопка WhatsApp в макете.
- `LeadRoutingRule` (тип заявки + категория → отдел + адреса) — маршрутизация заявок
  внутри филиала без участия разработчика.

Инварианты, вынесенные в ограничения БД: одна главная картинка на машину, ровно одно
заполненное значение в `MachineSpec`, владелец `ContactPoint` — либо филиал, либо
сотрудник. Все FK на справочники — `PROTECT`, на контент — `SET_NULL`. Физического
удаления нет: `is_active` / `is_published`.

## 6. Ключевые механики

**Нормализация характеристик** (`apps/specs/normalization.py`) — чистые функции без
Django: разбор `"257 кВт"` в число и единицу, разбор диапазона `"6,6–7,4 м"` в
`value_num` / `value_num_max`, сопоставление названия параметра со `SpecKey.aliases`.
Предусловие всех фильтров, покрывается параметризованными тестами.

**Фасетные фильтры** — `EXISTS`-подзапросы к `MachineSpec` вместо цепочки JOIN.
Счётчики фасетов кэшируются в Redis на 15 минут, инвалидация по сигналу сохранения.
Состояние фильтров живёт в query-string.

**Денормализация** — `Machine.specs_cache` пересчитывается сигналом при сохранении
`MachineSpec`; `raw_specs` хранит сырые данные импорта.

**Поиск** — `SearchVectorField` + GIN по технике (веса name A, full_name A, brand B,
description D); `Part.article_norm` + trigram, чтобы `600 311 3750`, `600-311-3750` и
`6003113750` находили одну позицию.

**Заявки и 152-ФЗ** — honeypot, дросселирование, привязка к версии согласия
(`ConsentVersion`), сохранение UTM/referrer/IP/User-Agent, маршрутизация письма
Celery-задачей по `LeadRoutingRule`, поле `purge_after` и периодическая задача
обезличивания просроченных персональных данных.

**Дросселирование создания заявок** — многоуровневое: DRF-throttle по IP на
`POST /api/v1/leads/`, тот же лимит на HTML-форме, honeypot-поле, минимальное время
заполнения формы, дедупликация повторной отправки одинаковой заявки в коротком окне.
Лимиты задаются переменными окружения.

**SEO** — middleware редиректов по `RedirectRule` со счётчиком попаданий,
автосоздание правила при смене slug, логирование 404 в `NotFoundLog`, `sitemap.xml`,
`robots.txt`, JSON-LD `Organization` / `LocalBusiness` / `Product` / `BreadcrumbList`,
ЧПУ: `/tehnika/`, `/zapchasti/`, `/uslugi/`, `/o-kompanii/`.

**Калькулятор TCO** — чистая функция расчёта, результат сохраняется как
`Lead(type=tco, payload=...)`.

## 7. API

`/api/v1/`: `machines`, `brands`, `categories`, `machine-types`, `spec-keys`, `parts`,
`part-categories`, `services`, `branches`, `pages`, `news`, `vacancies`,
`leads` (только POST), `tco/calculate`. Схема — `/api/schema/`, Swagger UI — `/api/docs/`.
Чтение анонимно, запись только заявки и только с дросселированием.

## 8. Фронт

Порт макета: шапка с мобильным меню, «Техника» (hero, полоса цифр, каталог), «Запчасти»
(табы категорий, таблица на десктопе и карточки на мобиле), «Сервисные услуги», карточка
техники с табами, форма заявки, футер, модалка, нижний таб-бар. Токены `#DD1C2B`,
`#B01020`, `#16181C`; Montserrat / Roboto / Roboto Mono локально, без Google Fonts.
Адаптив на container queries и `clamp()`, как в макете. HTMX закрывает фильтры,
пагинацию, автодополнение поиска и отправку форм.

## 9. Инфраструктура

Dev-профиль compose: web, db, redis, worker, beat с healthcheck'ами. Prod-профиль:
multi-stage образ (сборка через uv `--frozen`, рантайм без компиляторов), non-root
пользователь, gunicorn за nginx, наружу только nginx, БД и Redis без публикации портов,
`restart: unless-stopped`, лимиты ресурсов, ротация логов, тома `pg_data` / `media` /
`static`. `SECRET_KEY` без значения по умолчанию — прод не стартует без него.

Makefile: `up down logs shell test lint format migrate makemigrations seed superuser
cover ci build prod-up backup restore`.

## 10. Критерии готовности

- Все фильтры, поиск и фасеты работают на сгенерированных данных.
- Покрытие тестами не ниже 90%, CI зелёный по всем четырём джобам.
- `manage.py check --deploy` без предупреждений на prod-настройках.
- Заявка сохраняется, маршрутизируется по отделу и не создаётся при превышении лимита.
- `sitemap.xml` отдаётся, редиректы работают, 404 логируются.
