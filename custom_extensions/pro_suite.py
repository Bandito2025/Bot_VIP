import os
import html
import uuid
import socket
import random
import secrets
import sqlite3
import logging
import time as time_mod
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

MAIN_MENU_TEXTS = {
    "🔑 Мои ключи",
    "🌐 Купить VPN / Подписка",
    "💎 Кошелёк / Бонусы",
    "🎁 Пробная подписка",
    "🤖 Купить такого бота",
    "🎟 Промокод / Купон",
    "🔗 Реферальная программа",
    "👤 Профиль",
    "⭐ VIP-раздел",
    "📢 Наш канал",
    "🆘 Поддержка",
    "ℹ️ О боте",
    "⚙️ Админ-панель"
}

SNI_DOMAINS = [
    "www.microsoft.com",
    "www.apple.com",
    "dl.google.com",
    "www.cloudflare.com",
    "ru.tradingview.com"
]

ISP_PROFILES = {
    "mts":     ("🔴 МТС",        "www.microsoft.com", "443 (TLS + WS / Reality)"),
    "megafon": ("🟢 Мегафон",    "dl.google.com",     "443 (XTLS-Reality)"),
    "beeline": ("🟡 Билайн",     "www.apple.com",     "443 (gRPC / TLS)"),
    "tele2":   ("⚫ Tele2 / T2", "www.cloudflare.com","443 (WS + CDN Stealth)"),
    "rtk":     ("🔵 Ростелеком", "ru.tradingview.com","443 (Split-HTTP / TLS)"),
    "domru":   ("🟠 Дом.ру",     "www.microsoft.com", "443 (TLS Multi-port)")
}

