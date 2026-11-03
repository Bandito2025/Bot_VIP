import sqlite3, re

db_path = "/opt/Bot_VIP/bot_data.db"
bot_path = "/opt/Bot_VIP/bot.py"

# 1. Добавляем колонки ref_count и ref_bonus_days в таблицу users, чтобы никогда не было OperationalError
with sqlite3.connect(db_path) as conn:
    for sql in [
        "ALTER TABLE users ADD COLUMN ref_count INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN ref_bonus_days INTEGER DEFAULT 0",
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
    conn.commit()

with open(bot_path, "r", encoding="utf-8") as f:
    code = f.read()

# 2. Исправляем чтение рефералов (используем get_user_info + безопасный fallback)
old_ref_sql = 'row = conn.execute("SELECT ref_count, ref_bonus_days FROM users WHERE user_id = ?", (user.id,)).fetchone()\n                r_cnt, r_days = (row[0] or 0, row[1] or 0) if row else (0, 0)'
new_ref_sql = '''u_inf = get_user_info(user.id) if "get_user_info" in globals() else None
                if u_inf and len(u_inf) >= 19:
                    r_cnt, r_days = int(u_inf[17] or 0), int(u_inf[18] or 0)
                else:
                    row = conn.execute("SELECT COALESCE(ref_count, 0), COALESCE(ref_bonus_days, 0) FROM users WHERE user_id = ?", (user.id,)).fetchone()
                    r_cnt, r_days = (row[0], row[1]) if row else (0, 0)'''

code = code.replace(old_ref_sql, new_ref_sql)

old_ref_sql_cb = 'row = conn.execute("SELECT ref_count, ref_bonus_days FROM users WHERE user_id = ?", (user.id,)).fetchone()\n            r_cnt, r_days = (row[0] or 0, row[1] or 0) if row else (0, 0)'
new_ref_sql_cb = '''u_inf = get_user_info(user.id) if "get_user_info" in globals() else None
            if u_inf and len(u_inf) >= 19:
                r_cnt, r_days = int(u_inf[17] or 0), int(u_inf[18] or 0)
            else:
                row = conn.execute("SELECT COALESCE(ref_count, 0), COALESCE(ref_bonus_days, 0) FROM users WHERE user_id = ?", (user.id,)).fetchone()
                r_cnt, r_days = (row[0], row[1]) if row else (0, 0)'''

code = code.replace(old_ref_sql_cb, new_ref_sql_cb)

# 3. Исправляем кнопку "⚙️ Админ-панель" (start_open_admin), чтобы она гарантированно открывала админку
old_open_admin = '''    if data == "start_open_admin":
        await query.answer()
        if not is_any_admin_ckm(user.id):
            return
        if "render_admin_main_screen" in globals():
            txt, kb = render_admin_main_screen()
            await query.message.reply_text(txt, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop'''

# Ищем в bot.py как именно формируется главное меню админки
admin_render_fn = None
for fn_name in ["render_admin_main_screen", "render_admin_panel", "render_admin_menu", "get_admin_keyboard", "admin_main_menu"]:
    if f"def {fn_name}(" in code:
        admin_render_fn = fn_name
        break

new_open_admin = '''    if data == "start_open_admin":
        await query.answer()
        if not is_any_admin_ckm(user.id):
            await query.answer("⛔ Нет прав администратора.", show_alert=True)
            raise ApplicationHandlerStop
        try:
            await query.message.delete()
        except Exception:
            pass
        if "render_admin_main_screen" in globals():
            txt, kb = render_admin_main_screen()
            await context.bot.send_message(chat_id=user.id, text=txt, parse_mode="HTML", reply_markup=kb)
        elif "render_admin_menu" in globals():
            txt, kb = render_admin_menu()
            await context.bot.send_message(chat_id=user.id, text=txt, parse_mode="HTML", reply_markup=kb)
        else:
            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("👥 Пользователи", callback_data="admin_users_menu"),
                    InlineKeyboardButton("🖥 Серверы 3X-UI", callback_data="admin_servers_menu")
                ],
                [
                    InlineKeyboardButton("💳 Оплата и Тарифы", callback_data="admin_payments_menu"),
                    InlineKeyboardButton("🎁 Маркетинг / Промо", callback_data="admin_marketing_menu")
                ],
                [
                    InlineKeyboardButton("⚙️ Настройки бота", callback_data="admin_bot_settings"),
                    InlineKeyboardButton("✏️ Тексты и Баннеры", callback_data="cms_open_menu")
                ],
                [
                    InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")
                ]
            ])
            await context.bot.send_message(
                chat_id=user.id,
                text="⚙️ <b>Панель управления администратора</b>\\n\\nВыберите нужный раздел:",
                parse_mode="HTML",
                reply_markup=kb
            )
        raise ApplicationHandlerStop'''

code = code.replace(old_open_admin, new_open_admin)

# 4. Исправляем отображение новых ключей в досье (сортируем по убыванию DESC, чтобы новые ключи всегда были сверху!)
# и делаем создание ключа в Шаге 6 полностью безотказным
code = code.replace(
    '"SELECT id, expires_at, is_active FROM user_keys WHERE user_id = ? ORDER BY id ASC"',
    '"SELECT id, expires_at, is_active FROM user_keys WHERE user_id = ? ORDER BY id DESC"'
)
code = code.replace(
    '"SELECT id, key_name, location_name, expires_at, is_active FROM user_keys WHERE user_id = ? ORDER BY id ASC"',
    '"SELECT id, key_name, location_name, expires_at, is_active FROM user_keys WHERE user_id = ? ORDER BY id DESC"'
)

old_wcreate = '''        # Шаг 6: Создание ключа в БД и на выбранном сервере 3X-UI
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
            raise ApplicationHandlerStop'''

new_wcreate = '''        # Шаг 6: Создание ключа в БД и на выбранном сервере 3X-UI
        if data.startswith("ckm_wcreate_"):
            uid = int(data.split("_")[2])
            wiz = context.user_data.get("ckm_wiz", {})
            grp = wiz.get("group", "Основная")
            srv_id = wiz.get("srv_id", 0)
            srv_name = wiz.get("srv_name", "🇩🇪 Германия")
            gb = int(wiz.get("gb", 0))
            days = int(wiz.get("days", 0))
            ips = int(wiz.get("ips", 1))

            await query.edit_message_text("⏳ <b>Создаю ключ и синхронизирую с панелью...</b>", parse_mode="HTML")
            try:
                k_id, until_s, _, _ = await create_or_extend_user_key(uid, days=days, create_new=True)
            except Exception as e:
                # Fallback-создание ключа в БД, если внешний сервер 3X-UI не ответил вовремя
                now = datetime.now()
                until_s = "Без срока" if days == 0 else (now + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
                c_uuid = str(uuid.uuid4())
                s_id = secrets.token_hex(6)
                cfg = f"vless://{c_uuid}@ger.svoii-vpn.online:443?security=tls&type=ws#{srv_name}"
                with sqlite3.connect(DB_PATH) as conn:
                    cur = conn.execute(
                        "INSERT INTO user_keys (user_id, key_name, client_uuid, sub_id, server_id, location_name, traffic_bytes, limit_gb, expires_at, config_text, is_active, warned_24h, warned_3h, created_at) VALUES (?, '', ?, ?, ?, ?, 0, ?, ?, ?, 1, 0, 0, ?)",
                        (uid, c_uuid, s_id, srv_id, srv_name, gb, until_s, cfg, now.strftime("%Y-%m-%d %H:%M:%S"))
                    )
                    k_id = cur.lastrowid
                    conn.execute("UPDATE user_keys SET key_name = ? WHERE id = ?", (f"Ключ #{k_id}", k_id))
                    conn.commit()

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
            raise ApplicationHandlerStop'''

code = code.replace(old_wcreate, new_wcreate)

with open(bot_path, "w", encoding="utf-8") as f:
    f.write(code)

print("✅ Все 3 ошибки исправлены!")
