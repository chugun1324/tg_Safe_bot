from __future__ import annotations

import html
from typing import Final

DEFAULT_LANGUAGE: Final[str] = "ru"
SUPPORTED_LANGUAGES: Final[tuple[str, ...]] = ("ru", "en")

TRANSLATIONS: Final[dict[str, dict[str, str]]] = {
    "ru": {
        "lang_ru": "Русский",
        "lang_en": "English",
        "no_username": "без username",
        "unknown": "неизвестно",
        "btn_help": "🆘 Помощь",
        "btn_rules": "📘 Правила",
        "btn_rules_open_article": "🌐 Открыть правила в браузере",
        "btn_exit": "🚪 Выход",
        "btn_cancel": "❌ Отмена",
        "btn_leave_relay": "↩️ Выйти из чата",
        "btn_mark_done": "✅ Завершить",
        "btn_create_order": "📝 Создать заказ",
        "btn_my_orders": "📂 Мои заказы",
        "btn_search": "🔎 Поиск исполнителя",
        "btn_report": "🚩 Жалоба",
        "btn_send_art": "🖼️ Отправить работу",
        "btn_admin_stats": "📊 Статистика",
        "btn_wallet": "💼 Кошелек",
        "btn_language": "🌐 Язык",
        "btn_share_username": "👤 Дать username",
        "btn_pay_wallet": "Оплатить через Wallet",
        "btn_pay_tonkeeper": "Оплатить через Tonkeeper",
        "btn_invoice_status": "Проверить оплату",
        "btn_pay_order": "Оплатить заказ",
        "btn_topup_wallet": "Инструкция по пополнению кошелька",
        "btn_open_topup": "Открыть пополнение",
        "btn_back_payment_methods": "Назад к способам оплаты",
        "btn_pay_other_soon": "Другие способы (скоро)",
        "btn_relay_open_now": "Перейти в relay-чат",
        "btn_yes": "Да",
        "btn_no": "Нет",
        "btn_view_portfolio": "🎨 Посмотреть портфолио",
        "btn_create_order_with_artist": "📝 Создать заказ с этим исполнителем",
        "btn_open_profile": "🖼 Открыть профиль",
        "portfolio_empty": "У исполнителя пока нет работ в портфолио",
        "btn_profile": "👤 Профиль",
        "btn_show_profile": "✅ Показать профиль",
        "btn_hide_profile": "❌ Скрыть профиль",
        "btn_search_by_username": "🔍 Поиск по username",
        "btn_search_random": "🎲 Случайный поиск",
        "btn_take_artist": "✅ Взять",
        "btn_skip_artist": "➡️ Не взять",
        "profile_management_title": "Управление профилем",
        "profile_status_visible": "Ваш профиль виден заказчикам при автоматическом поиске",
        "profile_status_hidden": "Ваш профиль скрыт от автоматического поиска",
        "profile_visibility_updated": "Видимость профиля обновлена",
        "profile_empty_owner_prompt": (
            "Похоже, ваш профиль ещё не заполнен — заказчики видят его пустым.\n"
            "Нажмите «{btn_open_profile}», чтобы добавить описание и работы в портфолио."
        ),
        "choose_search_type": "Выберите способ поиска исполнителя:",
        "search_type_help": "• Поиск по username - вы вводите @username конкретного исполнителя\n• Случайный поиск - система подберет доступного исполнителя автоматически",
        "artist_profile_preview": (
            "Исполнитель найден:\n"
            "👤 Username: @{artist_username}\n"
            "📊 Завершено заказов: {completed_orders}\n"
            "⭐️ Рейтинг: {rating}/100\n"
            "📝 О себе: {bio}"
        ),
        "artist_profile_preview_no_bio": "не указано",
        "role_customer": "🧑‍💼 Заказчик",
        "role_artist": "🎨 Исполнитель",
        "role_admin": "🛡️ Админ",
        "currency_rub": "РУБ",
        "currency_usd": "USD",
        "currency_usdt": "USDT",
        "order_decision_accept": "✅ Принять",
        "order_decision_reject": "✖️ Отклонить",
        "art_kind_preview": "Предпросмотр",
        "art_kind_final": "Финал",
        "art_kind_direct": "Медиа 1:1",
        "order_action_paid": "💳 Оплатить (escrow)",
        "order_action_release": "💸 Релиз исполнителю",
        "order_action_dispute": "⚠️ Открыть спор",
        "order_action_relay": "💬 Открыть чат сделки",
        "order_action_delete": "🗑️ Удалить заказ",
        "dispute_reason_not_order": "❌ Не тот заказ",
        "dispute_reason_other": "ℹ️ Другое",
        "status_pending_artist": "Ожидает ответа исполнителя",
        "status_in_progress": "В работе",
        "status_preview_sent": "Предпросмотр отправлен",
        "status_paid_escrow": "Escrow оплачен",
        "status_pending_review": "Финальная проверка",
        "status_final_review": "Финальная проверка",
        "status_completed": "Завершен",
        "status_disputed": "Спор",
        "status_cancelled": "Отменен",
        "err_not_registered": "Сначала зарегистрируйтесь через /start",
        "err_banned": "Ваш аккаунт ограничен администратором.",
        "err_wrong_role": "Эта команда доступна для другой роли пользователя.",
        "start_welcome": (
            "Добро пожаловать в ArtSecure.\n"
            "Tonkeeper (Android): https://play.google.com/store/apps/details?id=com.ton_keeper"
        ),
        "start_choose_role": "Выберите вашу роль:",
        "start_registered": "Вы уже зарегистрированы как {role}. Используйте кнопки меню ниже.",
        "invalid_role": "Неверная роль",
        "ask_contact_username_only": (
            "Укажите ваш Telegram username в формате @username.\n"
            "Можно нажать кнопку ниже или ввести вручную."
        ),
        "registration_username_required": (
            "У вас не установлен username в Telegram.\n"
            "Откройте настройки Telegram и добавьте username, затем отправьте его сюда в формате @username."
        ),
        "registration_username_mismatch": (
            "Нужно отправить именно ваш username: {username}.\n"
            "Проверьте ввод и попробуйте снова."
        ),
        "registration_expired": "Сессия регистрации устарела. Повторите /start",
        "registration_done": "Регистрация завершена. Роль: {role}.",
        "registration_quick_guide": (
            "Кратко по главному меню:\n"
            "{btn_create_order} — создать новый заказ\n"
            "{btn_my_orders} — открыть ваши заказы\n"
            "{btn_report} — отправить жалобу\n"
            "{btn_wallet} — указать адрес кошелька\n"
            "{btn_help} — подсказки по командам\n"
            "{btn_language} — сменить язык\n\n"
            "Важно: сначала обязательно заполните кошелек, иначе заказы будут недоступны.\n"
            "Tonkeeper (Android): https://play.google.com/store/apps/details?id=com.ton_keeper"
        ),
        "wallet_address_screenshot_caption": "Пример, где взять адрес кошелька:",
        "help_text": (
            "Команды и кнопки:\n"
            "/start - регистрация\n"
            "/exit - вернуться к выбору роли\n"
            "{btn_create_order} / /create\n"
            "{btn_my_orders} / /my_orders\n"
            "{btn_send_art} / /send_art\n"
            "{btn_search} / /search\n"
            "{btn_report} / /report\n"
            "/relay &lt;id&gt; - защищенный relay-чат по заказу\n"
            "/leave_relay - выйти из relay-чата\n"
            "/pay &lt;id&gt; - escrow оплата\n"
            "/invoice &lt;id&gt; - создать крипто-инвойс escrow\n"
            "/invoice_status &lt;id&gt; - статус инвойса\n"
            "/set_wallet &lt;address&gt; - подключить кошелек заказчика\n"
            "/wallet - показать подключенный кошелек\n"
            "/release &lt;id&gt; - релиз средств исполнителю\n"
            "/dispute &lt;id&gt; - открыть спор\n"
            "/langue - смена языка\n"
            "Поддержка: {support_chat_url}"
        ),
        "rules_link_text": "Полная статья с правилами: {rules_url}",
        "scenario_cancelled": "Текущий сценарий отменен.",
        "exit_role_selecting": "Выход в выбор роли.",
        "exit_role_selected": "Вы вернулись к выбору роли. Нажмите нужную кнопку:",
        "language_choose": "Выберите язык интерфейса:",
        "language_saved": "Язык обновлен: {language_name}",
        "create_ask_artist": "Введите @username исполнителя, которому хотите отправить заявку, или отправьте 'авто' для автоматического выбора:",
        "btn_auto_artist": "🎲 Автоматический выбор",
        "no_available_artists": "Нет доступных исполнителей. Попробуйте позже.",
        "artist_auto_selected": "Автоматически выбран исполнитель: @{artist_username}",
        "username_invalid": "Некорректный username. Пример: @artist_name (5-32 символа, буквы/цифры/_)",
        "username_not_exists": "Такого Telegram username не существует.",
        "username_not_registered_artist": (
            "Пользователь найден, но не зарегистрирован в боте как исполнитель. "
            "Попросите его пройти /start и выбрать роль Исполнитель."
        ),
        "username_check_failed": (
            "Username корректный, но проверить существование через API сейчас не удалось. "
            "Попросите исполнителя начать диалог с ботом через /start."
        ),
        "username_not_artist_role": "Этот пользователь зарегистрирован, но не в роли исполнителя.",
        "create_ask_title": "Введите название заказа:",
        "create_ask_currency": "Выберите валюту заказа:",
        "create_currency_selected": "Валюта выбрана: {currency}",
        "currency_invalid": "Неверная валюта.",
        "create_title_short": "Название слишком короткое.",
        "create_ask_details": "Опишите детали заказа:",
        "create_details_short": "Опишите заказ чуть подробнее (минимум 5 символов).",
        "create_ask_price": "Введите цену в рублях (например 3500):",
        "create_ask_price_currency": "Введите цену в валюте {currency} (число, до 6 знаков после запятой):",
        "price_int_only": "Цена должна быть числом (до 6 знаков после запятой).",
        "price_positive": "Цена должна быть больше нуля.",
        "create_expired": "Сценарий устарел. Начните заново: /create",
        "create_user_not_found": "Не удалось создать заказ: пользователь не найден.",
        "create_only_customer": "Создавать заказ может только заказчик.",
        "create_done": (
            "Заявка #{order_id} создана и отправлена исполнителю.\n"
            "Исполнитель: @{artist_username}\n"
            "Название: {title}\n"
            "Цена: {price} {currency}\n"
            "Ожидайте принятия заявки."
        ),
        "create_send_to_artist": (
            "Новая заявка #{order_id}\n"
            "От: {customer_name} (@{customer_username})\n"
            "Название: {title}\n"
            "Цена: {price} {currency}"
        ),
        "create_send_to_artist_failed": (
            "Не удалось отправить заявку исполнителю в ЛС. "
            "Убедитесь, что он начал диалог с ботом через /start."
        ),
        "order_decision_invalid_format": "Неверный формат",
        "order_decision_invalid_data": "Неверные данные",
        "order_not_found": "Заказ не найден.",
        "order_not_yours": "Это не ваш заказ.",
        "order_already_processed": "Заказ уже обработан",
        "order_accept_short": "Заявка принята",
        "order_reject_short": "Заявка отклонена",
        "order_rejected_message": "Заявка отклонена.",
        "relay_activated_artist": (
            "Заявка #{order_id} принята.\n"
            "Relay-чат уже активирован: отправляйте сюда обычные текстовые сообщения, "
            "они будут пересланы заказчику.\n"
            "Выход: {leave_label}"
        ),
        "relay_activated_customer": (
            "Исполнитель принял заявку #{order_id}.\n"
            "Relay-чат уже активирован: просто отправляйте текстовые сообщения в этот чат, "
            "бот будет пересылать их исполнителю.\n"
            "Выход: {leave_label}"
        ),
        "order_rejected_notify_customer": "Исполнитель отклонил заявку #{order_id}.",
        "my_orders_empty": "У вас пока нет заказов.",
        "my_order_card": (
            "Заказ #{order_id}\n"
            "Статус: {status}\n"
            "Название: {title}\n"
            "Цена: {price} {currency}\n"
            "Заказчик: {customer}\n"
            "Исполнитель: {artist}"
        ),
        "my_orders_footer": "Выше список ваших заказов.",
        "usage_pay": "Использование: /pay &lt;order_id&gt;",
        "usage_invoice": "Использование: /invoice &lt;order_id&gt;",
        "usage_invoice_status": "Использование: /invoice_status &lt;invoice_id&gt;",
        "usage_mock_paid": "Использование: /mock_paid &lt;invoice_id&gt;",
        "usage_set_wallet": "Использование: /set_wallet &lt;your_wallet_address&gt;",
        "usage_release": "Использование: /release &lt;order_id&gt;",
        "usage_dispute": "Использование: /dispute &lt;order_id&gt;",
        "usage_force_close": "Использование: /force_close &lt;order_id&gt;",
        "usage_nda": "Использование: /nda &lt;order_id&gt;",
        "pay_not_your_order": "Это не ваш заказ.",
        "payment_wallet_not_configured": "Escrow-кошелек пока не настроен в .env (ESCROW_WALLET_ADDRESS).",
        "wallet_not_connected": "Сначала подключите кошелек: /set_wallet &lt;wallet_address&gt;",
        "wallet_required_before_orders": (
            "Сначала заполните кошелек через кнопку «{btn_wallet}».\n"
            "До этого создание и просмотр заказов недоступны."
        ),
        "wallet_connected": "Ваш кошелек: {wallet_address}",
        "wallet_saved": "Кошелек сохранен: {wallet_address}",
        "wallet_existing_prompt": (
            "Текущий кошелек: {wallet_address}\n"
            "Оставить этот кошелек или сменить?"
        ),
        "wallet_keep_current": "✅ Оставить текущий",
        "wallet_change_current": "✏️ Сменить кошелек",
        "wallet_keep_done": "Текущий кошелек оставлен без изменений.",
        "wallet_payout_warning": (
            "Внимание: выплаты и возвраты по заказам будут отправляться только на этот адрес.\n"
            "Проверьте адрес внимательно перед каждой сделкой.\n"
            "Tonkeeper (Android): https://play.google.com/store/apps/details?id=com.ton_keeper\n"
            "Ниже пример, где смотреть адрес в кошельке."
        ),
        "wallet_address_invalid": "Некорректный адрес кошелька.",
        "wallet_address_not_found": "Кошелек не найден в сети TON. Проверьте адрес.",
        "wallet_check_unavailable": "Не удалось проверить кошелек через TON API. Попробуйте позже.",
        "wallet_address_not_found_soft": (
            "Внимание: TON API не подтвердил существование кошелька. "
            "Адрес сохранен, но перед сделкой сделайте тестовый перевод."
        ),
        "wallet_check_unavailable_soft": (
            "Внимание: TON API сейчас недоступен. Адрес сохранен без онлайн-проверки."
        ),
        "wallet_enter_prompt": "Введите адрес TON-кошелька для переводов:",
        "wallet_not_enough_balance": "Недостаточно USDT на кошельке. Пополните Wallet и повторите оплату.",
        "invoice_payment_menu": (
            "Заказ #{order_id}\n"
            "Сумма: {amount_usdt} USDT\n"
            "Адрес: {payment_address}\n"
            "Memo: {payment_memo}\n"
            "Выберите способ оплаты ниже.\n"
            "Tonkeeper (Android): https://play.google.com/store/apps/details?id=com.ton_keeper"
        ),
        "invoice_method_choice": (
            "Заказ #{order_id}\n"
            "Сумма: {amount_usdt} USDT\n"
            "Способ: {method}\n"
            "Далее выберите: «Оплатить заказ» или «Инструкция по пополнению кошелька»."
        ),
        "pay_method_soon_notice": "Этот способ оплаты будет добавлен позже.",
        "topup_wallet_instructions": (
            "Инструкция по пополнению через Wallet Telegram:\n"
            "1) Откройте Wallet.\n"
            "2) Выберите пополнение (карта/P2P Express).\n"
            "3) Пополните баланс и вернитесь в бот.\n"
            "4) Нажмите «Проверить оплату»."
        ),
        "topup_tonkeeper_instructions": (
            "Инструкция по пополнению через Tonkeeper:\n"
            "1) Установите или откройте Tonkeeper.\n"
            "2) Пополните TON/USDT через встроенные способы.\n"
            "3) Вернитесь в бот и выберите «Оплатить заказ».\n"
            "4) После перевода нажмите «Проверить оплату».\n"
            "Tonkeeper (Android): https://play.google.com/store/apps/details?id=com.ton_keeper"
        ),
        "invoice_created": (
            "Инвойс #{invoice_id} по заказу #{order_id} создан.\n"
            "Сумма: {amount_usdt} USDT\n"
            "Адрес: {payment_address}\n"
            "Memo: {payment_memo}\n"
            "Срок до: {expires_at}\n"
            "Режим: {mode}\n"
            "Рекомендуется кнопка Tonkeeper (обычно без фикс-комиссии 1 USDT).\n"
            "Кнопка оплаты открывает Wallet, перевод выполните вручную по реквизитам выше.\n"
            "Проверка статуса: /invoice_status {invoice_id}"
        ),
        "invoice_not_found": "Инвойс не найден.",
        "invoice_status_compact": (
            "Заказ #{order_id}\n"
            "Сумма: {amount_usdt} USDT\n"
            "Статус оплаты: {status_line}"
        ),
        "payment_status_created": "Ожидает оплаты",
        "payment_status_awaiting_payment": "Ожидает оплаты",
        "payment_status_paid_pending_confirm": "Проверяется",
        "payment_status_confirmed": "Оплачено",
        "payment_status_underpaid": "Недоплата",
        "payment_status_overpaid": "Переплата",
        "payment_status_expired": "Истек",
        "payment_status_released": "Оплачено",
        "payment_status_refunded": "Возврат",
        "payment_status_cancelled": "Отменен",
        "invoice_status_checking": "Идет проверка оплаты...",
        "invoice_paid_notify_customer": "Оплата успешно выполнена, по заказу #{order_id}.",
        "invoice_paid_notify_artist": "Оплата успешно выполнена, по заказу #{order_id}.",
        "mock_only_mode": "Команда доступна только в PAYMENTS_MODE=mock.",
        "mock_paid_done": (
            "MOCK-оплата подтверждена.\n"
            "Инвойс #{invoice_id}, заказ #{order_id}\n"
            "Tx: {tx_hash}"
        ),
        "mock_paid_notify_artist": "Заказ #{order_id}: escrow отмечен как оплаченный (mock).",
        "pay_not_available_status": "Оплата доступна только для заказов в работе/после предпросмотра.",
        "pay_marked_done": (
            "Escrow для заказа #{order_id} отмечен как оплаченный.\n"
            "Исполнитель может отправить 1:1 медиа и/или медиафайлы в relay-чате.\n"
            "После выполнения работы обе стороны нажимают кнопку «{done_label}» в relay-чате."
        ),
        "pay_notify_artist": "Заказ #{order_id}: заказчик пополнил escrow на {price} RUB.",
        "release_not_available_status": "Релиз через команду отключен. Завершайте заказ кнопкой «{done_label}» в relay-чате.",
        "release_done": (
            "Заказ #{order_id} завершен.\n"
            "Комиссия платформы: {commission} RUB\n"
            "К выплате исполнителю: {payout} RUB"
        ),
        "release_notify_artist": (
            "Заказ #{order_id} успешно завершен заказчиком.\n"
            "К выплате (mock): {payout} RUB, комиссия: {commission} RUB"
        ),
        "dispute_not_participant": "Вы не участник этого заказа.",
        "dispute_choose_reason": "Выберите причину спора по заказу #{order_id}:",
        "dispute_confirm_open": "Вы уверены, что хотите открыть спор по заказу #{order_id}? Заказ будет временно приостановлен.",
        "dispute_open_cancelled": "Спор не открыт. Заказ продолжает выполняться.",
        "dispute_already_under_review": "Спор уже открыт и находится на рассмотрении.",
        "dispute_opened": "Спор по заказу #{order_id} открыт. Администратор рассмотрит его в течение 7 дней.",
        "dispute_opened_with_reason": (
            "Спор по заказу #{order_id} открыт. Администратор рассмотрит его в течение 7 дней.\n"
            "Причина: {reason}"
        ),
        "dispute_notify_user": "По заказу #{order_id} открыт спор.",
        "dispute_admin_new": (
            "[ADMIN] Новый спор\n"
            "Заказ #{order_id}\n"
            "Заказчик: {customer_tg}\n"
            "Исполнитель: {artist_tg}\n"
            "Причина: {reason}"
        ),
        "force_close_already": "Заказ уже закрыт.",
        "force_close_done": "Заказ #{order_id} закрыт принудительно.",
        "force_close_notify_other": "Заказ #{order_id} закрыт принудительно второй стороной.",
        "delete_only_customer": "Удалять заказ может только заказчик.",
        "delete_order_done": "Заказ #{order_id} удален из списка.",
        "delete_order_notify_artist": "Заказ #{order_id} был удален заказчиком и скрыт из ваших списков.",
        "delete_order_paid_confirm": (
            "Заказ #{order_id} уже оплачен ({amount_usdt} USDT в escrow).\n"
            "Удалить заказ и вернуть средства на ваш кошелек?"
        ),
        "delete_order_paid_cancelled": "Удаление оплаченного заказа отменено.",
        "delete_order_refund_wallet_missing": (
            "Невозможно вернуть средства: у вас не заполнен кошелек. "
            "Сначала заполните «Кошелек», затем повторите удаление."
        ),
        "delete_order_refund_failed": "Возврат средств временно недоступен. Заказ не удален, попробуйте позже.",
        "delete_order_refund_done": "Возврат выполнен: {amount_usdt} USDT отправлено на {wallet_address}.",
        "cb_use_pay": "Используйте команду /pay &lt;id&gt;",
        "cb_use_release": "Используйте команду /release &lt;id&gt;",
        "cb_use_dispute": "Используйте команду /dispute &lt;id&gt;",
        "relay_usage": "Использование: /relay &lt;order_id&gt;",
        "relay_not_available_status": "Relay-чат станет доступен после принятия заказа исполнителем.",
        "relay_order_closed": "Этот заказ уже закрыт.",
        "relay_activated": (
            "Relay-чат для заказа #{order_id} активирован.\n"
            "Отправляйте текстовые сообщения и медиа, бот перешлет их второй стороне.\n"
            "Выход: {leave_label}"
        ),
        "relay_off": "Relay-чат выключен.",
        "relay_send_text_or_media": "Отправьте текстовое сообщение или медиафайл.",
        "relay_use_leave": "Для выхода используйте /leave_relay",
        "relay_session_expired": "Сессия relay устарела. Используйте /relay &lt;order_id&gt;.",
        "relay_not_participant_anymore": "Вы больше не участник этого заказа.",
        "relay_sender_customer": "Заказчик",
        "relay_sender_artist": "Исполнитель",
        "relay_forward": "{sender_name}: {text}",
        "relay_forward_other_order": "[Relay заказ #{order_id}] {sender_name}: {text}",
        "relay_media_forward": "{sender_name} отправил медиафайл.",
        "relay_media_forward_other_order": "[Relay заказ #{order_id}] {sender_name} отправил медиафайл.",
        "relay_media_use_send_art": "Для отправки работы используйте кнопку «Отправить работу».",
        # "relay_sent": "Сообщение отправлено.",
        "relay_done_not_paid": "Завершение доступно только после оплаты escrow.",
        "relay_done_already": "Вы уже подтвердили завершение по этому заказу.",
        "relay_done_marked": "Ваше подтверждение учтено.",
        "relay_done_wait_other": "Ожидаем подтверждение второй стороны.",
        "relay_done_progress": "Подтверждения: заказчик={customer_done}, исполнитель={artist_done}.",
        "relay_done_other_confirmed": "Вторая сторона нажала «{done_label}».",
        "relay_done_no_artwork": "Нельзя завершить заказ: исполнитель еще не отправил работу в бота.",
        "relay_review_started": (
            "Обе стороны нажали «{done_label}». Начат этап финальной проверки.\n"
            "{minutes} минут до окончания проверки.\n"
            "В этот период можно открыть спор. Если спор не открыт — средства автоматически уйдут исполнителю."
        ),
        "relay_review_wait": (
            "Идет финальная проверка. {minutes} минут до окончания проверки.\n"
            "Если есть проблема — откройте спор до окончания таймера."
        ),
        "relay_done_complete": (
            "Обе стороны подтвердили завершение. Заказ #{order_id} завершен.\n"
            "Отправляю архив с оригиналами без масок."
        ),
        "relay_done_archive_caption": "Архив оригиналов по заказу #{order_id} (без масок).",
        "relay_done_archive_missing": "Не удалось собрать архив: исходные файлы недоступны.",
        "relay_done_archive_sent_artist": "Заказ #{order_id}: архив всех медиа отправлен заказчику.",
        "relay_payout_customer": (
            "Escrow релиз выполнен: исполнителю отправлено {amount_usdt} USDT.\n"
            "Tx: {tx_hash}"
        ),
        "relay_payout_artist": (
            "Выплата по заказу выполнена: {amount_usdt} USDT.\n"
            "Tx: {tx_hash}"
        ),
        "relay_payout_retry_later": (
            "Автовыплата временно недоступна (проблема сети/API).\n"
            "Заказ не закрыт. Нажмите «{done_label}» позже, чтобы повторить выплату."
        ),
        "payout_auto_failed_customer": (
            "Автовыплата исполнителю не выполнена. Платеж отмечен как требующий ручной обработки админом."
        ),
        "payout_auto_failed_artist": (
            "Автовыплата не выполнена. Админ выполнит перевод вручную и отправит tx hash."
        ),
        "send_art_ask_order": "Введите ID заказа, по которому отправляете файл:",
        "order_id_must_be_number": "ID заказа должен быть числом.",
        "send_art_choose_kind": "Выберите тип отправки:",
        "send_art_unknown_kind": "Неизвестный тип",
        "send_art_upload_image": "Отправьте изображение (фото или документ-изображение).",
        "send_art_session_expired": "Сессия отправки устарела. Повторите отправку через кнопку меню.",
        "send_art_need_image": "Нужна картинка: отправьте фото или документ-изображение.",
        "send_art_order_not_yours": "Этот заказ не назначен на вас.",
        "send_art_final_only_after_pay": "Финал можно отправить только после escrow оплаты заказчиком (/pay).",
        "send_art_direct_not_available": "1:1 медиа можно отправить только по активному заказу в работе.",
        "send_art_preview_caption": (
            "Предпросмотр по заказу #{order_id}.\n"
            "Файл защищен и предназначен только для проверки до оплаты."
        ),
        "send_art_final_caption": (
            "Финальный файл по заказу #{order_id}.\n"
            "Рекомендуется дополнительно отправить оригинал в приватном чате как disappearing media (1:1)."
        ),
        "send_art_direct_caption": (
            "1:1 медиа по заказу #{order_id}.\n"
            "Файл отправлен с защитной маской."
        ),
        "send_art_preview_done": (
            "Предпросмотр отправлен заказчику.\n"
            "Дальше: заказчик подтверждает оплату escrow через /pay &lt;order_id&gt;."
        ),
        "send_art_preview_notify_customer": (
            "Заказ #{order_id}: после проверки предпросмотра используйте /pay {order_id}, "
            "затем работа передается через relay/1:1, а завершение подтверждается кнопкой «Завершить»."
        ),
        "send_art_final_done": (
            "Финал отправлен заказчику.\n"
            "Ожидайте релиз средств командой /release {order_id} от заказчика."
        ),
        "send_art_direct_done": (
            "1:1 медиа подготовлено.\n"
            "Инструкция:\n"
            "1) Скачайте изображение выше, на котором есть уникальная маска.\n"
            "2) Перейдите в чат с заказчиком ({customer_ref}).\n"
            "3) Отправьте медиафайл «на один просмотр», как показано в инструкции ниже.\n"
            "4) Скриншоты к шагу 3 отправлены ниже."
        ),
        "send_art_controls": "Дальше используйте кнопки ниже.",
        "send_art_uploaded_notify_customer": (
            "Заказ #{order_id}: исполнитель загрузил работу в бота.\n"
            "Всего загружено работ: {count}."
        ),
        "report_ask_target_username": (
            "Введите username пользователя в формате @username, на которого хотите пожаловаться."
        ),
        "report_target_username_invalid": "Некорректный формат. Пример: @artist_name",
        "report_target_self_forbidden": "Нельзя отправить жалобу на самого себя.",
        "report_ask_order_pick": "Выберите заказ, к которому относится жалоба:",
        "report_order_pick_button": "Заказ #{order_id} — {title}",
        "report_order_pick_none": "Не связано с заказом",
        "report_order_pick_invalid": "Этот заказ недоступен для выбора.",
        "report_use_buttons_for_order": "Выберите заказ кнопками ниже.",
        "report_ask_reason": (
            "Опишите проблему понятным текстом.\n"
            "Пример: «Исполнитель отправил не тот файл, и отказывается исправлять»."
        ),
        "report_reason_short": "Опишите проблему подробнее (минимум 8 символов).",
        "report_target_not_found": "Пользователь с таким username не найден в системе.",
        "report_created": "Жалоба #{report_id} создана. Администратор рассмотрит ее в течение 7 дней.",
        "search_no_results": "Исполнители не найдены.",
        "search_results_title": "Найденные исполнители:",
        "search_item": "- {nickname} | {username} | TG ID: {tg_id} | контакт: {contact}",
        "search_ask_query": "Введите запрос для поиска исполнителя (ник/username/контакт):",
        "search_query_short": "Слишком короткий запрос. Минимум 2 символа.",
        "admin_only": "Команда доступна только администратору.",
        "admin_panel_entering": "Открываю админ-панель...",
        "admin_panel_welcome": "Вы находитесь в админ-панели. Выберите раздел:",
        "admin_btn_disputes": "Открытые споры",
        "admin_btn_reports": "Жалобы",
        "admin_btn_blocks": "Блок/Разблок пользователей",
        "admin_btn_users": "БД users",
        "admin_btn_exit_panel": "Выйти из админ-панели",
        "admin_btn_back": "Назад",
        "admin_btn_prev": "Предыдущая",
        "admin_btn_next": "Следующая",
        "admin_btn_search": "Поиск пользователя",
        "admin_btn_resolve_refund": "Решение: возврат",
        "admin_btn_resolve_release": "Решение: релиз",
        "admin_btn_dispute_close": "Закрыть спор",
        "admin_btn_report_close": "Убрать жалобу",
        "admin_btn_toggle_found_user": "Блок/Разблок пользователя",
        "admin_btn_back_blocks": "К блокировкам",
        "admin_btn_back_users": "К users",
        "admin_btn_back_section": "Назад к разделу",
        "admin_btn_back_disputes": "К списку споров",
        "admin_disputes_empty": "Открытых споров сейчас нет.",
        "admin_disputes_title": "Открытые споры ({count}):",
        "admin_disputes_row": (
            "- Заказ #{order_id} | заказчик: {customer_ref} | исполнитель: {artist_ref} | {price} RUB"
        ),
        "admin_dispute_row_button": "Открыть спор #{order_id}",
        "admin_dispute_card": (
            "Спор по заказу #{order_id}\n"
            "Статус: {status}\n"
            "Заказчик: {customer_ref}\n"
            "Исполнитель: {artist_ref}\n"
            "Название: {title}\n"
            "Цена: {price} RUB\n"
            "Причина: {dispute_reason}\n"
            "Файлов исполнителя в ZIP: {assets}"
        ),
        "admin_dispute_not_open": "Этот спор уже закрыт.",
        "admin_dispute_closed": "Спор закрыт.",
        "admin_dispute_closed_text": "Спор по заказу #{order_id} закрыт без решения. Заказ возвращен в работу.",
        "admin_dispute_closed_notify": "Администратор закрыл спор по заказу #{order_id}. Заказ возвращен в работу.",
        "admin_dispute_zip_caption": "Спор #{order_id}: ZIP с медиа исполнителя ({files} файлов).",
        "admin_dispute_zip_empty": "По спору #{order_id} не найдено доступных медиа исполнителя.",
        "admin_reports_empty": "Жалоб пока нет.",
        "admin_report_not_found": "Жалоба не найдена.",
        "admin_report_closed": "Жалоба убрана.",
        "admin_reports_card": (
            "Жалоба {index}/{total}\n"
            "ID жалобы: #{report_id}\n"
            "Создана: {created_at}\n"
            "ID заказа: {order_id}\n"
            "Кто жалуется: {reporter_ref}\n"
            "На кого жалоба: {target_ref}\n"
            "Статус: {status}\n"
            "Причина:\n"
            "{reason}"
        ),
        "admin_users_empty": "В таблице users нет записей.",
        "admin_users_header": "Users ({start}-{end} из {total}):",
        "admin_users_row": "ID={user_id} | {user_ref} | роль={role} | статус={status}",
        "admin_user_active": "активен",
        "admin_user_blocked": "заблокирован",
        "admin_user_no_username": "без username",
        "admin_user_open_profile": "Открыть профиль",
        "admin_toggle_user": "{username} ({status})",
        "admin_toggle_done": "Пользователь {username}: статус обновлен -> {status}",
        "admin_search_prompt": "Введите @username или TG ID пользователя:",
        "admin_search_invalid": "Неверный формат. Введите @username или числовой TG ID.",
        "admin_user_not_found_search": "Пользователь не найден.",
        "admin_user_found_card": (
            "Пользователь найден:\n"
            "ID в БД: {user_id}\n"
            "Профиль: {user_ref}\n"
            "Роль: {role}\n"
            "Статус: {status}"
        ),
        "admin_block_reason": "Блокировка через админ-панель",
        "admin_stats": (
            "[ADMIN] Статистика\n"
            "Всего заказов: {total_orders}\n"
            "Завершено: {completed_orders}\n"
            "В спорах: {disputed_orders}\n"
            "Оборот (gross): {gross_rub} RUB"
        ),
        "admin_panel_closed": "Админ-панель закрыта.",
        "admin_panel_back_to_user": "Вы вернулись в обычное меню.",
        "usage_ban": "Использование: /ban &lt;tg_id&gt; &lt;причина&gt;",
        "usage_unban": "Использование: /unban &lt;tg_id&gt;",
        "user_not_found": "Пользователь не найден.",
        "user_banned": "Пользователь {tg_id} заблокирован.",
        "user_banned_notify": "Вы заблокированы в ArtSecure. Причина: {reason}",
        "user_unbanned": "Пользователь {tg_id} разблокирован.",
        "usage_resolve": "Использование: /resolve &lt;order_id&gt; &lt;refund|release&gt;",
        "admin_refund_customer": (
            "[ADMIN] Спор по заказу #{order_id} закрыт: возврат {amount_usdt} USDT заказчику.\n"
            "Tx: {tx_hash}"
        ),
        "admin_refund_artist": (
            "[ADMIN] Спор по заказу #{order_id} закрыт: средства возвращены заказчику ({amount_usdt} USDT).\n"
            "Tx: {tx_hash}"
        ),
        "admin_release_customer": (
            "[ADMIN] Спор по заказу #{order_id} закрыт: релиз исполнителю {payout_usdt} USDT.\n"
            "Tx: {tx_hash}"
        ),
        "admin_release_artist": (
            "[ADMIN] Спор по заказу #{order_id} закрыт: релиз средств {payout_usdt} USDT.\n"
            "Tx: {tx_hash}"
        ),
        "admin_resolve_done": "Спор по заказу #{order_id} закрыт решением: {decision}",
        "admin_payment_invoice_missing": "Внимание: у заказа #{order_id} не найден подтвержденный escrow-инвойс.",
        "nda_not_available": "NDA доступен только участникам заказа.",
        "nda_generated": "Шаблон NDA сгенерирован. Подпишите и согласуйте условия в чате.",
    },
    "en": {
        "lang_ru": "Русский",
        "lang_en": "English",
        "no_username": "no username",
        "unknown": "unknown",
        "btn_help": "🆘 Help",
        "btn_rules": "📘 Rules",
        "btn_rules_open_article": "🌐 Open Rules in Browser",
        "btn_exit": "🚪 Exit",
        "btn_cancel": "❌ Cancel",
        "btn_leave_relay": "↩️ Leave Chat",
        "btn_mark_done": "✅ Complete",
        "btn_create_order": "📝 Create Order",
        "btn_my_orders": "📂 My Orders",
        "btn_search": "🔎 Find Artist",
        "btn_report": "🚩 Report",
        "btn_send_art": "🖼️ Send Artwork",
        "btn_admin_stats": "📊 Stats",
        "btn_wallet": "💼 Wallet",
        "btn_language": "🌐 Language",
        "btn_share_username": "👤 Share username",
        "btn_pay_wallet": "Pay via Wallet",
        "btn_pay_tonkeeper": "Pay via Tonkeeper",
        "btn_invoice_status": "Check Payment",
        "btn_pay_order": "Pay order",
        "btn_topup_wallet": "Wallet top-up guide",
        "btn_open_topup": "Open top-up",
        "btn_back_payment_methods": "Back to payment methods",
        "btn_pay_other_soon": "Other methods (soon)",
        "btn_relay_open_now": "Open relay chat",
        "btn_yes": "Yes",
        "btn_no": "No",
        "btn_view_portfolio": "🎨 View portfolio",
        "btn_create_order_with_artist": "📝 Create order with this artist",
        "btn_open_profile": "🖼 Open profile",
        "portfolio_empty": "Artist has no portfolio items yet",
        "btn_profile": "👤 Profile",
        "btn_show_profile": "✅ Show profile",
        "btn_hide_profile": "❌ Hide profile",
        "btn_search_by_username": "🔍 Search by username",
        "btn_search_random": "🎲 Random search",
        "btn_take_artist": "✅ Take",
        "btn_skip_artist": "➡️ Skip",
        "profile_management_title": "Profile management",
        "profile_status_visible": "Your profile is visible to customers in automatic search",
        "profile_status_hidden": "Your profile is hidden from automatic search",
        "profile_visibility_updated": "Profile visibility updated",
        "profile_empty_owner_prompt": (
            "Looks like your profile is still empty — customers see a blank page.\n"
            "Tap «{btn_open_profile}» to add a bio and portfolio works."
        ),
        "choose_search_type": "Choose artist search method:",
        "search_type_help": "• Search by username - enter specific artist @username\n• Random search - system will automatically select available artist",
        "artist_profile_preview": (
            "Artist found:\n"
            "👤 Username: @{artist_username}\n"
            "📊 Completed orders: {completed_orders}\n"
            "⭐️ Rating: {rating}/100\n"
            "📝 Bio: {bio}"
        ),
        "artist_profile_preview_no_bio": "not specified",
        "role_customer": "🧑‍💼 Customer",
        "role_artist": "🎨 Artist",
        "role_admin": "🛡️ Admin",
        "currency_rub": "RUB",
        "currency_usd": "USD",
        "currency_usdt": "USDT",
        "order_decision_accept": "✅ Accept",
        "order_decision_reject": "✖️ Reject",
        "art_kind_preview": "Preview",
        "art_kind_final": "Final",
        "art_kind_direct": "1:1 Media",
        "order_action_paid": "💳 Pay (escrow)",
        "order_action_release": "💸 Release to Artist",
        "order_action_dispute": "⚠️ Open Dispute",
        "order_action_relay": "💬 Open Deal Chat",
        "order_action_delete": "🗑️ Delete Order",
        "dispute_reason_not_order": "❌ Wrong order",
        "dispute_reason_other": "ℹ️ Other",
        "status_pending_artist": "Waiting for artist response",
        "status_in_progress": "In progress",
        "status_preview_sent": "Preview sent",
        "status_paid_escrow": "Escrow paid",
        "status_pending_review": "Final timed review",
        "status_final_review": "Final review",
        "status_completed": "Completed",
        "status_disputed": "Disputed",
        "status_cancelled": "Cancelled",
        "err_not_registered": "Please register first via /start",
        "err_banned": "Your account is restricted by administrator.",
        "err_wrong_role": "This action is available for another role.",
        "start_welcome": (
            "Welcome to ArtSecure.\n"
            "Tonkeeper (Android): https://play.google.com/store/apps/details?id=com.ton_keeper"
        ),
        "start_choose_role": "Choose your role:",
        "start_registered": "You are already registered as {role}. Use the menu buttons below.",
        "invalid_role": "Invalid role",
        "ask_contact_username_only": (
            "Send your Telegram username in format @username.\n"
            "You can tap the button below or type it manually."
        ),
        "registration_username_required": (
            "You don't have Telegram username yet.\n"
            "Set it in Telegram settings and send it here in format @username."
        ),
        "registration_username_mismatch": (
            "Please send your own username: {username}.\n"
            "Check input and try again."
        ),
        "registration_expired": "Registration session expired. Repeat /start",
        "registration_done": "Registration completed. Role: {role}.",
        "registration_quick_guide": (
            "Quick main menu guide:\n"
            "{btn_create_order} - create a new order\n"
            "{btn_my_orders} - open your orders\n"
            "{btn_report} - send a complaint\n"
            "{btn_wallet} - set wallet address\n"
            "{btn_help} - command tips\n"
            "{btn_language} - change language\n\n"
            "Important: set wallet first, otherwise order actions are disabled.\n"
            "Tonkeeper (Android): https://play.google.com/store/apps/details?id=com.ton_keeper"
        ),
        "wallet_address_screenshot_caption": "Example where to find wallet address:",
        "help_text": (
            "Commands and buttons:\n"
            "/start - registration\n"
            "/exit - return to role selection\n"
            "{btn_create_order} / /create\n"
            "{btn_my_orders} / /my_orders\n"
            "{btn_send_art} / /send_art\n"
            "{btn_search} / /search\n"
            "{btn_report} / /report\n"
            "/relay &lt;id&gt; - secure relay chat by order\n"
            "/leave_relay - leave relay chat\n"
            "/pay &lt;id&gt; - mock escrow payment\n"
            "/invoice &lt;id&gt; - create crypto escrow invoice\n"
            "/invoice_status &lt;id&gt; - invoice status\n"
            "/set_wallet &lt;address&gt; - connect customer wallet\n"
            "/wallet - show connected wallet\n"
            "/release &lt;id&gt; - release funds to artist\n"
            "/dispute &lt;id&gt; - open dispute\n"
            "/langue - switch language\n"
            "Support: {support_chat_url}"
        ),
        "rules_link_text": "Full rules article: {rules_url}",
        "scenario_cancelled": "Current scenario canceled.",
        "exit_role_selecting": "Back to role selection.",
        "exit_role_selected": "You returned to role selection. Click a role button:",
        "language_choose": "Choose interface language:",
        "language_saved": "Language updated: {language_name}",
        "create_ask_artist": "Enter artist @username to send request, or send 'auto' for automatic selection:",
        "btn_auto_artist": "🎲 Auto select",
        "no_available_artists": "No available artists. Try again later.",
        "artist_auto_selected": "Artist auto-selected: @{artist_username}",
        "username_invalid": "Invalid username. Example: @artist_name (5-32 chars, letters/digits/_)",
        "username_not_exists": "This Telegram username does not exist.",
        "username_not_registered_artist": (
            "User exists, but is not registered in bot as artist. "
            "Ask them to run /start and pick Artist role."
        ),
        "username_check_failed": (
            "Username format is valid, but API check is unavailable now. "
            "Ask artist to start bot with /start."
        ),
        "username_not_artist_role": "This user is registered but not as artist.",
        "create_ask_title": "Enter order title:",
        "create_ask_currency": "Choose order currency:",
        "create_currency_selected": "Currency selected: {currency}",
        "currency_invalid": "Invalid currency.",
        "create_title_short": "Title is too short.",
        "create_ask_details": "Describe order details:",
        "create_details_short": "Please describe in more detail (min 5 characters).",
        "create_ask_price": "Enter price in RUB (for example 3500):",
        "create_ask_price_currency": "Enter price in {currency} (number, up to 6 decimals):",
        "price_int_only": "Price must be a number (up to 6 decimals).",
        "price_positive": "Price must be greater than zero.",
        "create_expired": "Scenario expired. Start again: /create",
        "create_user_not_found": "Unable to create order: user not found.",
        "create_only_customer": "Only customer can create order.",
        "create_done": (
            "Request #{order_id} created and sent to artist.\n"
            "Artist: @{artist_username}\n"
            "Title: {title}\n"
            "Price: {price} {currency}\n"
            "Wait for artist decision."
        ),
        "create_send_to_artist": (
            "New request #{order_id}\n"
            "From: {customer_name} (@{customer_username})\n"
            "Title: {title}\n"
            "Price: {price} {currency}"
        ),
        "create_send_to_artist_failed": "Could not send request in DM. Ask artist to run /start with bot.",
        "order_decision_invalid_format": "Invalid format",
        "order_decision_invalid_data": "Invalid data",
        "order_not_found": "Order not found.",
        "order_not_yours": "This is not your order.",
        "order_already_processed": "Order already processed",
        "order_accept_short": "Request accepted",
        "order_reject_short": "Request rejected",
        "order_rejected_message": "Request rejected.",
        "relay_activated_artist": (
            "Request #{order_id} accepted.\n"
            "Relay chat is active: send plain text messages here, they will be forwarded.\n"
            "Exit: {leave_label}"
        ),
        "relay_activated_customer": (
            "Artist accepted request #{order_id}.\n"
            "Relay chat is active: send plain text messages here, bot forwards them.\n"
            "Exit: {leave_label}"
        ),
        "order_rejected_notify_customer": "Artist rejected request #{order_id}.",
        "my_orders_empty": "You have no orders yet.",
        "my_order_card": (
            "Order #{order_id}\n"
            "Status: {status}\n"
            "Title: {title}\n"
            "Price: {price} {currency}\n"
            "Customer: {customer}\n"
            "Artist: {artist}"
        ),
        "my_orders_footer": "Your orders are listed above.",
        "usage_pay": "Usage: /pay &lt;order_id&gt;",
        "usage_invoice": "Usage: /invoice &lt;order_id&gt;",
        "usage_invoice_status": "Usage: /invoice_status &lt;invoice_id&gt;",
        "usage_mock_paid": "Usage: /mock_paid &lt;invoice_id&gt;",
        "usage_set_wallet": "Usage: /set_wallet &lt;your_wallet_address&gt;",
        "usage_release": "Usage: /release &lt;order_id&gt;",
        "usage_dispute": "Usage: /dispute &lt;order_id&gt;",
        "usage_force_close": "Usage: /force_close &lt;order_id&gt;",
        "usage_nda": "Usage: /nda &lt;order_id&gt;",
        "pay_not_your_order": "This is not your order.",
        "payment_wallet_not_configured": "Escrow wallet is not configured in .env (ESCROW_WALLET_ADDRESS).",
        "wallet_not_connected": "Connect wallet first: /set_wallet &lt;wallet_address&gt;",
        "wallet_required_before_orders": (
            "Please fill wallet via «{btn_wallet}» first.\n"
            "Until then creating and viewing orders is disabled."
        ),
        "wallet_connected": "Your wallet: {wallet_address}",
        "wallet_saved": "Wallet saved: {wallet_address}",
        "wallet_existing_prompt": (
            "Current wallet: {wallet_address}\n"
            "Keep this wallet or change it?"
        ),
        "wallet_keep_current": "✅ Keep current",
        "wallet_change_current": "✏️ Change wallet",
        "wallet_keep_done": "Current wallet was kept unchanged.",
        "wallet_payout_warning": (
            "Important: payouts and refunds for orders will be sent only to this wallet address.\n"
            "Double-check it carefully before each deal.\n"
            "Tonkeeper (Android): https://play.google.com/store/apps/details?id=com.ton_keeper\n"
            "See the example below where to find the wallet address."
        ),
        "wallet_address_invalid": "Invalid wallet address.",
        "wallet_address_not_found": "Wallet was not found in TON network. Check the address.",
        "wallet_check_unavailable": "Unable to verify wallet via TON API now. Please try again later.",
        "wallet_address_not_found_soft": (
            "Warning: TON API did not confirm this wallet yet. "
            "Address was saved, but make a small test transfer before real deal."
        ),
        "wallet_check_unavailable_soft": (
            "Warning: TON API is unavailable now. Address was saved without online verification."
        ),
        "wallet_enter_prompt": "Enter TON wallet address for transfers:",
        "wallet_not_enough_balance": "Not enough USDT in wallet. Please top up Wallet and retry.",
        "invoice_payment_menu": (
            "Order #{order_id}\n"
            "Amount: {amount_usdt} USDT\n"
            "Address: {payment_address}\n"
            "Memo: {payment_memo}\n"
            "Choose payment method below.\n"
            "Tonkeeper (Android): https://play.google.com/store/apps/details?id=com.ton_keeper"
        ),
        "invoice_method_choice": (
            "Order #{order_id}\n"
            "Amount: {amount_usdt} USDT\n"
            "Method: {method}\n"
            "Choose next step: \"Pay order\" or \"Wallet top-up guide\"."
        ),
        "pay_method_soon_notice": "This payment method will be added later.",
        "topup_wallet_instructions": (
            "Wallet Telegram top-up guide:\n"
            "1) Open Wallet.\n"
            "2) Choose top up (card/P2P Express).\n"
            "3) Add balance and return to bot.\n"
            "4) Press \"Check Payment\"."
        ),
        "topup_tonkeeper_instructions": (
            "Tonkeeper top-up guide:\n"
            "1) Install or open Tonkeeper.\n"
            "2) Top up TON/USDT using built-in options.\n"
            "3) Return to bot and choose \"Pay order\".\n"
            "4) After transfer press \"Check Payment\".\n"
            "Tonkeeper (Android): https://play.google.com/store/apps/details?id=com.ton_keeper"
        ),
        "invoice_created": (
            "Invoice #{invoice_id} for order #{order_id} created.\n"
            "Amount: {amount_usdt} USDT\n"
            "Address: {payment_address}\n"
            "Memo: {payment_memo}\n"
            "Expires at: {expires_at}\n"
            "Mode: {mode}\n"
            "Tonkeeper button is recommended (usually no fixed 1 USDT Wallet fee).\n"
            "Pay button opens Wallet, complete transfer manually with details above.\n"
            "Check status: /invoice_status {invoice_id}"
        ),
        "invoice_not_found": "Invoice not found.",
        "invoice_status_compact": (
            "Order #{order_id}\n"
            "Amount: {amount_usdt} USDT\n"
            "Payment status: {status_line}"
        ),
        "payment_status_created": "Awaiting payment",
        "payment_status_awaiting_payment": "Awaiting payment",
        "payment_status_paid_pending_confirm": "Checking",
        "payment_status_confirmed": "Paid",
        "payment_status_underpaid": "Underpaid",
        "payment_status_overpaid": "Overpaid",
        "payment_status_expired": "Expired",
        "payment_status_released": "Paid",
        "payment_status_refunded": "Refunded",
        "payment_status_cancelled": "Cancelled",
        "invoice_status_checking": "Checking payment status...",
        "invoice_paid_notify_customer": "Payment completed successfully for order #{order_id}.",
        "invoice_paid_notify_artist": "Payment completed successfully for order #{order_id}.",
        "mock_only_mode": "This command is available only in PAYMENTS_MODE=mock.",
        "mock_paid_done": (
            "MOCK payment confirmed.\n"
            "Invoice #{invoice_id}, order #{order_id}\n"
            "Tx: {tx_hash}"
        ),
        "mock_paid_notify_artist": "Order #{order_id}: escrow marked as paid (mock).",
        "pay_not_available_status": "Payment is available only for in-progress/preview orders.",
        "pay_marked_done": (
            "Escrow for order #{order_id} marked as paid.\n"
            "Artist can send 1:1 media and/or media files in relay chat.\n"
            "After work is done, both sides press \"{done_label}\" in relay chat."
        ),
        "pay_notify_artist": "Order #{order_id}: customer funded escrow with {price} RUB.",
        "release_not_available_status": "Release command is disabled. Complete order with \"{done_label}\" in relay chat.",
        "release_done": (
            "Order #{order_id} completed.\n"
            "Platform fee: {commission} RUB\n"
            "Artist payout: {payout} RUB"
        ),
        "release_notify_artist": (
            "Order #{order_id} was completed by customer.\n"
            "Mock payout: {payout} RUB, fee: {commission} RUB"
        ),
        "dispute_not_participant": "You are not a participant of this order.",
        "dispute_choose_reason": "Choose dispute reason for order #{order_id}:",
        "dispute_confirm_open": "Are you sure you want to open a dispute for order #{order_id}? The order will be temporarily paused.",
        "dispute_open_cancelled": "Dispute was not opened. The order will continue.",
        "dispute_already_under_review": "This dispute is already open and under review.",
        "dispute_opened": "Dispute for order #{order_id} opened. Admin will review within 7 days.",
        "dispute_opened_with_reason": (
            "Dispute for order #{order_id} opened. Admin will review within 7 days.\n"
            "Reason: {reason}"
        ),
        "dispute_notify_user": "Dispute opened for order #{order_id}.",
        "dispute_admin_new": (
            "[ADMIN] New dispute\n"
            "Order #{order_id}\n"
            "Customer: {customer_tg}\n"
            "Artist: {artist_tg}\n"
            "Reason: {reason}"
        ),
        "force_close_already": "Order is already closed.",
        "force_close_done": "Order #{order_id} force-closed.",
        "force_close_notify_other": "Order #{order_id} was force-closed by the other side.",
        "delete_only_customer": "Only customer can delete order.",
        "delete_order_done": "Order #{order_id} was deleted from lists.",
        "delete_order_notify_artist": "Order #{order_id} was deleted by customer and removed from your lists.",
        "delete_order_paid_confirm": (
            "Order #{order_id} is already paid ({amount_usdt} USDT in escrow).\n"
            "Delete this order and refund funds to your wallet?"
        ),
        "delete_order_paid_cancelled": "Paid order deletion was cancelled.",
        "delete_order_refund_wallet_missing": (
            "Refund is not possible: wallet is not set. "
            "Set your wallet first, then retry deletion."
        ),
        "delete_order_refund_failed": "Refund is temporarily unavailable. Order was not deleted, try again later.",
        "delete_order_refund_done": "Refund completed: {amount_usdt} USDT sent to {wallet_address}.",
        "cb_use_pay": "Use /pay &lt;id&gt;",
        "cb_use_release": "Use /release &lt;id&gt;",
        "cb_use_dispute": "Use /dispute &lt;id&gt;",
        "relay_usage": "Usage: /relay &lt;order_id&gt;",
        "relay_not_available_status": "Relay chat becomes available after artist accepts the order.",
        "relay_order_closed": "This order is already closed.",
        "relay_activated": (
            "Relay chat for order #{order_id} is active.\n"
            "Send text messages and media, bot will relay them.\n"
            "Exit: {leave_label}"
        ),
        "relay_off": "Relay chat disabled.",
        "relay_send_text_or_media": "Send a text message or media file.",
        "relay_use_leave": "Use /leave_relay to exit",
        "relay_session_expired": "Relay session expired. Use /relay &lt;order_id&gt;.",
        "relay_not_participant_anymore": "You are no longer participant of this order.",
        "relay_sender_customer": "Customer",
        "relay_sender_artist": "Artist",
        "relay_forward": "{sender_name}: {text}",
        "relay_forward_other_order": "[Relay order #{order_id}] {sender_name}: {text}",
        "relay_media_forward": "{sender_name} sent a media file.",
        "relay_media_forward_other_order": "[Relay order #{order_id}] {sender_name} sent a media file.",
        "relay_media_use_send_art": "Use the \"Send Artwork\" button to deliver the work.",
        # "relay_sent": "Message sent.",
        "relay_done_not_paid": "Completion is available only after escrow payment.",
        "relay_done_already": "You already confirmed completion for this order.",
        "relay_done_marked": "Your completion confirmation is saved.",
        "relay_done_wait_other": "Waiting for the other side confirmation.",
        "relay_done_progress": "Confirmations: customer={customer_done}, artist={artist_done}.",
        "relay_done_other_confirmed": "The other side pressed \"{done_label}\".",
        "relay_done_no_artwork": "You cannot complete order yet: artist has not uploaded work to the bot.",
        "relay_review_started": (
            "Both sides pressed \"{done_label}\". Final timed review has started.\n"
            "{minutes} minutes left until review ends.\n"
            "You can open dispute during this period. If dispute is not opened, funds are auto-released to artist."
        ),
        "relay_review_wait": (
            "Final review is active. {minutes} minutes left until it ends.\n"
            "If something is wrong, open dispute before timer ends."
        ),
        "relay_done_complete": (
            "Both sides confirmed completion. Order #{order_id} is completed.\n"
            "Sending archive with original files without watermarks."
        ),
        "relay_done_archive_caption": "Original files archive for order #{order_id} (without watermarks).",
        "relay_done_archive_missing": "Could not build archive: original files are unavailable.",
        "relay_done_archive_sent_artist": "Order #{order_id}: archive with all media was sent to customer.",
        "relay_payout_customer": (
            "Escrow released: {amount_usdt} USDT sent to artist.\n"
            "Tx: {tx_hash}"
        ),
        "relay_payout_artist": (
            "Order payout completed: {amount_usdt} USDT.\n"
            "Tx: {tx_hash}"
        ),
        "relay_payout_retry_later": (
            "Automatic payout is temporarily unavailable (network/API issue).\n"
            "Order is not closed. Press \"{done_label}\" later to retry payout."
        ),
        "payout_auto_failed_customer": (
            "Automatic payout to artist failed. Payment is marked for manual admin processing."
        ),
        "payout_auto_failed_artist": (
            "Automatic payout failed. Admin will send funds manually and share tx hash."
        ),
        "send_art_ask_order": "Enter order ID for artwork upload:",
        "order_id_must_be_number": "Order ID must be a number.",
        "send_art_choose_kind": "Choose upload type:",
        "send_art_unknown_kind": "Unknown type",
        "send_art_upload_image": "Send image (photo or image document).",
        "send_art_session_expired": "Upload session expired. Start again from menu button.",
        "send_art_need_image": "Image required: send photo or image document.",
        "send_art_order_not_yours": "This order is not assigned to you.",
        "send_art_final_only_after_pay": "Final can be sent only after escrow payment by customer (/pay).",
        "send_art_direct_not_available": "1:1 media can be sent only for active in-progress order.",
        "send_art_preview_caption": (
            "Preview for order #{order_id}.\n"
            "File is protected and intended for review before payment."
        ),
        "send_art_final_caption": (
            "Final file for order #{order_id}.\n"
            "You can additionally send original in private chat as disappearing media (1:1)."
        ),
        "send_art_direct_caption": (
            "1:1 media for order #{order_id}.\n"
            "File was sent with protective watermark."
        ),
        "send_art_preview_done": (
            "Preview sent to customer.\n"
            "Next: customer confirms escrow payment via /pay &lt;order_id&gt;."
        ),
        "send_art_preview_notify_customer": (
            "Order #{order_id}: after preview check use /pay {order_id}, "
            "then delivery goes via relay/1:1 and completion is confirmed by \"Complete\"."
        ),
        "send_art_final_done": (
            "Final sent to customer.\n"
            "Wait for /release {order_id} from customer."
        ),
        "send_art_direct_done": (
            "1:1 media prepared.\n"
            "Instruction:\n"
            "1) Download the image above with the unique watermark.\n"
            "2) Open a private chat with customer ({customer_ref}).\n"
            "3) Send the media as \"one-time view\" as shown below.\n"
            "4) Two screenshots for step 3 are sent below."
        ),
        "send_art_controls": "Use the buttons below for next actions.",
        "send_art_uploaded_notify_customer": (
            "Order #{order_id}: artist uploaded work to bot.\n"
            "Total uploaded files: {count}."
        ),
        "report_ask_target_username": "Enter user username in format @username you want to report.",
        "report_target_username_invalid": "Invalid format. Example: @artist_name",
        "report_target_self_forbidden": "You cannot send report against yourself.",
        "report_ask_order_pick": "Choose the order related to the complaint:",
        "report_order_pick_button": "Order #{order_id} - {title}",
        "report_order_pick_none": "Not related to any order",
        "report_order_pick_invalid": "This order is not available for selection.",
        "report_use_buttons_for_order": "Please choose order with buttons below.",
        "report_ask_reason": (
            "Describe issue clearly.\n"
            "Example: \"Artist sent a wrong file and refuses to fix it\"."
        ),
        "report_reason_short": "Please describe issue in more detail (min 8 characters).",
        "report_target_not_found": "User with this username was not found in system.",
        "report_created": "Report #{report_id} created. Admin will review within 7 days.",
        "search_no_results": "No artists found.",
        "search_results_title": "Found artists:",
        "search_item": "- {nickname} | {username} | TG ID: {tg_id} | contact: {contact}",
        "search_ask_query": "Enter artist search query (nickname/username/contact):",
        "search_query_short": "Query is too short. Minimum 2 characters.",
        "admin_only": "Command is available only to admin.",
        "admin_panel_entering": "Opening admin panel...",
        "admin_panel_welcome": "You are in admin panel. Choose a section:",
        "admin_btn_disputes": "Open Disputes",
        "admin_btn_reports": "Reports",
        "admin_btn_blocks": "Block/Unblock Users",
        "admin_btn_users": "Users DB",
        "admin_btn_exit_panel": "Exit Admin Panel",
        "admin_btn_back": "Back",
        "admin_btn_prev": "Previous",
        "admin_btn_next": "Next",
        "admin_btn_search": "Find User",
        "admin_btn_resolve_refund": "Decision: refund",
        "admin_btn_resolve_release": "Decision: release",
        "admin_btn_dispute_close": "Close Dispute",
        "admin_btn_report_close": "Remove Report",
        "admin_btn_toggle_found_user": "Block/Unblock User",
        "admin_btn_back_blocks": "Back to blocks",
        "admin_btn_back_users": "Back to users",
        "admin_btn_back_section": "Back to section",
        "admin_btn_back_disputes": "Back to disputes",
        "admin_disputes_empty": "No open disputes right now.",
        "admin_disputes_title": "Open disputes ({count}):",
        "admin_disputes_row": (
            "- Order #{order_id} | customer: {customer_ref} | artist: {artist_ref} | {price} RUB"
        ),
        "admin_dispute_row_button": "Open dispute #{order_id}",
        "admin_dispute_card": (
            "Dispute for order #{order_id}\n"
            "Status: {status}\n"
            "Customer: {customer_ref}\n"
            "Artist: {artist_ref}\n"
            "Title: {title}\n"
            "Price: {price} RUB\n"
            "Reason: {dispute_reason}\n"
            "Artist files in ZIP: {assets}"
        ),
        "admin_dispute_not_open": "This dispute is already closed.",
        "admin_dispute_closed": "Dispute closed.",
        "admin_dispute_closed_text": "Dispute for order #{order_id} was closed without decision. Order returned to work.",
        "admin_dispute_closed_notify": "Admin closed dispute for order #{order_id}. Order returned to work.",
        "admin_dispute_zip_caption": "Dispute #{order_id}: ZIP with artist media ({files} files).",
        "admin_dispute_zip_empty": "No available artist media was found for dispute #{order_id}.",
        "admin_reports_empty": "No reports yet.",
        "admin_report_not_found": "Report not found.",
        "admin_report_closed": "Report removed.",
        "admin_reports_card": (
            "Report {index}/{total}\n"
            "Report ID: #{report_id}\n"
            "Created at: {created_at}\n"
            "Order ID: {order_id}\n"
            "Reporter: {reporter_ref}\n"
            "Target: {target_ref}\n"
            "Status: {status}\n"
            "Reason:\n"
            "{reason}"
        ),
        "admin_users_empty": "No records in users table.",
        "admin_users_header": "Users ({start}-{end} of {total}):",
        "admin_users_row": "ID={user_id} | {user_ref} | role={role} | status={status}",
        "admin_user_active": "active",
        "admin_user_blocked": "blocked",
        "admin_user_no_username": "no username",
        "admin_user_open_profile": "Open Profile",
        "admin_toggle_user": "{username} ({status})",
        "admin_toggle_done": "User {username}: status updated -> {status}",
        "admin_search_prompt": "Enter user @username or TG ID:",
        "admin_search_invalid": "Invalid format. Enter @username or numeric TG ID.",
        "admin_user_not_found_search": "User not found.",
        "admin_user_found_card": (
            "User found:\n"
            "DB ID: {user_id}\n"
            "Profile: {user_ref}\n"
            "Role: {role}\n"
            "Status: {status}"
        ),
        "admin_block_reason": "Blocked from admin panel",
        "admin_stats": (
            "[ADMIN] Statistics\n"
            "Total orders: {total_orders}\n"
            "Completed: {completed_orders}\n"
            "Disputed: {disputed_orders}\n"
            "Gross turnover: {gross_rub} RUB"
        ),
        "admin_panel_closed": "Admin panel closed.",
        "admin_panel_back_to_user": "Returned to user menu.",
        "usage_ban": "Usage: /ban &lt;tg_id&gt; &lt;reason&gt;",
        "usage_unban": "Usage: /unban &lt;tg_id&gt;",
        "user_not_found": "User not found.",
        "user_banned": "User {tg_id} has been banned.",
        "user_banned_notify": "You are banned in ArtSecure. Reason: {reason}",
        "user_unbanned": "User {tg_id} has been unbanned.",
        "usage_resolve": "Usage: /resolve &lt;order_id&gt; &lt;refund|release&gt;",
        "admin_refund_customer": (
            "[ADMIN] Dispute for order #{order_id} closed: refund {amount_usdt} USDT to customer.\n"
            "Tx: {tx_hash}"
        ),
        "admin_refund_artist": (
            "[ADMIN] Dispute for order #{order_id} closed: funds returned to customer ({amount_usdt} USDT).\n"
            "Tx: {tx_hash}"
        ),
        "admin_release_customer": (
            "[ADMIN] Dispute for order #{order_id} closed: release {payout_usdt} USDT to artist.\n"
            "Tx: {tx_hash}"
        ),
        "admin_release_artist": (
            "[ADMIN] Dispute for order #{order_id} closed: funds released {payout_usdt} USDT.\n"
            "Tx: {tx_hash}"
        ),
        "admin_resolve_done": "Dispute for order #{order_id} resolved with decision: {decision}",
        "admin_payment_invoice_missing": "Warning: no confirmed escrow invoice was found for order #{order_id}.",
        "nda_not_available": "NDA is available only to order participants.",
        "nda_generated": "NDA template generated. Sign and agree terms in chat.",
    },
}


def normalize_language(language: str | None) -> str:
    if language in SUPPORTED_LANGUAGES:
        return str(language)
    return DEFAULT_LANGUAGE


def tr(key: str, language: str = DEFAULT_LANGUAGE, **kwargs: object) -> str:
    lang = normalize_language(language)
    template = TRANSLATIONS.get(lang, {}).get(key)
    if template is None:
        template = TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)
    if kwargs:
        safe_kwargs = {name: html.escape(str(value), quote=False) for name, value in kwargs.items()}
        return template.format(**safe_kwargs)
    return template


def variants(key: str) -> set[str]:
    values = set()
    for lang in SUPPORTED_LANGUAGES:
        value = TRANSLATIONS.get(lang, {}).get(key)
        if value:
            values.add(value)
    return values
