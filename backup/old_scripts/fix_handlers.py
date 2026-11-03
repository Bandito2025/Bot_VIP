import re

bot_path = "/opt/Bot_VIP/bot.py"
with open(bot_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Очищаем старые попытки вставки в main(), если они не сработали
code = re.sub(r"# =+\n# 🔵 КНОПКА \"МЕНЮ\".*?def main\(\)", "def main()", code, flags=re.DOTALL)
code = re.sub(r"\s*app\.add_handler\(CommandHandler\(\"id\".*?\n", "\n", code)
code = re.sub(r"\s*app\.add_handler\(CommandHandler\(\"status\".*?\n", "\n", code)
code = re.sub(r"\s*app\.add_handler\(CommandHandler\(\"help\".*?\n", "\n", code)
code = re.sub(r"\s*app\.add_handler\(CallbackQueryHandler\(handle_ckm_callback.*?\n", "\n", code)
code = re.sub(r"\s*app\.add_handler\(MessageHandler\(filters\.TEXT & ~filters\.COMMAND, handle_ckm_text_input\), group=-1\)\n", "\n", code)

# 2. Создаем универсальный авто-инжектор прямо в Application.run_polling
universal_hook = '''
# ==============================================================================
# 🔵 КНОПКА "МЕНЮ" И АВТО-РЕГИСТРАЦИЯ ВСЕХ КАСТОМНЫХ ОБРАБОТЧИКОВ
# ==============================================================================
from telegram import BotCommand, MenuButtonCommands
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

async def cmd_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await update.message.reply_text(
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
    await update.message.reply_text(
        f"🟢 <b>Статус бота: Работает в штатном режиме</b>\\n\\n"
        f"🖥 Активных серверов: <b>{srvs} шт.</b>\\n"
        f"🔑 Ваших активных ключей: <b>{keys} шт.</b>",
        parse_mode="HTML"
    )
    raise ApplicationHandlerStop

async def cmd_help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
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
    self.add_handler(CommandHandler("id", cmd_id_handler), group=-1)
    self.add_handler(CommandHandler("status", cmd_status_handler), group=-1)
    self.add_handler(CommandHandler("help", cmd_help_handler), group=-1)
    if "handle_ckm_callback" in globals():
        self.add_handler(CallbackQueryHandler(handle_ckm_callback, pattern=r"^ckm_"), group=-1)
    if "handle_ckm_text_input" in globals():
        self.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ckm_text_input), group=-1)
    return _orig_run_polling(self, *args, **kwargs)

Application.run_polling = _patched_run_polling
'''

# 3. Также проверяем, добавлена ли кнопка кастомных ключей в карточку пользователя
if "ckm_menu_" not in code:
    code = re.sub(
        r'(InlineKeyboardButton\("➕ Ключ \+30 дн\.",\s*callback_data=f"admin_uact_add30_\{uid\}"\)\s*\],)',
        r'\1\n        [\n            InlineKeyboardButton("⚙️ Управление ключами (Кастом / +/-)", callback_data=f"ckm_menu_{uid}")\n        ],',
        code,
        count=1
    )

if "_patched_run_polling" not in code:
    if "def main(" in code:
        code = code.replace("def main(", universal_hook + "\ndef main(", 1)
    else:
        code = code + "\n" + universal_hook

with open(bot_path, "w", encoding="utf-8") as f:
    f.write(code)

print("✅ Универсальный перехватчик команд и кнопок установлен!")
