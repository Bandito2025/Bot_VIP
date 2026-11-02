import os
import sqlite3
import json
import html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest

MAX_EXTRA_ADMINS = 2
MAX_MODERATORS = 3

PERMISSIONS_META = {
    "users": ("👥 Пользователи и Ключи", "Просмотр базы, выдача/удаление ключей"),
    "marketing": ("📣 Маркетинг и Промо", "Рассылки, купоны и промокоды"),
    "servers": ("🖥 Сервера 3X-UI", "Мониторинг и управление нодами"),
    "payments": ("💳 Касса и Тарифы", "Редактирование тарифов и статистика оплат"),
    "settings": ("⚙️ Настройки бота", "Глобальные параметры, тексты и расширения")
}

DEFAULT_PERMS = {
    "admin": {"users": True, "marketing": True, "servers": True, "payments": True, "settings": True},
    "moderator": {"users": True, "marketing": True, "servers": False, "payments": False, "settings": False}
}

SECTION_PERM_MAP = {
    "users": ("admin_users", "admin_user_", "admin_key_"),
    "marketing": ("admin_marketing", "admin_promo", "admin_coupon", "admin_broadcast"),
    "servers": ("admin_servers", "admin_srv"),
    "payments": ("admin_payments", "admin_tariff"),
    "settings": ("admin_settings", "admin_ext", "admin_notif")
}

def init_staff_db(db_path: str):
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_staff (
                user_id INTEGER PRIMARY KEY,
                role TEXT NOT NULL,
                label TEXT DEFAULT '',
                perms TEXT DEFAULT '{}',
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(bot_staff);").fetchall()]
        if "perms" not in cols:
            conn.execute("ALTER TABLE bot_staff ADD COLUMN perms TEXT DEFAULT '{}';")
        conn.commit()

def is_pro_edition(get_setting_fn) -> bool:
    if os.path.exists("/opt/Bot_VIP/.pro_unlocked"):
        return True
    try:
        tier = str(get_setting_fn("bot_edition_tier", "free")).lower().strip()
        lic = str(get_setting_fn("bot_license_key", "")).strip()
        if tier in ("pro", "vip", "full", "business") or lic.startswith("LIC-BOT-"):
            return True
    except Exception:
        pass
    return False

def get_staff_list(db_path: str, role: str = None):
    init_staff_db(db_path)
    with sqlite3.connect(db_path) as conn:
        if role:
            cur = conn.execute("SELECT user_id, role, label, perms FROM bot_staff WHERE role = ? ORDER BY added_at ASC", (role,))
        else:
            cur = conn.execute("SELECT user_id, role, label, perms FROM bot_staff ORDER BY role ASC, added_at ASC")
        return cur.fetchall()

def get_staff_member(db_path: str, user_id: int):
    init_staff_db(db_path)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT user_id, role, label, perms FROM bot_staff WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return None
    uid, role, label, perms_raw = row
    base = DEFAULT_PERMS.get(role, DEFAULT_PERMS["moderator"]).copy()
    try:
        saved = json.loads(perms_raw or "{}")
        if isinstance(saved, dict):
            base.update(saved)
    except Exception:
        pass
    return {"user_id": uid, "role": role, "label": label, "perms": base}

def get_user_role(db_path: str, user_id: int, owner_id: int, get_setting_fn=None) -> str:
    if user_id == owner_id:
        return "owner"
    if get_setting_fn and not is_pro_edition(get_setting_fn):
        return "user"
    member = get_staff_member(db_path, user_id)
    return member["role"] if member else "user"

def check_staff_permission(db_path: str, user_id: int, owner_id: int, callback_data: str, get_setting_fn=None) -> tuple[bool, str]:
    if user_id == owner_id:
        return True, ""
    if get_setting_fn and not is_pro_edition(get_setting_fn):
        return False, "⛔ Доступ запрещён."

    member = get_staff_member(db_path, user_id)
    if not member:
        return False, "⛔ Доступ запрещён."

    if callback_data.startswith(("admin_staff_", "admin_pay_cfg_", "admin_pay_inp_", "admin_pay_toggle_")):
        return False, "⛔ Изменять реквизиты шлюзов и состав команды может только Главный Владелец."

    perms = member["perms"]
    for perm_key, prefixes in SECTION_PERM_MAP.items():
        if callback_data.startswith(prefixes):
            if not perms.get(perm_key, False):
                title = PERMISSIONS_META[perm_key][0]
                return False, f"⛔ У вас отключено право доступа к разделу «{title}»."
            return True, ""

    return True, ""

def add_staff_member(db_path: str, user_id: int, role: str, label: str = "") -> tuple[bool, str]:
    init_staff_db(db_path)
    current = get_staff_list(db_path, role)
    limit = MAX_EXTRA_ADMINS if role == "admin" else MAX_MODERATORS
    if len(current) >= limit and not any(r[0] == user_id for r in current):
        role_title = "Администраторов" if role == "admin" else "Модераторов"
        return False, f"⚠️ Достигнут лимит {role_title} (максимум {limit})."

    default_p = json.dumps(DEFAULT_PERMS.get(role, DEFAULT_PERMS["moderator"]))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO bot_staff (user_id, role, label, perms) VALUES (?, ?, ?, ?)",
            (user_id, role, label.strip()[:32], default_p)
        )
        conn.commit()
    return True, "✅ Сотрудник добавлен!"

