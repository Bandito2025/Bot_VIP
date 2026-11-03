import re, asyncio
from telegram import Bot, BotCommand, MenuButtonCommands

bot_path = "/opt/Bot_VIP/bot.py"
with open(bot_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Мгновенно регистрируем кнопку "Меню" и список команд через API Telegram
async def register_now():
    env_path = "/opt/Bot_VIP/.env"
    token = ""
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
        print("✅ Кнопка 'Меню' и команды зарегистрированы в Telegram API!")

asyncio.run(register_now())

# 2. Встраиваем обработчики команд /help, /status, /id и автоустановку меню в bot.py
menu_module = '''
# ==============================================================================
# 🔵 КНОПКА "МЕНЮ" И КОМАНДЫ (/start, /help, /status, /id)
# ==============================================================================
from telegram import BotCommand, MenuButtonCommands

async def cmd_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await update.message.reply_text(
        f"🆔 Ваш Telegram ID: <code>{u.id}</code>\\n"
        f"👤 Username: @{u.username or 'нет'}",
        parse_mode="HTML"
    )

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

async def cmd_help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ <b>Справка по командам бота:</b>\\n\\n"
        "/start — Показать главное меню\\n"
        "/help — Справка по боту\\n"
        "/status — Проверить статус бота и ключей\\n"
        "/id — Показать ваш Telegram ID",
        parse_mode="HTML"
    )

async def setup_bot_menu_commands(app):
    cmds = [
        BotCommand("start", "Показать главное меню"),
        BotCommand("help", "Справка по боту"),
        BotCommand("status", "Проверить статус бота"),
        BotCommand("id", "Показать ваш Telegram ID"),
    ]
    await app.bot.set_my_commands(cmds)
    await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
'''

if "def cmd_id_handler" not in code:
    code = code.replace("def main()", menu_module + "\ndef main()", 1)
    hook_target = "app.run_polling("
    hook_inject = """app.add_handler(CommandHandler("id", cmd_id_handler), group=-1)
    app.add_handler(CommandHandler("status", cmd_status_handler), group=-1)
    app.add_handler(CommandHandler("help", cmd_help_handler), group=-1)
    app.run_polling("""
    code = code.replace(hook_target, hook_inject, 1)

with open(bot_path, "w", encoding="utf-8") as f:
    f.write(code)

print("✅ Обработчики /help, /status, /id успешно добавлены в bot.py!")
