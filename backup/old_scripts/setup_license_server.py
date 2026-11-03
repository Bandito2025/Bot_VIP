import sqlite3, secrets, re

db_path = "/opt/Bot_VIP/bot_data.db"
bot_path = "/opt/Bot_VIP/bot.py"

# 1. Создаем таблицу лицензий и сразу выпускаем вечный Мастер-ключ для тебя
with sqlite3.connect(db_path) as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lic_key TEXT UNIQUE,
            buyer_note TEXT DEFAULT '',
            bound_ip TEXT DEFAULT '',
            bound_admin_id TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "INSERT OR IGNORE INTO bot_licenses (lic_key, buyer_note, is_active) VALUES ('VIP-MASTER-OWNER-777', 'Мой Мастер-Ключ (Без лимита IP)', 1)"
    )
    conn.commit()

with open(bot_path, "r", encoding="utf-8") as f:
    code = f.read()

# 2. Добавляем HTTP-эндпоинт /api/verify_license в существующий веб-агрегатор (порт 2096)
if "/api/verify_license" not in code:
    target_sub_route = 'if path.startswith("/sub/"):'
    license_route_code = '''if path.startswith("/api/verify_license"):
                from urllib.parse import parse_qs, urlparse
                qs = parse_qs(urlparse(self.path).query)
                l_key = (qs.get("key", [""])[0]).strip()
                c_ip = (qs.get("ip", [""])[0]).strip() or self.client_address[0]
                c_adm = (qs.get("admin_id", [""])[0]).strip()
                with sqlite3.connect(DB_PATH) as conn:
                    row = conn.execute("SELECT id, bound_ip, is_active FROM bot_licenses WHERE lic_key = ?", (l_key,)).fetchone()
                    if not row or row[2] == 0:
                        self.send_response(403)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(b'{"status":"error","msg":"Invalid or disabled license key"}')
                        return
                    lic_id, b_ip, _ = row
                    # Мастер-ключ работает на любых IP, обычная лицензия привязывается к первому IP покупателя
                    if l_key != "VIP-MASTER-OWNER-777":
                        if b_ip and b_ip != c_ip:
                            self.send_response(403)
                            self.send_header("Content-Type", "application/json")
                            self.end_headers()
                            self.wfile.write(b'{"status":"error","msg":"License already bound to another server IP"}')
                            return
                        if not b_ip:
                            conn.execute("UPDATE bot_licenses SET bound_ip = ?, bound_admin_id = ? WHERE id = ?", (c_ip, c_adm, lic_id))
                            conn.commit()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok","msg":"License verified"}')
                return

            if path.startswith("/sub/"):'''
    code = code.replace(target_sub_route, license_route_code, 1)

# 3. Добавляем управление лицензиями в админку (кнопка + генерация ключей)
if "lic_admin_menu" not in code:
    code = code.replace(
        'InlineKeyboardButton("✏️ Редактирование текстов и баннеров", callback_data="cms_open_menu")',
        'InlineKeyboardButton("✏️ Редактирование текстов и баннеров", callback_data="cms_open_menu")],\n                [InlineKeyboardButton("🔐 Лицензии на бота (Продажи)", callback_data="lic_admin_menu")'
    )

    lic_handlers = '''
    # 8. Управление лицензиями проданных копий бота
    if data == "lic_admin_menu":
        await query.answer()
        if not is_any_admin_ckm(user.id):
            return
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("SELECT id, lic_key, bound_ip, bound_admin_id, is_active FROM bot_licenses ORDER BY id DESC LIMIT 15").fetchall()
        lines = ["🔐 <b>Управление лицензиями Bot_VIP</b>\\n"]
        kb_rows = [[InlineKeyboardButton("➕ Сгенерировать новый ключ продажи", callback_data="lic_gen_new")]]
        for lid, lkey, bip, badm, lact in rows:
            st = "🟢" if lact else "🔴"
            ip_info = f"IP: {bip} (ID: {badm})" if bip else "Свободен (ждет установки)"
            lines.append(f"{st} <code>{lkey}</code> — {ip_info}")
            if lkey != "VIP-MASTER-OWNER-777":
                kb_rows.append([
                    InlineKeyboardButton(f"{'🔴 Откл' if lact else '🟢 Вкл'} {lkey[:12]}...", callback_data=f"lic_tog_{lid}"),
                    InlineKeyboardButton("🔄 Сброс IP", callback_data=f"lic_rst_{lid}")
                ])
        kb_rows.append([InlineKeyboardButton("⬅️ В админ-панель", callback_data="start_open_admin")])
        await query.edit_message_text("\\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))
        raise ApplicationHandlerStop

    if data == "lic_gen_new":
        await query.answer("Ключ создан!")
        if not is_any_admin_ckm(user.id):
            return
        new_k = "VIP-" + "-".join(secrets.token_hex(2).upper() for _ in range(3))
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO bot_licenses (lic_key, is_active) VALUES (?, 1)", (new_k,))
            conn.commit()
        await query.message.reply_text(
            f"✅ <b>Новая лицензия для покупателя готова:</b>\\n\\n<code>{new_k}</code>\\n\\n"
            f"Передайте этот ключ клиенту — он введет его при установке бота одной командой.",
            parse_mode="HTML"
        )
        raise ApplicationHandlerStop

    if data.startswith("lic_tog_") or data.startswith("lic_rst_"):
        await query.answer("Обновлено!")
        lid = int(data.split("_")[-1])
        with sqlite3.connect(DB_PATH) as conn:
            if "lic_tog_" in data:
                conn.execute("UPDATE bot_licenses SET is_active = CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id = ?", (lid,))
            else:
                conn.execute("UPDATE bot_licenses SET bound_ip = '', bound_admin_id = '' WHERE id = ?", (lid,))
            conn.commit()
        query.data = "lic_admin_menu"
        await handle_all_custom_callbacks(update, context)
        raise ApplicationHandlerStop
'''
    target_anchor = '    # 7. Пошаговый мастер ключей'
    code = code.replace(target_anchor, lic_handlers + "\n" + target_anchor, 1)
    code = code.replace('pattern=r"^(start_|', 'pattern=r"^(lic_|start_|')

with open(bot_path, "w", encoding="utf-8") as f:
    f.write(code)

print("✅ Сервер лицензий и меню продаж успешно встроены в Bot_VIP!")