def toggle_staff_perm(db_path: str, user_id: int, perm_key: str) -> bool:
    member = get_staff_member(db_path, user_id)
    if not member or perm_key not in PERMISSIONS_META:
        return False
    perms = member["perms"]
    perms[perm_key] = not perms.get(perm_key, False)
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE bot_staff SET perms = ? WHERE user_id = ?", (json.dumps(perms), user_id))
        conn.commit()
    return perms[perm_key]

def switch_staff_role(db_path: str, user_id: int) -> tuple[bool, str]:
    member = get_staff_member(db_path, user_id)
    if not member:
        return False, "Сотрудник не найден"
    new_role = "moderator" if member["role"] == "admin" else "admin"
    current = get_staff_list(db_path, new_role)
    limit = MAX_EXTRA_ADMINS if new_role == "admin" else MAX_MODERATORS
    if len(current) >= limit:
        return False, f"⚠️ Нет свободных слотов для роли"
    new_perms = json.dumps(DEFAULT_PERMS[new_role])
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE bot_staff SET role = ?, perms = ? WHERE user_id = ?", (new_role, new_perms, user_id))
        conn.commit()
    return True, f"Роль изменена"

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
            "🔒 <b>Управление персоналом и правами</b>\n"
            "━━━━━━━━━━━━━━\n"
            "⚠️ <b>Функция закрыта во FREE-версии бота!</b>\n\n"
            "В полной <b>PRO / VIP версии</b> вам доступны:\n"
            f"• 👔 До {MAX_EXTRA_ADMINS} Администраторов\n"
            f"• 🛡 До {MAX_MODERATORS} Модераторов\n\n"
            "💎 <i>Активируйте PRO-лицензию для разблокировки.</i>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 Активировать PRO (Владелец)", callback_data="admin_staff_toggle_tier")],
            [InlineKeyboardButton("🔑 Ввести ключ PRO-лицензии", callback_data="admin_staff_enter_lic")],
            [InlineKeyboardButton("⬅️ Назад в админ-панель", callback_data="admin_back_main")]
        ])
        return text, kb

    lines = [
        "👥 <b>Персонал и Права доступа [PRO]</b>",
        "━━━━━━━━━━━━━━",
        f"👑 <b>Владелец:</b> <code>{owner_id}</code>\n",
        f"👔 <b>Администраторы ({len(admins)}/{MAX_EXTRA_ADMINS}):</b>"
    ]
    for uid, _, lbl, _ in admins:
        note = f" — {html.escape(lbl)}" if lbl else ""
        lines.append(f"  • <code>{uid}</code>{note}")

    lines.append(f"\n🛡 <b>Модераторы ({len(mods)}/{MAX_MODERATORS}):</b>")
    for uid, _, lbl, _ in mods:
        note = f" — {html.escape(lbl)}" if lbl else ""
        lines.append(f"  • <code>{uid}</code>{note}")

    buttons = []
    for uid, _, lbl, _ in admins:
        name_btn = f"{lbl} ({uid})" if lbl else f"ID {uid}"
        buttons.append([InlineKeyboardButton(f"👔 Админ: {name_btn} ⚙️ Права", callback_data=f"admin_staff_cfg_{uid}")])

    for uid, _, lbl, _ in mods:
        name_btn = f"{lbl} ({uid})" if lbl else f"ID {uid}"
        buttons.append([InlineKeyboardButton(f"🛡 Модер: {name_btn} ⚙️ Права", callback_data=f"admin_staff_cfg_{uid}")])

    add_row = []
    if len(admins) < MAX_EXTRA_ADMINS:
        add_row.append(InlineKeyboardButton(f"➕ Админ", callback_data="admin_staff_add_admin"))
    if len(mods) < MAX_MODERATORS:
        add_row.append(InlineKeyboardButton(f"➕ Модератор", callback_data="admin_staff_add_mod"))
    if add_row:
        buttons.append(add_row)

    buttons.append([InlineKeyboardButton("🔒 Переключить в FREE-режим", callback_data="admin_staff_toggle_tier")])
    buttons.append([InlineKeyboardButton("⬅️ Назад в админ-панель", callback_data="admin_back_main")])

    return "\n".join(lines), InlineKeyboardMarkup(buttons)

