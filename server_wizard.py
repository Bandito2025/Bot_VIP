import re
from urllib.parse import urlparse
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def is_valid_panel_url(url_str: str) -> tuple[bool, str]:
    raw = url_str.strip()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    try:
        parsed = urlparse(raw)
        if not parsed.hostname or not parsed.port:
            return False, ""
        return True, raw
    except Exception:
        return False, ""

def extract_host_port(url_str: str) -> str:
    raw = url_str.strip()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    parsed = urlparse(raw)
    return f"{parsed.hostname}:{parsed.port}"

def render_method_choice() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "🔐 <b>Подключение сервера</b>\n\n"
        "🔑 <b>API-ключ</b> — рекомендуемый вариант для 3X-UI 3.3.0 и новее. "
        "Бот работает без входа в аккаунт панели, поэтому в панели можно оставить "
        "включённой двухфакторную аутентификацию.\n\n"
        "👤 <b>Логин и пароль</b> — бот входит в 3X-UI только для получения и восстановления "
        "собственного API-ключа. Обычные операции всё равно идут через Bearer API. "
        "При включённой двухфакторной аутентификации этот способ не работает.\n\n"
        "Выберите способ подключения:"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔑 По API-ключу", callback_data="srvwiz_mode_api"),
            InlineKeyboardButton("👤 Логин и пароль", callback_data="srvwiz_mode_login"),
        ],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="admin_servers"),
            InlineKeyboardButton("🈴 На главную", callback_data="back_to_main"),
        ]
    ])
    return text, kb

def render_wizard_step(wiz: dict, error_msg: str = "") -> tuple[str, InlineKeyboardMarkup]:
    mode = wiz.get("mode", "api")
    total = 4 if mode == "api" else 5
    step = wiz.get("step", 1)

    err_block = f"{error_msg}\n\n" if error_msg else ""
    name_val = wiz.get("name", "")
    url_val = wiz.get("url", "")
    grp_val = wiz.get("group_label", "Все inbound’ы")
    login_val = wiz.get("login", "")

    if step == 1:
        text = (
            f"📝 <b>Добавление сервера ({step}/{total})</b>\n\n"
            f"{err_block}"
            "Введите <b>название</b>:\n"
            "<i>(например: Server-DE, Германия-1)</i>"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="srvwiz_cancel")]])
        return text, kb

    if step == 2:
        text = (
            f"📝 <b>Добавление сервера ({step}/{total})</b>\n\n"
            f"{err_block}"
            f"✅ Название: <code>{name_val}</code>\n\n"
            "Введите <b>url панели</b>:\n"
            "<i>(например: https://192.168.1.1:2053/secretpath/ или просто 192.168.1.1:2053)</i>"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Назад", callback_data="srvwiz_back"),
            InlineKeyboardButton("❌ Отмена", callback_data="srvwiz_cancel"),
        ]])
        return text, kb

    if step == 3:
        text = (
            f"🧩 <b>Виртуальная группа inbound’ов ({step}/{total})</b>\n\n"
            f"{err_block}"
            f"✅ Название: <code>{name_val}</code>\n"
            f"✅ URL панели: <code>{url_val}</code>\n\n"
            "Она позволяет разделить одну 3x-ui панель на несколько виртуальных серверов. "
            "В 3x-ui откройте: Inbounds → изменить подключение → «Расширенный шаблон» → «Всё» → "
            "поле <code>\"tag\"</code> и добавьте в конец существующего tag маркер <code>--1</code>, "
            "<code>--2</code> и т. д. Один inbound может иметь несколько маркеров, например "
            "<code>--1--2</code>.\n\n"
            "Здесь отправьте только номер без <code>--</code>, например <code>1</code> или <code>2</code>. "
            "Если разделение не нужно, нажмите «⏭ Пропустить» — сервер будет использовать все inbound’ы."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Пропустить", callback_data="srvwiz_skip_group")],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="srvwiz_back"),
                InlineKeyboardButton("❌ Отмена", callback_data="srvwiz_cancel"),
            ]
        ])
        return text, kb

    if step == 4 and mode == "api":
        text = (
            f"📝 <b>Добавление сервера ({step}/{total})</b>\n\n"
            f"{err_block}"
            f"✅ Название: <code>{name_val}</code>\n"
            f"✅ URL панели: <code>{url_val}</code>\n"
            f"✅ Виртуальная inbound-группа: <code>{grp_val}</code>\n\n"
            "Введите <b>api-ключ</b>:\n"
            "<i>(создайте отдельный токен в настройках безопасности 3X-UI и отправьте его сюда)</i>"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Назад", callback_data="srvwiz_back"),
            InlineKeyboardButton("❌ Отмена", callback_data="srvwiz_cancel"),
        ]])
        return text, kb

    if step == 4 and mode == "login":
        text = (
            f"📝 <b>Добавление сервера ({step}/{total})</b>\n\n"
            f"{err_block}"
            f"✅ Название: <code>{name_val}</code>\n"
            f"✅ URL панели: <code>{url_val}</code>\n"
            f"✅ Виртуальная inbound-группа: <code>{grp_val}</code>\n\n"
            "Введите <b>логин</b>:\n"
            "<i>(логин для входа в панель)</i>"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Назад", callback_data="srvwiz_back"),
            InlineKeyboardButton("❌ Отмена", callback_data="srvwiz_cancel"),
        ]])
        return text, kb

    if step == 5 and mode == "login":
        text = (
            f"📝 <b>Добавление сервера ({step}/{total})</b>\n\n"
            f"{err_block}"
            f"✅ Название: <code>{name_val}</code>\n"
            f"✅ URL панели: <code>{url_val}</code>\n"
            f"✅ Виртуальная inbound-группа: <code>{grp_val}</code>\n"
            f"✅ Логин: <code>{login_val}</code>\n\n"
            "Введите <b>пароль</b>:\n"
            "<i>(пароль для входа в панель)</i>"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Назад", callback_data="srvwiz_back"),
            InlineKeyboardButton("❌ Отмена", callback_data="srvwiz_cancel"),
        ]])
        return text, kb

    return render_method_choice()
