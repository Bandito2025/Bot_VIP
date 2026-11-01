import sqlite3
import html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

MAX_EXTRA_ADMINS = 2
MAX_MODERATORS = 3

# Разделы callback_data, которые запрещены модераторам (доступны только Админам)
MODERATOR_RESTRICTED_PREFIXES = (
    "admin_pay_",
    "admin_gw_",
    "admin_srv_del",
    "admin_staff_",
    "admin_settings_global",
    "admin_backup"
)

def init_staff_db(db_path: str):
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_staff (
                user_id INTEGER PRIMARY KEY,
                role TEXT NOT NULL, -- 'admin' (макс 2) или 'moderator' (макс 3)
                label TEXT DEFAULT '',
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()

def is_pro_edition(get_setting_fn) -> bool:
    """Проверяет, активирована ли PRO/VIP версия бота (не Free)."""
    tier = str(get_setting_fn("bot_edition_tier", "free")).lower().strip()
    lic = str(get_setting_fn("bot_license_key", "")).strip()
    if tier in ("pro", "vip", "full", "business") or lic.startswith("LIC-BOT-"):
        return True
    return False

def get_staff_list(db_path: str, role: str = None):
    init_staff_db(db_path)
    with sqlite3.connect(db_path) as conn:
        if role:
            cur = conn.execute("SELECT user_id, role, label FROM bot_staff WHERE role = ? ORDER BY added_at ASC", (role,))
        else:
            cur = conn.execute("SELECT user_id, role, label FROM bot_staff ORDER BY role ASC, added_at ASC")
        return cur.fetchall()

def get_user_role(db_path: str, user_id: int, owner_id: int, get_setting_fn=None) -> str:
    """Возвращает 'owner', 'admin', 'moderator' или 'user'."""
    if user_id == owner_id:
        return "owner"
    if get_setting_fn and not is_pro_edition(get_setting_fn):
        return "user"
    init_staff_db(db_path)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT role FROM bot_staff WHERE user_id = ?", (user_id,)).fetchone()
        return row[0] if row else "user"

def add_staff_member(db_path: str, user_id: int, role: str, label: str = "") -> tuple[bool, str]:
    init_staff_db(db_path)
    current = get_staff_list(db_path, role)
    limit = MAX_EXTRA_ADMINS if role == "admin" else MAX_MODERATORS
    if len(current) >= limit and not any(r[0] == user_id for r in current):
        role_title = "Администраторов" if role == "admin" else "Модераторов"
        return False, f"⚠️ Достигнут лимит {role_title} (максимум {limit})."
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO bot_staff (user_id, role, label) VALUES (?, ?, ?)",
            (user_id, role, label.strip()[:32])
        )
        conn.commit()
    return True, "✅ Сотрудник успешно добавлен!"

def remove_staff_member(db_path: str, user_id: int):
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM bot_staff WHERE user_id = ?", (user_id,))
        conn.commit()

def render_staff_menu(db_path: str, owner_id: int, get_setting_fn):
    pro_active = is_pro_edition(get_setting_fn)
    admins = get_staff_list(db_path, "admin")
    mods = get_staff_list(db_path, "moderator")

    if not pro_active:
        text = (
            "🔒 <b>Управление персоналом (Админы и Модераторы)</b>\n"
            "━━━━━━━━━━━━━━\n"
            "⚠️ <b>Функция недоступна во FREE-версии бота!</b>\n\n"
            "В полной <b>PRO / VIP версии</b> вы получаете:\n"
            f"• 👑 До <b>{MAX_EXTRA_ADMINS} доп. Администраторов</b> (полное управление панелью)\n"
            f"• 🛡 До <b>{MAX_MODERATORS} Модераторов поддержки</b> (выдача ключей и работа с клиентами без доступа к вашей кассе и токенам)\n\n"
            "💎 <i>Активируйте PRO-лицензию, чтобы разблокировать командную работу.</i>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔑 Ввести ключ PRO-лицензии", callback_data="admin_staff_enter_lic")],
            [InlineKeyboardButton("⬅️ Назад в админ-панель", callback_data="admin_back_main")]
        ])
        return text, kb

    lines = [
        "👥 <b>Управление персоналом и ролями [PRO]</b>",
        "━━━━━━━━━━━━━━",
        f"👑 <b>Главный владелец:</b> <code>{owner_id}</code>\n",
        f"👔 <b>Доп. Администраторы ({len(admins)}/{MAX_EXTRA_ADMINS}):</b>"
    ]
    if admins:
        for uid, _, lbl in admins:
            note = f" ({html.escape(lbl)})" if lbl else ""
            lines.append(f"  • ID <code>{uid}</code>{note}")
    else:
        lines.append("  • <i>Слоты свободны</i>")

    lines.append(f"\n🛡 <b>Модераторы поддержки ({len(mods)}/{MAX_MODERATORS}):</b>")
    if mods:
        for uid, _, lbl in mods:
            note = f" ({html.escape(lbl)})" if lbl else ""
            lines.append(f"  • ID <code>{uid}</code>{note}")
    else:
        lines.append("  • <i>Слоты свободны</i>")

    lines.append(
        "\nℹ️ <i>Модераторы могут управлять ключами клиентов, но не имеют доступа к настройкам кассы и удалению серверов.</i>"
    )

    buttons = []
    if len(admins) < MAX_EXTRA_ADMINS:
        buttons.append([InlineKeyboardButton(f"➕ Добавить Админа ({len(admins)}/{MAX_EXTRA_ADMINS})", callback_data="admin_staff_add_admin")])
    if len(mods) < MAX_MODERATORS:
        buttons.append([InlineKeyboardButton(f"➕ Добавить Модератора ({len(mods)}/{MAX_MODERATORS})", callback_data="admin_staff_add_mod")])

    for uid, _, lbl in admins:
        buttons.append([InlineKeyboardButton(f"❌ Удалить Админа {uid}", callback_data=f"admin_staff_del_{uid}")])
    for uid, _, lbl in mods:
        buttons.append([InlineKeyboardButton(f"❌ Удалить Модератора {uid}", callback_data=f"admin_staff_del_{uid}")])

    buttons.append([InlineKeyboardButton("🔄 Переключить в FREE-режим (тест замка)", callback_data="admin_staff_toggle_tier")])
    buttons.append([InlineKeyboardButton("⬅️ Назад в админ-панель", callback_data="admin_back_main")])

    return "\n".join(lines), InlineKeyboardMarkup(buttons)