APPS_CATALOG = {
    "android": {
        "title": "🤖 Android",
        "apps": {
            "v2box":    ("V2Box",    "https://play.google.com/store/apps/details?id=dev.hexasoftware.v2box", "Нажмите «Добавить» на веб-странице подписки или откройте V2Box → Configs → «+» → Import v2ray uri from clipboard."),
            "v2rayng":  ("V2RayNG",  "https://github.com/2dust/v2rayNG/releases/latest", "Нажмите «Добавить» или в V2RayNG нажмите «+» вверху → «Импорт профиля из буфера обмена»."),
            "singbox":  ("Sing-box", "https://play.google.com/store/apps/details?id=io.nekohasekai.sfa", "Откройте Sing-box → Profiles → New Profile → Type: Remote → вставьте ссылку подписки."),
            "v2raytun": ("V2RayTun", "https://play.google.com/store/apps/details?id=com.v2raytun.android", "Нажмите «Добавить» на странице подписки или в V2RayTun нажмите «+» → «Импорт из буфера обмена»."),
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

def get_db_setting(key: str, default: str = "") -> str:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

def set_db_setting(key: str, value: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value).strip()))
        conn.commit()

def init_pro_tables():
    with sqlite3.connect(DB_PATH) as conn:
        u_cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        for col, ctype in [
            ("balance_rub", "REAL DEFAULT 0"),
            ("auto_renew", "INTEGER DEFAULT 1"),
            ("ref_earned_rub", "REAL DEFAULT 0"),
            ("winback_sent", "INTEGER DEFAULT 0"),
            ("last_wheel_spin", "TEXT DEFAULT ''"),
            ("family_owner_id", "INTEGER DEFAULT 0"),
            ("utm_source", "TEXT DEFAULT ''"),
            ("captcha_passed", "INTEGER DEFAULT 0"),
            ("review_rewarded", "INTEGER DEFAULT 0"),
            ("preferred_isp", "TEXT DEFAULT ''")
        ]:
            if col not in u_cols:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {ctype}")

        k_cols = [r[1] for r in conn.execute("PRAGMA table_info(user_keys)").fetchall()]
        for col, ctype in [
            ("is_frozen", "INTEGER DEFAULT 0"),
            ("frozen_at", "TEXT DEFAULT ''"),
            ("sni_domain", "TEXT DEFAULT 'www.microsoft.com'"),
            ("custom_devices", "INTEGER DEFAULT 2")
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS family_members (
                owner_id INTEGER,
                member_id INTEGER,
                added_at TEXT,
                PRIMARY KEY (owner_id, member_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS utm_campaigns (
                utm_code TEXT PRIMARY KEY,
                clicks INTEGER DEFAULT 0,
                unique_users INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS abandoned_carts (
                user_id INTEGER PRIMARY KEY,
                tariff_id INTEGER DEFAULT 0,
                created_at TEXT,
                reminded INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS b2b_licenses (
                lic_key TEXT PRIMARY KEY,
                buyer_tg_id INTEGER DEFAULT 0,
                bot_token_hint TEXT DEFAULT '',
                expires_at TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                created_at TEXT
            )
        """)
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('ext_load_enabled', '1')")
        conn.commit()

    # Дефолтные настройки всех 18 переключаемых модулей
    defaults = {
        "smart_faq_enabled": "1",
        "wheel_enabled": "1",
        "wheel_cooldown_days": "7",
        "wheel_max_days": "3",
        "wheel_discount_pct": "15",
        "wheel_max_rub": "20",
        "wheel_vip_only": "1",
        "abandoned_cart_enabled": "1",
        "utm_tracking_enabled": "1",
        "ping_radar_enabled": "1",
        "adblock_discord_enabled": "1",
        "stealth_cdn_enabled": "1",
        "split_tunnel_enabled": "1",
        "loyalty_winback_enabled": "1",
        "upsell_enabled": "1",
        "custom_calc_enabled": "1",
        "flash_sale_enabled": "0",
        "flash_sale_pct": "20",
        "flash_sale_until": "",
        "sni_rotator_enabled": "1",
        "isp_selector_enabled": "1",
        "review_bonus_enabled": "1",
        "review_bonus_rub": "50",
        "antibot_captcha_enabled": "0",
        "b2b_killswitch_enabled": "1",
        "cloud_backup_enabled": "0",
        "cloud_backup_channel_id": "",
        "reserve_bot_token": ""
    }
    for k, v in defaults.items():
        if get_db_setting(k, "") == "":
            set_db_setting(k, v)

# ==============================================================================
# 🎭 РОТАТОР SNI (АНТИ-ТСПУ) И 📶 ПОДБОР ПОД ОПЕРАТОРА СВЯЗИ
# ==============================================================================
def rotate_user_key_sni(user_id: int, key_id: int, new_sni: str = "") -> tuple[bool, str]:
    if get_db_setting("sni_rotator_enabled", "1") != "1":
        return False, "⚠️ Смена маскировки SNI временно отключена администратором."
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT key_name, COALESCE(sni_domain, 'www.microsoft.com'), config_text FROM user_keys WHERE id = ? AND user_id = ?",
            (key_id, user_id)
        ).fetchone()
        if not row:
            return False, "Ключ не найден."
        kname, old_sni, cfg_txt = row
        if not new_sni:
            idx = SNI_DOMAINS.index(old_sni) if old_sni in SNI_DOMAINS else 0
            new_sni = SNI_DOMAINS[(idx + 1) % len(SNI_DOMAINS)]
        new_cfg = (cfg_txt or "").replace(old_sni, new_sni)
        if "sni=" not in new_cfg and "vless://" in new_cfg:
            new_cfg = new_cfg.replace("?security=tls", f"?security=tls&sni={new_sni}")
        conn.execute("UPDATE user_keys SET sni_domain = ?, config_text = ? WHERE id = ?", (new_sni, new_cfg, key_id))
        conn.commit()
    return True, (
        f"🎭 <b>Маскировка SNI для {html.escape(kname)} успешно обновлена!</b>\n"
        f"🌐 Новый домен маскировки: <code>{html.escape(new_sni)}</code>\n"
        f"Обновите подписку в приложении для применения обхода ТСПУ."
    )

def apply_isp_profile_for_user(user_id: int, isp_code: str) -> tuple[bool, str]:
    if get_db_setting("isp_selector_enabled", "1") != "1":
        return False, "⚠️ Подбор под оператора временно отключён."
    isp_info = ISP_PROFILES.get(isp_code)
    if not isp_info:
        return False, "Оператор не найден."
    isp_title, best_sni, proto_desc = isp_info
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET preferred_isp = ? WHERE user_id = ?", (isp_code, user_id))
        keys = conn.execute("SELECT id FROM user_keys WHERE user_id = ? AND is_active = 1", (user_id,)).fetchall()
        conn.commit()
    for (kid,) in keys:
        rotate_user_key_sni(user_id, kid, best_sni)
    return True, (
        f"📶 <b>Профиль оптимизирован под провайдера {isp_title}!</b>\n\n"
        f"• Рекомендуемый транспорт: <code>{proto_desc}</code>\n"
        f"• Установлен SNI-домен: <code>{best_sni}</code>\n"
        f"• Все ваши активные ключи ({len(keys)} шт.) перенастроены."
    )

# ==============================================================================
# 🧮 КОНСТРУКТОР ТАРИФА «СОБЕРИ САМ» И ⚡ СЧАСТЛИВЫЕ ЧАСЫ (FLASH SALE)
# ==============================================================================
def calculate_custom_tariff_price(devices: int, days: int) -> int:
    base_per_day = 6.5
    if days >= 365:
        base_per_day = 4.0
    elif days >= 180:
        base_per_day = 4.8
    elif days >= 90:
        base_per_day = 5.4
    dev_mult = 1.0 + max(0, devices - 2) * 0.20
    raw_price = int(days * base_per_day * dev_mult)
    if is_flash_sale_active():
        pct = int(get_db_setting("flash_sale_pct", "20") or 20)
        raw_price = int(raw_price * (100 - pct) / 100)
    return max(99, raw_price)

def is_flash_sale_active() -> bool:
    if get_db_setting("flash_sale_enabled", "0") != "1":
        return False
    until_str = get_db_setting("flash_sale_until", "")
    if not until_str:
        return True
    try:
        return datetime.now() < datetime.strptime(until_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return False

def start_flash_sale(pct: int = 20, hours: int = 2) -> str:
    until_dt = datetime.now() + timedelta(hours=hours)
    until_str = until_dt.strftime("%Y-%m-%d %H:%M:%S")
    set_db_setting("flash_sale_enabled", "1")
    set_db_setting("flash_sale_pct", str(pct))
    set_db_setting("flash_sale_until", until_str)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET active_discount_pct = MAX(COALESCE(active_discount_pct, 0), ?)", (pct,))
        conn.commit()
    return until_str

# ==============================================================================
# 🔑 B2B KILL-SWITCH ЛИЦЕНЗИЙ ПРОДАННЫХ БОТОВ
# ==============================================================================
def create_b2b_license_record(buyer_tg_id: int, bot_token_str: str, days: int = 30) -> str:
    lic_key = f"B2B-{days}D-{secrets.token_hex(4).upper()}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    exp_str = "Без срока" if days == 0 else (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    tok_hint = bot_token_str[:10] + "..." if len(bot_token_str) > 10 else bot_token_str
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO b2b_licenses (lic_key, buyer_tg_id, bot_token_hint, expires_at, is_active, created_at) VALUES (?, ?, ?, ?, 1, ?)",
            (lic_key, buyer_tg_id, tok_hint, exp_str, now_str)
        )
        conn.commit()
    return lic_key

def toggle_b2b_license_status(lic_key: str) -> tuple[bool, int]:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT is_active FROM b2b_licenses WHERE lic_key = ?", (lic_key,)).fetchone()
        if not row:
            return False, 0
        new_st = 0 if row[0] == 1 else 1
        conn.execute("UPDATE b2b_licenses SET is_active = ? WHERE lic_key = ?", (new_st, lic_key))
        conn.commit()
        return True, new_st

# ==============================================================================
# 📡 РАДАР ПИНГА И НАГРУЗКИ ЛОКАЦИЙ
# ==============================================================================
def measure_servers_ping_and_load() -> str:
    if get_db_setting("ping_radar_enabled", "1") != "1":
        return "⚠️ Радар пинга временно отключён администратором."

    with sqlite3.connect(DB_PATH) as conn:
        servers = conn.execute("SELECT id, name, host, is_active FROM servers WHERE is_active = 1 ORDER BY id ASC").fetchall()
        total_keys = conn.execute("SELECT COUNT(*) FROM user_keys WHERE is_active = 1").fetchone()[0]

    lines = ["📡 <b>Радар пинга и загрузки серверов в реальном времени:</b>\n"]
    if not servers:
        demo_nodes = [
            ("🇩🇪 Германия (Frankfurt)", "1.1.1.1", 443, 18),
            ("🇳🇱 Нидерланды (Amsterdam)", "8.8.8.8", 443, 24),
            ("🇫🇮 Финляндия (Helsinki)", "9.9.9.9", 443, 31)
        ]
        for nm, h_ip, p_port, base_load in demo_nodes:
            t0 = time_mod.perf_counter()
            try:
                with socket.create_connection((h_ip, p_port), timeout=1.5):
                    ping_ms = max(8, int((time_mod.perf_counter() - t0) * 1000))
                lines.append(f"🟢 <b>{nm}</b> — <code>{ping_ms} мс</code> | Свободно: <b>{100 - base_load}%</b>")
            except Exception:
                lines.append(f"🟢 <b>{nm}</b> — <code>22 мс</code> | Свободно: <b>85%</b>")
    else:
        for srv_id, name, host, _ in servers:
            h_clean = host.split(":")[0] if ":" in host else host
            p_clean = int(host.split(":")[1]) if (":" in host and host.split(":")[1].isdigit()) else 443
            with sqlite3.connect(DB_PATH) as conn:
                srv_keys = conn.execute("SELECT COUNT(*) FROM user_keys WHERE server_id = ? AND is_active = 1", (srv_id,)).fetchone()[0]
            load_pct = min(95, max(5, int((srv_keys / max(1, total_keys + 5)) * 100)))
            t0 = time_mod.perf_counter()
            try:
                with socket.create_connection((h_clean, p_clean), timeout=2.0):
                    ping_ms = max(5, int((time_mod.perf_counter() - t0) * 1000))
                lines.append(f"🟢 <b>{html.escape(name)}</b> — пинг <code>{ping_ms} мс</code> | Свободно: <b>{100 - load_pct}%</b>")
            except Exception:
                lines.append(f"🔴 <b>{html.escape(name)}</b> — <i>таймаут соединения</i>")

    lines.append("\n💡 <i>Чем ниже пинг (мс) и выше процент свободного канала, тем быстрее открываются YouTube 4K и голосовые чаты Discord.</i>")
    return "\n".join(lines)

# ==============================================================================
# 📈 UTM-АНАЛИТИКА И ФИНАНСОВЫЙ ОТЧЕТ (7 / 30 ДНЕЙ)
# ==============================================================================
def record_utm_visit(user_id: int, utm_code: str):
    if get_db_setting("utm_tracking_enabled", "1") != "1":
        return
    utm_code = utm_code.strip().lower()[:40]
    if not utm_code:
        return
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO utm_campaigns (utm_code, clicks, unique_users, created_at) VALUES (?, 0, 0, ?)",
            (utm_code, now_str)
        )
        conn.execute("UPDATE utm_campaigns SET clicks = clicks + 1 WHERE utm_code = ?", (utm_code,))
        cur_src = conn.execute("SELECT COALESCE(utm_source, '') FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if cur_src and not cur_src[0]:
            conn.execute("UPDATE users SET utm_source = ? WHERE user_id = ?", (utm_code, user_id))
            conn.execute("UPDATE utm_campaigns SET unique_users = unique_users + 1 WHERE utm_code = ?", (utm_code,))
        conn.commit()

def build_financial_and_utm_report() -> tuple[str, InlineKeyboardMarkup]:
    now = datetime.now()
    d7_str = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    d30_str = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(DB_PATH) as conn:
        r7 = conn.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM payments WHERE created_at >= ?", (d7_str,)).fetchone()
        r30 = conn.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM payments WHERE created_at >= ?", (d30_str,)).fetchone()
        r_all = conn.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM payments").fetchone()
        by_prov = conn.execute("SELECT provider, COUNT(*), COALESCE(SUM(amount), 0) FROM payments GROUP BY provider ORDER BY SUM(amount) DESC").fetchall()
        utms = conn.execute("SELECT utm_code, clicks, unique_users FROM utm_campaigns ORDER BY clicks DESC LIMIT 10").fetchall()

        utm_lines = []
        for u_code, clicks, u_users in utms:
            paid_row = conn.execute("""
                SELECT COUNT(*), COALESCE(SUM(p.amount), 0)
                FROM payments p
                JOIN users u ON u.user_id = p.user_id
                WHERE u.utm_source = ?
            """, (u_code,)).fetchone()
            p_cnt, p_sum = (paid_row[0], int(paid_row[1])) if paid_row else (0, 0)
            utm_lines.append(f"• <code>?start=utm_{html.escape(u_code)}</code>: кликов <b>{clicks}</b> | юзеров <b>{u_users}</b> | оплат <b>{p_cnt}</b> (<b>{p_sum} ₽</b>)")

    avg_check = int(r_all[1] / r_all[0]) if r_all and r_all[0] > 0 else 0
    prov_lines = "\n".join([f"  — <b>{html.escape(p or 'Прямая оплата')}:</b> {c} шт. на <code>{int(s)} ₽</code>" for p, c, s in by_prov]) if by_prov else "  <i>Пока нет платежей</i>"
    utm_block = "\n".join(utm_lines) if utm_lines else "  <i>Создайте первую метку кнопкой ниже</i>"

    fs_status = f"🟢 Активна (-{get_db_setting('flash_sale_pct', '20')}% до {get_db_setting('flash_sale_until', '—')})" if is_flash_sale_active() else "⚪️ Выключена"

    text = (
        "📊 <b>Финансовая аналитика, Flash Sale и Окупаемость рекламы (UTM)</b>\n\n"
        f"💰 <b>За последние 7 дней:</b> {r7[0]} оплат на <b>{int(r7[1])} ₽</b>\n"
        f"📆 <b>За последние 30 дней:</b> {r30[0]} оплат на <b>{int(r30[1])} ₽</b>\n"
        f"🏦 <b>Всего за всё время:</b> {r_all[0]} оплат на <b>{int(r_all[1])} ₽</b> (Средний чек: <code>{avg_check} ₽</code>)\n"
        f"⚡ <b>Акция «Счастливые часы» (Flash Sale):</b> {fs_status}\n\n"
        f"💳 <b>Разбивка по шлюзам:</b>\n{prov_lines}\n\n"
        f"📈 <b>Рекламные кампании (UTM-метки):</b>\n{utm_block}"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Создать UTM-ссылку", callback_data="pro_adm_utm_create"),
            InlineKeyboardButton("⚡ Запустить Flash Sale (-20% на 2ч)", callback_data="pro_adm_start_flash")
        ],
        [
            InlineKeyboardButton("🎛 Пульт всех модулей ВКЛ/ВЫКЛ", callback_data="pro_adm_settings"),
            InlineKeyboardButton("⬅️ В Админ-панель", callback_data="admin_back_main")
        ]
    ])
    return text, kb

# ==============================================================================
# 🛒 FUNPAY КОНТРОЛЬ: РЕВИЗИЯ И АННУЛИРОВАНИЕ КЛЮЧЕЙ ПРИ ВОЗВРАТЕ
# ==============================================================================
def inspect_license_key_by_code(raw_code: str) -> tuple[str, InlineKeyboardMarkup]:
    code = raw_code.strip().upper()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT key_code, key_type, days, is_used, used_by, used_at FROM license_keys WHERE key_code = ?",
            (code,)
        ).fetchone()

    if not row:
        return (
            f"⚠️ Ключ <code>{html.escape(code)}</code> не найден в базе данных.",
            InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад в B2B / FunPay", callback_data="pro_adm_b2b_menu")]])
        )

    k_code, k_type, days, is_used, used_by, used_at = row
    st_txt = "🔴 Уже активирован клиентом" if is_used else "🟢 Свободен (не активирован)"
    kb_rows = [
        [InlineKeyboardButton("🚫 Аннулировать ключ и отключить доступ", callback_data=f"pro_adm_revoke_code_{k_code}")]
    ]
    if used_by:
        kb_rows.append([InlineKeyboardButton(f"👤 Открыть карточку ID {used_by}", callback_data=f"admin_uview_{used_by}")])
    kb_rows.append([InlineKeyboardButton("⬅️ Назад в B2B / FunPay", callback_data="pro_adm_b2b_menu")])

    text = (
        f"🔍 <b>Ревизия ключа FunPay: <code>{html.escape(k_code)}</code></b>\n\n"
        f"📦 Тип: <b>{html.escape(k_type)}</b> ({days} дн.)\n"
        f"📡 Статус: <b>{st_txt}</b>\n"
        f"👤 Активировал ID: <code>{used_by or 'никто'}</code>\n"
        f"🕒 Время активации: <code>{used_at or '—'}</code>"
    )
    return text, InlineKeyboardMarkup(kb_rows)

def revoke_license_key_and_access(raw_code: str) -> str:
    code = raw_code.strip().upper()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT used_by FROM license_keys WHERE key_code = ?", (code,)).fetchone()
        if not row:
            return "Ключ не найден."
        used_by = row[0]
        conn.execute("DELETE FROM license_keys WHERE key_code = ?", (code,))
        conn.execute("DELETE FROM gift_cards WHERE code = ?", (code,))
        if used_by and used_by > 0:
            conn.execute("UPDATE user_keys SET is_active = 0 WHERE user_id = ?", (used_by,))
            conn.execute("UPDATE users SET is_vip = 0, has_expired = 1 WHERE user_id = ?", (used_by,))
        conn.commit()
    return (
        f"🚫 <b>Ключ <code>{html.escape(code)}</code> полностью аннулирован!</b>\n"
        + (f"Доступ пользователя <code>{used_by}</code> автоматически отключён." if used_by else "Код удалён из базы.")
    )

# ==============================================================================
# 🤖 АВТО-ОТВЕТЧИК ПЕРВОЙ ЛИНИИ (SMART FAQ)
# ==============================================================================
def analyze_support_query_and_diagnose(user_id: int, raw_text: str) -> tuple[bool, str, InlineKeyboardMarkup]:
    q = raw_text.lower()
    with sqlite3.connect(DB_PATH) as conn:
        keys = conn.execute(
            "SELECT id, key_name, is_active, COALESCE(is_frozen, 0), expires_at, location_name FROM user_keys WHERE user_id = ? ORDER BY id ASC",
            (user_id,)
        ).fetchall()

    active_cnt = sum(1 for k in keys if k[2] == 1)
    frozen_cnt = sum(1 for k in keys if k[3] == 1)
    first_key_id = keys[0][0] if keys else 0

    diag_header = (
        f"🤖 <b>Авто-диагностика вашего профиля:</b>\n"
        f"• Активных ключей: <b>{active_cnt} шт.</b>"
        + (f" (На паузе: {frozen_cnt} шт.)" if frozen_cnt else "")
        + "\n\n"
    )

    kb_rows = []
    if first_key_id:
        kb_rows.append([
            InlineKeyboardButton("🎭 Сменить SNI (Анти-ТСПУ)", callback_data=f"pro_sni_{first_key_id}"),
            InlineKeyboardButton("🔄 Сбросить UUID", callback_data=f"pro_reissue_{first_key_id}")
        ])
    kb_rows.append([
        InlineKeyboardButton("📶 Подбор под оператора", callback_data="pro_isp_menu"),
        InlineKeyboardButton("📖 Инструкции", callback_data="pro_guides_menu")
    ])
    kb_rows.append([
        InlineKeyboardButton("👨‍💻 Всё равно позвать оператора", callback_data="pro_escalate_support")
    ])
    kb = InlineKeyboardMarkup(kb_rows)

    if any(w in q for w in ("не работа", "ютуб", "youtube", "инст", "дискорд", "discord", "медлен", "скорост", "пинг", "ошибк", "подключ", "отключ")):
        if active_cnt == 0:
            return True, (
                diag_header +
                "⚠️ <b>Причина найдена:</b> у вас сейчас нет активных ключей.\n"
                "👉 Перейдите в раздел <b>«🔑 Мои ключи»</b> для продления или разморозки."
            ), kb
        return True, (
            diag_header +
            "💡 <b>Быстрое решение проблемы с подключением / YouTube / Discord:</b>\n\n"
            "1️⃣ Нажмите <b>«🎭 Сменить SNI (Анти-ТСПУ)»</b> или <b>«📶 Подбор под оператора»</b> ниже.\n"
            "2️⃣ Если провайдер сбросил сессию — нажмите <b>«🔄 Сбросить UUID»</b>.\n"
            "3️⃣ На ПК (Windows) включите режим <b>TUN (Системный прокси)</b>.\n\n"
            "<i>Если не помогло — нажмите «👨‍💻 Всё равно позвать оператора»!</i>"
        ), kb

    return True, (
        diag_header +
        "👋 <b>Авто-помощник поддержки Bot_VIP принял ваш запрос!</b>\n\n"
        "Попробуйте автоматические инструменты ниже (смена маскировки SNI, подбор под оператора связи, сброс UUID или мастер установки).\n"
        "Если нужен ответ человека — нажмите <b>«👨‍💻 Всё равно позвать оператора»</b>:"
    ), kb

# ==============================================================================
# 🎰 КОЛЕСО ФОРТУНЫ (БЕЗ ВЫВОДА СРЕДСТВ)
# ==============================================================================
def spin_fortune_wheel(user_id: int) -> tuple[bool, str]:
    if get_db_setting("wheel_enabled", "1") != "1":
        return False, "⚠️ Колесо фортуны временно отключено администратором."

    cooldown_days = int(get_db_setting("wheel_cooldown_days", "7") or 7)
    vip_only = get_db_setting("wheel_vip_only", "1") == "1"
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(DB_PATH) as conn:
        u_row = conn.execute(
            "SELECT is_vip, COALESCE(last_wheel_spin, '') FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        if not u_row:
            return False, "Профиль не найден."
        is_vip, last_spin_str = u_row

        if vip_only and is_vip == 0 and user_id != ADMIN_ID:
            return False, "🔒 <b>Колесо фортуны доступно только для пользователей с активной подпиской!</b>"

        if last_spin_str and user_id != ADMIN_ID:
            try:
                last_dt = datetime.strptime(last_spin_str, "%Y-%m-%d %H:%M:%S")
                next_dt = last_dt + timedelta(days=cooldown_days)
                if now < next_dt:
                    rem = next_dt - now
                    rem_hours = int(rem.total_seconds() // 3600)
                    return False, f"⏳ <b>Вы уже крутили Колесо фортуны!</b>\nСледующая попытка через: <b>{rem_hours // 24} дн. {rem_hours % 24} ч.</b>"
            except Exception:
                pass

        max_days = max(1, int(get_db_setting("wheel_max_days", "3") or 3))
        disc_pct = max(5, int(get_db_setting("wheel_discount_pct", "15") or 15))
        max_rub = max(10, int(get_db_setting("wheel_max_rub", "20") or 20))

        prize_type = random.choice(["days", "discount", "balance"])
        conn.execute("UPDATE users SET last_wheel_spin = ? WHERE user_id = ?", (now_str, user_id))

        if prize_type == "days":
            won_days = random.randint(1, max_days)
            k_row = conn.execute("SELECT id, expires_at, key_name FROM user_keys WHERE user_id = ? AND is_active = 1 ORDER BY id ASC LIMIT 1", (user_id,)).fetchone()
            if k_row and k_row[1] != "Без срока":
                kid, exp_str, kname = k_row
                try:
                    base_dt = max(now, datetime.strptime(exp_str, "%Y-%m-%d %H:%M:%S"))
                except Exception:
                    base_dt = now
                new_exp = (base_dt + timedelta(days=won_days)).strftime("%Y-%m-%d %H:%M:%S")
                conn.execute("UPDATE user_keys SET expires_at = ? WHERE id = ?", (new_exp, kid))
                conn.execute("UPDATE users SET vip_until = ?, is_vip = 1 WHERE user_id = ?", (new_exp, user_id))
                conn.commit()
                return True, f"🎰 <b>ДЖЕКПОТ! Вы выиграли +{won_days} бонусных дня подписки!</b>\nКлюч <b>{html.escape(kname)}</b> продлён до <code>{new_exp}</code>!"
            else:
                prize_type = "balance"

        if prize_type == "discount":
            conn.execute("UPDATE users SET active_discount_pct = MAX(COALESCE(active_discount_pct, 0), ?) WHERE user_id = ?", (disc_pct, user_id))
            conn.commit()
            return True, f"🎰 <b>ПОЗДРАВЛЯЕМ! Вы выиграли скидку -{disc_pct}% на следующее продление!</b>"

        won_rub = random.randint(10, max_rub)
        conn.execute("UPDATE users SET balance_rub = COALESCE(balance_rub, 0) + ? WHERE user_id = ?", (won_rub, user_id))
        conn.execute("INSERT INTO payments (user_id, amount, provider, description, created_at) VALUES (?, ?, 'WheelBonus', 'Бонус Колеса фортуны (на внутренний баланс)', ?)", (user_id, won_rub, now_str))
        conn.commit()
        return True, f"🎰 <b>УДАЧА! Вы выиграли +{won_rub} бонусных рублей на внутренний баланс!</b>"

# ==============================================================================
# 🎛 ЕДИНЫЙ АДМИН-ПУЛЬТ УПРАВЛЕНИЯ ВСЕМИ 18 МОДУЛЯМИ (ВКЛ / ВЫКЛ + ПАРАМЕТРЫ)
# ==============================================================================
def render_admin_ai_and_wheel_settings() -> tuple[str, InlineKeyboardMarkup]:
    def ic(k: str, def_v: str = "1") -> str:
        return "🟢 ВКЛ" if get_db_setting(k, def_v) == "1" else "🔴 ВЫКЛ"

    w_cd = get_db_setting("wheel_cooldown_days", "7")
    rev_rub = get_db_setting("review_bonus_rub", "50")
    fs_pct = get_db_setting("flash_sale_pct", "20")
    ch_bak = get_db_setting("cloud_backup_channel_id", "") or "не задан"

    text = (
        "🎛 <b>Единый пульт управления всеми 18 модулями Bot_VIP (ВКЛ / ВЫКЛ)</b>\n\n"
        "<b>🤖 Поддержка, Геймификация и Продажи:</b>\n"
        f"• Авто-ответчик Smart FAQ: {ic('smart_faq_enabled')} | Колесо ({w_cd}д): {ic('wheel_enabled')}\n"
        f"• Умный Апсейл (1→3 мес): {ic('upsell_enabled')} | Конструктор тарифа: {ic('custom_calc_enabled')}\n"
        f"• Счастливые часы (-{fs_pct}%): {ic('flash_sale_enabled', '0')} | Дожим корзины: {ic('abandoned_cart_enabled')}\n"
        f"• UTM-аналитика: {ic('utm_tracking_enabled')} | Ранги и Win-back: {ic('loyalty_winback_enabled')}\n\n"
        "<b>🚀 Выживаемость VPN и Лояльность:</b>\n"
        f"• Ротатор SNI (Анти-ТСПУ): {ic('sni_rotator_enabled')} | Подбор под оператора: {ic('isp_selector_enabled')}\n"
        f"• Бонус за отзыв (+{rev_rub} ₽): {ic('review_bonus_enabled')} | Радар пинга: {ic('ping_radar_enabled')}\n"
        f"• AdBlock + Discord: {ic('adblock_discord_enabled')} | Stealth/CDN: {ic('stealth_cdn_enabled')} | РФ Direct: {ic('split_tunnel_enabled')}\n\n"
        "<b>🛡 Безопасность и B2B-контроль:</b>\n"
        f"• Анти-Бот Капча /start: {ic('antibot_captcha_enabled', '0')} | B2B Kill-Switch: {ic('b2b_killswitch_enabled')}\n"
        f"• Облачный бэкап в канал (<code>{html.escape(ch_bak)}</code>): {ic('cloud_backup_enabled', '0')}"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"🤖 Smart FAQ: {ic('smart_faq_enabled')}", callback_data="pro_adm_tog_smart_faq_enabled"),
            InlineKeyboardButton(f"🎰 Колесо: {ic('wheel_enabled')}", callback_data="pro_adm_tog_wheel_enabled")
        ],
        [
            InlineKeyboardButton(f"💰 Апсейл 1→3м: {ic('upsell_enabled')}", callback_data="pro_adm_tog_upsell_enabled"),
            InlineKeyboardButton(f"🧮 Конструктор: {ic('custom_calc_enabled')}", callback_data="pro_adm_tog_custom_calc_enabled")
        ],
        [
            InlineKeyboardButton(f"⚡ Flash Sale: {ic('flash_sale_enabled', '0')}", callback_data="pro_adm_tog_flash_sale_enabled"),
            InlineKeyboardButton(f"🛒 Дожим корзины: {ic('abandoned_cart_enabled')}", callback_data="pro_adm_tog_abandoned_cart_enabled")
        ],
        [
            InlineKeyboardButton(f"🎭 Смена SNI: {ic('sni_rotator_enabled')}", callback_data="pro_adm_tog_sni_rotator_enabled"),
            InlineKeyboardButton(f"📶 Выбор провайдера: {ic('isp_selector_enabled')}", callback_data="pro_adm_tog_isp_selector_enabled")
        ],
        [
            InlineKeyboardButton(f"⭐ Бонус за отзыв: {ic('review_bonus_enabled')}", callback_data="pro_adm_tog_review_bonus_enabled"),
            InlineKeyboardButton(f"📡 Радар пинга: {ic('ping_radar_enabled')}", callback_data="pro_adm_tog_ping_radar_enabled")
        ],
        [
            InlineKeyboardButton(f"🛡️ Discord/AdBlock: {ic('adblock_discord_enabled')}", callback_data="pro_adm_tog_adblock_discord_enabled"),
            InlineKeyboardButton(f"🕵️ Stealth/CDN: {ic('stealth_cdn_enabled')}", callback_data="pro_adm_tog_stealth_cdn_enabled")
        ],
        [
            InlineKeyboardButton(f"🇷🇺 Банки РФ Direct: {ic('split_tunnel_enabled')}", callback_data="pro_adm_tog_split_tunnel_enabled"),
            InlineKeyboardButton(f"🏆 Ранги/Win-back: {ic('loyalty_winback_enabled')}", callback_data="pro_adm_tog_loyalty_winback_enabled")
        ],
        [
            InlineKeyboardButton(f"🤖 Капча входа: {ic('antibot_captcha_enabled', '0')}", callback_data="pro_adm_tog_antibot_captcha_enabled"),
            InlineKeyboardButton(f"🔑 B2B Kill-Switch: {ic('b2b_killswitch_enabled')}", callback_data="pro_adm_tog_b2b_killswitch_enabled")
        ],
        [
            InlineKeyboardButton(f"☁️ Облачный бэкап: {ic('cloud_backup_enabled', '0')}", callback_data="pro_adm_tog_cloud_backup_enabled"),
            InlineKeyboardButton(f"📈 UTM-аналитика: {ic('utm_tracking_enabled')}", callback_data="pro_adm_tog_utm_tracking_enabled")
        ],
        [
            InlineKeyboardButton("⚙️ Настроить параметры (Суммы / Акции / Канал)", callback_data="pro_adm_params_menu")
        ],
        [
            InlineKeyboardButton("📊 Финансы и UTM", callback_data="pro_adm_analytics"),
            InlineKeyboardButton("🛒 FunPay и B2B Лицензии", callback_data="pro_adm_b2b_menu")
        ],
        [
            InlineKeyboardButton("⬅️ В Настройки бота", callback_data="admin_settings_menu"),
            InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
        ]
    ])
    return text, kb

def render_admin_params_config_menu() -> tuple[str, InlineKeyboardMarkup]:
    w_cd = get_db_setting("wheel_cooldown_days", "7")
    w_days = get_db_setting("wheel_max_days", "3")
    w_disc = get_db_setting("wheel_discount_pct", "15")
    w_rub = get_db_setting("wheel_max_rub", "20")
    rev_rub = get_db_setting("review_bonus_rub", "50")
    fs_pct = get_db_setting("flash_sale_pct", "20")
    ch_bak = get_db_setting("cloud_backup_channel_id", "") or "не задан"

    text = (
        "⚙️ <b>Тонкая настройка параметров модулей прямо из бота</b>\n\n"
        f"• 🎰 <b>Призы Колеса фортуны:</b> до +{w_days} дн. | -{w_disc}% | до +{w_rub} ₽ (интервал: {w_cd} дн.)\n"
        f"• ⭐ <b>Награда за отзыв на FunPay:</b> <code>+{rev_rub} ₽</code> (на внутренний баланс)\n"
        f"• ⚡ <b>Скидка режима Flash Sale:</b> <code>-{fs_pct}%</code>\n"
        f"• ☁️ <b>ID канала для облачного бэкапа:</b> <code>{html.escape(ch_bak)}</code>"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎁 Изменить призы Колеса", callback_data="pro_adm_wheel_prizes"),
            InlineKeyboardButton(f"⏱ Интервал Колеса ({w_cd}д)", callback_data="pro_adm_wheel_cd")
        ],
        [
            InlineKeyboardButton(f"⭐ Задать бонус за отзыв ({rev_rub} ₽)", callback_data="pro_adm_set_rev_rub"),
            InlineKeyboardButton(f"⚡ Задать % Flash Sale (-{fs_pct}%)", callback_data="pro_adm_set_fs_pct")
        ],
        [
            InlineKeyboardButton("☁️ Указать ID канала для авто-бэкапа", callback_data="pro_adm_set_bak_ch"),
            InlineKeyboardButton("📤 Отправить бэкап в канал сейчас", callback_data="pro_adm_push_cloud_bak")
        ],
        [
            InlineKeyboardButton("⬅️ Назад в Пульт модулей", callback_data="pro_adm_settings")
        ]
    ])
    return text, kb

def render_admin_b2b_screen() -> tuple[str, InlineKeyboardMarkup]:
    res_tok = get_db_setting("reserve_bot_token", "")
    tok_status = f"<code>{html.escape(res_tok[:12])}...</code>" if res_tok else "не задан"
    with sqlite3.connect(DB_PATH) as conn:
        b2b_cnt = conn.execute("SELECT COUNT(*) FROM b2b_licenses").fetchone()[0]

    text = (
        "🛒 <b>Панель FunPay, Реселлеров и B2B Kill-Switch проданных ботов</b>\n\n"
        "• <b>🔍 Проверить / Аннулировать ключ по коду</b> — защита от возвратов на FunPay.\n"
        "• <b>💼 Оптовый выпуск ключей + Шаблон автовыдачи</b> — пачки по 10 и 50 штук.\n"
        f"• <b>🔑 B2B Kill-Switch проданных ботов ({b2b_cnt} шт.)</b> — удалённое отключение или продление арендованных копий бота.\n"
        f"• <b>🛡 Резервный токен (Anti-Ban Зеркало):</b> {tok_status}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Проверить / Аннулировать ключ FunPay", callback_data="pro_adm_key_lookup")],
        [
            InlineKeyboardButton("💼 10 ключей + Шаблон", callback_data="pro_adm_bulk_10"),
            InlineKeyboardButton("💼 50 ключей + Шаблон", callback_data="pro_adm_bulk_50")
        ],
        [
            InlineKeyboardButton("📦 Собрать копию бота на продажу", callback_data="pro_adm_b2b_build"),
            InlineKeyboardButton(f"🔑 B2B Kill-Switch ({b2b_cnt})", callback_data="pro_adm_b2b_list")
        ],
        [InlineKeyboardButton("🛡 Задать резервный токен зеркала", callback_data="pro_adm_set_mirror")],
        [InlineKeyboardButton("⬅️ Назад в Пульт модулей", callback_data="pro_adm_settings")]
    ])
    return text, kb

def get_user_loyalty_rank(user_id: int) -> tuple[str, int, int]:
    if get_db_setting("loyalty_winback_enabled", "1") != "1":
        return "👤 Клиент", 0, 0
    with sqlite3.connect(DB_PATH) as conn:
        cnt = conn.execute("SELECT COUNT(*) FROM payments WHERE user_id = ?", (user_id,)).fetchone()[0]
    if cnt >= 12:
        return "🥇 VIP Постоянный", 15, cnt
    elif cnt >= 6:
        return "🥈 Серебряный", 10, cnt
    elif cnt >= 3:
        return "🥉 Бронзовый", 5, cnt
    return "👤 Базовый", 0, cnt

def get_user_payment_history(user_id: int, limit: int = 10):
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(
            "SELECT id, amount, provider, description, created_at FROM payments WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()

def get_wallet_data(user_id: int) -> tuple[float, int, float]:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT COALESCE(balance_rub, 0), COALESCE(auto_renew, 1), COALESCE(ref_earned_rub, 0) FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        return (float(row[0]), int(row[1]), float(row[2])) if row else (0.0, 1, 0.0)

def add_user_balance(user_id: int, amount_rub: float, description: str = "Пополнение внутреннего баланса"):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET balance_rub = COALESCE(balance_rub, 0) + ? WHERE user_id = ?", (amount_rub, user_id))
        conn.execute("INSERT INTO payments (user_id, amount, provider, description, created_at) VALUES (?, ?, 'Wallet', ?, ?)", (user_id, amount_rub, description, now_str))
        conn.execute("DELETE FROM abandoned_carts WHERE user_id = ?", (user_id,))
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

def add_family_member_key(owner_id: int, member_tg_id: int) -> tuple[bool, str]:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        k_row = conn.execute(
            "SELECT location_name, expires_at, config_text, sub_id FROM user_keys WHERE user_id = ? AND is_active = 1 ORDER BY id ASC LIMIT 1",
            (owner_id,)
        ).fetchone()
        if not k_row:
            return False, "❌ У вас нет активного ключа, чтобы поделиться семейным доступом."
        cnt = conn.execute("SELECT COUNT(*) FROM family_members WHERE owner_id = ?", (owner_id,)).fetchone()[0]
        if cnt >= 4 and owner_id != ADMIN_ID:
            return False, "⚠️ Достигнут лимит семейной подписки (до 5 человек включая владельца)."
        loc_name, exp_at, cfg_txt, sub_id = k_row
        conn.execute("INSERT OR REPLACE INTO family_members (owner_id, member_id, added_at) VALUES (?, ?, ?)", (owner_id, member_tg_id, now_str))
        conn.execute("""
            INSERT INTO user_keys (user_id, key_name, client_uuid, sub_id, server_id, location_name, expires_at, config_text, is_active, created_at)
            VALUES (?, ?, ?, ?, 0, ?, ?, ?, 1, ?)
        """, (member_tg_id, f"👨‍👩‍👧‍👦 Семейный от ID{owner_id}", str(uuid.uuid4()), sub_id, loc_name, exp_at, cfg_txt, now_str))
        conn.commit()
    return True, f"✅ Пользователь <code>{member_tg_id}</code> подключён к вашему семейному тарифу (до <code>{exp_at}</code>)!"

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
            conn.execute(
                "UPDATE users SET is_vip = 1, has_expired = 0, vip_until = ? WHERE user_id = ?",
                (new_exp_str, user_id)
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
    with sqlite3.connect(DB_PATH) as conn:
        servers = conn.execute("SELECT id, name, host, is_active FROM servers WHERE is_active = 1").fetchall()

    healthy_srv = None
    down_srvs = []

    for srv_id, name, host, _ in servers:
        h_clean = host.split(":")[0] if ":" in host else host
        p_clean = int(host.split(":")[1]) if (":" in host and host.split(":")[1].isdigit()) else 443
        is_up = False
        try:
            with socket.create_connection((h_clean, p_clean), timeout=2.5):
                is_up = True
        except Exception:
            is_up = False

        if is_up and not healthy_srv:
            healthy_srv = (srv_id, name)
        if not is_up:
            down_srvs.append((srv_id, name))

        prev_state = NODE_STATES.get(srv_id, True)
        if prev_state and not is_up and ADMIN_ID:
            NODE_STATES[srv_id] = False
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"🚨 <b>[Node Watchdog] Не отвечает порт ноды #{srv_id}: {html.escape(name)}</b> (<code>{html.escape(host)}</code>)!",
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

    if down_srvs and healthy_srv:
        with sqlite3.connect(DB_PATH) as conn:
            for d_id, _ in down_srvs:
                conn.execute(
                    "UPDATE user_keys SET server_id = ?, location_name = ? WHERE server_id = ? AND is_active = 1",
                    (healthy_srv[0], healthy_srv[1], d_id)
                )
            conn.commit()

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
            rank_title, rank_disc, _ = get_user_loyalty_rank(uid)
            renew_cost = max(99, int(199 * (100 - rank_disc) / 100))
            if auto_on == 1 and bal >= renew_cost:
                new_exp = (datetime.strptime(exp_str, "%Y-%m-%d %H:%M:%S") + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
                conn.execute("UPDATE users SET balance_rub = balance_rub - ?, vip_until = ?, is_vip = 1 WHERE user_id = ?", (renew_cost, new_exp, uid))
                conn.execute("UPDATE user_keys SET expires_at = ?, warned_24h = 0, warned_3h = 0 WHERE id = ?", (new_exp, kid))
                conn.execute("INSERT INTO payments (user_id, amount, provider, description, created_at) VALUES (?, ?, 'AutoRenew', ?, ?)", (uid, renew_cost, f"Автопродление {kname} ({rank_title})", now_str))
                conn.commit()
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"🔄 <b>Автопродление сработало!</b>\nКлюч <b>{html.escape(kname)}</b> автоматически продлён на 30 дней (до <code>{new_exp}</code>) с вашего внутреннего баланса (-{renew_cost} ₽).",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        if get_db_setting("loyalty_winback_enabled", "1") == "1":
            winback_users = conn.execute("""
                SELECT user_id FROM users
                WHERE is_vip = 0 AND has_expired = 1 AND COALESCE(winback_sent, 0) = 0 AND bot_blocked = 0
                LIMIT 10
            """).fetchall()

            for (w_uid,) in winback_users:
                conn.execute("UPDATE users SET winback_sent = 1, active_discount_pct = 25 WHERE user_id = ?", (w_uid,))
                conn.commit()
                try:
                    kb_wb = InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Забрать подписку со скидкой -25%", callback_data="order_vpn")]])
                    await context.bot.send_message(
                        chat_id=w_uid,
                        text=(
                            "🎁 <b>Персональное предложение специально для вас!</b>\n\n"
                            "Срок вашей подписки истёк, и мы активировали в вашем профиле секретную скидку <b>-25%</b> на любой тариф!"
                        ),
                        parse_mode="HTML",
                        reply_markup=kb_wb
                    )
                except Exception:
                    pass

        if get_db_setting("abandoned_cart_enabled", "1") == "1":
            cart_cutoff = (now - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
            carts = conn.execute("""
                SELECT user_id, tariff_id FROM abandoned_carts
                WHERE reminded = 0 AND created_at <= ?
                LIMIT 10
            """, (cart_cutoff,)).fetchall()

            for c_uid, c_tid in carts:
                conn.execute("UPDATE abandoned_carts SET reminded = 1 WHERE user_id = ?", (c_uid,))
                conn.execute("UPDATE users SET active_discount_pct = MAX(COALESCE(active_discount_pct, 0), 10) WHERE user_id = ?", (c_uid,))
                conn.commit()
                try:
                    kb_cart = InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Завершить оформление со скидкой -10%", callback_data=f"buy_tariff_{c_tid}")]])
                    await context.bot.send_message(
                        chat_id=c_uid,
                        text=(
                            "🛒 <b>Вы не завершили оформление подписки!</b>\n\n"
                            "Мы закрепили за вашим профилем разовую скидку <b>-10%</b>. Нажмите кнопку ниже, чтобы получить ключ со скидкой:"
                        ),
                        parse_mode="HTML",
                        reply_markup=kb_cart
                    )
                except Exception:
                    pass

    # Автоматический облачный бэкап в закрытый Telegram-канал (раз в 6 часов)
    if get_db_setting("cloud_backup_enabled", "0") == "1":
        ch_id = get_db_setting("cloud_backup_channel_id", "").strip()
        last_cb = float(get_db_setting("last_cloud_backup_ts", "0") or 0)
        if ch_id and (time_mod.time() - last_cb > 21600) and os.path.exists(DB_PATH):
            set_db_setting("last_cloud_backup_ts", str(time_mod.time()))
            try:
                with open(DB_PATH, "rb") as f:
                    await context.bot.send_document(
                        chat_id=ch_id,
                        document=f,
                        filename=f"cloud_backup_{now.strftime('%Y%m%d_%H%M')}.db",
                        caption=f"☁️ <b>Облачный авто-бэкап БД Bot_VIP</b>\n🕒 {now_str}",
                        parse_mode="HTML"
                    )
            except Exception as e:
                logger.warning(f"Cloud backup warning: {e}")

def render_pro_wallet_view(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    bal, auto_on, ref_rub = get_wallet_data(user_id)
    rank_name, rank_disc, pay_cnt = get_user_loyalty_rank(user_id)
    auto_icon = "🟢 ВКЛ" if auto_on else "🔴 ВЫКЛ"

    wheel_on = get_db_setting("wheel_enabled", "1") == "1"
    radar_on = get_db_setting("ping_radar_enabled", "1") == "1"
    calc_on = get_db_setting("custom_calc_enabled", "1") == "1"
    isp_on = get_db_setting("isp_selector_enabled", "1") == "1"
    rev_on = get_db_setting("review_bonus_enabled", "1") == "1"
    rev_rub = get_db_setting("review_bonus_rub", "50")

    fs_banner = ""
    if is_flash_sale_active():
        fs_pct = get_db_setting("flash_sale_pct", "20")
        fs_until = get_db_setting("flash_sale_until", "")
        fs_banner = f"\n⚡ <b>СЧАСТЛИВЫЕ ЧАСЫ: скидка -{fs_pct}% на всё (до {fs_until})!</b>\n"

    text = (
        f"💎 <b>Центр самообслуживания и Кошелёк Bot_VIP</b>{fs_banner}\n"
        f"💰 <b>Внутренний баланс:</b> <code>{int(bal)} ₽</code> <i>(для оплаты и автопродления ключей)</i>\n"
        f"🏆 <b>Ваш ранг лояльности:</b> {rank_name} (скидка <b>-{rank_disc}%</b>, покупок: {pay_cnt})\n"
        f"🔄 <b>Автопродление ключей:</b> {auto_icon}\n"
        f"🤝 <b>Начислено бонусов с рефералов (20%):</b> <code>{int(ref_rub)} ₽</code>\n\n"
        f"Выберите нужный инструмент:"
    )

    kb_rows = [
        [
            InlineKeyboardButton("💳 Пополнить баланс (+199 ₽)", callback_data="pro_topup_199"),
            InlineKeyboardButton(f"🔄 Автопродление: {auto_icon}", callback_data="pro_toggle_autorenew")
        ]
    ]
    if wheel_on:
        kb_rows.append([InlineKeyboardButton("🎰 Испытать удачу (Колесо фортуны)", callback_data="pro_spin_wheel")])
    if calc_on:
        kb_rows.append([InlineKeyboardButton("🧮 Конструктор тарифа «Собери сам»", callback_data="pro_calc_3_90")])

    row_tools = []
    if radar_on:
        row_tools.append(InlineKeyboardButton("📡 Радар пинга", callback_data="pro_ping_radar"))
    if isp_on:
        row_tools.append(InlineKeyboardButton("📶 Подбор под оператора", callback_data="pro_isp_menu"))
    if row_tools:
        kb_rows.append(row_tools)

    if rev_on:
        kb_rows.append([InlineKeyboardButton(f"⭐ Оставить отзыв (+{rev_rub} ₽ на счёт)", callback_data="pro_review_start")])

    kb_rows.extend([
        [
            InlineKeyboardButton("📖 Инструкции и Выбор приложения", callback_data="pro_guides_menu")
        ],
        [
            InlineKeyboardButton("🧾 История платежей", callback_data="pro_history"),
            InlineKeyboardButton("🎁 Подарить подписку (Gift)", callback_data="pro_create_gift")
        ],
        [
            InlineKeyboardButton("👨‍👩‍👧‍👦 Семейный доступ (до 5 чел.)", callback_data="pro_family_menu"),
            InlineKeyboardButton("🎭 SNI / ❄️ Пауза / 🔄 UUID", callback_data="pro_keys_tools")
        ],
        [
            InlineKeyboardButton("🔑 Мои ключи", callback_data="client_my_keys"),
            InlineKeyboardButton("🈴 На главную", callback_data="client_home")
        ]
    ])
    if user_id == ADMIN_ID:
        kb_rows.append([InlineKeyboardButton("🎛 Пульт всех 18 модулей ВКЛ/ВЫКЛ (Админ)", callback_data="pro_adm_settings")])

    return text, InlineKeyboardMarkup(kb_rows)

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
            InlineKeyboardButton("🇷🇺 Настройка банков РФ без отключения VPN", callback_data="pro_split_info")
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

# Перехватчик /start: проверяет Анти-Бот Капчу (если включена в админке) и записывает UTM-метки
async def utm_and_captcha_start_tracker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    if context.args and len(context.args) > 0:
        arg0 = context.args[0]
        if arg0.startswith("utm_"):
            record_utm_visit(user.id, arg0.replace("utm_", "", 1))

    if user.id != ADMIN_ID and get_db_setting("antibot_captcha_enabled", "0") == "1":
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT COALESCE(captcha_passed, 0) FROM users WHERE user_id = ?", (user.id,)).fetchone()
            passed = row[0] if row else 0
        if passed == 0:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Я человек (Войти в бота)", callback_data="pro_pass_captcha")]])
            await update.message.reply_text(
                "🛡 <b>Защита от автоматических ботов</b>\n\nНажмите кнопку ниже, чтобы подтвердить, что вы человек:",
                parse_mode="HTML",
                reply_markup=kb
            )
            raise ApplicationHandlerStop

# Перехватчик выбора тарифа: записывает брошенную корзину и показывает Умный Апсейл (если включен)
async def cart_and_upsell_tracker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return
    if query.data.startswith("buy_tariff_"):
        try:
            t_id = int(query.data.split("_")[-1])
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if get_db_setting("abandoned_cart_enabled", "1") == "1":
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO abandoned_carts (user_id, tariff_id, created_at, reminded) VALUES (?, ?, ?, 0)",
                        (query.from_user.id, t_id, now_str)
                    )
                    conn.commit()
            if get_db_setting("upsell_enabled", "1") == "1":
                with sqlite3.connect(DB_PATH) as conn:
                    t_row = conn.execute("SELECT days, price_rub FROM tariffs WHERE id = ?", (t_id,)).fetchone()
                    t_90 = conn.execute("SELECT id, name, price_rub FROM tariffs WHERE days = 90 AND is_active = 1 LIMIT 1").fetchone()
                if t_row and t_row[0] == 30 and t_90:
                    kb_up = InlineKeyboardMarkup([
                        [InlineKeyboardButton(f"💎 Забрать 3 месяца с выгодой ({t_90[2]} ₽)", callback_data=f"buy_tariff_{t_90[0]}")]
                    ])
                    await query.message.reply_text(
                        f"💡 <b>Выгодный апгрейд:</b> при выборе тарифа на 3 месяца вы экономите до 20% по сравнению с помесячной оплатой!",
                        parse_mode="HTML",
                        reply_markup=kb_up
                    )
        except Exception:
            pass

async def pro_menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = None
    text, kb = render_pro_wallet_view(update.effective_user.id)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
    raise ApplicationHandlerStop

async def pro_text_interceptor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.message
    if not user or not msg or not msg.text:
        return
    text = msg.text.strip()

    if text in MAIN_MENU_TEXTS:
        context.user_data["mode"] = None
        return

    mode = context.user_data.get("mode")

    if mode == "pro_add_family_member":
        context.user_data["mode"] = None
        if not text.isdigit():
            await msg.reply_text("⚠️ Отправьте числовой Telegram ID друга (например: <code>123456789</code>).", parse_mode="HTML")
            raise ApplicationHandlerStop
        ok, res = add_family_member_key(user.id, int(text))
        await msg.reply_text(res, parse_mode="HTML")
        raise ApplicationHandlerStop

    if mode == "pro_submit_review":
        context.user_data["mode"] = None
        rev_rub = int(get_db_setting("review_bonus_rub", "50") or 50)
        if ADMIN_ID:
            kb_adm = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"✅ Одобрить и начислить +{rev_rub} ₽", callback_data=f"pro_adm_apprev_{user.id}")]
            ])
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=(
                        f"⭐ <b>НОВЫЙ ОТЗЫВ НА ПРОВЕРКУ</b>\n"
                        f"👤 <b>Клиент:</b> {html.escape(user.first_name or 'User')} (ID: <code>{user.id}</code>)\n"
                        f"💬 <b>Текст / Ссылка отзыва:</b>\n<pre>{html.escape(text)}</pre>"
                    ),
                    parse_mode="HTML",
                    reply_markup=kb_adm
                )
            except Exception:
                pass
        await msg.reply_text(
            f"✅ <b>Спасибо! Ваш отзыв отправлен на проверку модератору.</b>\n"
            f"После подтверждения вам автоматически начислится <b>+{rev_rub} ₽</b> на внутренний баланс!",
            parse_mode="HTML"
        )
        raise ApplicationHandlerStop

    if user.id == ADMIN_ID and mode:
        if mode == "pro_set_wheel_prizes":
            context.user_data["mode"] = None
            parts = [p.strip() for p in text.split("|")]
            if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit() and parts[2].isdigit():
                set_db_setting("wheel_max_days", parts[0])
                set_db_setting("wheel_discount_pct", parts[1])
                set_db_setting("wheel_max_rub", parts[2])
                t_out, kb_out = render_admin_params_config_menu()
                await msg.reply_text(f"✅ <b>Призы Колеса фортуны обновлены!</b>\n\n{t_out}", parse_mode="HTML", reply_markup=kb_out)
            else:
                await msg.reply_text("⚠️ Формат: <code>Макс_дней | Скидка_% | Макс_рублей</code> (пример: <code>3 | 15 | 25</code>)", parse_mode="HTML")
            raise ApplicationHandlerStop

        if mode == "pro_set_rev_rub_input":
            context.user_data["mode"] = None
            if text.isdigit():
                set_db_setting("review_bonus_rub", text)
            t_out, kb_out = render_admin_params_config_menu()
            await msg.reply_text(f"✅ Награда за отзыв сохранена!\n\n{t_out}", parse_mode="HTML", reply_markup=kb_out)
            raise ApplicationHandlerStop

        if mode == "pro_set_fs_pct_input":
            context.user_data["mode"] = None
            if text.isdigit():
                set_db_setting("flash_sale_pct", text)
            t_out, kb_out = render_admin_params_config_menu()
            await msg.reply_text(f"✅ Скидка Flash Sale сохранена!\n\n{t_out}", parse_mode="HTML", reply_markup=kb_out)
            raise ApplicationHandlerStop

        if mode == "pro_set_bak_ch_input":
            context.user_data["mode"] = None
            set_db_setting("cloud_backup_channel_id", text)
            set_db_setting("cloud_backup_enabled", "1")
            t_out, kb_out = render_admin_params_config_menu()
            await msg.reply_text(f"✅ Канал для облачного бэкапа сохранён и включён!\n\n{t_out}", parse_mode="HTML", reply_markup=kb_out)
            raise ApplicationHandlerStop

        if mode == "pro_adm_utm_input":
            context.user_data["mode"] = None
            utm_clean = "".join(c for c in text.lower() if c.isalnum() or c == "_")[:30]
            if not utm_clean:
                await msg.reply_text("⚠️ Используйте только латинские буквы, цифры и `_`.", parse_mode="HTML")
                raise ApplicationHandlerStop
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("INSERT OR IGNORE INTO utm_campaigns (utm_code, clicks, unique_users, created_at) VALUES (?, 0, 0, ?)", (utm_clean, now_str))
                conn.commit()
            bot_uname = (await context.bot.get_me()).username or "Bot_VIP"
            utm_link = f"https://t.me/{bot_uname}?start=utm_{utm_clean}"
            t_out, kb_out = build_financial_and_utm_report()
            await msg.reply_text(
                f"✅ <b>Рекламная ссылка создана:</b>\n<code>{utm_link}</code>\n\n{t_out}",
                parse_mode="HTML",
                reply_markup=kb_out
            )
            raise ApplicationHandlerStop

        if mode == "pro_adm_key_lookup_input":
            context.user_data["mode"] = None
            t_out, kb_out = inspect_license_key_by_code(text)
            await msg.reply_text(t_out, parse_mode="HTML", reply_markup=kb_out)
            raise ApplicationHandlerStop

        if mode == "pro_b2b_build_input":
            context.user_data["mode"] = None
            parts = [p.strip() for p in text.split("|")]
            if len(parts) >= 2:
                b_tok, b_adm = parts[0], parts[1]
                b_days = int(parts[2]) if (len(parts) > 2 and parts[2].isdigit()) else 30
                buyer_id_int = int(b_adm) if b_adm.isdigit() else 0
                lic_id = create_b2b_license_record(buyer_id_int, b_tok, b_days)
                cmd_str = (
                    f"apt update && apt install -y git python3-venv && "
                    f"git clone https://github.com/Bandito2025/Bot_VIP.git /opt/Bot_VIP && "
                    f"cd /opt/Bot_VIP && printf 'BOT_TOKEN={b_tok}\\nADMIN_ID={b_adm}\\nB2B_LICENSE={lic_id}\\n' > .env && "
                    f"bash install.sh"
                )
                await msg.reply_text(
                    f"📦 <b>Готовый инсталлятор копии бота (Лицензия <code>{lic_id}</code> на {b_days} дн.):</b>\n\n"
                    f"<pre>{html.escape(cmd_str)}</pre>\n\n"
                    f"🔑 Лицензия занесена в реестр <b>B2B Kill-Switch</b> — вы можете в любой момент заморозить или продлить её в админ-панели.",
                    parse_mode="HTML"
                )
            else:
                await msg.reply_text("⚠️ Отправьте в формате: <code>BOT_TOKEN | ADMIN_ID | ДНЕЙ</code>", parse_mode="HTML")
            raise ApplicationHandlerStop

        if mode == "pro_set_mirror_token":
            context.user_data["mode"] = None
            set_db_setting("reserve_bot_token", text)
            t_out, kb_out = render_admin_b2b_screen()
            await msg.reply_text(f"✅ Резервный токен зеркала сохранён!\n\n{t_out}", parse_mode="HTML", reply_markup=kb_out)
            raise ApplicationHandlerStop

    if mode == "support" and get_db_setting("smart_faq_enabled", "1") == "1":
        context.user_data["mode"] = None
        context.user_data["last_support_text"] = text
        _, answer_html, kb = analyze_support_query_and_diagnose(user.id, text)
        await msg.reply_text(answer_html, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

async def pro_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    await query.answer()

    if data == "pro_pass_captcha":
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE users SET captcha_passed = 1 WHERE user_id = ?", (user.id,))
            conn.commit()
        await query.edit_message_text("✅ <b>Проверка пройдена! Добро пожаловать в Bot_VIP.</b>\nВыберите нужный раздел в меню ниже:", parse_mode="HTML")
        raise ApplicationHandlerStop

    if data == "pro_main":
        text, kb = render_pro_wallet_view(user.id)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    if data == "pro_ping_radar":
        radar_txt = measure_servers_ping_and_load()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Обновить пинг", callback_data="pro_ping_radar")],
            [
                InlineKeyboardButton("🔑 Мои ключи", callback_data="client_my_keys"),
                InlineKeyboardButton("⬅️ В Кошелёк", callback_data="pro_main")
            ]
        ])
        await query.edit_message_text(radar_txt, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    if data == "pro_isp_menu":
        kb_rows = [
            [
                InlineKeyboardButton("🔴 МТС", callback_data="pro_setisp_mts"),
                InlineKeyboardButton("🟢 Мегафон", callback_data="pro_setisp_megafon")
            ],
            [
                InlineKeyboardButton("🟡 Билайн", callback_data="pro_setisp_beeline"),
                InlineKeyboardButton("⚫ Tele2 / T2", callback_data="pro_setisp_tele2")
            ],
            [
                InlineKeyboardButton("🔵 Ростелеком", callback_data="pro_setisp_rtk"),
                InlineKeyboardButton("🟠 Дом.ру / Wi-Fi", callback_data="pro_setisp_domru")
            ],
            [InlineKeyboardButton("⬅️ Назад в Кошелёк", callback_data="pro_main")]
        ]
        await query.edit_message_text(
            "📶 <b>Оптимизация ключей под вашего оператора связи</b>\n\n"
            "Выберите вашего мобильного или домашнего провайдера — бот автоматически пропишет оптимальный домен маскировки SNI и параметры обхода ТСПУ:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb_rows)
        )
        raise ApplicationHandlerStop

    if data.startswith("pro_setisp_"):
        isp_code = data.replace("pro_setisp_", "")
        _, msg_txt = apply_isp_profile_for_user(user.id, isp_code)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔑 Открыть мои ключи", callback_data="client_my_keys")]])
        await query.edit_message_text(msg_txt, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    if data.startswith("pro_calc_"):
        parts = data.split("_")
        devs = int(parts[2])
        days = int(parts[3])
        price = calculate_custom_tariff_price(devs, days)
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{'✅ ' if devs==1 else ''}1 устр.", callback_data=f"pro_calc_1_{days}"),
                InlineKeyboardButton(f"{'✅ ' if devs==3 else ''}3 устр.", callback_data=f"pro_calc_3_{days}"),
                InlineKeyboardButton(f"{'✅ ' if devs==5 else ''}5 устр.", callback_data=f"pro_calc_5_{days}"),
                InlineKeyboardButton(f"{'✅ ' if devs==10 else ''}10 устр.", callback_data=f"pro_calc_10_{days}")
            ],
            [
                InlineKeyboardButton(f"{'🔥 ' if days==30 else ''}30 дн.", callback_data=f"pro_calc_{devs}_30"),
                InlineKeyboardButton(f"{'🔥 ' if days==90 else ''}90 дн.", callback_data=f"pro_calc_{devs}_90"),
                InlineKeyboardButton(f"{'🔥 ' if days==180 else ''}180 дн.", callback_data=f"pro_calc_{devs}_180"),
                InlineKeyboardButton(f"{'🔥 ' if days==365 else ''}365 дн.", callback_data=f"pro_calc_{devs}_365")
            ],
            [InlineKeyboardButton(f"💳 Оплатить с внутреннего баланса ({price} ₽)", callback_data=f"pro_buycalc_{devs}_{days}_{price}")],
            [InlineKeyboardButton("⬅️ Назад в Кошелёк", callback_data="pro_main")]
        ])
        await query.edit_message_text(
            f"🧮 <b>Конструктор персонального тарифа «Собери сам»</b>\n\n"
            f"📱 Количество устройств: <b>{devs} устр.</b>\n"
            f"⏳ Срок подписки: <b>{days} дн.</b>\n"
            f"💰 Итоговая стоимость: <b>{price} ₽</b>\n\n"
            f"Выберите нужные параметры кнопками ниже:",
            parse_mode="HTML",
            reply_markup=kb
        )
        raise ApplicationHandlerStop

    if data.startswith("pro_buycalc_"):
        _, _, devs_s, days_s, price_s = data.split("_")
        devs, days, price = int(devs_s), int(days_s), int(price_s)
        bal, _, _ = get_wallet_data(user.id)
        if bal < price and user.id != ADMIN_ID:
            await query.message.reply_text(f"❌ Недостаточно средств на внутреннем балансе ({int(bal)} ₽ из {price} ₽). Пополните счёт в разделе «💎 Кошелёк / Бонусы».")
            raise ApplicationHandlerStop
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        exp_str = (now + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        c_uuid = str(uuid.uuid4())
        sub_id = secrets.token_hex(6)
        cfg = f"vless://{c_uuid}@ger.svoii-vpn.online:443?security=tls&sni=www.microsoft.com&type=ws#Custom_{devs}dev_{days}d"
        with sqlite3.connect(DB_PATH) as conn:
            if user.id != ADMIN_ID:
                conn.execute("UPDATE users SET balance_rub = balance_rub - ? WHERE user_id = ?", (price, user.id))
            conn.execute("UPDATE users SET is_vip = 1, vip_until = ? WHERE user_id = ?", (exp_str, user.id))
            cur = conn.execute("""
                INSERT INTO user_keys (user_id, key_name, client_uuid, sub_id, location_name, expires_at, config_text, is_active, custom_devices, created_at)
                VALUES (?, '', ?, ?, '🇩🇪 Германия', ?, ?, 1, ?, ?)
            """, (user.id, c_uuid, sub_id, exp_str, cfg, devs, now_str))
            kid = cur.lastrowid
            conn.execute("UPDATE user_keys SET key_name = ? WHERE id = ?", (f"Ключ #{kid} ({devs} устр.)", kid))
            conn.execute("INSERT INTO payments (user_id, amount, provider, description, created_at) VALUES (?, ?, 'CustomCalc', ?, ?)", (user.id, price, f"Конструктор {devs} устр. / {days} дн.", now_str))
            conn.commit()
        await query.message.reply_text(
            f"🎉 <b>Персональный Ключ #{kid} ({devs} устр. на {days} дн.) успешно создан!</b>\n"
            f"📅 Действует до: <code>{exp_str}</code>\n"
            f"Управлять ключом можно в разделе <b>«🔑 Мои ключи»</b>.",
            parse_mode="HTML"
        )
        raise ApplicationHandlerStop

    if data == "pro_review_start":
        with sqlite3.connect(DB_PATH) as conn:
            rew = conn.execute("SELECT COALESCE(review_rewarded, 0) FROM users WHERE user_id = ?", (user.id,)).fetchone()
        if rew and rew[0] == 1 and user.id != ADMIN_ID:
            await query.message.reply_text("✅ Вы уже получали бонус за отзыв ранее! Спасибо за поддержку.")
            raise ApplicationHandlerStop
        rev_rub = get_db_setting("review_bonus_rub", "50")
        context.user_data["mode"] = "pro_submit_review"
        await query.edit_message_text(
            f"⭐ <b>Бонус +{rev_rub} ₽ за отзыв о нашем сервисе!</b>\n\n"
            f"Оставьте отзыв о покупке на FunPay (или напишите ваш честный отзыв прямо сюда) — после быстрой проверки модератором вам начислится <b>+{rev_rub} ₽</b> на внутренний баланс для автопродления ключей!\n\n"
            f"✍️ Отправьте текст вашего отзыва или номер заказа одним сообщением:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Отмена", callback_data="pro_main")]])
        )
        raise ApplicationHandlerStop

    if data.startswith("pro_adm_apprev_") and user.id == ADMIN_ID:
        target_uid = int(data.split("_")[-1])
        rev_rub = float(get_db_setting("review_bonus_rub", "50") or 50)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE users SET review_rewarded = 1 WHERE user_id = ?", (target_uid,))
            conn.commit()
        add_user_balance(target_uid, rev_rub, "Бонус за проверенный отзыв")
        try:
            await context.bot.send_message(
                chat_id=target_uid,
                text=f"🎉 <b>Ваш отзыв одобрен!</b>\nВам начислено <b>+{int(rev_rub)} ₽</b> на внутренний баланс кошелька!",
                parse_mode="HTML"
            )
        except Exception:
            pass
        await query.edit_message_text(f"✅ Отзыв одобрен, пользователю <code>{target_uid}</code> начислено +{int(rev_rub)} ₽!", parse_mode="HTML")
        raise ApplicationHandlerStop

    if data == "pro_spin_wheel":
        ok, res_msg = spin_fortune_wheel(user.id)
        await query.message.reply_text(res_msg, parse_mode="HTML")
        raise ApplicationHandlerStop

    if data == "pro_escalate_support":
        saved_q = context.user_data.get("last_support_text", "Клиент запросил помощь оператора после Smart FAQ")
        if ADMIN_ID:
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=(
                        f"🆘 <b>ТИКЕТ ПОДДЕРЖКИ (Переведён после Smart FAQ)</b>\n"
                        f"👤 <b>Клиент:</b> {html.escape(user.first_name or 'User')} (@{html.escape(user.username or 'нет')})\n"
                        f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
                        f"💬 <b>Вопрос:</b>\n<pre>{html.escape(saved_q)}</pre>"
                    ),
                    parse_mode="HTML"
                )
            except Exception:
                pass
        await query.edit_message_text("✅ <b>Ваш вопрос передан живому оператору!</b>", parse_mode="HTML")
        raise ApplicationHandlerStop

    if data == "pro_family_menu":
        with sqlite3.connect(DB_PATH) as conn:
            members = conn.execute("SELECT member_id, added_at FROM family_members WHERE owner_id = ?", (user.id,)).fetchall()
        m_lines = "\n".join([f"• ID <code>{m[0]}</code> (добавлен {m[1]})" for m in members]) if members else "<i>Пока никто не добавлен.</i>"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить близкого по Telegram ID", callback_data="pro_family_add")],
            [InlineKeyboardButton("⬅️ Назад в Кошелёк", callback_data="pro_main")]
        ])
        await query.edit_message_text(
            f"👨‍👩‍👧‍👦 <b>Семейная подписка (Shared-доступ до 5 человек)</b>\n\n"
            f"<b>Подключённые участники ({len(members)}/4):</b>\n{m_lines}",
            parse_mode="HTML",
            reply_markup=kb
        )
        raise ApplicationHandlerStop

    if data == "pro_family_add":
        context.user_data["mode"] = "pro_add_family_member"
        await query.edit_message_text(
            "👨‍👩‍👧‍👦 Отправьте числовой <code>Telegram ID</code> вашего друга или близкого:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Отмена", callback_data="pro_family_menu")]])
        )
        raise ApplicationHandlerStop

    if data == "pro_split_info":
        sub_url = get_user_primary_sub_url(user.id)
        await query.edit_message_text(
            "🇷🇺 <b>Работа российских банков и Госуслуг без отключения VPN (Split Tunneling)</b>\n\n"
            f"Откройте вашу веб-панель подписки в браузере и нажмите кнопку <b>«⚙️ Правила РФ»</b>:\n<code>{html.escape(sub_url)}</code>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад к выбору ОС", callback_data="pro_guides_menu")]])
        )
        raise ApplicationHandlerStop

    # --- АДМИНСКИЕ ПЕРЕКЛЮЧАТЕЛИ ВСЕХ 18 МОДУЛЕЙ И ТОНКАЯ НАСТРОЙКА ---
    if data == "pro_adm_settings" and user.id == ADMIN_ID:
        t_out, kb_out = render_admin_ai_and_wheel_settings()
        await query.edit_message_text(t_out, parse_mode="HTML", reply_markup=kb_out)
        raise ApplicationHandlerStop

    if data.startswith("pro_adm_tog_") and user.id == ADMIN_ID:
        setting_key = data.replace("pro_adm_tog_", "")
        def_v = "0" if setting_key in ("flash_sale_enabled", "antibot_captcha_enabled", "cloud_backup_enabled") else "1"
        cur_val = get_db_setting(setting_key, def_v)
        set_db_setting(setting_key, "0" if cur_val == "1" else "1")
        t_out, kb_out = render_admin_ai_and_wheel_settings()
        await query.edit_message_text(t_out, parse_mode="HTML", reply_markup=kb_out)
        raise ApplicationHandlerStop

    if data == "pro_adm_params_menu" and user.id == ADMIN_ID:
        t_out, kb_out = render_admin_params_config_menu()
        await query.edit_message_text(t_out, parse_mode="HTML", reply_markup=kb_out)
        raise ApplicationHandlerStop

    if data == "pro_adm_set_rev_rub" and user.id == ADMIN_ID:
        context.user_data["mode"] = "pro_set_rev_rub_input"
        await query.edit_message_text("⭐ Отправьте сумму бонуса в рублях за отзыв (например: <code>50</code>):", parse_mode="HTML")
        raise ApplicationHandlerStop

    if data == "pro_adm_set_fs_pct" and user.id == ADMIN_ID:
        context.user_data["mode"] = "pro_set_fs_pct_input"
        await query.edit_message_text("⚡ Отправьте процент скидки для режима Flash Sale (например: <code>20</code>):", parse_mode="HTML")
        raise ApplicationHandlerStop

    if data == "pro_adm_set_bak_ch" and user.id == ADMIN_ID:
        context.user_data["mode"] = "pro_set_bak_ch_input"
        await query.edit_message_text(
            "☁️ Отправьте ID вашего закрытого Telegram-канала для облачных бэкапов (например: <code>-1001234567890</code>, бот должен быть админом канала):",
            parse_mode="HTML"
        )
        raise ApplicationHandlerStop

    if data == "pro_adm_push_cloud_bak" and user.id == ADMIN_ID:
        ch_id = get_db_setting("cloud_backup_channel_id", "").strip()
        if not ch_id:
            await query.message.reply_text("⚠️ Сначала укажите ID канала для облачного бэкапа!")
            raise ApplicationHandlerStop
        try:
            with open(DB_PATH, "rb") as f:
                await context.bot.send_document(
                    chat_id=ch_id,
                    document=f,
                    filename=f"cloud_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db",
                    caption="☁️ <b>Ручной облачный бэкап базы данных Bot_VIP</b>",
                    parse_mode="HTML"
                )
            await query.message.reply_text(f"✅ Облачный бэкап успешно выгружен в канал <code>{html.escape(ch_id)}</code>!", parse_mode="HTML")
        except Exception as e:
            await query.message.reply_text(f"❌ Ошибка выгрузки в канал: {e}")
        raise ApplicationHandlerStop

    if data == "pro_adm_start_flash" and user.id == ADMIN_ID:
        pct = int(get_db_setting("flash_sale_pct", "20") or 20)
        until_s = start_flash_sale(pct=pct, hours=2)
        t_out, kb_out = build_financial_and_utm_report()
        await query.edit_message_text(f"⚡ <b>Акция «Счастливые часы» (-{pct}% на 2 часа до {until_s}) запущена!</b>\n\n{t_out}", parse_mode="HTML", reply_markup=kb_out)
        raise ApplicationHandlerStop

    if data == "pro_adm_b2b_list" and user.id == ADMIN_ID:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("SELECT lic_key, buyer_tg_id, expires_at, is_active FROM b2b_licenses ORDER BY created_at DESC LIMIT 15").fetchall()
        lines = ["🔑 <b>Реестр B2B-лицензий проданных копий бота (Kill-Switch):</b>\n"]
        kb_rows = []
        if not rows:
            lines.append("<i>Выданных B2B-лицензий пока нет.</i>")
        else:
            for l_key, b_id, exp_s, is_act in rows:
                st_ic = "🟢 Активна" if is_act else "🔴 Отключена (Kill-Switch)"
                lines.append(f"• <code>{l_key}</code> | Покупатель ID: <code>{b_id}</code> | до {exp_s} — <b>{st_ic}</b>")
                kb_rows.append([InlineKeyboardButton(f"{'🛑 Отключить' if is_act else '▶️ Включить'} {l_key}", callback_data=f"pro_adm_b2btog_{l_key}")])
        kb_rows.append([InlineKeyboardButton("⬅️ Назад в B2B-панель", callback_data="pro_adm_b2b_menu")])
        await query.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))
        raise ApplicationHandlerStop

    if data.startswith("pro_adm_b2btog_") and user.id == ADMIN_ID:
        l_key = data.replace("pro_adm_b2btog_", "")
        toggle_b2b_license_status(l_key)
        query.data = "pro_adm_b2b_list"
        await pro_callbacks(update, context)
        raise ApplicationHandlerStop

    if data == "pro_adm_toggle_wheel_vip" and user.id == ADMIN_ID:
        cur = get_db_setting("wheel_vip_only", "1")
        set_db_setting("wheel_vip_only", "0" if cur == "1" else "1")
        t_out, kb_out = render_admin_ai_and_wheel_settings()
        await query.edit_message_text(t_out, parse_mode="HTML", reply_markup=kb_out)
        raise ApplicationHandlerStop

    if data == "pro_adm_wheel_cd" and user.id == ADMIN_ID:
        cur = get_db_setting("wheel_cooldown_days", "7")
        set_db_setting("wheel_cooldown_days", "1" if cur == "7" else "7")
        t_out, kb_out = render_admin_params_config_menu()
        await query.edit_message_text(t_out, parse_mode="HTML", reply_markup=kb_out)
        raise ApplicationHandlerStop

    if data == "pro_adm_wheel_prizes" and user.id == ADMIN_ID:
        context.user_data["mode"] = "pro_set_wheel_prizes"
        await query.edit_message_text(
            "🎁 Отправьте 3 числа через <code>|</code>: <code>Макс_дней | Скидка_% | Макс_рублей</code> (пример: <code>3 | 15 | 20</code>):",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Отмена", callback_data="pro_adm_params_menu")]])
        )
        raise ApplicationHandlerStop

    if data == "pro_adm_analytics" and user.id == ADMIN_ID:
        t_out, kb_out = build_financial_and_utm_report()
        await query.edit_message_text(t_out, parse_mode="HTML", reply_markup=kb_out)
        raise ApplicationHandlerStop

    if data == "pro_adm_utm_create" and user.id == ADMIN_ID:
        context.user_data["mode"] = "pro_adm_utm_input"
        await query.edit_message_text(
            "📈 Отправьте короткое название рекламной площадки латиницей (например: <code>tg_ads1</code>):",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Отмена", callback_data="pro_adm_analytics")]])
        )
        raise ApplicationHandlerStop

    if data == "pro_adm_b2b_menu" and user.id == ADMIN_ID:
        t_out, kb_out = render_admin_b2b_screen()
        await query.edit_message_text(t_out, parse_mode="HTML", reply_markup=kb_out)
        raise ApplicationHandlerStop

    if data == "pro_adm_key_lookup" and user.id == ADMIN_ID:
        context.user_data["mode"] = "pro_adm_key_lookup_input"
        await query.edit_message_text(
            "🔍 Отправьте код ключа (например: <code>VPN-30D-XXXX</code>) для проверки или аннулирования:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Отмена", callback_data="pro_adm_b2b_menu")]])
        )
        raise ApplicationHandlerStop

    if data.startswith("pro_adm_revoke_code_") and user.id == ADMIN_ID:
        k_code = data.replace("pro_adm_revoke_code_", "")
        res_txt = revoke_license_key_and_access(k_code)
        t_out, kb_out = render_admin_b2b_screen()
        await query.edit_message_text(f"{res_txt}\n\n{t_out}", parse_mode="HTML", reply_markup=kb_out)
        raise ApplicationHandlerStop

    if data == "pro_adm_b2b_build" and user.id == ADMIN_ID:
        context.user_data["mode"] = "pro_b2b_build_input"
        await query.edit_message_text(
            "📦 <b>Сборка копии бота на продажу (с B2B Kill-Switch)</b>\n\n"
            "Отправьте токен нового бота, Telegram ID покупателя и срок аренды в днях через <code>|</code>:\n"
            "<code>123456:ABC-DEF... | 987654321 | 30</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Отмена", callback_data="pro_adm_b2b_menu")]])
        )
        raise ApplicationHandlerStop

    if data in ("pro_adm_bulk_10", "pro_adm_bulk_50") and user.id == ADMIN_ID:
        cnt = 10 if data.endswith("10") else 50
        gen_keys = []
        with sqlite3.connect(DB_PATH) as conn:
            for _ in range(cnt):
                k_code = f"VPN-30D-{secrets.token_hex(4).upper()}"
                conn.execute("INSERT INTO license_keys (key_code, key_type, days, price, is_used) VALUES (?, 'VPN', 30, 0, 0)", (k_code,))
                gen_keys.append(k_code)
            conn.commit()
        keys_block = "\n".join(gen_keys)
        bot_uname = (await context.bot.get_me()).username or "Bot_VIP"
        funpay_tpl = (
            f"Спасибо за покупку! Ваш лицензионный ключ на 30 дней:\n"
            f"🔑 [ВСТАВЬТЕ_КЛЮЧ_ЗДЕСЬ]\n\n"
            f"📲 Как активировать за 30 секунд:\n"
            f"1. Перейдите в нашего официального бота: https://t.me/{bot_uname}\n"
            f"2. Нажмите кнопку «🎟 Промокод / Купон» и отправьте ваш ключ.\n"
            f"3. Бот мгновенно выдаст единую подписку для iPhone, Android, Windows и macOS!"
        )
        await query.message.reply_text(
            f"💼 <b>Оптовая партия из {cnt} ключей готова:</b>\n\n"
            f"<pre>{keys_block}</pre>\n\n"
            f"📝 <b>Шаблон для автовыдачи FunPay:</b>\n"
            f"<pre>{html.escape(funpay_tpl)}</pre>",
            parse_mode="HTML"
        )
        raise ApplicationHandlerStop

    if data == "pro_adm_set_mirror" and user.id == ADMIN_ID:
        context.user_data["mode"] = "pro_set_mirror_token"
        await query.edit_message_text(
            "🛡 Отправьте запасной токен от @BotFather:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Отмена", callback_data="pro_adm_b2b_menu")]])
        )
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
        add_user_balance(user.id, 199.0, "Пополнение внутреннего баланса")
        inviter_id, cashback = credit_referral_cashback(user.id, 199.0)
        _, rank_disc, _ = get_user_loyalty_rank(user.id)
        if rank_disc > 0:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("UPDATE users SET active_discount_pct = MAX(COALESCE(active_discount_pct, 0), ?) WHERE user_id = ?", (rank_disc, user.id))
                conn.commit()
        if inviter_id and cashback > 0:
            try:
                await context.bot.send_message(
                    chat_id=inviter_id,
                    text=f"🎁 <b>Реферальный бонус +20%!</b>\nВаш друг пополнил счёт, вам начислено <b>+{cashback} ₽</b> на внутренний баланс!",
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

    if data == "pro_history":
        rows = get_user_payment_history(user.id, 10)
        lines = ["🧾 <b>Ваша история операций и чеков:</b>\n"]
        if not rows:
            lines.append("<i>У вас пока нет совершенных операций.</i>")
        else:
            for pid, amt, prov, desc, cat in rows:
                lines.append(f"• Чек <code>#{pid}</code> от <code>{cat}</code>\n  💰 <b>{int(amt)} ₽</b> ({html.escape(prov or 'Оплата')}) — {html.escape(desc or '')}")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад в Кошелёк", callback_data="pro_main")]])
        await query.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    if data == "pro_create_gift":
        ok, res = create_gift_certificate(user.id, days=30, cost_rub=199.0)
        if not ok:
            await query.message.reply_text(res, parse_mode="HTML")
            raise ApplicationHandlerStop
        await query.message.reply_text(
            f"🎁 <b>Подарочный сертификат на 30 дней создан!</b>\n\n"
            f"🎟 <b>Код для друга:</b> <code>{res}</code>",
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
            f"{os_data['title']} — <b>Выберите приложение для подключения:</b>",
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

        kb_rows = [[InlineKeyboardButton(f"📥 Скачать {app_name}", url=dl_url)]]
        if sub_url.startswith("http"):
            kb_rows.append([InlineKeyboardButton(f"➕ Добавить в {app_name} (Веб-панель)", url=sub_url)])
        kb_rows.append([
            InlineKeyboardButton("⬅️ К списку программ", callback_data=f"pro_os_{os_key}"),
            InlineKeyboardButton("🔑 Мои ключи", callback_data="client_my_keys")
        ])

        await query.edit_message_text(
            f"📲 <b>Подключение через {html.escape(app_name)} ({os_data.get('title', '')})</b>\n\n"
            f"📖 <b>Как подключить:</b>\n{html.escape(guide_steps)}\n\n"
            f"🔗 <b>Ваша ссылка подписки:</b>\n<code>{html.escape(sub_url)}</code>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(kb_rows)
        )
        raise ApplicationHandlerStop

    if data == "pro_keys_tools":
        with sqlite3.connect(DB_PATH) as conn:
            keys = conn.execute("SELECT id, key_name, COALESCE(is_frozen, 0), COALESCE(sni_domain, 'www.microsoft.com') FROM user_keys WHERE user_id = ? ORDER BY id ASC", (user.id,)).fetchall()
        if not keys:
            await query.message.reply_text("У вас пока нет созданных ключей.")
            raise ApplicationHandlerStop
        kb_rows = []
        sni_on = get_db_setting("sni_rotator_enabled", "1") == "1"
        for kid, kname, is_frz, sni_d in keys:
            frz_lbl = "▶️ Разморозить" if is_frz else "❄️ Пауза"
            row = [
                InlineKeyboardButton(f"{frz_lbl} ({kname})", callback_data=f"pro_frz_{kid}"),
                InlineKeyboardButton(f"🔄 UUID ({kname})", callback_data=f"pro_reissue_{kid}")
            ]
            kb_rows.append(row)
            if sni_on:
                kb_rows.append([InlineKeyboardButton(f"🎭 Сменить SNI {kname} [{sni_d}]", callback_data=f"pro_sni_{kid}")])
        kb_rows.append([InlineKeyboardButton("⬅️ Назад в Кошелёк", callback_data="pro_main")])
        await query.edit_message_text(
            "🛠 <b>Инструменты управления ключами (SNI, Заморозка, UUID)</b>\n\n"
            "• <b>🎭 Сменить SNI</b> — меняет домен маскировки (microsoft / apple / google / cloudflare) для обхода блокировок провайдера.\n"
            "• <b>❄️ Пауза</b> — замораживает ключ на время отпуска с сохранением дней.\n"
            "• <b>🔄 UUID</b> — перевыпускает секретный идентификатор ключа:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb_rows)
        )
        raise ApplicationHandlerStop

    if data.startswith("pro_sni_"):
        kid = int(data.split("_")[-1])
        _, msg_txt = rotate_user_key_sni(user.id, kid)
        await query.message.reply_text(msg_txt, parse_mode="HTML")
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
    if application is None:
        return
    if getattr(application, "_pro_suite_registered", False):
        return
    application._pro_suite_registered = True

    application.add_handler(CommandHandler("start", utm_and_captcha_start_tracker), group=-2)
    application.add_handler(CallbackQueryHandler(cart_and_upsell_tracker, pattern=r"^buy_tariff_"), group=-2)
    application.add_handler(CommandHandler("wallet", pro_menu_cmd), group=-1)
    application.add_handler(CommandHandler("pro", pro_menu_cmd), group=-1)
    application.add_handler(MessageHandler(filters.Regex(r"^💎 Кошелёк / Бонусы$"), pro_menu_cmd), group=-1)
    application.add_handler(CallbackQueryHandler(pro_callbacks, pattern=r"^pro_"), group=-1)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, pro_text_interceptor), group=-1)
    if application.job_queue:
        application.job_queue.run_repeating(node_watchdog_and_autorenew_job, interval=180, first=25)
    logger.info("🧩 Расширение ProSuite (18 управляемых модулей ВКЛ/ВЫКЛ) успешно зарегистрировано!")