def render_member_permissions_card(db_path: str, target_uid: int):
    member = get_staff_member(db_path, target_uid)
    if not member:
        return "❌ Сотрудник не найден.", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="admin_staff_menu")]])

    role_badge = "👔 Администратор" if member["role"] == "admin" else "🛡 Модератор"
    perms = member["perms"]

    lines = [
        f"🎛 <b>Настройка прав сотрудника</b>",
        "━━━━━━━━━━━━━━",
        f"👤 <b>ID:</b> <code>{target_uid}</code>",
        f"🔰 <b>Роль:</b> {role_badge}\n"
    ]

    buttons = []
    for p_key, (p_title, p_desc) in PERMISSIONS_META.items():
        is_on = perms.get(p_key, False)
        status_icon = "🟢 Вкл" if is_on else "🔴 Выкл"
        lines.append(f"• {p_title}: <b>{status_icon}</b>")
        buttons.append([
            InlineKeyboardButton(
                f"{'🟢' if is_on else '🔴'} {p_title}",
                callback_data=f"admin_staff_perm_{target_uid}_{p_key}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("🔄 Сменить роль", callback_data=f"admin_staff_role_{target_uid}"),
        InlineKeyboardButton("🗑 Удалить", callback_data=f"admin_staff_del_{target_uid}")
    ])
    buttons.append([InlineKeyboardButton("⬅️ К списку персонала", callback_data="admin_staff_menu")])

    return "\n".join(lines), InlineKeyboardMarkup(buttons)

async def safe_edit(query, text, reply_markup=None, parse_mode="HTML"):
    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
    except BadRequest as e:
        if "Message is not modified" in str(e):
            await query.answer("Уже актуально 👌")
        else:
            raise

async def handle_staff_callback(query, context, db_path: str, owner_id: int, get_setting_fn, set_setting_fn) -> bool:
    data = query.data or ""
    if not data.startswith("admin_staff_"):
        return False

    if query.from_user.id != owner_id:
        await query.answer("⛔ Доступно только Владельцу.", show_alert=True)
        return True

    if data == "admin_staff_menu":
        text, kb = render_staff_menu(db_path, owner_id, get_setting_fn)
        await safe_edit(query, text, kb)
        return True

    if data == "admin_staff_toggle_tier":
        curr = is_pro_edition(get_setting_fn)
        if curr:
            if os.path.exists("/opt/Bot_VIP/.pro_unlocked"):
                os.remove("/opt/Bot_VIP/.pro_unlocked")
            set_setting_fn("bot_edition_tier", "free")
            await query.answer("🔒 Включен режим FREE (тест замка)", show_alert=True)
        else:
            with open("/opt/Bot_VIP/.pro_unlocked", "w") as f:
                f.write("PRO_ACTIVE=1\n")
            set_setting_fn("bot_edition_tier", "pro")
            await query.answer("💎 PRO-версия активирована!", show_alert=True)
        text, kb = render_staff_menu(db_path, owner_id, get_setting_fn)
        await safe_edit(query, text, kb)
        return True

    if data == "admin_staff_enter_lic":
        context.user_data["staff_input_mode"] = "activate_pro"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Отмена", callback_data="admin_staff_menu")]])
        await safe_edit(query, "🔑 Отправьте кодовое слово <b>PRO</b>:", kb)
        return True

    if not is_pro_edition(get_setting_fn):
        await query.answer("🔒 Функция заблокирована во FREE-версии!", show_alert=True)
        return True

    if data.startswith("admin_staff_cfg_"):
        target_uid = int(data.replace("admin_staff_cfg_", ""))
        text, kb = render_member_permissions_card(db_path, target_uid)
        await safe_edit(query, text, kb)
        return True

    if data.startswith("admin_staff_perm_"):
        rest = data.replace("admin_staff_perm_", "")
        uid_str, perm_key = rest.split("_", 1)
        target_uid = int(uid_str)
        toggle_staff_perm(db_path, target_uid, perm_key)
        await query.answer("Сохранено")
        text, kb = render_member_permissions_card(db_path, target_uid)
        await safe_edit(query, text, kb)
        return True

    if data.startswith("admin_staff_role_"):
        target_uid = int(data.replace("admin_staff_role_", ""))
        switch_staff_role(db_path, target_uid)
        await query.answer("Роль изменена")
        text, kb = render_member_permissions_card(db_path, target_uid)
        await safe_edit(query, text, kb)
        return True

    if data in ("admin_staff_add_admin", "admin_staff_add_mod"):
        role = "admin" if data.endswith("_admin") else "moderator"
        context.user_data["staff_input_mode"] = f"add_{role}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Отмена", callback_data="admin_staff_menu")]])
        await safe_edit(query, "👤 Отправьте в чат <b>Telegram ID</b> сотрудника:", kb)
        return True

    if data.startswith("admin_staff_del_"):
        target_id = int(data.replace("admin_staff_del_", ""))
        remove_staff_member(db_path, target_id)
        await query.answer("Удалено", show_alert=True)
        text, kb = render_staff_menu(db_path, owner_id, get_setting_fn)
        await safe_edit(query, text, kb)
        return True

    return False

