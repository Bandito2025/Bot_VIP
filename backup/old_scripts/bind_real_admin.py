import re

bot_path = "/opt/Bot_VIP/bot.py"
with open(bot_path, "r", encoding="utf-8") as f:
    code = f.read()

old_block_pattern = r'if data == "start_open_admin":.*?raise ApplicationHandlerStop'

new_block = '''if data == "start_open_admin":
        await query.answer()
        if not is_any_admin_ckm(user.id):
            await query.answer("⛔ Нет прав администратора.", show_alert=True)
            raise ApplicationHandlerStop
        try:
            await query.message.delete()
        except Exception:
            pass
        txt = build_admin_dashboard_text()
        kb = admin_dashboard_keyboard()
        kb_rows = [list(row) for row in kb.inline_keyboard]
        if not any(b.callback_data == "cms_open_menu" for r in kb_rows for b in r):
            kb_rows.append([InlineKeyboardButton("✏️ Редактирование текстов и баннеров", callback_data="cms_open_menu")])
        if not any(b.callback_data == "start_back_main" for r in kb_rows for b in r):
            kb_rows.append([InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")])
        await context.bot.send_message(chat_id=user.id, text=txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))
        raise ApplicationHandlerStop'''

code_updated = re.sub(old_block_pattern, new_block, code, flags=re.DOTALL)

with open(bot_path, "w", encoding="utf-8") as f:
    f.write(code_updated)

print("✅ Полный дашборд админки успешно привязан!")
