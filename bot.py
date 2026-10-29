import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN or TOKEN == "your_telegram_bot_token_here":
    raise ValueError("Ошибка: BOT_TOKEN не задан! Создайте файл .env и укажите токен.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name if update.effective_user else "друг"
    await update.message.reply_text(f"Привет, {user}! Бот готов к работе.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Команды:\n/start - Начать\n/help - Помощь")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    print("Бот запущен...")
    app.run_polling()
