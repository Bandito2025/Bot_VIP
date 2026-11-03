import os, re, sqlite3, asyncio
from telegram import Bot, BotCommand, MenuButtonCommands

db_path = "/opt/Bot_VIP/bot_data.db"
bot_path = "/opt/Bot_VIP/bot.py"
env_path = "/opt/Bot_VIP/.env"

# 1. Подготовка БД: колонки и тарифы со скриншота
with sqlite3.connect(db_path) as conn:
    for sql in [
        "ALTER TABLE users ADD COLUMN balance INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN ref_coeff REAL DEFAULT 1.0",
        "ALTER TABLE user_keys ADD COLUMN limit_ip INTEGER DEFAULT 1",
        "ALTER TABLE user_keys ADD COLUMN group_name TEXT DEFAULT 'Основная'",
        "ALTER TABLE user_keys ADD COLUMN history_log TEXT DEFAULT ''",
    ]:
        try:
            conn.execute(sql)
        except Exception:
            pass

    # Проверяем наличие тарифов; если таблица пустая — заполняем тарифами со скриншота
    cnt = conn.execute("SELECT COUNT(*) FROM tariffs").fetchone()[0]
    if cnt == 0:
        tariffs_data = [
            ("Основная", "📱 30 Дней 1 Устр.", 30, 200, 100),
            ("Основная", "📱 60 Дней 1 Устр.", 60, 350, 175),
            ("Основная", "📱 90 Дней 1 Устр.", 90, 500, 250),
            ("Основная", "📱 180 Дней 1 Устр.", 180, 999, 500),
            ("Основная", "📱 365 Дней 1 Устр.", 365, 1799, 900),
            ("Основная", "📱 Акция 30дней 2Устроиства", 30, 150, 75),
            ("Основная", "📱 Акция 60дней 2Устроиства", 60, 250, 125),
        ]
        for g_name, name, days, rub, stars in tariffs_data:
            conn.execute(
                "INSERT INTO tariffs (group_name, name, days, price_rub, price_stars, is_active) VALUES (?, ?, ?, ?, ?, 1)",
                (g_name, name, days, rub, stars)
            )

    default_main_text = (
        "🔐 <b>Добро пожаловать в VPN-бот!</b>\n\n"
        "Быстрый, безопасный и анонимный доступ к интернету.\n"
        "Без логов, без ограничений, без проблем! 🚀\n\n"
        "%тарифы%\n\n"
        "✍️ <a href='https://telegra.ph/Polzovatelskoe-soglashenie-01-01'>ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ</a> ✍️\n\n"
        "✍️ <a href='https://telegra.ph/Politika-konfidencialnosti-01-01'>ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ</a> ✍️"
    )
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('cms_main_text', ?)", (default_main_text,))
    conn.commit()

# 2. Регистрация синей кнопки "Меню" в Telegram API
async def register_menu():
    token = ""
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as ef:
            for line in ef:
                if line.startswith("BOT_TOKEN="):
                    token = line.split("=", 1)[1].strip()
    if token:
        bot = Bot(token=token)
        cmds = [
            BotCommand("start", "Показать главное меню"),
            BotCommand("help", "Справка по боту"),
            BotCommand("status", "Проверить статус бота"),
            BotCommand("id", "Показать ваш Telegram ID"),
        ]
        await bot.set_my_commands(cmds)
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())

try:
    asyncio.run(register_menu())
except Exception as e:
    print("Menu API info:", e)

# 3. Очистка bot.py от всех предыдущих тестовых вставок в конце файла и лишних кнопок
with open(bot_path, "r", encoding="utf-8") as f:
    code = f.read()

# Убираем ошибочно попавшую кнопку "Редактирование текстов и медиа" из других функций (например, из ключа)
code = re.sub(r'\[InlineKeyboardButton\("✏️ Редактирование текстов и медиа",\s*callback_data="cms_open_menu"\)\],\s*', '', code)
code = re.sub(r'InlineKeyboardButton\("⚙️ Управление ключами \(Кастом / \+/-\)",\s*callback_data=f"ckm_menu_\{uid\}"\)\s*\],\s*\[\s*', '', code)

# Отрезаем все старые кастомные блоки, добавленные в конец файла после основного кода
markers_to_cut = [
    "# ⚙️ МОДУЛЬ КАСТОМНЫХ КЛЮЧЕЙ",
    "# 👤 НОВАЯ КАРТОЧКА КЛИЕНТА",
    "# 🔵 КНОПКА \"МЕНЮ\"",
    "def render_client_key_detail(",
    "async def render_referral_screen_handler("
]
for m in markers_to_cut:
    if m in code:
        idx = code.index(m)
        # Отрезаем вместе с предшествующей линией комментариев # ====
        prev_sep = code.rfind("# ====", max(0, idx - 120), idx)
        cut_pos = prev_sep if prev_sep != -1 else idx
        code = code[:cut_pos].rstrip()

# Добавляем кнопку "✏️ Редактирование текстов" ТОЛЬКО внутри функции render_bot_settings_main_screen
if "def render_bot_settings_main_screen" in code and "cms_open_menu" not in code:
    s_pos = code.index("def render_bot_settings_main_screen")
    kb_pos = code.find("InlineKeyboardMarkup([", s_pos)
    if kb_pos != -1 and kb_pos - s_pos < 2500:
        insert_at = kb_pos + len("InlineKeyboardMarkup([")
        code = code[:insert_at] + '\n        [InlineKeyboardButton("✏️ Редактирование текстов", callback_data="cms_open_menu")],' + code[insert_at:]

