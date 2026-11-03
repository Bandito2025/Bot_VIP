import sqlite3, re

db_path = "/opt/Bot_VIP/bot_data.db"
bot_path = "/opt/Bot_VIP/bot.py"

# 1. Записываем дефолтный шаблон главной страницы с макросом %тарифы% (если ещё не задан)
default_main_text = (
    "🔐 <b>Добро пожаловать в VPN-бот!</b>\n\n"
    "Быстрый, безопасный и анонимный доступ к интернету.\n"
    "Без логов, без ограничений, без проблем! 🚀\n\n"
    "%тарифы%\n\n"
    "✍️ <a href='https://telegra.ph/Polzovatelskoe-soglashenie-01-01'>ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ</a> ✍️\n\n"
    "✍️ <a href='https://telegra.ph/Politika-konfidencialnosti-01-01'>ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ</a> ✍️"
)

with sqlite3.connect(db_path) as conn:
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('cms_main_text', ?)", (default_main_text,))
    conn.commit()

with open(bot_path, "r", encoding="utf-8") as f:
    code = f.read()

# 2. Добавляем кнопку "✏️ Редактирование текстов" в меню настроек бота (render_bot_settings_main_screen)
if "cms_open_menu" not in code:
    code = re.sub(
        r'(def render_bot_settings_main_screen\(\).*?InlineKeyboardMarkup\(\[\s*)',
        r'\1[InlineKeyboardButton("✏️ Редактирование текстов и медиа", callback_data="cms_open_menu")],\n        ',
        code,
        count=1,
        flags=re.DOTALL
    )

# 3. Заменяем старый блок приветствия на полноценную систему управления текстами и медиа из настроек
code = re.sub(r"# =+\n# 🔵 КНОПКА \"МЕНЮ\".*", "", code, flags=re.DOTALL)

