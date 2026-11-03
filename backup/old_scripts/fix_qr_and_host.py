import sqlite3

db_path = "/opt/Bot_VIP/bot_data.db"
bot_path = "/opt/Bot_VIP/bot.py"

# 1. Исправляем 127.0.0.1 в базе данных (в таблицах servers и user_keys) на реальный домен pl.svoii-vpn.online
with sqlite3.connect(db_path) as conn:
    conn.execute("UPDATE user_keys SET config_text = REPLACE(config_text, '127.0.0.1', 'pl.svoii-vpn.online') WHERE config_text LIKE '%127.0.0.1%'")
    try:
        conn.execute("UPDATE servers SET host = 'pl.svoii-vpn.online' WHERE host = '127.0.0.1' OR host = 'localhost'")
    except Exception:
        pass
    conn.commit()

with open(bot_path, "r", encoding="utf-8") as f:
    code = f.read()

# Заменяем fallback 127.0.0.1 в самом коде bot.py, если он там прописан
code = code.replace("@127.0.0.1:", "@pl.svoii-vpn.online:").replace("host=127.0.0.1", "host=pl.svoii-vpn.online")

# 2. Обновляем ckey_sub_, чтобы он СРАЗУ отправлял фото с QR-кодом + текст подписки в caption
old_sub_block = '''    if data.startswith("ckey_sub_"):
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
        raise ApplicationHandlerStop'''

new_sub_block = '''    if data.startswith("ckey_sub_"):
        await query.answer()
        kid = int(data.split("_")[-1])
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT user_id, key_name, sub_id, config_text, location_name FROM user_keys WHERE id = ?", (kid,)).fetchone()
        if not row:
            return
        k_uid, kname, sub_id, cfg_txt, loc = row
        sub_prefix = get_setting("sub_domain_prefix", "") or "https://pl.svoii-vpn.online:2096/sub"
        sub_url = f"{sub_prefix.rstrip('/')}/{sub_id}"

        clean_lines = [ln.strip().replace("127.0.0.1", "pl.svoii-vpn.online") for ln in (cfg_txt or "").splitlines() if ln.strip().startswith(("vless://", "vmess://", "trojan://", "ss://"))]
        vless_block = "\\n".join(clean_lines) if clean_lines else (cfg_txt or "").replace("127.0.0.1", "pl.svoii-vpn.online")
        qr_payload = clean_lines[0] if clean_lines else sub_url

        txt = (
            f"📋 <b>Подписка для {html.escape(kname or f'Ключ #{kid}')}</b>\\n\\n"
            f"🔗 <b>Ссылка подписки (для Happ / v2rayTun / Hiddify):</b>\\n"
            f"<code>{sub_url}</code>\\n\\n"
            f"🔐 <b>Прямой ключ подключения (нажмите, чтобы скопировать):</b>\\n"
            f"<code>{html.escape(vless_block)}</code>"
        )
        back_cb = f"ckm_kview_{kid}_{k_uid}" if (is_any_admin_ckm(user.id) and user.id != k_uid) else f"ckey_view_{kid}"
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⬅️ Назад к ключу", callback_data=back_cb),
                InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")
            ]
        ])

        # Генерируем QR-код в памяти и отправляем СРАЗУ картинкой с текстом
        import io
        qr_buf = None
        try:
            if "generate_qr_image_bytes" in globals():
                qr_buf = generate_qr_image_bytes(qr_payload)
            else:
                import qrcode
                qr = qrcode.QRCode(version=1, box_size=10, border=3)
                qr.add_data(qr_payload)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                qr_buf = io.BytesIO()
                img.save(qr_buf, format="PNG")
                qr_buf.seek(0)
        except Exception:
            qr_buf = None

        try:
            await query.message.delete()
        except Exception:
            pass

        if qr_buf:
            await context.bot.send_photo(chat_id=user.id, photo=qr_buf, caption=txt, parse_mode="HTML", reply_markup=kb)
        else:
            await context.bot.send_message(chat_id=user.id, text=txt, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
        raise ApplicationHandlerStop'''

code = code.replace(old_sub_block, new_sub_block)

# 3. Также делаем так, чтобы возврат "⬅️ Назад к ключу" (ckey_view_ и ckm_kview_) корректно работал после фото с QR-кодом
old_ckey_view = '''    if data.startswith(("ckey_view_", "key_open_", "mykey_", "key_info_", "key_manage_", "view_key_", "u_key_")):
        await query.answer()
        kid = int(data.split("_")[-1])
        txt, kb = render_client_single_key_screen(kid, user.id)
        try:
            await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await query.message.reply_text(txt, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop'''

new_ckey_view = '''    if data.startswith(("ckey_view_", "key_open_", "mykey_", "key_info_", "key_manage_", "view_key_", "u_key_")):
        await query.answer()
        kid = int(data.split("_")[-1])
        txt, kb = render_client_single_key_screen(kid, user.id)
        if query.message and query.message.photo:
            try:
                await query.message.delete()
            except Exception:
                pass
            await context.bot.send_message(chat_id=user.id, text=txt, parse_mode="HTML", reply_markup=kb)
        else:
            try:
                await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
            except Exception:
                await query.message.reply_text(txt, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop'''

code = code.replace(old_ckey_view, new_ckey_view)

old_ckm_kview = '''        if data.startswith("ckm_kview_"):
            _, _, kid_s, uid_s = data.split("_")
            txt, kb = render_ckm_key_detail(int(kid_s), int(uid_s))
            await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop'''

new_ckm_kview = '''        if data.startswith("ckm_kview_"):
            _, _, kid_s, uid_s = data.split("_")
            txt, kb = render_ckm_key_detail(int(kid_s), int(uid_s))
            if query.message and query.message.photo:
                try:
                    await query.message.delete()
                except Exception:
                    pass
                await context.bot.send_message(chat_id=user.id, text=txt, parse_mode="HTML", reply_markup=kb)
            else:
                await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop'''

code = code.replace(old_ckm_kview, new_ckm_kview)

with open(bot_path, "w", encoding="utf-8") as f:
    f.write(code)

print("✅ QR-код встроен прямо в сообщение подписки, а адрес 127.0.0.1 заменен на pl.svoii-vpn.online!")