# 4. Полный единый модуль всех экранов и функций
unified_module = '''

# ==============================================================================
# 🚀 ЕДИНЫЙ МОДУЛЬ: ГЛАВНОЕ МЕНЮ, РЕФЕРАЛКА, КЛЮЧИ КЛИЕНТА, ДОСЬЕ И МАСТЕР 3X-UI
# ==============================================================================
import os
from datetime import datetime, timedelta
from telegram import BotCommand, MenuButtonCommands, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

def is_any_admin_ckm(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = 'extra_admins'").fetchone()
            if row and str(user_id) in [x.strip() for x in row[0].split(",") if x.strip()]:
                return True
    except Exception:
        pass
    return False

CMS_SECTIONS = {
    "main": ("📝 Главная страница", "cms_main_text", "cms_main_media"),
    "help": ("📝 Справка (текст)", "cms_help_text", "cms_help_media"),
    "ref": ("👥 Реферальная программа", "cms_ref_text", "cms_ref_media"),
    "prepay": ("📝 Текст перед оплатой", "cms_prepay_text", "cms_prepay_media"),
    "keyout": ("📝 Текст выдачи ключа", "cms_keyout_text", "cms_keyout_media"),
    "news": ("📢 Ссылка: Новости", "cms_news_url", ""),
    "support": ("💬 Ссылка: Поддержка", "cms_support_url", ""),
}

def build_tariffs_block() -> str:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("SELECT name, days, price_rub FROM tariffs WHERE is_active = 1 ORDER BY id ASC").fetchall()
        if rows:
            lines = ["📋 <b>Тарифы:</b>"]
            for name, days, rub in rows:
                clean_name = name if name.startswith("📱") else f"📱 {name}"
                lines.append(f"• {clean_name} — <b>{rub} ₽</b>")
            return "\\n".join(lines)
    except Exception:
        pass
    return (
        "📋 <b>Тарифы:</b>\\n"
        "• 📱 30 Дней 1 Устр. — <b>200 ₽</b>\\n"
        "• 📱 60 Дней 1 Устр. — <b>350 ₽</b>\\n"
        "• 📱 90 Дней 1 Устр. — <b>500 ₽</b>\\n"
        "• 📱 180 Дней 1 Устр. — <b>999 ₽</b>\\n"
        "• 📱 365 Дней 1 Устр. — <b>1799 ₽</b>\\n"
        "• 📱 Акция 30дней 2Устроиства — <b>150 ₽</b>\\n"
        "• 📱 Акция 60дней 2Устроиства — <b>250 ₽</b>"
    )

def build_custom_start_content(user_id: int):
    raw_tpl = get_setting("cms_main_text", "")
    if not raw_tpl:
        raw_tpl = (
            "🔐 <b>Добро пожаловать в VPN-бот!</b>\\n\\n"
            "Быстрый, безопасный и анонимный доступ к интернету.\\n"
            "Без логов, без ограничений, без проблем! 🚀\\n\\n"
            "%тарифы%\\n\\n"
            "✍️ <a href='https://telegra.ph/Polzovatelskoe-soglashenie-01-01'>ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ</a> ✍️\\n\\n"
            "✍️ <a href='https://telegra.ph/Politika-konfidencialnosti-01-01'>ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ</a> ✍️"
        )
    caption = raw_tpl.replace("%тарифы%", build_tariffs_block())

    rows = [
        [
            InlineKeyboardButton("🔑 Мои ключи", callback_data="client_my_keys"),
            InlineKeyboardButton("💳 Купить ключ", callback_data="order_vpn")
        ],
        [
            InlineKeyboardButton("🎁 Пробная подписка", callback_data="claim_trial")
        ],
        [
            InlineKeyboardButton("🔗 Реферальная ссылка", callback_data="start_ref_link"),
            InlineKeyboardButton("❓ Справка", callback_data="start_help_box")
        ]
    ]
    if is_any_admin_ckm(user_id):
        rows.append([InlineKeyboardButton("⚙️ Админ-панель", callback_data="start_open_admin")])

    return caption, InlineKeyboardMarkup(rows)

async def send_or_replace_main_menu(bot, chat_id: int, user_id: int, old_message=None):
    caption, kb = build_custom_start_content(user_id)
    banner_file_id = get_setting("cms_main_media", "") or get_setting("welcome_banner_id", "")
    banner_path = "/opt/Bot_VIP/welcome.jpg"

    if old_message:
        try:
            await old_message.delete()
        except Exception:
            pass

    try:
        if banner_file_id:
            await bot.send_photo(chat_id=chat_id, photo=banner_file_id, caption=caption, parse_mode="HTML", reply_markup=kb)
            return
        elif os.path.exists(banner_path):
            with open(banner_path, "rb") as ph:
                await bot.send_photo(chat_id=chat_id, photo=ph, caption=caption, parse_mode="HTML", reply_markup=kb)
                return
    except Exception:
        pass

    await bot.send_message(chat_id=chat_id, text=caption, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)

# ------------------------------------------------------------------------------
# 🔑 ЭКРАН КЛЮЧЕЙ КЛИЕНТА (ТОЧНО КАК НА СКРИНШОТЕ #9)
# ------------------------------------------------------------------------------
def render_client_keys_list_screen(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, key_name, location_name, expires_at, is_active FROM user_keys WHERE user_id = ? ORDER BY id ASC",
            (user_id,)
        ).fetchall()

    if not rows:
        txt = (
            "🔑 <b>Мои ключи</b>\\n\\n"
            "У вас пока нет активных VPN-ключей.\\n"
            "Нажмите <b>«💳 Купить ключ»</b> или активируйте <b>«🎁 Пробную подписку»</b>!"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Купить ключ", callback_data="order_vpn")],
            [InlineKeyboardButton("🎁 Пробная подписка", callback_data="claim_trial")],
            [InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")]
        ])
        return txt, kb

    txt = f"🔑 <b>Мои ключи ({len(rows)} шт.)</b>\\n\\nВыберите ключ для управления и просмотра подписки:"
    kb_rows = []
    now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for kid, kname, loc, exp, act in rows:
        is_ok = act == 1 and (not exp or exp == "Без срока" or exp > now_s)
        st = "🟢" if is_ok else "🔴"
        title = kname or f"Ключ #{kid}"
        exp_s = "Без срока" if (not exp or exp == "Без срока") else exp[:10]
        kb_rows.append([InlineKeyboardButton(f"{st} {title} | {loc or '🇩🇪 Германия'} (до {exp_s})", callback_data=f"ckey_view_{kid}")])

    kb_rows.append([InlineKeyboardButton("➕ Купить еще ключ", callback_data="order_vpn")])
    kb_rows.append([InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")])
    return txt, InlineKeyboardMarkup(kb_rows)

def render_client_single_key_screen(kid: int, user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, key_name, location_name, COALESCE(traffic_bytes, 0), COALESCE(limit_gb, 0), COALESCE(limit_ip, 1), expires_at, is_active, COALESCE(group_name, 'Индивидуальный тариф'), COALESCE(history_log, '') FROM user_keys WHERE id = ? AND user_id = ?",
            (kid, user_id)
        ).fetchone()

    if not row:
        return "❌ Ключ не найден.", InlineKeyboardMarkup([[InlineKeyboardButton("🔑 Мои ключи", callback_data="client_my_keys")]])

    kid, kname, loc, t_bytes, lgb, lip, exp, act, grp, h_log = row
    now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    is_ok = act == 1 and (not exp or exp == "Без срока" or exp > now_s)
    st_icon = "🟢" if is_ok else "🔴"

    used_gb = float(t_bytes or 0) / (1024 ** 3)
    gb_str = f"{used_gb:.2f} GB (безлимит)" if not lgb or lgb <= 0 else f"{used_gb:.2f} / {lgb} GB"
    exp_str = "Без срока" if not exp or exp == "Без срока" else exp
    k_title = html.escape(kname or f"Ключ #{kid}")
    tariff_title = "Индивидуальный тариф" if grp in ("Основная", "", None) else html.escape(grp)

    if not h_log:
        today_d = datetime.now().strftime("%Y-%m-%d")
        h_log = f"• {today_d}: Переоформление на произвольный тариф"

    text = (
        f"🔑 <b>{k_title}</b>\\n\\n"
        f"<b>Статус:</b> {st_icon}\\n"
        f"<b>Сервер:</b> {html.escape(loc or '🇩🇪 Германия')}\\n"
        f"<b>Тариф:</b> {tariff_title}\\n"
        f"<b>Устройств:</b> {lip}\\n"
        f"<b>Трафик:</b> {gb_str}\\n"
        f"<b>Действует до:</b> {exp_str}\\n\\n"
        f"📜 <b>История операций:</b>\\n"
        f"{h_log}"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Показать подписку", callback_data=f"ckey_sub_{kid}"),
            InlineKeyboardButton("📈 Продлить", callback_data="order_vpn")
        ],
        [
            InlineKeyboardButton("🔄 Заменить", callback_data=f"key_loc_{kid}"),
            InlineKeyboardButton("✏️ Переименовать", callback_data=f"key_ren_{kid}")
        ],
        [
            InlineKeyboardButton("📱 Мои устройства", callback_data=f"ckey_devs_{kid}")
        ],
        [
            InlineKeyboardButton("🔑 Мои ключи", callback_data="client_my_keys"),
            InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")
        ]
    ])
    return text, kb

# ------------------------------------------------------------------------------
# 👤 ДОСЬЕ ПОЛЬЗОВАТЕЛЯ В АДМИНКЕ И ПОШАГОВЫЙ МАСТЕР КЛЮЧЕЙ
# ------------------------------------------------------------------------------
def render_single_user_dossier(target_id: int) -> tuple[str, InlineKeyboardMarkup]:
    info = get_user_info(target_id)
    if not info:
        return "Пользователь не найден в БД.", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="admin_users_menu")]])

    uid, uname, fname, joined, is_vip, is_ban, until, attempts, vpn_cfg, bot_lic, srv_id, sub_id, c_uuid, trial_u, has_exp, bot_blk, ref_by, ref_cnt, ref_days, disc_pct = info

    with sqlite3.connect(DB_PATH) as conn:
        u_extra = conn.execute("SELECT COALESCE(balance, 0), COALESCE(ref_coeff, 1.0) FROM users WHERE user_id = ?", (uid,)).fetchone()
        balance, ref_coeff = (int(u_extra[0]), float(u_extra[1])) if u_extra else (0, 1.0)

        pay_row = conn.execute("SELECT COUNT(*), MAX(created_at) FROM payments WHERE user_id = ?", (uid,)).fetchone()
        p_cnt = pay_row[0] if pay_row and pay_row[0] else 0
        p_last = pay_row[1] if pay_row and pay_row[1] else "нет"

        key_rows = conn.execute(
            "SELECT id, expires_at, is_active FROM user_keys WHERE user_id = ? ORDER BY id ASC",
            (uid,)
        ).fetchall()

    uname_str = f"@{html.escape(uname)}" if uname else "<i>_не указан_</i>"
    deliv_str = "<b>недоступен (блок)</b>" if bot_blk else "<b>доступен для сообщений</b>"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    keys_lines = []
    for kid, kexp, kact in key_rows:
        is_ok = kact == 1 and (not kexp or kexp == "Без срока" or kexp > now_str)
        icon = "🟢" if is_ok else "🔴"
        exp_disp = "без срока" if (not kexp or kexp == "Без срока") else kexp
        keys_lines.append(f"  {icon} Ключ #{kid} (до {exp_disp})")

    keys_block = "\\n".join(keys_lines) if keys_lines else "  <i>Нет ключей</i>"

    text = (
        f"👤 Username: {uname_str}\\n"
        f"📱 Telegram ID: <code>{uid}</code>\\n"
        f"📨 Статус доставки: {deliv_str}\\n"
        f"📧 E-mail в панели: <code>user_{uid}_</code>\\n"
        f"📅 Зарегистрирован: {joined}\\n"
        f"💰 Баланс: <b>{balance} ₽</b>\\n"
        f"📊 Реферальный коэффициент: <b>{ref_coeff:.1f}x</b>\\n\\n"
        f"🔑 <b>VPN-ключи ({len(key_rows)}):</b>\\n"
        f"{keys_block}\\n\\n"
        f"💳 <b>Оплаты:</b>\\n"
        f"  📊 Всего платежей: {p_cnt}\\n"
        f"  📅 Последняя оплата: {p_last}"
    )

    kb_rows = []
    for kid, _, _ in key_rows[:15]:
        kb_rows.append([InlineKeyboardButton(f"🔑 Ключ #{kid}", callback_data=f"ckm_kview_{kid}_{uid}")])

    kb_rows.append([InlineKeyboardButton("➕ Добавить ключ", callback_data=f"ckm_wgrp_{uid}")])
    kb_rows.append([InlineKeyboardButton("💬 Написать", callback_data=f"admin_uact_msg_{uid}")])
    kb_rows.append([
        InlineKeyboardButton(f"💰 Баланс: {balance} ₽", callback_data=f"ckm_balinfo_{uid}"),
        InlineKeyboardButton("➕ Пополнить", callback_data=f"ckm_baladd_{uid}"),
        InlineKeyboardButton("➖ Списать", callback_data=f"ckm_balsub_{uid}")
    ])
    kb_rows.append([InlineKeyboardButton(f"📊 Реферальный коэффициент: {ref_coeff:.1f}x", callback_data=f"ckm_refc_{uid}")])

    ban_txt = "✅ Разблокировать" if is_ban else "🚫 Заблокировать"
    kb_rows.append([InlineKeyboardButton(ban_txt, callback_data=f"admin_uact_ban_{uid}")])
    kb_rows.append([
        InlineKeyboardButton("⬅️ Назад", callback_data="admin_ulist_0"),
        InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")
    ])

    return text, InlineKeyboardMarkup(kb_rows)

def render_ckm_key_detail(kid: int, uid: int):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, COALESCE(group_name, 'Основная'), location_name, limit_gb, COALESCE(limit_ip, 1), expires_at, is_active, sub_id, config_text FROM user_keys WHERE id = ?",
            (kid,)
        ).fetchone()
    if not row:
        return "❌ Ключ не найден.", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_back_u_{uid}")]])

    kid, grp, loc, lgb, lip, exp, act, sub_id, cfg = row
    st = "🟢 Активен" if act else "🔴 Отключен"
    gb_str = "без лимита" if not lgb or lgb <= 0 else f"{lgb} ГБ"
    exp_str = "без срока" if not exp or exp == "Без срока" else exp

    txt = (
        f"🔑 <b>Управление ключом #{kid}</b> (Клиент: <code>{uid}</code>)\\n\\n"
        f"📡 Статус: <b>{st}</b>\\n"
        f"📁 Группа: <b>{html.escape(grp)}</b>\\n"
        f"🖥 Сервер: <b>{html.escape(loc or '🇩🇪 Германия')}</b>\\n"
        f"📊 Трафик: <b>{gb_str}</b>\\n"
        f"📅 Срок: <b>{exp_str}</b>\\n"
        f"💻 Устройств: <b>{lip}</b>"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 Изменить срок (дни)", callback_data=f"ckm_ked_{kid}_{uid}_days"),
            InlineKeyboardButton("📊 Изменить трафик (ГБ)", callback_data=f"ckm_ked_{kid}_{uid}_gb")
        ],
        [
            InlineKeyboardButton("💻 Изменить устр-ва", callback_data=f"ckm_ked_{kid}_{uid}_ip"),
            InlineKeyboardButton("🔄 Вкл / Выкл", callback_data=f"ckm_ktog_{kid}_{uid}")
        ],
        [InlineKeyboardButton("📋 Показать ссылку / конфиг", callback_data=f"ckey_sub_{kid}")],
        [InlineKeyboardButton("🗑 Удалить ключ", callback_data=f"ckm_kdel_{kid}_{uid}")],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_back_u_{uid}"),
            InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")
        ]
    ])
    return txt, kb

async def show_ckm_confirm_screen(message, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    wiz = context.user_data.get("ckm_wiz", {})
    uid = wiz.get("uid", 0)
    grp = wiz.get("group", "Основная")
    srv_name = wiz.get("srv_name", "🇩🇪 Германия")
    gb = wiz.get("gb", 0)
    days = wiz.get("days", 0)
    ips = wiz.get("ips", 1)

    gb_str = "без лимита" if gb == 0 else f"{gb} ГБ"
    days_str = "без срока" if days == 0 else f"{days} дн."

    txt = (
        "✅ <b>Подтверждение создания ключа</b>\\n\\n"
        f"📁 Группа: {html.escape(grp)}\\n"
        f"🖥 Сервер: {html.escape(srv_name)}\\n"
        f"📊 Трафик: {gb_str}\\n"
        f"📅 Срок: {days_str}\\n"
        f"💻 Устройств: {ips}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Создать ключ", callback_data=f"ckm_wcreate_{uid}")],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wstep_ip_{uid}"),
            InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
        ]
    ])
    if edit:
        await message.edit_text(txt, parse_mode="HTML", reply_markup=kb)
    else:
        await message.reply_text(txt, parse_mode="HTML", reply_markup=kb)

# ------------------------------------------------------------------------------
# ✏️ РЕДАКТОР ТЕКСТОВ И МЕДИА (CMS)
# ------------------------------------------------------------------------------
def render_cms_main_menu():
    txt = "✏️ <b>Редактирование текстов</b>\\n\\nВыберите, что хотите изменить:"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Главная страница", callback_data="cms_edit_main")],
        [InlineKeyboardButton("👥 Реферальная программа", callback_data="cms_edit_ref")],
        [InlineKeyboardButton("📝 Справка (текст)", callback_data="cms_edit_help")],
        [InlineKeyboardButton("📝 Текст перед оплатой", callback_data="cms_edit_prepay")],
        [InlineKeyboardButton("📝 Текст выдачи ключа", callback_data="cms_edit_keyout")],
        [InlineKeyboardButton("📢 Ссылка: Новости", callback_data="cms_edit_news")],
        [InlineKeyboardButton("💬 Ссылка: Поддержка", callback_data="cms_edit_support")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="admin_bot_settings")]
    ])
    return txt, kb

async def send_cms_section_preview(message, sec_key: str):
    title, text_key, media_key = CMS_SECTIONS[sec_key]
    cur_text = get_setting(text_key, "")
    cur_media = get_setting(media_key, "") if media_key else ""

    if not cur_text:
        if sec_key == "main":
            cur_text = (
                "🔐 <b>Добро пожаловать в VPN-бот!</b>\\n\\n"
                "Быстрый, безопасный и анонимный доступ к интернету.\\n"
                "Без логов, без ограничений, без проблем! 🚀\\n\\n"
                "%тарифы%\\n\\n"
                "✍️ <a href='https://telegra.ph/Polzovatelskoe-soglashenie-01-01'>ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ</a> ✍️\\n\\n"
                "✍️ <a href='https://telegra.ph/Politika-konfidencialnosti-01-01'>ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ</a> ✍️"
            )
        else:
            cur_text = f"<i>({title} — отправьте новое сообщение или фото с подписью)</i>"

    kb_rows = [
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="cms_open_menu"),
            InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")
        ]
    ]
    if media_key and cur_media:
        kb_rows.append([InlineKeyboardButton("🗑 Удалить медиа", callback_data=f"cms_delmedia_{sec_key}")])
    kb_rows.append([InlineKeyboardButton("📝 Отправьте новое сообщение ⬇️", callback_data="cms_noop")])
    kb = InlineKeyboardMarkup(kb_rows)

    try:
        if cur_media:
            await message.reply_photo(photo=cur_media, caption=cur_text, parse_mode="HTML", reply_markup=kb)
            return
    except Exception:
        pass
    await message.reply_text(cur_text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)

# ------------------------------------------------------------------------------
# 🎯 ОБРАБОТЧИКИ КОМАНД И КНОПОК
# ------------------------------------------------------------------------------
async def custom_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["mode"] = None
    if "ensure_user" in globals():
        try:
            ensure_user(user.id, user.username or "", user.first_name or "User")
        except Exception:
            pass
    await send_or_replace_main_menu(context.bot, update.effective_chat.id, user.id)
    raise ApplicationHandlerStop

async def cmd_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")]])
    await update.effective_message.reply_text(
        f"🆔 <b>Ваш Telegram ID</b>\\n\\n<code>{u.id}</code>",
        parse_mode="HTML",
        reply_markup=kb
    )
    raise ApplicationHandlerStop

async def cmd_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    with sqlite3.connect(DB_PATH) as conn:
        srvs = conn.execute("SELECT COUNT(*) FROM servers WHERE is_active = 1").fetchone()[0]
        keys = conn.execute("SELECT COUNT(*) FROM user_keys WHERE user_id = ? AND is_active = 1", (u.id,)).fetchone()[0]
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")]])
    await update.effective_message.reply_text(
        f"🟢 <b>Статус бота: Работает в штатном режиме</b>\\n\\n"
        f"🖥 Активных серверов: <b>{srvs} шт.</b>\\n"
        f"🔑 Ваших активных ключей: <b>{keys} шт.</b>",
        parse_mode="HTML",
        reply_markup=kb
    )
    raise ApplicationHandlerStop

async def cmd_help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")]])
    await update.effective_message.reply_text(
        "ℹ️ <b>Справка по командам бота:</b>\\n\\n"
        "/start — Показать главное меню\\n"
        "/help — Справка по боту\\n"
        "/status — Проверить статус бота и ключей\\n"
        "/id — Показать ваш Telegram ID",
        parse_mode="HTML",
        reply_markup=kb
    )
    raise ApplicationHandlerStop

async def handle_all_custom_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data

    # 1. Возврат на главную (обрабатываем и start_back_main, и старый back_to_main!)
    if data in ("start_back_main", "back_to_main", "main_menu"):
        await query.answer()
        context.user_data["mode"] = None
        await send_or_replace_main_menu(context.bot, query.message.chat_id, user.id, old_message=query.message)
        raise ApplicationHandlerStop

    # 2. Реферальная программа (как на скриншоте с баннером и статистикой)
    if data in ("start_ref_link", "ref_program", "client_ref"):
        await query.answer()
        bot_me = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_me.username}?start=ref_{user.id}"
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT ref_count, ref_bonus_days FROM users WHERE user_id = ?", (user.id,)).fetchone()
            r_cnt, r_days = (row[0] or 0, row[1] or 0) if row else (0, 0)

        custom_ref_tpl = get_setting("cms_ref_text", "")
        if custom_ref_tpl:
            caption = (
                custom_ref_tpl
                .replace("%ссылка%", ref_link)
                .replace("%рефералы%", str(r_cnt))
                .replace("%дни%", str(r_days))
            )
        else:
            caption = (
                "👥 <b>ПРИГЛАШАЙ ДРУЗЕЙ В SVOII VPN — ПОЛУЧАЙ ДНИ ПОДПИСКИ!</b> 🎁\\n\\n"
                "Пользуйся быстрым интернетом бесплатно! Делись ссылкой с друзьями и сразу получай бонусные дни к своей подписке.\\n\\n"
                "📎 <b>Твоя персональная ссылка:</b>\\n"
                f"{ref_link}\\n"
                "───────────────────\\n"
                "🚀 <b>Как это работает:</b>\\n"
                "1️⃣ Отправь ссылку другу.\\n"
                "2️⃣ Друг регистрируется и оплачивает подписку.\\n"
                "3️⃣ Тебе СРАЗУ начисляются бонусные дни доступа! ⚡️\\n\\n"
                "Чем больше друзей подключается — тем дольше твой VPN работает абсолютно бесплатно! 🛡\\n"
                "───────────────────\\n"
                "📊 <b>Твоя статистика:</b>\\n\\n"
                f"✅ Уровень 1 (10%): {r_cnt} чел. — {r_days} дн."
            )

        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")]])
        ref_media = get_setting("cms_ref_media", "")
        try:
            await query.message.delete()
        except Exception:
            pass
        if ref_media:
            try:
                await context.bot.send_photo(chat_id=user.id, photo=ref_media, caption=caption, parse_mode="HTML", reply_markup=kb)
                raise ApplicationHandlerStop
            except Exception:
                pass
        await context.bot.send_message(chat_id=user.id, text=caption, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
        raise ApplicationHandlerStop

    # 3. Справка
    if data == "start_help_box":
        await query.answer()
        help_txt = get_setting("cms_help_text", "") or (
            "❓ <b>Справка и помощь по подключению</b>\\n\\n"
            "1️⃣ Нажмите <b>«💳 Купить ключ»</b> или <b>«🎁 Пробная подписка»</b>.\\n"
            "2️⃣ Откройте раздел <b>«🔑 Мои ключи»</b> → выберите ваш ключ → нажмите <b>«📋 Показать подписку»</b>.\\n"
            "3️⃣ Скопируйте ссылку подписки и вставьте её в приложение <b>Happ</b>, <b>v2rayTun</b>, <b>Hiddify</b> или <b>Streisand</b>."
        )
        help_media = get_setting("cms_help_media", "")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")]])
        try:
            await query.message.delete()
        except Exception:
            pass
        if help_media:
            try:
                await context.bot.send_photo(chat_id=user.id, photo=help_media, caption=help_txt, parse_mode="HTML", reply_markup=kb)
                raise ApplicationHandlerStop
            except Exception:
                pass
        await context.bot.send_message(chat_id=user.id, text=help_txt, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
        raise ApplicationHandlerStop

    # 4. Открытие Админ-панели с главного экрана
    if data == "start_open_admin":
        await query.answer()
        if not is_any_admin_ckm(user.id):
            return
        if "render_admin_main_screen" in globals():
            txt, kb = render_admin_main_screen()
            await query.message.reply_text(txt, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    # 5. Клиентский раздел "🔑 Мои ключи" и карточка ключа (#9 на скриншоте)
    if data == "client_my_keys":
        await query.answer()
        with sqlite3.connect(DB_PATH) as conn:
            k_ids = [r[0] for r in conn.execute("SELECT id FROM user_keys WHERE user_id = ? ORDER BY id ASC", (user.id,)).fetchall()]
        try:
            await query.message.delete()
        except Exception:
            pass
        if len(k_ids) == 1:
            txt, kb = render_client_single_key_screen(k_ids[0], user.id)
        else:
            txt, kb = render_client_keys_list_screen(user.id)
        await context.bot.send_message(chat_id=user.id, text=txt, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    if data.startswith("ckey_view_") or data.startswith("key_open_") or data.startswith("mykey_"):
        await query.answer()
        kid = int(data.split("_")[-1])
        txt, kb = render_client_single_key_screen(kid, user.id)
        try:
            await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await query.message.reply_text(txt, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    if data.startswith("ckey_sub_"):
        await query.answer()
        kid = int(data.split("_")[-1])
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT user_id, key_name, sub_id, config_text, location_name FROM user_keys WHERE id = ?", (kid,)).fetchone()
        if not row:
            return
        k_uid, kname, sub_id, cfg_txt, loc = row
        sub_prefix = get_setting("sub_domain_prefix", "") or "https://pl.svoii-vpn.online:2096/sub"
        sub_url = f"{sub_prefix.rstrip('/')}/{sub_id}"

        # Берем только чистые vless:// / vmess:// / trojan:// / ss:// ссылки для легкого импорта
        clean_lines = [ln.strip() for ln in (cfg_txt or "").splitlines() if ln.strip().startswith(("vless://", "vmess://", "trojan://", "ss://"))]
        vless_block = "\\n".join(clean_lines) if clean_lines else (cfg_txt or "")

        txt = (
            f"📋 <b>Подписка для {html.escape(kname or f'Ключ #{kid}')}</b>\\n\\n"
            f"🔗 <b>Ссылка подписки (для Happ / v2rayTun / Hiddify):</b>\\n"
            f"<code>{sub_url}</code>\\n\\n"
            f"🔐 <b>Прямой ключ подключения (нажмите, чтобы скопировать):</b>\\n"
            f"<code>{html.escape(vless_block)}</code>"
        )
        back_cb = f"ckm_kview_{kid}_{k_uid}" if (is_any_admin_ckm(user.id) and user.id != k_uid) else f"ckey_view_{kid}"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📲 Показать QR-код", callback_data=f"key_qr_{kid}")],
            [
                InlineKeyboardButton("⬅️ Назад к ключу", callback_data=back_cb),
                InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")
            ]
        ])
        try:
            await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            await query.message.reply_text(txt, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
        raise ApplicationHandlerStop

    if data.startswith("ckey_devs_"):
        kid = int(data.split("_")[-1])
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT COALESCE(limit_ip, 1) FROM user_keys WHERE id = ?", (kid,)).fetchone()
        lip = row[0] if row else 1
        await query.answer(f"📱 Лимит устройств по этому ключу: {lip} шт.", show_alert=True)
        raise ApplicationHandlerStop

    # 6. Редактор текстов и медиа (CMS)
    if data == "cms_noop":
        await query.answer("Просто отправьте в чат новое фото с подписью или текст!", show_alert=True)
        raise ApplicationHandlerStop

    if data == "cms_open_menu":
        await query.answer()
        if not is_any_admin_ckm(user.id):
            return
        context.user_data["mode"] = None
        txt, kb = render_cms_main_menu()
        try:
            await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await query.message.reply_text(txt, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    if data.startswith("cms_edit_"):
        await query.answer()
        if not is_any_admin_ckm(user.id):
            return
        sec_key = data.split("_", 2)[2]
        if sec_key in CMS_SECTIONS:
            context.user_data["mode"] = f"cms_wait_{sec_key}"
            await send_cms_section_preview(query.message, sec_key)
        raise ApplicationHandlerStop

    if data.startswith("cms_delmedia_"):
        await query.answer()
        if not is_any_admin_ckm(user.id):
            return
        sec_key = data.split("_", 2)[2]
        if sec_key in CMS_SECTIONS:
            _, _, media_key = CMS_SECTIONS[sec_key]
            if media_key:
                set_setting(media_key, "")
            if sec_key == "main":
                set_setting("welcome_banner_id", "")
            context.user_data["mode"] = f"cms_wait_{sec_key}"
            await query.message.reply_text("🗑 Медиафайл удалён!")
            await send_cms_section_preview(query.message, sec_key)
        raise ApplicationHandlerStop

    # 7. Пошаговый мастер ключей и управление карточкой пользователя (ckm_)
    if data.startswith("ckm_"):
        if not is_any_admin_ckm(user.id):
            await query.answer("⛔ Нет прав администратора.", show_alert=True)
            raise ApplicationHandlerStop
        await query.answer()

        if data.startswith("ckm_back_u_") or data.startswith("ckm_menu_"):
            context.user_data["mode"] = None
            uid = int(data.split("_")[-1])
            txt, kb = render_single_user_dossier(uid)
            await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        # Шаг 1: Выбор группы тарифов
        if data.startswith("ckm_wgrp_"):
            uid = int(data.split("_")[2])
            context.user_data["mode"] = None
            context.user_data["ckm_wiz"] = {"uid": uid}
            with sqlite3.connect(DB_PATH) as conn:
                g_rows = [r[0] for r in conn.execute("SELECT DISTINCT group_name FROM tariffs WHERE group_name != ''").fetchall()]
            groups = ["Основная"]
            for g in g_rows:
                if g not in groups:
                    groups.append(g)
            context.user_data["ckm_groups_list"] = groups
            kb_rows = [[InlineKeyboardButton(f"📁 {g}", callback_data=f"ckm_wselgrp_{uid}_{idx}")] for idx, g in enumerate(groups)]
            kb_rows.append([InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")])
            txt = f"➕ <b>Добавление ключа для ID:</b> <code>{uid}</code>\\n\\nВыберите группу тарифов:"
            await query.edit_message_text(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))
            raise ApplicationHandlerStop

        # Шаг 2: Выбор сервера
        if data.startswith("ckm_wselgrp_"):
            parts = data.split("_")
            uid, g_idx = int(parts[2]), int(parts[3])
            groups = context.user_data.get("ckm_groups_list", ["Основная"])
            grp_name = groups[g_idx] if g_idx < len(groups) else "Основная"
            wiz = context.user_data.setdefault("ckm_wiz", {"uid": uid})
            wiz["group"] = grp_name

            servers = get_all_servers_full() if "get_all_servers_full" in globals() else []
            kb_rows = []
            if servers:
                for s in servers:
                    kb_rows.append([InlineKeyboardButton(f"🖥 {s[1]}", callback_data=f"ckm_wselsrv_{uid}_{s[0]}")])
            else:
                kb_rows.append([InlineKeyboardButton("🖥 🇩🇪 Германия", callback_data=f"ckm_wselsrv_{uid}_0")])
            kb_rows.append([InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")])
            txt = f"🖥 <b>Группа: {html.escape(grp_name)}</b>\\n\\nВыберите сервер:"
            await query.edit_message_text(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))
            raise ApplicationHandlerStop

        # Шаг 3: Ввод лимита трафика (ГБ)
        if data.startswith("ckm_wselsrv_") or data.startswith("ckm_wstep_gb_"):
            parts = data.split("_")
            if data.startswith("ckm_wselsrv_"):
                uid, srv_id = int(parts[2]), int(parts[3])
                srv_name = "🇩🇪 Германия"
                if "get_all_servers_full" in globals():
                    for s in get_all_servers_full():
                        if s[0] == srv_id:
                            srv_name = s[1]
                            break
                wiz = context.user_data.setdefault("ckm_wiz", {"uid": uid})
                wiz["srv_id"] = srv_id
                wiz["srv_name"] = srv_name
            else:
                uid = int(parts[3])
                wiz = context.user_data.setdefault("ckm_wiz", {"uid": uid})

            context.user_data["mode"] = "ckm_wiz_gb"
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wgrp_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]])
            await query.edit_message_text("📊 <b>Лимит трафика</b>\\n\\nВведите лимит в ГБ (0 = без лимита):", parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        # Шаг 4: Срок действия
        if data.startswith("ckm_wstep_days_"):
            uid = int(data.split("_")[3])
            context.user_data["mode"] = "ckm_wiz_days"
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wstep_gb_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]])
            await query.edit_message_text("📅 <b>Срок действия</b>\\n\\nВведите количество дней (0 = без срока):", parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        # Шаг 5: Лимит устройств
        if data.startswith("ckm_wstep_ip_"):
            uid = int(data.split("_")[3])
            context.user_data["mode"] = "ckm_wiz_ip"
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wstep_days_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]])
            await query.edit_message_text("💻 <b>Лимит устройств</b>\\n\\nВведите число от 1 до 999:", parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        # Шаг 6: Создание ключа в БД и на выбранном сервере 3X-UI
        if data.startswith("ckm_wcreate_"):
            uid = int(data.split("_")[2])
            wiz = context.user_data.get("ckm_wiz", {})
            grp = wiz.get("group", "Основная")
            srv_id = wiz.get("srv_id", 0)
            srv_name = wiz.get("srv_name", "🇩🇪 Германия")
            gb = int(wiz.get("gb", 0))
            days = int(wiz.get("days", 0))
            ips = int(wiz.get("ips", 1))

            k_id, until_s, _, _ = await create_or_extend_user_key(uid, days=days, create_new=True)
            today_d = datetime.now().strftime("%Y-%m-%d")
            h_entry = f"• {today_d}: Выдан ключ ({'без срока' if days == 0 else f'{days} дн.'}, {'безлимит' if gb == 0 else f'{gb} ГБ'}, {ips} устр.)"

            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "UPDATE user_keys SET group_name = ?, server_id = ?, location_name = ?, limit_gb = ?, limit_ip = ?, history_log = ? WHERE id = ?",
                    (grp, srv_id, srv_name, gb, ips, h_entry, k_id)
                )
                conn.commit()

            context.user_data["mode"] = None
            txt, kb = render_single_user_dossier(uid)
            await query.edit_message_text(f"✅ <b>Ключ #{k_id} успешно создан!</b>\\n\\n{txt}", parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if data.startswith("ckm_kview_"):
            _, _, kid_s, uid_s = data.split("_")
            txt, kb = render_ckm_key_detail(int(kid_s), int(uid_s))
            await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if data.startswith("ckm_ktog_"):
            _, _, kid_s, uid_s = data.split("_")
            kid, uid = int(kid_s), int(uid_s)
            with sqlite3.connect(DB_PATH) as conn:
                row = conn.execute("SELECT is_active FROM user_keys WHERE id = ?", (kid,)).fetchone()
                if row:
                    conn.execute("UPDATE user_keys SET is_active = ? WHERE id = ?", (0 if row[0] else 1, kid))
                    conn.commit()
            txt, kb = render_ckm_key_detail(kid, uid)
            await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if data.startswith("ckm_kdel_"):
            _, _, kid_s, uid_s = data.split("_")
            kid, uid = int(kid_s), int(uid_s)
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("DELETE FROM user_keys WHERE id = ?", (kid,))
                conn.commit()
            txt, kb = render_single_user_dossier(uid)
            await query.edit_message_text(f"🗑 Ключ #{kid} удалён!\\n\\n{txt}", parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if data.startswith("ckm_ked_"):
            _, _, kid_s, uid_s, field = data.split("_")
            kid, uid = int(kid_s), int(uid_s)
            context.user_data["mode"] = f"ckm_edit_{field}"
            context.user_data["ckm_kid"] = kid
            context.user_data["ckm_uid"] = uid
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_kview_{kid}_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]])
            prompts = {
                "days": f"📅 <b>Срок действия Ключа #{kid}</b>\\n\\nВведите количество дней (0 = без срока, можно <code>+10</code> или <code>-5</code>):",
                "gb": f"📊 <b>Лимит трафика Ключа #{kid}</b>\\n\\nВведите лимит в ГБ (0 = без лимита, можно <code>+20</code> или <code>-10</code>):",
                "ip": f"💻 <b>Лимит устройств Ключа #{kid}</b>\\n\\nВведите число от 1 до 999 (можно <code>+1</code> или <code>-1</code>):"
            }
            await query.edit_message_text(prompts[field], parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if data.startswith("ckm_balinfo_"):
            await query.answer("Используйте кнопки ➕ Пополнить или ➖ Списать рядом с балансом.", show_alert=True)
            raise ApplicationHandlerStop

        if data.startswith("ckm_baladd_") or data.startswith("ckm_balsub_"):
            uid = int(data.split("_")[2])
            act = "add" if "baladd" in data else "sub"
            context.user_data["mode"] = f"ckm_bal_{act}"
            context.user_data["ckm_uid"] = uid
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")]])
            title = "➕ <b>Пополнение баланса</b>" if act == "add" else "➖ <b>Списание с баланса</b>"
            await query.edit_message_text(f"{title} (ID: <code>{uid}</code>)\\n\\nВведите сумму в рублях:", parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if data.startswith("ckm_refc_"):
            uid = int(data.split("_")[2])
            context.user_data["mode"] = "ckm_ref_coeff"
            context.user_data["ckm_uid"] = uid
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")]])
            await query.edit_message_text(
                f"📊 <b>Реферальный коэффициент (ID: <code>{uid}</code>)</b>\\n\\n"
                f"Введите новое значение коэффициента (например: <code>1.0</code>, <code>1.5</code> или <code>2.0</code>):",
                parse_mode="HTML",
                reply_markup=kb
            )
            raise ApplicationHandlerStop

async def handle_all_custom_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    user = update.effective_user
    msg = update.effective_message

    # Быстрая установка баннера по подписи /setbanner
    if msg and msg.photo and msg.caption and msg.caption.strip().lower() == "/setbanner" and is_any_admin_ckm(user.id):
        file_id = msg.photo[-1].file_id
        set_setting("cms_main_media", file_id)
        set_setting("welcome_banner_id", file_id)
        await msg.reply_text("✅ Баннер главного меню сохранен! Нажмите /start для проверки.")
        raise ApplicationHandlerStop

    if not mode:
        return

    # Ввод для редактора текстов и медиа (CMS)
    if mode.startswith("cms_wait_") and is_any_admin_ckm(user.id):
        sec_key = mode.split("cms_wait_", 1)[1]
        if sec_key in CMS_SECTIONS:
            title, text_key, media_key = CMS_SECTIONS[sec_key]
            new_text = msg.caption_html if (msg.photo and msg.caption) else (msg.text_html if msg.text else "")
            if msg.photo and media_key:
                fid = msg.photo[-1].file_id
                set_setting(media_key, fid)
                if sec_key == "main":
                    set_setting("welcome_banner_id", fid)
            if new_text:
                set_setting(text_key, new_text)
            await msg.reply_text(f"✅ Раздел <b>{title}</b> успешно обновлён!", parse_mode="HTML")
            await send_cms_section_preview(msg, sec_key)
            raise ApplicationHandlerStop

    # Ввод для пошагового мастера ключей и карточки клиента (ckm_)
    if mode.startswith("ckm_") and is_any_admin_ckm(user.id) and msg.text:
        text = msg.text.strip()
        wiz = context.user_data.setdefault("ckm_wiz", {})
        uid = wiz.get("uid") or context.user_data.get("ckm_uid", user.id)

        if mode == "ckm_wiz_gb":
            if not text.isdigit():
                await msg.reply_text("❌ Введите целое число (0 = без лимита):")
                raise ApplicationHandlerStop
            wiz["gb"] = int(text)
            context.user_data["mode"] = "ckm_wiz_days"
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wstep_gb_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]])
            await msg.reply_text("📅 <b>Срок действия</b>\\n\\nВведите количество дней (0 = без срока):", parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if mode == "ckm_wiz_days":
            if not text.isdigit():
                await msg.reply_text("❌ Введите количество дней числом (0 = без срока):")
                raise ApplicationHandlerStop
            wiz["days"] = int(text)
            context.user_data["mode"] = "ckm_wiz_ip"
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wstep_days_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]])
            await msg.reply_text("💻 <b>Лимит устройств</b>\\n\\nВведите число от 1 до 999:", parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if mode == "ckm_wiz_ip":
            if not text.isdigit() or not (1 <= int(text) <= 999):
                await msg.reply_text("❌ Введите число от 1 до 999:")
                raise ApplicationHandlerStop
            wiz["ips"] = int(text)
            context.user_data["mode"] = None
            await show_ckm_confirm_screen(msg, context, edit=False)
            raise ApplicationHandlerStop

        if mode.startswith("ckm_edit_"):
            field = mode.split("ckm_edit_")[1]
            kid = context.user_data.get("ckm_kid", 0)
            context.user_data["mode"] = None
            now = datetime.now()
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    row = conn.execute("SELECT limit_gb, COALESCE(limit_ip, 1), expires_at FROM user_keys WHERE id = ?", (kid,)).fetchone()
                    if row:
                        cur_gb, cur_ip, cur_exp = row
                        if field == "days":
                            if text == "0":
                                new_exp = "Без срока"
                            elif text.startswith("+") or text.startswith("-"):
                                base_dt = now
                                if cur_exp and cur_exp != "Без срока":
                                    try:
                                        p = datetime.strptime(cur_exp, "%Y-%m-%d %H:%M:%S")
                                        if p > now:
                                            base_dt = p
                                    except Exception:
                                        pass
                                new_exp = max(now, base_dt + timedelta(days=int(text))).strftime("%Y-%m-%d %H:%M:%S")
                            else:
                                new_exp = (now + timedelta(days=int(text))).strftime("%Y-%m-%d %H:%M:%S")
                            conn.execute("UPDATE user_keys SET expires_at = ?, is_active = 1 WHERE id = ?", (new_exp, kid))
                        elif field == "gb":
                            val = max(0, (cur_gb or 0) + int(text)) if (text.startswith("+") or text.startswith("-")) else max(0, int(text))
                            conn.execute("UPDATE user_keys SET limit_gb = ? WHERE id = ?", (val, kid))
                        elif field == "ip":
                            val = max(1, (cur_ip or 1) + int(text)) if (text.startswith("+") or text.startswith("-")) else max(1, int(text))
                            conn.execute("UPDATE user_keys SET limit_ip = ? WHERE id = ?", (val, kid))
                        conn.commit()
            except Exception:
                await msg.reply_text("❌ Некорректное число.")
                raise ApplicationHandlerStop

            txt, kb = render_ckm_key_detail(kid, uid)
            await msg.reply_text(f"✅ Изменения сохранены!\\n\\n{txt}", parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if mode in ("ckm_bal_add", "ckm_bal_sub"):
            context.user_data["mode"] = None
            try:
                amt = abs(int(text))
                delta = amt if mode == "ckm_bal_add" else -amt
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("UPDATE users SET balance = MAX(0, COALESCE(balance, 0) + ?) WHERE user_id = ?", (delta, uid))
                    conn.commit()
            except Exception:
                await msg.reply_text("❌ Введите сумму целым числом.")
                raise ApplicationHandlerStop
            txt, kb = render_single_user_dossier(uid)
            await msg.reply_text(txt, parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if mode == "ckm_ref_coeff":
            context.user_data["mode"] = None
            try:
                coeff = max(0.1, float(text.replace(",", ".")))
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("UPDATE users SET ref_coeff = ? WHERE user_id = ?", (coeff, uid))
                    conn.commit()
            except Exception:
                await msg.reply_text("❌ Введите число (например 1.5).")
                raise ApplicationHandlerStop
            txt, kb = render_single_user_dossier(uid)
            await msg.reply_text(txt, parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

_orig_run_polling = Application.run_polling
def _patched_run_polling(self, *args, **kwargs):
    self.add_handler(CommandHandler("start", custom_start_command), group=-10)
    self.add_handler(CommandHandler("id", cmd_id_handler), group=-10)
    self.add_handler(CommandHandler("status", cmd_status_handler), group=-10)
    self.add_handler(CommandHandler("help", cmd_help_handler), group=-10)
    self.add_handler(
        CallbackQueryHandler(
            handle_all_custom_callbacks,
            pattern=r"^(start_|back_to_main|main_menu|ref_program|client_ref|client_my_keys|ckey_|key_open_|mykey_|cms_|ckm_)"
        ),
        group=-10
    )
    self.add_handler(MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.COMMAND, handle_all_custom_messages), group=-10)
    return _orig_run_polling(self, *args, **kwargs)

Application.run_polling = _patched_run_polling
'''

code = code.rstrip() + "\n" + unified_module + "\n"

with open(bot_path, "w", encoding="utf-8") as f:
    f.write(code)

print("✅ Полная сборка всех экранов успешно записана в bot.py!")
