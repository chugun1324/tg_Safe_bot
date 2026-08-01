# ArtSecure Bot (MVP)

Telegram-бот для безопасной передачи заказных артов между заказчиком и исполнителем.

## Что реализовано

- Регистрация ролей через `/start` (заказчик/исполнитель).
- Создание заказа заказчиком `/create` с отправкой заявки исполнителю.
- Принятие/отклонение заявки исполнителем (inline-кнопки).
- Список заказов `/my_orders`.
- Поиск исполнителей `/search <query>`.
- Отправка предпросмотра и финала `/send_art`.
- Авто-watermark предпросмотра (Pillow) + `protect_content=true`.
- Mock escrow-флоу:
  - `/pay <order_id>` — отметка оплаты escrow.
  - `/release <order_id>` — релиз средств исполнителю с комиссией.
- Споры `/dispute <order_id>` и админ-решение `/resolve <id> <refund|release>`.
- Жалобы `/report`.
- Relay-чат внутри заказа `/relay <order_id>`, выход `/leave_relay`.
- Принудительное закрытие заказа `/force_close <order_id>`.
- Админ-функции: `/admin`, `/ban`, `/unban`.
- Rate limiting middleware.

## Стек

- Python 3.10+
- aiogram 3.x
- SQLAlchemy + SQLite (`aiosqlite`)
- Pillow
- reportlab
- pytest

## Быстрый запуск

1. Установить зависимости:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -f requements.txt
```

2. Создать env:

```bash
cp .env.example .env
```

3. Заполнить в `.env` минимум:

- `BOT_TOKEN`
- `ADMIN_IDS` (через запятую) 
- `все другие данныеы` 

4. Запустить бота:

```bash
python -m artsecure_bot.main
# или после установки:
artsecure-bot
```

При первом старте будет создана база `artsecure.db`.

## Как проверить (ручной сценарий)

1. Аккаунт A: `/start` → роль `Заказчик`.
2. Аккаунт B: `/start` → роль `Исполнитель`.
3. A: `/search` чтобы найти B, затем `/create` и указать TG ID B.
4. B: принять заявку кнопкой `Принять`.
5. B: `/send_art` → `1 : 1 медиа ` и отправить картинку.
6. A: `/pay <order_id>`.
7. B: `/send_art` → `Финал`.
8. A: `/release <order_id>`.
9. Проверить `/my_orders`, финальный статус должен быть `Завершен`.

## Тесты

```bash
pytest
```

Покрыты unit-тестами:

- watermark-сервис,
- генерация NDA PDF,
- расчет комиссии/выплаты.
