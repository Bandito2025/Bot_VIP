import sqlite3, re

db_path = "/opt/Bot_VIP/bot_data.db"
bot_path = "/opt/Bot_VIP/bot.py"

# 1. Записываем тарифы со скриншота в БД (если нужно)
with sqlite3.connect(db_path) as conn:
    try:
        conn.execute("DELETE FROM tariffs")
        tariffs_data = [
            ("Стандарт", "📱 30 Дней 1 Устр.", 30, 200, 100),
            ("Стандарт", "📱 60 Дней 1 Устр.", 60, 350, 175),
            ("Стандарт", "📱 90 Дней 1 Устр.", 90, 500, 250),
            ("Стандарт", "📱 180 Дней 1 Устр.", 180, 999, 500),
            ("Стандарт", "📱 365 Дней 1 Устр.", 365, 1799, 900),
            ("Акции", "📱 Акция 30дней 2Устроиства", 30, 150, 75),
            ("Акции", "📱 Акция 60дней 2Устроиства", 60, 250, 125),
        ]
        for g_name, name, days, rub, stars in tariffs_data:
            conn.execute(
                "INSERT INTO tariffs (group_name, name, days, price_rub, price_stars, is_active) VALUES (?, ?, ?, ?, ?, 1)",
                (g_name, name, days, rub, stars)
            )
        conn.commit()
    except Exception as e:
        print("Инфо по тарифам:", e)

with open(bot_path, "r", encoding="utf-8") as f:
    code = f.read()

# Очищаем старый перехватчик, если он есть
code = re.sub(r"# =+\n# 🔵 КНОПКА \"МЕНЮ\".*", "", code, flags=re.DOTALL)

welcome_module = '''
# ==============================================================================
# 🔵 КНОПКА "МЕНЮ", НОВЫЙ ЭКРАН /start С БАННЕРОМ И КАСТОМНЫЕ ОБРАБОТЧИКИ
# ==============================================================================
import os
from telegram import BotCommand, MenuButtonCommands, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

def build_custom_start_content(user_id: int):
    # Ссылки на документы (можно поменять в настройках БД или прямо тут)
    tos_url = get_setting("tos_url", "https://telegra.ph/Polzovatelskoe-soglashenie-01-01")
    priv_url = get_setting("privacy_url", "https://telegra.ph/Politika-konfidencialnosti-01-01")

    caption = (
        "🔐 <b>Добро пожаловать в VPN-бот!</b>\\n\\n"
        "Быстрый, безопасный и анонимный доступ к интернету.\\n"
        "Без логов, без ограничений, без проблем! 🚀\\n\\n"
        "📋 <b>Тарифы:</b>\\n"
        "• 📱 30 Дней 1 Устр. — <b>200 ₽</b>\\n"
        "• 📱 60 Дней 1 Устр. — <b>350 ₽</b>\\n"
        "• 📱 90 Дней 1 Устр. — <b>500 ₽</b>\\n"
        "• 📱 180 Дней 1 Устр. — <b>999 ₽</b>\\n"
        "• 📱 365 Дней 1 Устр. — <b>1799 ₽</b>\\n"
        "• 📱 Акция 30дней 2Устроиства — <b>150 ₽</b>\\n"
        "• 📱 Акция 60дней 2Устроиства — <b>250 ₽</b>\\n\\n"
        f"✍️ <a href='{tos_url}'>ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ</a> ✍️\\n\\n"
        f"✍️ <a href='{priv_url}'>ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ</a> ✍️"
    )

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

async def custom_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Регистрируем пользователя стандартной функцией бота, если она есть
    if "ensure_user" in globals():
        try:
            ensure_user(user.id, user.username or "", user.first_name or "User")
        except Exception:
            pass

    caption, kb = build_custom_start_content(user.id)
    banner_file_id = get_setting("welcome_banner_id", "")
    banner_path = "/opt/Bot_VIP/welcome.jpg"

    msg = update.effective_message
    try:
        if banner_file_id:
            await msg.reply_photo(photo=banner_file_id, caption=caption, parse_mode="HTML", reply_markup=kb)
        elif os.path.exists(banner_path):
            with open(banner_path, "rb") as ph:
                await msg.reply_photo(photo=ph, caption=caption, parse_mode="HTML", reply_markup=kb)
        else:
            await msg.reply_text(caption, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
    except Exception:
        await msg.reply_text(caption, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)

    raise ApplicationHandlerStop

async def handle_start_extra_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    await query.answer()

    if data == "start_back_main":
        caption, kb = build_custom_start_content(user.id)
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
        txt = (
            "❓ <b>Справка и помощь по подключению</b>\\n\\n"
            "1️⃣ Нажмите <b>«💳 Купить ключ»</b> или <b>«🎁 Пробная подписка»</b>.\\n"
            "2️⃣ Скопируйте полученный ключ или ссылку подписки в разделе <b>«🔑 Мои ключи»</b>.\\n"
            "3️⃣ Вставьте ключ в приложение <b>Happ</b>, <b>v2rayTun</b>, <b>Hiddify</b> или <b>Streisand</b>.\\n\\n"
            "По всем вопросам обращайтесь в поддержку через меню бота."
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ В главное меню", callback_data="start_back_main")]])
        await query.message.reply_text(txt, parse_mode="HTML", reply_markup=kb)
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

async def save_welcome_banner_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_any_admin_ckm(user.id):
        return
    msg = update.effective_message
    if msg and msg.photo and msg.caption and msg.caption.strip().lower() == "/setbanner":
        file_id = msg.photo[-1].file_id
        set_setting("welcome_banner_id", file_id)
        await msg.reply_text("✅ Картинка-баннер для приветствия /start успешно сохранена! Нажмите /start для проверки.")
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
    self.add_handler(MessageHandler(filters.PHOTO, save_welcome_banner_photo), group=-2)
    self.add_handler(CallbackQueryHandler(handle_start_extra_callbacks, pattern=r"^start_"), group=-2)
    if "handle_ckm_callback" in globals():
        self.add_handler(CallbackQueryHandler(handle_ckm_callback, pattern=r"^ckm_"), group=-2)
    if "handle_ckm_text_input" in globals():
        self.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ckm_text_input), group=-2)
    return _orig_run_polling(self, *args, **kwargs)

Application.run_polling = _patched_run_polling
'''

code = code.rstrip() + "\n\n" + welcome_module + "\n"

with open(bot_path, "w", encoding="utf-8") as f:
    f.write(code)

print("✅ Новое меню /start, тарифы и кнопки успешно установлены в конец bot.py!")