async def handle_staff_text_input(update, context, db_path: str, owner_id: int, get_setting_fn, set_setting_fn) -> bool:
    mode = context.user_data.get("staff_input_mode")
    if not mode or update.effective_user.id != owner_id:
        return False

    raw = (update.message.text or "").strip()
    kb_back = InlineKeyboardMarkup([[InlineKeyboardButton("👥 К персоналу", callback_data="admin_staff_menu")]])

    if mode == "activate_pro":
        context.user_data.pop("staff_input_mode", None)
        if raw.upper() == "PRO" or raw.startswith("LIC-BOT-"):
            set_setting_fn("bot_edition_tier", "pro")
            await update.message.reply_text("🎉 <b>PRO-версия активирована!</b>", parse_mode="HTML", reply_markup=kb_back)
        else:
            await update.message.reply_text("❌ Неверный ключ.", parse_mode="HTML", reply_markup=kb_back)
        return True

    if mode in ("add_admin", "add_moderator"):
        parts = raw.split(maxsplit=1)
        if not parts or not parts[0].isdigit():
            await update.message.reply_text("⚠️ Введите числовой Telegram ID.", parse_mode="HTML", reply_markup=kb_back)
            return True

        target_uid = int(parts[0])
        label = parts[1] if len(parts) > 1 else ""
        role = "admin" if mode == "add_admin" else "moderator"

        context.user_data.pop("staff_input_mode", None)
        ok, msg = add_staff_member(db_path, target_uid, role, label)
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=kb_back)
        return True

    return False


def render_pro_locked_screen(section_title: str):
    text = (
        f"🔒 <b>Раздел «{section_title}» доступен только в PRO-версии!</b>\n"
        "━━━━━━━━━━━━━━\n"
        "⚠️ Вы используете базовую <b>FREE-версию</b> бота.\n\n"
        "💎 <b>Что открывает PRO / VIP лицензия:</b>\n"
        "• 👥 <b>Персонал (2 Адм / 3 Мод)</b> — командная работа и тумблеры прав\n"
        "• 📣 <b>Маркетинг и Промо</b> — массовые рассылки, купоны и промокоды\n"
        "• 🧩 <b>PRO-Расширения</b> — анти-бан зеркала, возврат брошенных корзин, AI-агент\n"
        "• 🔔 <b>Гибкие уведомления</b> — тонкая настройка оповещений в реальном времени\n\n"
        "<i>Активируйте лицензионный ключ, чтобы снять все ограничения:</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 Ввести ключ PRO-лицензии", callback_data="admin_staff_enter_lic")],
        [InlineKeyboardButton("💎 Активировать PRO (Тест владельца)", callback_data="admin_staff_toggle_tier")],
        [InlineKeyboardButton("⬅️ Назад в админ-панель", callback_data="admin_back_main")]
    ])
    return text, kb
