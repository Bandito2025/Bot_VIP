import re
from urllib.parse import quote

bot_path = "/opt/Bot_VIP/bot.py"
with open(bot_path, "r", encoding="utf-8") as f:
    code = f.read()

pattern = r'if data\.startswith\("ckey_sub_"\):.*?raise ApplicationHandlerStop'

new_ckey_sub = '''if data.startswith("ckey_sub_"):
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

        import io
        from urllib.parse import quote as url_quote
        qr_photo = None
        try:
            import qrcode
            qr = qrcode.QRCode(version=1, box_size=10, border=3)
            qr.add_data(qr_payload)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            qr_photo = buf
        except Exception:
            try:
                if "generate_qr_image_bytes" in globals():
                    raw_qr = generate_qr_image_bytes(qr_payload)
                    qr_photo = io.BytesIO(raw_qr) if isinstance(raw_qr, bytes) else raw_qr
                    if hasattr(qr_photo, "seek"):
                        qr_photo.seek(0)
            except Exception:
                pass

        if not qr_photo:
            qr_photo = f"https://api.qrserver.com/v1/create-qr-code/?size=400x400&margin=15&data={url_quote(qr_payload)}"

        try:
            await query.message.delete()
        except Exception:
            pass

        try:
            await context.bot.send_photo(chat_id=user.id, photo=qr_photo, caption=txt, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await context.bot.send_message(chat_id=user.id, text=txt, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
        raise ApplicationHandlerStop'''

code_updated = re.sub(pattern, new_ckey_sub, code, flags=re.DOTALL)

with open(bot_path, "w", encoding="utf-8") as f:
    f.write(code_updated)

print("✅ Генератор QR-кодов успешно обновлён!")
