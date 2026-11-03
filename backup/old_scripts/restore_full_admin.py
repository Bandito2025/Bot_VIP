import re

bot_path = "/opt/Bot_VIP/bot.py"
with open(bot_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Находим в bot.py оригинальную функцию или блок, который рендерит главное меню админки (по команде /admin или callback admin_main / admin_back)
# Проверим все функции, где есть кнопки админки
admin_funcs = re.findall(r'def ([a-zA-Z0-9_]*admin[a-zA-Z0-9_]*)\(', code)
print("Найденные функции админки в bot.py:", admin_funcs)

# 2. Заменяем обработчик start_open_admin так, чтобы он вызывал родную функцию админки из bot.py (например, admin_command или render_admin_panel)
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
        # Вызываем штатный обработчик /admin из bot.py, чтобы открыть ПОЛНУЮ админ-панель со всеми панелями
        for fn_name in ("admin_panel_command", "admin_command", "cmd_admin", "show_admin_panel", "open_admin_panel"):
            if fn_name in globals() and callable(globals()[fn_name]):
                await globals()[fn_name](update, context)
                raise ApplicationHandlerStop
        for r_name in ("render_admin_panel", "render_admin_main", "render_admin_dashboard", "build_admin_menu", "get_admin_main_kb"):
            if r_name in globals() and callable(globals()[r_name]):
                res = globals()[r_name](user.id) if r_name in ("render_admin_panel",) else globals()[r_name]()
                if isinstance(res, tuple) and len(res) == 2:
                    txt, kb = res
                    await context.bot.send_message(chat_id=user.id, text=txt, parse_mode="HTML", reply_markup=kb)
                    raise ApplicationHandlerStop
        raise ApplicationHandlerStop'''

code_updated = re.sub(old_block_pattern, new_block, code, flags=re.DOTALL)

with open(bot_path, "w", encoding="utf-8") as f:
    f.write(code_updated)

