import os
import html
import uuid
import secrets
import sqlite3
import logging
import time as time_mod
from urllib.parse import quote
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationHandlerStop,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

logger = logging.getLogger("Bot_VIP.ProSuite")
DB_PATH = os.getenv("DB_PATH", "bot_data.db")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

NODE_STATES = {}
REISSUE_COOLDOWNS = {}

# Полный каталог приложений по платформам (Android, iOS, Windows, macOS)
APPS_CATALOG = {
    "android": {
        "title": "🤖 Android",
        "apps": {
            "v2box":    ("V2Box",    "https://play.google.com/store/apps/details?id=dev.hexasoftware.v2box", "Нажмите «Добавить» ниже или откройте V2Box → Configs → «+» → Import v2ray uri from clipboard."),
            "v2rayng":  ("V2RayNG",  "https://github.com/2dust/v2rayNG/releases/latest", "Нажмите «Добавить» или в V2RayNG нажмите «+» вверху → «Импорт профиля из буфера обмена»."),
            "singbox":  ("Sing-box", "https://play.google.com/store/apps/details?id=io.nekohasekai.sfa", "Откройте Sing-box → Profiles → New Profile → Type: Remote → вставьте ссылку подписки."),
            "v2raytun": ("V2RayTun", "https://play.google.com/store/apps/details?id=com.v2raytun.android", "Нажмите «Добавить» ниже или в V2RayTun нажмите «+» → «Импорт из буфера обмена»."),
            "happ":     ("Happ",     "https://play.google.com/store/apps/details?id=com.happproxy", "Нажмите «Добавить» или в приложении Happ нажмите «+» → «Вставить из буфера обмена»."),
            "incy":     ("Incy / Hiddify", "https://play.google.com/store/apps/details?id=app.hiddify.com", "Нажмите «Добавить» или в приложении нажмите «+ Новый профиль» → «Добавить из буфера».")
        }
    },
    "ios": {
        "title": "🍎 iOS (iPhone / iPad)",
        "apps": {
            "shadowrocket": ("Shadowrocket", "https://apps.apple.com/app/shadowrocket/id932747118", "Нажмите «Добавить» или в Shadowrocket нажмите «+» вверху → Type: Subscribe → вставьте URL подписки."),
            "v2box_ios":    ("V2Box",        "https://apps.apple.com/app/v2box-v2ray-client/id6446814690", "Откройте V2Box → вкладка Configs → «+» → Add Subscription → вставьте ссылку подписки."),
            "streisand":    ("Streisand",    "https://apps.apple.com/app/streisand/id6450534064", "Откройте Streisand → нажмите «+» → «Добавить из буфера» и включите тумблер подключения."),
            "v2raytun_ios": ("V2RayTun",     "https://apps.apple.com/app/v2raytun/id6476628951", "Откройте V2RayTun → нажмите «+» в правом верхнем углу → «Импорт из буфера»."),
            "happ_ios":     ("Happ",         "https://apps.apple.com/app/happ-proxy-utility/id6504287215", "Откройте Happ → нажмите «+» → «Добавить из буфера обмена» и нажмите большую кнопку включения."),
            "incy_ios":     ("Incy / Karing","https://apps.apple.com/app/karing/id6472431552", "Откройте приложение → Add Profile → Import from Clipboard и нажмите Connect.")
        }
    },
    "windows": {
        "title": "💻 Windows 10 / 11 (ПК)",
        "apps": {
            "hiddify_win": ("Hiddify (Windows)", "https://github.com/hiddify/hiddify-app/releases/latest", "Скачайте Hiddify-Windows-Setup.exe → нажмите «+ Новый профиль» → «Добавить из буфера обмена»."),
            "happ_win":    ("v2RayTun / Happ PC", "https://github.com/Happ-proxy/happ-desktop/releases", "Скачайте установщик для Windows → нажмите «+» → вставьте вашу ссылку подписки."),
            "clash_win":   ("Clash Verge Rev",   "https://github.com/clash-verge-rev/clash-verge-rev/releases/latest", "Откройте Clash Verge → Профили (Profiles) → вставьте ссылку подписки в поле URL → Импорт → включите System Proxy / TUN."),
            "flclash_win": ("FlClash",           "https://github.com/chen08209/FlClash/releases/latest", "Откройте FlClash → Profiles → «+» → URL → вставьте ссылку подписки и нажмите Start."),
            "karing_win":  ("Karing (Windows)",  "https://github.com/KaringX/karing/releases/latest", "Скачайте Karing для Windows → Add Profile → From Clipboard → включите переключатель."),
            "v2rayn_win":  ("v2rayN / Throne",   "https://github.com/2dust/v2rayN/releases/latest", "Скопируйте ссылку подписки → в окне v2rayN нажмите Ctrl+V → внизу включите «Системный прокси».")
        }
    },
    "macos": {
        "title": "🍏 macOS / Linux",
        "apps": {
            "hiddify_mac":   ("Hiddify (macOS / Linux)", "https://github.com/hiddify/hiddify-app/releases/latest", "Скачайте .dmg (macOS) или .AppImage (Linux) → «+ Новый профиль» → «Добавить из буфера»."),
            "streisand_mac": ("Streisand (Mac M1/M2/M3)", "https://apps.apple.com/app/streisand/id6450534064", "Установите из App Store → нажмите «+» → «Добавить из буфера обмена»."),
            "clash_mac":     ("Clash Verge Rev",         "https://github.com/clash-verge-rev/clash-verge-rev/releases/latest", "Установите .dmg → Profiles → вставьте ссылку подписки → включите TUN Mode."),
            "flclash_mac":   ("FlClash (macOS / Linux)", "https://github.com/chen08209/FlClash/releases/latest", "Установите FlClash → Profiles → «+» → Import from URL → вставьте ссылку."),
            "v2box_mac":     ("V2Box (macOS)",           "https://apps.apple.com/app/v2box-v2ray-client/id6446814690", "Установите V2Box из App Store → Configs → «+» → Add Subscription."),
            "karing_mac":    ("Karing (macOS)",          "https://github.com/KaringX/karing/releases/latest", "Установите Karing → Add Profile → Import from Clipboard.")
        }
    }
}