async def handle_staff_callback(query, context, db_path: str, owner_id: int, get_setting_fn, set_setting_fn) -> bool:
    data = query.data or ""
    if not data.startswith("admin_staff_"):
        return False

    user_id = query.from_user.id
    if user_id != owner_id:
        await query.answer("⛔ Управлять составом команды может только Главный Владелец бота.", show_alert=True)
        return True

    if data == "admin_staff_menu":
        text, kb = render_staff_menu(db_path, owner_id, get_setting_fn)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        return True

    if data == "admin_staff_toggle_tier":
        curr = is_pro_edition(get_setting_fn)
        set_setting_fn("bot_edition_tier", "free" if curr else "pro")
        status_msg = "🔒 Включен режим FREE (раздел заблокирован)" if curr else "💎 Включен режим PRO (раздел разблокирован)"
        await query.answer(status_msg, show_alert=True)
        text, kb = render_staff_menu(db_path, owner_id, get_setting_fn)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        return True

    if data == "admin_staff_enter_lic":
        context.user_data["staff_input_mode"] = "activate_pro"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Отмена", callback_data="admin_staff_menu")]])
        await query.edit_message_text(
            "🔑 <b>Активация PRO-режима</b>\n\n"
            "Отправьте в чат ваш лицензионный ключ (формата <code>LIC-BOT-...</code>) или кодовое слово <code>PRO</code> (для теста владельцем):",
            parse_mode="HTML",
            reply_markup=kb
        )
        return True

    if not is_pro_edition(get_setting_fn):
        await query.answer("🔒 Эта функция заблокирована во FREE-версии бота!", show_alert=True)
        return True

    if data in ("admin_staff_add_admin", "admin_staff_add_mod"):
        role = "admin" if data.endswith("_admin") else "moderator"
        role_title = "Администратора (макс. 2)" if role == "admin" else "Модератора (макс. 3)"
        context.user_data["staff_input_mode"] = f"add_{role}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Отмена", callback_data="admin_staff_menu")]])
        await query.edit_message_text(
            f"👤 <b>Добавление {role_title}</b>\n\n"
            "Отправьте в чат <b>Telegram ID</b> пользователя (и через пробел имя/заметку, по желанию).\n"
            "Например: <code>123456789 Иван Саппорт</code>",
            parse_mode="HTML",
            reply_markup=kb
        )
        return True

    if data.startswith("admin_staff_del_"):
        target_id = int(data.replace("admin_staff_del_", ""))
        remove_staff_member(db_path, target_id)
        await query.answer(f"🗑 Сотрудник {target_id} удален", show_alert=True)
        text, kb = render_staff_menu(db_path, owner_id, get_setting_fn)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        return True

    return False

async def handle_staff_text_input(update, context, db_path: str, owner_id: int, get_setting_fn, set_setting_fn) -> bool:
    mode = context.user_data.get("staff_input_mode")
    if not mode or update.effective_user.id != owner_id:
        return False

    raw = (update.message.text or "").strip()
    kb_back = InlineKeyboardMarkup([[InlineKeyboardButton("👥 К управлению персоналом", callback_data="admin_staff_menu")]])

    if mode == "activate_pro":
        context.user_data.pop("staff_input_mode", None)
        if raw.upper() == "PRO" or raw.startswith("LIC-BOT-"):
            set_setting_fn("bot_edition_tier", "pro")
            await update.message.reply_text("🎉 <b>PRO-версия успешно активирована!</b>\nТеперь вам доступно добавление 2 Админов и 3 Модераторов.", parse_mode="HTML", reply_markup=kb_back)
        else:
            await update.message.reply_text("❌ Неверный ключ лицензии. Раздел остается закрытым во FREE-версии.", parse_mode="HTML", reply_markup=kb_back)
        return True

    if mode in ("add_admin", "add_moderator"):
        parts = raw.split(maxsplit=1)
        if not parts or not parts[0].isdigit():
            await update.message.reply_text("⚠️ Укажите числовой Telegram ID первым словом (например: <code>987654321 Алекс</code>).", parse_mode="HTML", reply_markup=kb_back)
            return True

        target_uid = int(parts[0])
        label = parts[1] if len(parts) > 1 else ""
        role = "admin" if mode == "add_admin" else "moderator"

        context.user_data.pop("staff_input_mode", None)
        ok, msg = add_staff_member(db_path, target_uid, role, label)
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=kb_back)
        return True

    return False