cms_module = '''
# ==============================================================================
# 🔵 КНОПКА "МЕНЮ", РЕДАКТОР ТЕКСТОВ/МЕДИА В НАСТРОЙКАХ И ЭКРАН /start
# ==============================================================================
import os
from telegram import BotCommand, MenuButtonCommands, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

CMS_SECTIONS = {
    "main": ("📝 Главная страница", "cms_main_text", "cms_main_media"),
    "help": ("📝 Справка (текст)", "cms_help_text", "cms_help_media"),
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
                lines.append(f"• {name} — <b>{rub} ₽</b>")
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
        rows.append([
            InlineKeyboardButton("⚙️ Админ-панель", callback_data="start_open_admin"),
            InlineKeyboardButton("✏️ Тексты и Баннер", callback_data="cms_open_menu")
        ])

    return caption, InlineKeyboardMarkup(rows)

def render_cms_main_menu():
    txt = "✏️ <b>Редактирование текстов</b>\\n\\nВыберите, что хотите изменить:"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Главная страница", callback_data="cms_edit_main")],
        [InlineKeyboardButton("📝 Справка (текст)", callback_data="cms_edit_help")],
        [InlineKeyboardButton("📝 Текст перед оплатой", callback_data="cms_edit_prepay")],
        [InlineKeyboardButton("📝 Текст выдачи ключа", callback_data="cms_edit_keyout")],
        [InlineKeyboardButton("📢 Ссылка: Новости", callback_data="cms_edit_news")],
        [InlineKeyboardButton("💬 Ссылка: Поддержка", callback_data="cms_edit_support")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="admin_bot_settings")]
    ])
    return txt, kb

async def send_cms_section_preview(message, sec_key: str, edit: bool = False):
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
            cur_text = f"<i>({title} пока не задан)</i>"

    kb_rows = [
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="cms_open_menu"),
            InlineKeyboardButton("🏠 На главную", callback_data="start_back_main")
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

    if edit:
        try:
            await message.edit_text(cur_text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
            return
        except Exception:
            pass
    await message.reply_text(cur_text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)

async def custom_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["mode"] = None
    if "ensure_user" in globals():
        try:
            ensure_user(user.id, user.username or "", user.first_name or "User")
        except Exception:
            pass

    caption, kb = build_custom_start_content(user.id)
    banner_file_id = get_setting("cms_main_media", "") or get_setting("welcome_banner_id", "")

    msg = update.effective_message
    try:
        if banner_file_id:
            await msg.reply_photo(photo=banner_file_id, caption=caption, parse_mode="HTML", reply_markup=kb)
        else:
            await msg.reply_text(caption, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
    except Exception:
        await msg.reply_text(caption, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)

    raise ApplicationHandlerStop

async def handle_cms_and_start_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data

    if data == "cms_noop":
        await query.answer("Просто отправьте в чат фото с подписью или новый текст!", show_alert=True)
        raise ApplicationHandlerStop

    await query.answer()

    if data == "cms_open_menu":
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
        if not is_any_admin_ckm(user.id):
            return
        sec_key = data.split("_", 2)[2]
        if sec_key not in CMS_SECTIONS:
            return
        context.user_data["mode"] = f"cms_wait_{sec_key}"
        await send_cms_section_preview(query.message, sec_key, edit=False)
        raise ApplicationHandlerStop

    if data.startswith("cms_delmedia_"):
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
        await send_cms_section_preview(query.message, sec_key, edit=False)
        raise ApplicationHandlerStop

    if data == "start_back_main":
        context.user_data["mode"] = None
        caption, kb = build_custom_start_content(user.id)
        banner_file_id = get_setting("cms_main_media", "") or get_setting("welcome_banner_id", "")
        if banner_file_id:
            await query.message.reply_photo(photo=banner_file_id, caption=caption, parse_mode="HTML", reply_markup=kb)
        else:
            await query.message.reply_text(caption, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
        raise ApplicationHandlerStop

    if data == "start_ref_link":
        bot_me = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_me.username}?start=ref_{user.id}"
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT ref_count, ref_bonus_days FROM users WHERE user_id = ?", (user.id,)).fetchone()
            r_cnt, r_days = (row[0] or 0, row[1] or 0) if row else (0, 0)
        txt = (
            f"🔗 <b>Ваша реферальная программа</b>\\n\\n"
            f"Приглашайте друзей по вашей личной ссылке и получайте бонусные дни подписки!\\n\\n"
            f"👥 Приглашено друзей: <b>{r_cnt} чел.</b>\\n"
            f"🎁 Получено бонусов: <b>+{r_days} дн.</b>\\n\\n"
            f"👇 <b>Ваша ссылка для приглашения:</b>\\n"
            f"<code>{ref_link}</code>"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ В главное меню", callback_data="start_back_main")]])
        await query.message.reply_text(txt, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    if data == "start_help_box":
        help_txt = get_setting("cms_help_text", "") or (
            "❓ <b>Справка и помощь по подключению</b>\\n\\n"
            "1️⃣ Нажмите <b>«💳 Купить ключ»</b> или <b>«🎁 Пробная подписка»</b>.\\n"
            "2️⃣ Скопируйте полученный ключ или ссылку подписки в разделе <b>«🔑 Мои ключи»</b>.\\n"
            "3️⃣ Вставьте ключ в приложение <b>Happ</b>, <b>v2rayTun</b>, <b>Hiddify</b> или <b>Streisand</b>."
        )
        help_media = get_setting("cms_help_media", "")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ В главное меню", callback_data="start_back_main")]])
        if help_media:
            await query.message.reply_photo(photo=help_media, caption=help_txt, parse_mode="HTML", reply_markup=kb)
        else:
            await query.message.reply_text(help_txt, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
        raise ApplicationHandlerStop

    if data == "start_open_admin":
        if not is_any_admin_ckm(user.id):
            return
        if "render_admin_main_screen" in globals():
            txt, kb = render_admin_main_screen()
            await query.message.reply_text(txt, parse_mode="HTML", reply_markup=kb)
        elif "admin_command" in globals():
            await admin_command(update, context)
        raise ApplicationHandlerStop

async def handle_cms_message_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    if not mode or not mode.startswith("cms_wait_"):
        return
    user = update.effective_user
    if not is_any_admin_ckm(user.id):
        return

    sec_key = mode.split("cms_wait_", 1)[1]
    if sec_key not in CMS_SECTIONS:
        return

    title, text_key, media_key = CMS_SECTIONS[sec_key]
    msg = update.effective_message

    # Сохраняем HTML-форматирование (жирный шрифт, ссылки и т.д.), если оно есть в сообщении
    new_text = msg.caption_html if msg.photo and msg.caption else (msg.text_html if msg.text else "")

    if msg.photo and media_key:
        file_id = msg.photo[-1].file_id
        set_setting(media_key, file_id)
        if sec_key == "main":
            set_setting("welcome_banner_id", file_id)

    if new_text:
        set_setting(text_key, new_text)

    await msg.reply_text(f"✅ Раздел <b>{title}</b> успешно обновлён!", parse_mode="HTML")
    await send_cms_section_preview(msg, sec_key, edit=False)
    raise ApplicationHandlerStop

async def cmd_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await update.effective_message.reply_text(
        f"🆔 Ваш Telegram ID: <code>{u.id}</code>\\n"
        f"👤 Username: @{u.username or 'нет'}",
        parse_mode="HTML"
    )
    raise ApplicationHandlerStop

async def cmd_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    with sqlite3.connect(DB_PATH) as conn:
        srvs = conn.execute("SELECT COUNT(*) FROM servers WHERE is_active = 1").fetchone()[0]
        keys = conn.execute("SELECT COUNT(*) FROM user_keys WHERE user_id = ? AND is_active = 1", (u.id,)).fetchone()[0]
    await update.effective_message.reply_text(
        f"🟢 <b>Статус бота: Работает в штатном режиме</b>\\n\\n"
        f"🖥 Активных серверов: <b>{srvs} шт.</b>\\n"
        f"🔑 Ваших активных ключей: <b>{keys} шт.</b>",
        parse_mode="HTML"
    )
    raise ApplicationHandlerStop

async def cmd_help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "ℹ️ <b>Справка по командам бота:</b>\\n\\n"
        "/start — Показать главное меню\\n"
        "/help — Справка по боту\\n"
        "/status — Проверить статус бота и ключей\\n"
        "/id — Показать ваш Telegram ID",
        parse_mode="HTML"
    )
    raise ApplicationHandlerStop

_orig_run_polling = Application.run_polling
def _patched_run_polling(self, *args, **kwargs):
    self.add_handler(CommandHandler("start", custom_start_command), group=-2)
    self.add_handler(CommandHandler("id", cmd_id_handler), group=-2)
    self.add_handler(CommandHandler("status", cmd_status_handler), group=-2)
    self.add_handler(CommandHandler("help", cmd_help_handler), group=-2)
    self.add_handler(CallbackQueryHandler(handle_cms_and_start_callbacks, pattern=r"^(cms_|start_)"), group=-2)
    self.add_handler(MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.COMMAND, handle_cms_message_input), group=-3)
    if "handle_ckm_callback" in globals():
        self.add_handler(CallbackQueryHandler(handle_ckm_callback, pattern=r"^ckm_"), group=-2)
    if "handle_ckm_text_input" in globals():
        self.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ckm_text_input), group=-2)
    return _orig_run_polling(self, *args, **kwargs)

Application.run_polling = _patched_run_polling
'''

code = code.rstrip() + "\n\n" + cms_module + "\n"

with open(bot_path, "w", encoding="utf-8") as f:
    f.write(code)

print("✅ Редактор текстов и медиа через Настройки успешно установлен!")