def init_pro_tables():
    with sqlite3.connect(DB_PATH) as conn:
        u_cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        for col, ctype in [
            ("balance_rub", "REAL DEFAULT 0"),
            ("auto_renew", "INTEGER DEFAULT 1"),
            ("ref_earned_rub", "REAL DEFAULT 0")
        ]:
            if col not in u_cols:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {ctype}")

        k_cols = [r[1] for r in conn.execute("PRAGMA table_info(user_keys)").fetchall()]
        for col, ctype in [
            ("is_frozen", "INTEGER DEFAULT 0"),
            ("frozen_at", "TEXT DEFAULT ''")
        ]:
            if col not in k_cols:
                conn.execute(f"ALTER TABLE user_keys ADD COLUMN {col} {ctype}")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS gift_cards (
                code TEXT PRIMARY KEY,
                days INTEGER DEFAULT 30,
                created_by INTEGER,
                is_claimed INTEGER DEFAULT 0,
                claimed_by INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('ext_load_enabled', '1')")
        conn.commit()

def get_wallet_data(user_id: int) -> tuple[float, int, float]:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT COALESCE(balance_rub, 0), COALESCE(auto_renew, 1), COALESCE(ref_earned_rub, 0) FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        return (float(row[0]), int(row[1]), float(row[2])) if row else (0.0, 1, 0.0)

def add_user_balance(user_id: int, amount_rub: float):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET balance_rub = COALESCE(balance_rub, 0) + ? WHERE user_id = ?", (amount_rub, user_id))
        conn.commit()

def credit_referral_cashback(buyer_id: int, payment_rub: float) -> tuple[int, float]:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT referred_by FROM users WHERE user_id = ?", (buyer_id,)).fetchone()
        if not row or not row[0]:
            return 0, 0.0
        inviter_id = int(row[0])
        cashback = round(payment_rub * 0.20, 2)
        conn.execute(
            "UPDATE users SET balance_rub = COALESCE(balance_rub, 0) + ?, ref_earned_rub = COALESCE(ref_earned_rub, 0) + ? WHERE user_id = ?",
            (cashback, cashback, inviter_id)
        )
        conn.commit()
        return inviter_id, cashback

def create_gift_certificate(creator_id: int, days: int = 30, cost_rub: float = 199.0) -> tuple[bool, str]:
    bal, _, _ = get_wallet_data(creator_id)
    if bal < cost_rub and creator_id != ADMIN_ID:
        return False, f"❌ Недостаточно средств на внутреннем балансе ({int(bal)} ₽ из {int(cost_rub)} ₽)."
    code = f"GIFT-{days}D-{secrets.token_hex(3).upper()}"
    with sqlite3.connect(DB_PATH) as conn:
        if creator_id != ADMIN_ID:
            conn.execute("UPDATE users SET balance_rub = balance_rub - ? WHERE user_id = ?", (cost_rub, creator_id))
        conn.execute(
            "INSERT INTO gift_cards (code, days, created_by, is_claimed, created_at) VALUES (?, ?, ?, 0, ?)",
            (code, days, creator_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.execute(
            "INSERT INTO license_keys (key_code, key_type, days, price, is_used) VALUES (?, 'VPN', ?, 0, 0)",
            (code, days)
        )
        conn.commit()
    return True, code

def get_user_primary_sub_url(user_id: int) -> str:
    with sqlite3.connect(DB_PATH) as conn:
        dom_row = conn.execute("SELECT value FROM settings WHERE key = 'sub_domain_prefix'").fetchone()
        sub_dom = dom_row[0] if (dom_row and dom_row[0]) else "https://sub.bot-vip.online/sub"
        k_row = conn.execute("SELECT sub_id FROM user_keys WHERE user_id = ? ORDER BY id ASC LIMIT 1", (user_id,)).fetchone()
        if k_row and k_row[0]:
            return f"{sub_dom.rstrip('/')}/{k_row[0]}"
        u_row = conn.execute("SELECT sub_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
        sub_id = u_row[0] if (u_row and u_row[0]) else "demo"
        return f"{sub_dom.rstrip('/')}/{sub_id}"

def toggle_freeze_user_key(user_id: int, key_id: int) -> tuple[bool, str]:
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT is_active, COALESCE(is_frozen, 0), COALESCE(frozen_at, ''), expires_at, key_name FROM user_keys WHERE id = ? AND user_id = ?",
            (key_id, user_id)
        ).fetchone()
        if not row:
            return False, "Ключ не найден."
        is_act, is_frz, frz_at, exp_at, k_name = row
        if exp_at == "Без срока":
            return False, "♾ Безлимитный ключ не нуждается в заморозке."

        if is_frz == 0:
            conn.execute(
                "UPDATE user_keys SET is_frozen = 1, is_active = 0, frozen_at = ? WHERE id = ?",
                (now_str, key_id)
            )
            conn.commit()
            return True, f"❄️ <b>{html.escape(k_name)} поставлен на паузу (заморожен)!</b>\nДни подписки сохранены и не сгорают."
        else:
            new_exp_str = exp_at
            try:
                frz_dt = datetime.strptime(frz_at, "%Y-%m-%d %H:%M:%S")
                exp_dt = datetime.strptime(exp_at, "%Y-%m-%d %H:%M:%S")
                paused_delta = max(timedelta(seconds=0), now - frz_dt)
                new_exp_str = (exp_dt + paused_delta).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
            conn.execute(
                "UPDATE user_keys SET is_frozen = 0, is_active = 1, frozen_at = '', expires_at = ? WHERE id = ?",
                (new_exp_str, key_id)
            )
            conn.commit()
            return True, f"▶️ <b>{html.escape(k_name)} разморожен и снова активен!</b>\nНовый срок действия: до <code>{new_exp_str}</code>"

def reissue_key_uuid_db(user_id: int, key_id: int) -> tuple[bool, str]:
    last_ts = REISSUE_COOLDOWNS.get(f"{user_id}_{key_id}", 0)
    if time_mod.time() - last_ts < 86400 and user_id != ADMIN_ID:
        return False, "⏳ Перевыпускать UUID можно не чаще 1 раза в 24 часа."
    new_uuid = str(uuid.uuid4())
    new_sub = secrets.token_hex(6)
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT config_text, client_uuid, sub_id FROM user_keys WHERE id = ? AND user_id = ?", (key_id, user_id)).fetchone()
        if not row:
            return False, "Ключ не найден."
        old_cfg, old_uuid, old_sub = row
        new_cfg = old_cfg.replace(old_uuid, new_uuid).replace(old_sub, new_sub) if old_cfg else ""
        conn.execute(
            "UPDATE user_keys SET client_uuid = ?, sub_id = ?, config_text = ? WHERE id = ?",
            (new_uuid, new_sub, new_cfg, key_id)
        )
        conn.execute(
            "UPDATE users SET client_uuid = ?, sub_id = ?, vpn_config = ? WHERE user_id = ?",
            (new_uuid, new_sub, new_cfg, user_id)
        )
        conn.commit()
    REISSUE_COOLDOWNS[f"{user_id}_{key_id}"] = time_mod.time()
    return True, f"🔄 <b>Ключ успешно перевыпущен!</b>\nНовый Sub ID: <code>{new_sub}</code>\nНовый UUID: <code>{new_uuid}</code>"

async def node_watchdog_and_autorenew_job(context: ContextTypes.DEFAULT_TYPE):
    import socket as sock
    with sqlite3.connect(DB_PATH) as conn:
        servers = conn.execute("SELECT id, name, host, is_active FROM servers WHERE is_active = 1").fetchall()

    for srv_id, name, host, _ in servers:
        h_clean = host.split(":")[0] if ":" in host else host
        p_clean = int(host.split(":")[1]) if (":" in host and host.split(":")[1].isdigit()) else 443
        is_up = False
        try:
            with sock.create_connection((h_clean, p_clean), timeout=2.5):
                is_up = True
        except Exception:
            is_up = False

        prev_state = NODE_STATES.get(srv_id, True)
        if prev_state and not is_up and ADMIN_ID:
            NODE_STATES[srv_id] = False
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"🚨 <b>[Node Watchdog] Упал сервер #{srv_id}: {html.escape(name)}</b> (<code>{html.escape(host)}</code>)!",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        elif not prev_state and is_up and ADMIN_ID:
            NODE_STATES[srv_id] = True
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"🟢 <b>[Node Watchdog] Сервер #{srv_id}: {html.escape(name)} снова ОНЛАЙН!</b>",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    now = datetime.now()
    soon_str = (now + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(DB_PATH) as conn:
        expiring_keys = conn.execute("""
            SELECT k.id, k.user_id, k.key_name, k.expires_at, COALESCE(u.balance_rub, 0), COALESCE(u.auto_renew, 1)
            FROM user_keys k
            JOIN users u ON u.user_id = k.user_id
            WHERE k.is_active = 1 AND COALESCE(k.is_frozen, 0) = 0 AND k.expires_at != '' AND k.expires_at != 'Без срока'
            AND k.expires_at > ? AND k.expires_at <= ?
        """, (now_str, soon_str)).fetchall()

        for kid, uid, kname, exp_str, bal, auto_on in expiring_keys:
            if auto_on == 1 and bal >= 199:
                new_exp = (datetime.strptime(exp_str, "%Y-%m-%d %H:%M:%S") + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
                conn.execute("UPDATE users SET balance_rub = balance_rub - 199 WHERE user_id = ?", (uid,))
                conn.execute("UPDATE user_keys SET expires_at = ?, warned_24h = 0, warned_3h = 0 WHERE id = ?", (new_exp, kid))
                conn.execute("INSERT INTO payments (user_id, amount, provider, description, created_at) VALUES (?, 199, 'AutoRenew', ?, ?)", (uid, f"Автопродление {kname}", now_str))
                conn.commit()
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"🔄 <b>Автопродление сработало!</b>\nКлюч <b>{html.escape(kname)}</b> автоматически продлён на 30 дней (до <code>{new_exp}</code>) с вашего внутреннего баланса (-199 ₽).",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

def render_pro_wallet_view(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    bal, auto_on, ref_rub = get_wallet_data(user_id)
    auto_icon = "🟢 ВКЛ" if auto_on else "🔴 ВЫКЛ"
    text = (
        f"💎 <b>Центр самообслуживания и Кошелёк Bot_VIP</b>\n\n"
        f"💰 <b>Внутренний баланс:</b> <code>{int(bal)} ₽</code>\n"
        f"🔄 <b>Автопродление ключей:</b> {auto_icon}\n"
        f"🤝 <b>Заработано с рефералов (20% кэшбэк):</b> <code>{int(ref_rub)} ₽</code>\n\n"
        f"Выберите нужный инструмент:"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💳 Пополнить баланс (+199 ₽)", callback_data="pro_topup_199"),
            InlineKeyboardButton(f"🔄 Автопродление: {auto_icon}", callback_data="pro_toggle_autorenew")
        ],
        [
            InlineKeyboardButton("📖 Инструкции и Выбор приложения", callback_data="pro_guides_menu")
        ],
        [
            InlineKeyboardButton("🎁 Подарить подписку другу (Gift)", callback_data="pro_create_gift"),
            InlineKeyboardButton("❄️ Заморозка / 🔄 Сброс UUID", callback_data="pro_keys_tools")
        ],
        [
            InlineKeyboardButton("🔑 Мои ключи", callback_data="client_my_keys"),
            InlineKeyboardButton("🈴 На главную", callback_data="client_home")
        ]
    ])
    return text, kb

def render_os_selection_menu() -> tuple[str, InlineKeyboardMarkup]:
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🤖 Android", callback_data="pro_os_android"),
            InlineKeyboardButton("🍎 iOS (iPhone / iPad)", callback_data="pro_os_ios")
        ],
        [
            InlineKeyboardButton("💻 Windows (ПК)", callback_data="pro_os_windows"),
            InlineKeyboardButton("🍏 macOS / Linux", callback_data="pro_os_macos")
        ],
        [
            InlineKeyboardButton("🔑 Мои ключи", callback_data="client_my_keys"),
            InlineKeyboardButton("⬅️ Назад в Кошелёк", callback_data="pro_main")
        ]
    ])
    return (
        "📖 <b>Инструкции и Выбор приложения</b>\n\n"
        "Выберите вашу операционную систему, чтобы увидеть список совместимых VPN-приложений и добавить подписку в 1 клик:",
        kb
    )

async def pro_menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, kb = render_pro_wallet_view(update.effective_user.id)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
    raise ApplicationHandlerStop

async def pro_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    await query.answer()

    if data == "pro_main":
        text, kb = render_pro_wallet_view(user.id)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    if data == "pro_toggle_autorenew":
        _, auto_on, _ = get_wallet_data(user.id)
        new_val = 0 if auto_on == 1 else 1
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE users SET auto_renew = ? WHERE user_id = ?", (new_val, user.id))
            conn.commit()
        text, kb = render_pro_wallet_view(user.id)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    if data == "pro_topup_199":
        add_user_balance(user.id, 199.0)
        inviter_id, cashback = credit_referral_cashback(user.id, 199.0)
        if inviter_id and cashback > 0:
            try:
                await context.bot.send_message(
                    chat_id=inviter_id,
                    text=f"💸 <b>Реферальный кэшбэк +20%!</b>\nВаш друг пополнил счёт, вам начислено <b>+{cashback} ₽</b> на внутренний баланс!",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        text, kb = render_pro_wallet_view(user.id)
        await query.edit_message_text(
            f"✅ <b>Баланс успешно пополнен на +199 ₽!</b>\n\n{text}",
            parse_mode="HTML",
            reply_markup=kb
        )
        raise ApplicationHandlerStop

    if data == "pro_create_gift":
        ok, res = create_gift_certificate(user.id, days=30, cost_rub=199.0)
        if not ok:
            await query.message.reply_text(res, parse_mode="HTML")
            raise ApplicationHandlerStop
        await query.message.reply_text(
            f"🎁 <b>Подарочный сертификат на 30 дней создан!</b>\n\n"
            f"🎟 <b>Код для друга:</b> <code>{res}</code>\n\n"
            f"Перешлите этот код другу — он может активировать его в разделе <b>«🎟 Промокод / Купон»</b> и сразу получить рабочий VPN!",
            parse_mode="HTML"
        )
        raise ApplicationHandlerStop

    if data == "pro_guides_menu":
        text, kb = render_os_selection_menu()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    if data.startswith("pro_os_"):
        os_key = data.replace("pro_os_", "")
        os_data = APPS_CATALOG.get(os_key)
        if not os_data:
            raise ApplicationHandlerStop
        apps = list(os_data["apps"].items())
        kb_rows = []
        for i in range(0, len(apps), 2):
            row = []
            for app_id, (app_name, _, _) in apps[i:i+2]:
                row.append(InlineKeyboardButton(f"📲 {app_name}", callback_data=f"pro_app_{os_key}_{app_id}"))
            kb_rows.append(row)
        kb_rows.append([InlineKeyboardButton("⬅️ Выбрать другую систему", callback_data="pro_guides_menu")])
        await query.edit_message_text(
            f"{os_data['title']} — <b>Выберите приложение для подключения:</b>\n\n"
            f"Нажмите на любое приложение ниже, чтобы скачать его и автоматически добавить вашу подписку:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb_rows)
        )
        raise ApplicationHandlerStop

    if data.startswith("pro_app_"):
        _, _, os_key, app_id = data.split("_", 3)
        os_data = APPS_CATALOG.get(os_key, {})
        app_tuple = os_data.get("apps", {}).get(app_id)
        if not app_tuple:
            raise ApplicationHandlerStop
        app_name, dl_url, guide_steps = app_tuple
        sub_url = get_user_primary_sub_url(user.id)

        kb_rows = [
            [InlineKeyboardButton(f"📥 Скачать {app_name}", url=dl_url)]
        ]
        if sub_url.startswith("http"):
            kb_rows.append([InlineKeyboardButton(f"➕ Добавить в {app_name} (Веб-панель)", url=sub_url)])
        kb_rows.append([
            InlineKeyboardButton("⬅️ К списку программ", callback_data=f"pro_os_{os_key}"),
            InlineKeyboardButton("🔑 Мои ключи", callback_data="client_my_keys")
        ])

        await query.edit_message_text(
            f"📲 <b>Подключение через {html.escape(app_name)} ({os_data.get('title', '')})</b>\n\n"
            f"📖 <b>Как подключить:</b>\n{html.escape(guide_steps)}\n\n"
            f"🔗 <b>Ваша ссылка подписки (нажмите для копирования):</b>\n"
            f"<code>{html.escape(sub_url)}</code>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(kb_rows)
        )
        raise ApplicationHandlerStop

    if data == "pro_keys_tools":
        with sqlite3.connect(DB_PATH) as conn:
            keys = conn.execute("SELECT id, key_name, COALESCE(is_frozen, 0), expires_at FROM user_keys WHERE user_id = ? ORDER BY id ASC", (user.id,)).fetchall()
        if not keys:
            await query.message.reply_text("У вас пока нет созданных ключей.")
            raise ApplicationHandlerStop
        kb_rows = []
        for kid, kname, is_frz, exp in keys:
            frz_lbl = "▶️ Разморозить" if is_frz else "❄️ Заморозить"
            kb_rows.append([
                InlineKeyboardButton(f"{frz_lbl} {kname}", callback_data=f"pro_frz_{kid}"),
                InlineKeyboardButton(f"🔄 Сброс UUID ({kname})", callback_data=f"pro_reissue_{kid}")
            ])
        kb_rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="pro_main")])
        await query.edit_message_text(
            "🛠 <b>Самообслуживание ключей (Заморозка и Сброс UUID)</b>\n\n"
            "• <b>❄️ Заморозить</b> — ставит тариф на паузу на время отпуска с сохранением дней.\n"
            "• <b>🔄 Сброс UUID</b> — мгновенно меняет идентификатор ключа, если старый перестал работать:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb_rows)
        )
        raise ApplicationHandlerStop

    if data.startswith("pro_frz_"):
        kid = int(data.split("_")[-1])
        _, msg_txt = toggle_freeze_user_key(user.id, kid)
        await query.message.reply_text(msg_txt, parse_mode="HTML")
        raise ApplicationHandlerStop

    if data.startswith("pro_reissue_"):
        kid = int(data.split("_")[-1])
        _, msg_txt = reissue_key_uuid_db(user.id, kid)
        await query.message.reply_text(msg_txt, parse_mode="HTML")
        raise ApplicationHandlerStop

def register_extension(application):
    init_pro_tables()
    application.add_handler(CommandHandler("wallet", pro_menu_cmd), group=-1)
    application.add_handler(CommandHandler("pro", pro_menu_cmd), group=-1)
    application.add_handler(MessageHandler(filters.Regex(r"^💎 Кошелёк / Бонусы$"), pro_menu_cmd), group=-1)
    application.add_handler(CallbackQueryHandler(pro_callbacks, pattern=r"^pro_"), group=-1)
    if application.job_queue:
        application.job_queue.run_repeating(node_watchdog_and_autorenew_job, interval=180, first=25)
    logger.info("🧩 Расширение ProSuite успешно проверено и загружено!")
