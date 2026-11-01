import staff_roles
from payment_cards import handle_payment_admin_callback, handle_payment_admin_text, render_gateway_card
import autopay
import os
import re
import sys
import csv
import json
import html
import uuid
import shutil
import base64
import socket
import secrets
import hashlib
import sqlite3
import logging
import threading
import importlib.util
import subprocess
import traceback
import time as time_mod
from urllib.parse import quote
from datetime import datetime, timedelta, time
from http.server import HTTPServer, BaseHTTPRequestHandler
import httpx
from dotenv import load_dotenv
from telegram import (
    Update,
    WebAppInfo,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
)
from telegram.error import Forbidden
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
)

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "bot_data.db")
LOG_PATH = os.getenv("LOG_PATH", "bot.log")
SUB_PORT = int(os.getenv("SUB_PORT", "2097"))
EXTENSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_extensions")

if not TOKEN or TOKEN == "your_telegram_bot_token_here":
    raise ValueError("Ошибка: BOT_TOKEN не задан в файле .env!")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Bot_VIP")

USER_COOLDOWNS = {}
FLOOD_LIMIT_SECONDS = 0.5
MAX_KEY_ATTEMPTS = 5
USERS_PER_PAGE = 10
BOT_USERNAME_CACHE = ""

EXT_RUNTIME_STATE = {
    "last_load_str": "загрузка выключена",
    "loaded_count": 0,
    "error_count": 0,
    "details_log": []
}

MENU_BUTTONS = {
    "🔑 Мои ключи",
    "🌐 Купить VPN / Подписка",
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

NOTIF_TYPES = {
    "notify_orders":   ("🛒 Заявки и Оплаты", "1"),
    "notify_support":  ("🆘 Тикеты поддержки", "1"),
    "notify_keys":     ("🔑 Активация ключей и промо", "1"),
    "notify_text":     ("💬 Свободный текст", "1"),
    "notify_start":    ("🚀 Команда /start и Рефералы", "1"),
    "notify_menu":     ("🔘 Кнопки меню", "0"),
    "notify_security": ("🚨 Безопасность и баны", "1"),
    "notify_backup":   ("💾 Авто-бэкап в 03:00", "1"),
}

PAYMENT_PROVIDERS = {
    "stars":      {"title": "Telegram Stars",              "btn": "Telegram Stars",   "def_on": "0"},
    "cryptopay":  {"title": "Crypto Pay (@CryptoBot)",     "btn": "Crypto Pay",       "def_on": "0"},
    "yaseller":   {"title": "Крипто (@Ya_SellerBot)",      "btn": "Крипто",           "def_on": "0"},
    "tgpayments": {"title": "TG payments",                 "btn": "TG payments",      "def_on": "1"},
    "yookassa":   {"title": "ЮKassa",                      "btn": "ЮKassa",           "def_on": "1"},
    "wata":       {"title": "WATA",                        "btn": "WATA",             "def_on": "0"},
    "platega":    {"title": "Platega",                     "btn": "Platega",          "def_on": "0"},
    "cardlink":   {"title": "Cardlink",                    "btn": "Cardlink",         "def_on": "0"},
    "demo":       {"title": "Демо оплата (РФ)",            "btn": "Демо оплата (РФ)", "def_on": "0"},
}

def is_flooding(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return False
    now = time_mod.time()
    last = USER_COOLDOWNS.get(user_id, 0)
    if now - last < FLOOD_LIMIT_SECONDS:
        return True
    USER_COOLDOWNS[user_id] = now
    return False

def get_server_hwid() -> str:
    machine_id = ""
    if os.path.exists("/etc/machine-id"):
        try:
            with open("/etc/machine-id", "r") as f:
                machine_id = f.read().strip()
        except Exception:
            pass
    if not machine_id:
        machine_id = str(uuid.getnode())
    raw = f"{machine_id}:{ADMIN_ID}:Bot_VIP_Protected"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def format_bytes(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0.00 GB"
    gb = size_bytes / (1024 ** 3)
    if gb >= 1024:
        return f"{gb / 1024:.2f} TB"
    return f"{gb:.2f} GB"

# --- База данных SQLite ---
def init_db():
    os.makedirs(EXTENSIONS_DIR, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_at TEXT,
                is_vip INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                vip_until TEXT DEFAULT '',
                failed_attempts INTEGER DEFAULT 0,
                vpn_config TEXT DEFAULT '',
                bot_license TEXT DEFAULT '',
                server_id INTEGER DEFAULT 0,
                sub_id TEXT DEFAULT '',
                client_uuid TEXT DEFAULT '',
                trial_used INTEGER DEFAULT 0,
                has_expired INTEGER DEFAULT 0,
                bot_blocked INTEGER DEFAULT 0,
                referred_by INTEGER DEFAULT 0,
                referrals_count INTEGER DEFAULT 0,
                ref_bonus_days INTEGER DEFAULT 0,
                active_discount_pct INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                key_name TEXT DEFAULT '',
                client_uuid TEXT DEFAULT '',
                sub_id TEXT DEFAULT '',
                server_id INTEGER DEFAULT 0,
                location_name TEXT DEFAULT '🇩🇪 Германия',
                traffic_bytes INTEGER DEFAULT 0,
                limit_gb INTEGER DEFAULT 0,
                expires_at TEXT DEFAULT '',
                config_text TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                warned_24h INTEGER DEFAULT 0,
                warned_3h INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                days INTEGER DEFAULT 7,
                max_uses INTEGER DEFAULT 100,
                used_count INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS promo_usages (
                code TEXT,
                user_id INTEGER,
                used_at TEXT,
                PRIMARY KEY (code, user_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coupons (
                code TEXT PRIMARY KEY,
                discount_pct INTEGER DEFAULT 20,
                max_uses INTEGER DEFAULT 100,
                used_count INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coupon_usages (
                code TEXT,
                user_id INTEGER,
                used_at TEXT,
                PRIMARY KEY (code, user_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tariffs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_name TEXT DEFAULT 'VPN + Proxy',
                name TEXT,
                days INTEGER,
                price_rub INTEGER,
                price_stars INTEGER DEFAULT 100,
                is_active INTEGER DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS license_keys (
                key_code TEXT PRIMARY KEY,
                key_type TEXT DEFAULT 'VPN',
                days INTEGER,
                price REAL DEFAULT 0,
                is_used INTEGER DEFAULT 0,
                used_by INTEGER DEFAULT 0,
                used_at TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL DEFAULT 0,
                provider TEXT DEFAULT '',
                description TEXT,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                host TEXT,
                panel_type TEXT DEFAULT 'both',
                panel_url TEXT DEFAULT '',
                panel_user TEXT DEFAULT '',
                panel_pass TEXT DEFAULT '',
                inbound_id INTEGER DEFAULT 1,
                sub_url_prefix TEXT DEFAULT '',
                proxy_template TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vpn_pool (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id INTEGER DEFAULT 0,
                config_data TEXT,
                is_assigned INTEGER DEFAULT 0,
                assigned_to INTEGER DEFAULT 0,
                assigned_at TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                first_name TEXT,
                event_type TEXT,
                content TEXT,
                created_at TEXT
            )
        """)

        cur = conn.execute("PRAGMA table_info(users)")
        u_cols = [row[1] for row in cur.fetchall()]
        for col, default in [
            ("is_vip", "INTEGER DEFAULT 0"),
            ("is_banned", "INTEGER DEFAULT 0"),
            ("vip_until", "TEXT DEFAULT ''"),
            ("failed_attempts", "INTEGER DEFAULT 0"),
            ("vpn_config", "TEXT DEFAULT ''"),
            ("bot_license", "TEXT DEFAULT ''"),
            ("server_id", "INTEGER DEFAULT 0"),
            ("sub_id", "TEXT DEFAULT ''"),
            ("client_uuid", "TEXT DEFAULT ''"),
            ("trial_used", "INTEGER DEFAULT 0"),
            ("has_expired", "INTEGER DEFAULT 0"),
            ("bot_blocked", "INTEGER DEFAULT 0"),
            ("referred_by", "INTEGER DEFAULT 0"),
            ("referrals_count", "INTEGER DEFAULT 0"),
            ("ref_bonus_days", "INTEGER DEFAULT 0"),
            ("active_discount_pct", "INTEGER DEFAULT 0"),
        ]:
            if col not in u_cols:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {default}")

        cur_uk = conn.execute("PRAGMA table_info(user_keys)")
        uk_cols = [row[1] for row in cur_uk.fetchall()]
        for col, default in [
            ("warned_24h", "INTEGER DEFAULT 0"),
            ("warned_3h", "INTEGER DEFAULT 0"),
        ]:
            if col not in uk_cols:
                conn.execute(f"ALTER TABLE user_keys ADD COLUMN {col} {default}")

        cur_p = conn.execute("PRAGMA table_info(payments)")
        p_cols = [row[1] for row in cur_p.fetchall()]
        if "provider" not in p_cols:
            conn.execute("ALTER TABLE payments ADD COLUMN provider TEXT DEFAULT ''")

        t_cnt = conn.execute("SELECT COUNT(*) FROM tariffs").fetchone()[0]
        if t_cnt == 0:
            default_tariffs = [
                ("Единая подписка (3x-ui + Proxy)", "🔥 1 месяц (Все локации)", 30, 199, 100),
                ("Единая подписка (3x-ui + Proxy)", "💎 3 месяца (Выгодно)", 90, 499, 250),
                ("Единая подписка (3x-ui + Proxy)", "🚀 6 месяцев", 180, 899, 450),
                ("Единая подписка (3x-ui + Proxy)", "👑 1 год (VIP Максимум)", 365, 1490, 750),
                ("Единая подписка (3x-ui + Proxy)", "♾ Безлимит (Без срока)", 0, 2990, 1500),
                ("Лицензия Бота", "🤖 Аренда Бота (1 мес)", 30, 1500, 750),
                ("Лицензия Бота", "🤖 Полная лицензия Бота (1 год)", 365, 5900, 2900),
            ]
            for grp, nm, d_val, pr_rub, pr_st in default_tariffs:
                conn.execute(
                    "INSERT INTO tariffs (group_name, name, days, price_rub, price_stars, is_active) VALUES (?, ?, ?, ?, ?, 1)",
                    (grp, nm, d_val, pr_rub, pr_st)
                )

        conn.commit()

    for k, (_, def_val) in NOTIF_TYPES.items():
        if get_setting(k, "") == "":
            set_setting(k, def_val)

    for p_key, p_info in PAYMENT_PROVIDERS.items():
        if get_setting(f"pay_{p_key}_enabled", "") == "":
            set_setting(f"pay_{p_key}_enabled", p_info["def_on"])

    defaults = {
        "pay_yookassa_shop_id": "1368461",
        "pay_notify_enabled": "1",
        "trial_enabled": "1",
        "trial_days": "3",
        "currency_main": "RUB (₽)",
        "currency_usdt_rate": "95.0",
        "currency_stars_rate": "2.0",
        "ref_enabled": "1",
        "ref_bonus_days": "7",
        "ref_NewUser_days": "3",
        "device_limit_ip": "2",
        "webapp_url": "",
        "sub_domain_prefix": "https://sub.bot-vip.online/sub",
        "ext_load_enabled": "0",
        "ext_core_edit_allowed": "0",
        "require_channel_sub": "0",
        "text_welcome": "Добро пожаловать в <b>Bot_VIP</b>!\n\n🔑 Управляйте своими ключами в разделе <b>«🔑 Мои ключи»</b> или подключите новую подписку (<b>3x-ui + Web Panel Proxy 2.7.0</b>).",
        "text_about": "🤖 <b>Bot_VIP</b> — единая система подключения 3x-ui + Web Panel Proxy 2.7.0 и продажи защищенных Telegram-ботов.",
        "text_support": "✉️ <b>Напишите ваш вопрос одним сообщением:</b>\nОн будет сразу передан администратору, и вы получите ответ прямо в этом чате."
    }
    for d_key, d_val in defaults.items():
        if get_setting(d_key, "") == "":
            set_setting(d_key, d_val)

def get_setting(key: str, default: str = "") -> str:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else default

def set_setting(key: str, value: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value.strip()))
        conn.commit()

def is_notif_enabled(notif_key: str) -> bool:
    default_val = NOTIF_TYPES.get(notif_key, ("", "1"))[1]
    return get_setting(notif_key, default_val) == "1"

def verify_server_lock():
    current_hwid = get_server_hwid()
    saved_hwid = get_setting("server_hwid", "")
    if not saved_hwid:
        set_setting("server_hwid", current_hwid)
        logger.info("🔒 HWID Lock активирован.")
    elif saved_hwid != current_hwid:
        logger.critical("⛔ НАРУШЕНИЕ ЛИЦЕНЗИИ: База перенесена на чужой сервер или изменен ADMIN_ID!")
        sys.exit("FATAL: Unauthorized Server HWID or Admin ID change detected.")

def mark_user_blocked_bot(user_id: int, blocked: int = 1):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET bot_blocked = ? WHERE user_id = ?", (blocked, user_id))
        conn.commit()

# ==============================================================================
# 🌐 ВСТРОЕННЫЙ SUB-AGGREGATOR СЕРВЕР НА ПОРТУ 2096 (ВЫДАЕТ BASE64 ПОДПИСКУ)
# ==============================================================================
def start_sub_aggregator_server():
    try:
        class SubHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass
            def do_HEAD(self):
                self.do_GET()

            def do_GET(self):
                # --- Маршруты раздачи и проверки лицензий ---
                import os, sqlite3
                from urllib.parse import urlparse, parse_qs
                _parsed = urlparse(self.path)
                _req_path = _parsed.path
                
                if _req_path == '/install.sh':
                    _sh_file = '/opt/Bot_VIP/install.sh'
                    if os.path.exists(_sh_file):
                        with open(_sh_file, 'rb') as _f:
                            _c = _f.read()
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/plain; charset=utf-8')
                        self.send_header('Content-Length', str(len(_c)))
                        self.end_headers()
                        self.wfile.write(_c)
                    else:
                        self.send_response(404)
                        self.end_headers()
                        self.wfile.write(b'install.sh not found')
                    return
                
                if _req_path == '/api/download_bot':
                    _qs = parse_qs(_parsed.query)
                    _l_key = (_qs.get('key', [''])[0]).strip()
                    _allowed = (_l_key.upper() == 'FREE' or _l_key == 'VIP-MASTER-OWNER-777')
                    if not _allowed and 'DB_PATH' in globals():
                        try:
                            with sqlite3.connect(DB_PATH) as _conn:
                                _row = _conn.execute('SELECT id, is_active FROM bot_licenses WHERE lic_key = ?', (_l_key,)).fetchone()
                                if _row and _row[1] == 1:
                                    _allowed = True
                        except Exception:
                            pass
                    _arc = '/opt/Bot_VIP/bot.tar.gz'
                    if _allowed and os.path.exists(_arc):
                        with open(_arc, 'rb') as _f:
                            _ac = _f.read()
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/gzip')
                        self.send_header('Content-Disposition', 'attachment; filename="bot.tar.gz"')
                        self.send_header('Content-Length', str(len(_ac)))
                        self.end_headers()
                        self.wfile.write(_ac)
                    else:
                        self.send_response(403)
                        self.end_headers()
                        self.wfile.write(b'{"status":"error","msg":"Access denied or archive missing"}')
                    return
                
                if _req_path.startswith('/api/verify_license'):
                    _qs = parse_qs(_parsed.query)
                    _l_key = (_qs.get('key', [''])[0]).strip()
                    _c_ip = (_qs.get('ip', [''])[0]).strip() or self.client_address[0]
                    _c_adm = (_qs.get('admin_id', [''])[0]).strip()
                    if _l_key.upper() == 'FREE':
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(b'{"status":"ok","tier":"free","msg":"Free version activated"}')
                        return
                    if 'DB_PATH' in globals():
                        with sqlite3.connect(DB_PATH) as _conn:
                            _row = _conn.execute('SELECT id, bound_ip, is_active FROM bot_licenses WHERE lic_key = ?', (_l_key,)).fetchone()
                            if not _row or _row[2] == 0:
                                self.send_response(403)
                                self.send_header('Content-Type', 'application/json')
                                self.end_headers()
                                self.wfile.write(b'{"status":"error","msg":"Invalid or disabled license key"}')
                                return
                            _lid, _b_ip, _ = _row
                            if _l_key != 'VIP-MASTER-OWNER-777':
                                if _b_ip and _b_ip != _c_ip:
                                    self.send_response(403)
                                    self.send_header('Content-Type', 'application/json')
                                    self.end_headers()
                                    self.wfile.write(b'{"status":"error","msg":"License already bound to another server IP"}')
                                    return
                                if not _b_ip:
                                    _conn.execute('UPDATE bot_licenses SET bound_ip = ?, bound_admin_id = ? WHERE id = ?', (_c_ip, _c_adm, _lid))
                                    _conn.commit()
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(b'{"status":"ok","tier":"pro","msg":"PRO License verified"}')
                        return
                
                if "/sub/" in self.path:
                    sub_id = self.path.split("/sub/")[-1].split("?")[0].strip("/")
                    with sqlite3.connect(DB_PATH) as conn:
                        row_k = conn.execute("SELECT config_text FROM user_keys WHERE sub_id = ? AND is_active = 1", (sub_id,)).fetchone()
                        if row_k and row_k[0]:
                            cfg = row_k[0]
                        else:
                            row_u = conn.execute("SELECT vpn_config FROM users WHERE sub_id = ? AND is_vip = 1", (sub_id,)).fetchone()
                            cfg = row_u[0] if (row_u and row_u[0]) else ""
                    if cfg:
                        b64_body = base64.b64encode(cfg.encode("utf-8"))
                        self.send_response(200)
                        self.send_header("Content-Type", "text/plain; charset=utf-8")
                        self.send_header("Profile-Title", base64.b64encode("Bot_VIP Unified".encode("utf-8")).decode("utf-8"))
                        self.end_headers()
                        self.wfile.write(b64_body)
                        return
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Subscription not found or expired")

        srv = HTTPServer(("0.0.0.0", SUB_PORT), SubHandler)
        logger.info(f"🌐 Встроенный сервер единой подписки запущен на порту {SUB_PORT}")
        srv.serve_forever()
    except Exception as e:
        logger.warning(f"Sub-Aggregator port {SUB_PORT} warning: {e}")

# ==============================================================================
# 📢 ПРОВЕРКА ОБЯЗАТЕЛЬНОЙ ПОДПИСКИ НА КАНАЛ
# ==============================================================================
async def verify_user_subscribed_to_channel(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> tuple[bool, str]:
    if user_id == ADMIN_ID or get_setting("require_channel_sub", "0") != "1":
        return True, ""
    ch_url = get_setting("channel_url", "").strip()
    if not ch_url or "t.me/" not in ch_url:
        return True, ""
    ch_slug = ch_url.split("t.me/")[-1].split("/")[0].strip()
    if not ch_slug or ch_slug.startswith("+"):
        return True, ""
    chat_id_str = "@" + ch_slug.lstrip("@")
    try:
        member = await context.bot.get_chat_member(chat_id=chat_id_str, user_id=user_id)
        if member.status in ("left", "kicked"):
            return False, ch_url
        return True, ""
    except Exception:
        return True, ""

# ==============================================================================
# 🧩 МОДУЛЬ "ДИАГНОСТИКА РАСШИРЕНИЙ" (ТОЧЬ-В-ТОЧЬ ПО СКРИНШОТУ 9)
# ==============================================================================
def scan_and_load_extensions(application=None) -> dict:
    load_enabled = get_setting("ext_load_enabled", "0") == "1"
    core_edit_allowed = get_setting("ext_core_edit_allowed", "0") == "1"

    folder_exists = os.path.isdir(EXTENSIONS_DIR)
    total_files = 0
    to_load = 0
    bad_name = 0
    private_files = 0
    loaded_ok = 0
    load_errors = 0
    details = []

    if folder_exists:
        for fname in sorted(os.listdir(EXTENSIONS_DIR)):
            fpath = os.path.join(EXTENSIONS_DIR, fname)
            if os.path.isdir(fpath) or fname == "__pycache__":
                continue
            total_files += 1
            if fname.startswith("_"):
                private_files += 1
                details.append(f"🔒 <code>{html.escape(fname)}</code> — приватный файл (пропущен)")
                continue
            if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*\.py$", fname):
                bad_name += 1
                details.append(f"⚠️ <code>{html.escape(fname)}</code> — ошибка имени (требуется [a-zA-Z0-9_].py)")
                continue

            to_load += 1
            if load_enabled:
                try:
                    mod_name = f"custom_ext_{fname[:-3]}"
                    spec = importlib.util.spec_from_file_location(mod_name, fpath)
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        if application and hasattr(mod, "register_extension"):
                            mod.register_extension(application)
                        loaded_ok += 1
                        details.append(f"🟢 <code>{html.escape(fname)}</code> — успешно загружен")
                    else:
                        load_errors += 1
                        details.append(f"🔴 <code>{html.escape(fname)}</code> — не удалось создать spec")
                except Exception as e:
                    load_errors += 1
                    details.append(f"🔴 <code>{html.escape(fname)}</code> — ошибка: {html.escape(str(e)[:80])}")
            else:
                details.append(f"⚪️ <code>{html.escape(fname)}</code> — готов к загрузке (загрузка выключена)")

    if load_enabled:
        EXT_RUNTIME_STATE["last_load_str"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        EXT_RUNTIME_STATE["loaded_count"] = loaded_ok
        EXT_RUNTIME_STATE["error_count"] = load_errors
    else:
        EXT_RUNTIME_STATE["last_load_str"] = "загрузка выключена"
        EXT_RUNTIME_STATE["loaded_count"] = 0
        EXT_RUNTIME_STATE["error_count"] = 0

    EXT_RUNTIME_STATE["details_log"] = details

    if sys.platform.startswith("linux") and os.path.exists(__file__):
        try:
            os.chmod(__file__, 0o600 if core_edit_allowed else 0o400)
        except Exception:
            pass

    return {
        "load_enabled": load_enabled,
        "core_edit_allowed": core_edit_allowed,
        "folder_exists": folder_exists,
        "last_load_str": EXT_RUNTIME_STATE["last_load_str"],
        "total_files": total_files,
        "to_load": to_load,
        "bad_name": bad_name,
        "private_files": private_files,
        "loaded_ok": EXT_RUNTIME_STATE["loaded_count"],
        "load_errors": EXT_RUNTIME_STATE["error_count"],
        "details": details,
    }

def render_extensions_diagnostics_screen(application=None) -> tuple[str, InlineKeyboardMarkup]:
    st = scan_and_load_extensions(application)

    load_status_txt = "🟢 включена" if st["load_enabled"] else "⚪️ выключена"
    folder_status_txt = "найдена" if st["folder_exists"] else "не найдена"
    core_status_txt = "🔴 разрешено" if st["core_edit_allowed"] else "🟢 запрещено"

    btn_load_on_icon = "🟢" if st["load_enabled"] else "⚪️"
    btn_load_off_icon = "⚪️" if st["load_enabled"] else "🔴"

    btn_core_forbid_icon = "⚪️" if st["core_edit_allowed"] else "🟢"
    btn_core_allow_icon = "🟢" if st["core_edit_allowed"] else "⚪️"

    text = (
        "🧩 <b>Диагностика расширений</b>\n\n"
        f"<b>Загрузка:</b> {load_status_txt}\n"
        f"<b>Папка:</b> <code>custom_extensions</code> — {folder_status_txt}\n"
        f"<b>Последняя загрузка:</b> {html.escape(st['last_load_str'])}\n"
        f"<b>Файлы:</b> {st['total_files']} всего, {st['to_load']} к загрузке, {st['bad_name']} с ошибкой имени, {st['private_files']} приватных\n"
        f"<b>Итог:</b> {st['loaded_ok']} загружено, {st['load_errors']} с ошибками\n\n"
        f"<b>Редактирование ядра:</b> {core_status_txt}"
    )

    buttons = [
        [
            InlineKeyboardButton(f"{btn_load_on_icon} Загрузка включена", callback_data="admin_ext_load_on"),
            InlineKeyboardButton(f"{btn_load_off_icon} Загрузка выключена", callback_data="admin_ext_load_off")
        ],
        [
            InlineKeyboardButton(f"{btn_core_forbid_icon} Запрещено", callback_data="admin_ext_core_forbid"),
            InlineKeyboardButton(f"{btn_core_allow_icon} Разрешено", callback_data="admin_ext_core_allow")
        ],
        [
            InlineKeyboardButton("📋 Подробности", callback_data="admin_ext_details")
        ],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="admin_back_main"),
            InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
        ]
    ]
    return text, InlineKeyboardMarkup(buttons)

# ==============================================================================
# 🌐 ДВИЖОК ИНТЕГРАЦИИ: 3X-UI API + WEB PANEL PROXY 2.7.0
# ==============================================================================
async def poll_node_live_status(srv_row) -> dict:
    srv_id, name, host, panel_type, panel_url, panel_user, panel_pass, inbound_id, sub_prefix, proxy_tpl, is_active = srv_row
    if not is_active:
        return {"online": False, "deactivated": True, "error": "Деактивирован"}

    if panel_url and panel_type in ("3x-ui", "both"):
        base_url = panel_url.rstrip("/")
        try:
            async with httpx.AsyncClient(verify=False, timeout=4.0) as client:
                login_resp = await client.post(
                    f"{base_url}/login",
                    data={"username": panel_user, "password": panel_pass}
                )
                if login_resp.status_code != 200:
                    return {"online": False, "deactivated": False, "error": f"HTTP {login_resp.status_code} при входе"}

                inb_resp = await client.get(f"{base_url}/panel/api/inbounds/list")
                inb_data = inb_resp.json() if inb_resp.status_code == 200 else {}
                total_bytes = 0
                for inb in inb_data.get("obj", []) or []:
                    total_bytes += int(inb.get("up", 0)) + int(inb.get("down", 0))

                onl_resp = await client.post(f"{base_url}/panel/api/inbounds/onlines")
                onl_data = onl_resp.json() if onl_resp.status_code == 200 else {}
                online_list = onl_data.get("obj") or []
                online_count = len(online_list) if isinstance(online_list, list) else 0

                cpu_val = "4%"
                try:
                    st_resp = await client.post(f"{base_url}/server/status")
                    if st_resp.status_code == 200:
                        st_obj = st_resp.json().get("obj", {})
                        if "cpu" in st_obj:
                            cpu_val = f"{int(float(st_obj['cpu']))}%"
                except Exception:
                    pass

                return {
                    "online": True,
                    "deactivated": False,
                    "clients_online": online_count,
                    "traffic_str": format_bytes(total_bytes),
                    "cpu_str": cpu_val,
                    "error": ""
                }
        except httpx.TimeoutException:
            return {
                "online": False,
                "deactivated": False,
                "error": "Панель недоступна: timeout: /panel/api/inbounds/options: request timed out"
            }
        except Exception as e:
            return {"online": False, "deactivated": False, "error": f"Панель недоступна: {str(e)[:60]}"}

    host_clean = host.strip()
    port = 443
    if ":" in host_clean:
        h_part, p_part = host_clean.rsplit(":", 1)
        host_clean = h_part
        try:
            port = int(p_part)
        except ValueError:
            port = 443
    try:
        with socket.create_connection((host_clean, port), timeout=2.0):
            return {
                "online": True,
                "deactivated": False,
                "clients_online": 0,
                "traffic_str": "0.00 GB",
                "cpu_str": "2%",
                "error": ""
            }
    except Exception:
        return {
            "online": False,
            "deactivated": False,
            "error": "Панель недоступна: timeout: request timed out"
        }

async def fetch_key_live_traffic_bytes(email_tag: str, saved_bytes: int = 0) -> int:
    servers = [s for s in get_all_servers_full() if s[10] == 1 and s[4]]
    total_b = 0
    for srv in servers:
        base_url = srv[4].rstrip("/")
        try:
            async with httpx.AsyncClient(verify=False, timeout=3.0) as client:
                await client.post(f"{base_url}/login", data={"username": srv[5], "password": srv[6]})
                r = await client.get(f"{base_url}/panel/api/inbounds/getClientTraffics/{email_tag}")
                if r.status_code == 200:
                    obj = r.json().get("obj") or {}
                    total_b += int(obj.get("up", 0) or 0) + int(obj.get("down", 0) or 0)
        except Exception:
            pass
    return total_b if total_b > 0 else saved_bytes

async def provision_client_on_3xui(srv_row, user_id: int, client_uuid: str, sub_id: str, expiry_ms: int, key_id: int = 1) -> str:
    srv_id, name, host, panel_type, panel_url, panel_user, panel_pass, inbound_id, sub_prefix, proxy_tpl, is_active = srv_row
    email_tag = f"user_{user_id}_k{key_id}_s{srv_id}"
    host_only = host.split(":")[0] if ":" in host else host
    port_only = host.split(":")[1] if ":" in host else "443"
    limit_ip_val = int(get_setting("device_limit_ip", "2") or 2)

    if panel_url and panel_type in ("3x-ui", "both"):
        base_url = panel_url.rstrip("/")
        try:
            async with httpx.AsyncClient(verify=False, timeout=6.0) as client:
                await client.post(f"{base_url}/login", data={"username": panel_user, "password": panel_pass})
                client_settings = {
                    "clients": [{
                        "id": client_uuid,
                        "alterId": 0,
                        "email": email_tag,
                        "limitIp": limit_ip_val,
                        "totalGB": 0,
                        "expiryTime": expiry_ms,
                        "enable": True,
                        "tgId": str(user_id),
                        "subId": sub_id,
                        "flow": ""
                    }]
                }
                payload = {
                    "id": int(inbound_id or 1),
                    "settings": json.dumps(client_settings)
                }
                await client.post(f"{base_url}/panel/api/inbounds/addClient", data=payload)
        except Exception as e:
            logger.warning(f"3x-ui addClient warning on server #{srv_id}: {e}")

    if proxy_tpl:
        return (
            proxy_tpl.replace("{UUID}", client_uuid)
            .replace("{SUB_ID}", sub_id)
            .replace("{USER_ID}", str(user_id))
            .replace("{HOST}", host_only)
            .replace("{PORT}", port_only)
            .replace("{NAME}", quote(name))
        )

    return f"vless://{client_uuid}@{host_only}:{port_only}?encryption=none&security=tls&type=ws&host={host_only}&path=%2F#{quote(name)}"

async def create_or_extend_user_key(user_id: int, days: int = 30, create_new: bool = False, key_id: int = 0) -> tuple[int, str, str, str]:
    now = datetime.now()
    servers = [s for s in get_all_servers_full() if s[10] == 1]
    default_loc = servers[0][1] if servers else "🇩🇪 Германия"
    default_srv_id = servers[0][0] if servers else 0

    with sqlite3.connect(DB_PATH) as conn:
        if key_id > 0:
            k_row = conn.execute(
                "SELECT id, key_name, client_uuid, sub_id, location_name, expires_at FROM user_keys WHERE id = ? AND user_id = ?",
                (key_id, user_id)
            ).fetchone()
        elif not create_new:
            k_row = conn.execute(
                "SELECT id, key_name, client_uuid, sub_id, location_name, expires_at FROM user_keys WHERE user_id = ? AND is_active = 1 ORDER BY id ASC LIMIT 1",
                (user_id,)
            ).fetchone()
        else:
            k_row = None

        if k_row:
            k_id, k_name, client_uuid, sub_id, loc_name, exp_str = k_row
            base_date = now
            if exp_str and exp_str != "Без срока":
                try:
                    existing_dt = datetime.strptime(exp_str, "%Y-%m-%d %H:%M:%S")
                    if existing_dt > now:
                        base_date = existing_dt
                except Exception:
                    pass
            if days == 0:
                new_until_str = "Без срока"
                expiry_ms = 0
            else:
                new_until_dt = base_date + timedelta(days=days)
                new_until_str = new_until_dt.strftime("%Y-%m-%d %H:%M:%S")
                expiry_ms = int(new_until_dt.timestamp() * 1000)
        else:
            client_uuid = str(uuid.uuid4())
            sub_id = secrets.token_hex(6)
            loc_name = default_loc
            if days == 0:
                new_until_str = "Без срока"
                expiry_ms = 0
            else:
                new_until_dt = now + timedelta(days=days)
                new_until_str = new_until_dt.strftime("%Y-%m-%d %H:%M:%S")
                expiry_ms = int(new_until_dt.timestamp() * 1000)

            cur = conn.execute("""
                INSERT INTO user_keys (user_id, key_name, client_uuid, sub_id, server_id, location_name, traffic_bytes, limit_gb, expires_at, config_text, is_active, warned_24h, warned_3h, created_at)
                VALUES (?, '', ?, ?, ?, ?, 0, 0, ?, '', 1, 0, 0, ?)
            """, (user_id, client_uuid, sub_id, default_srv_id, loc_name, new_until_str, now.strftime("%Y-%m-%d %H:%M:%S")))
            k_id = cur.lastrowid
            k_name = f"Ключ #{k_id}"
            conn.execute("UPDATE user_keys SET key_name = ? WHERE id = ?", (k_name, k_id))
            conn.commit()

    generated_links = []
    primary_sub_url = ""

    for srv in servers:
        link = await provision_client_on_3xui(srv, user_id, client_uuid, sub_id, expiry_ms, k_id)
        generated_links.append(link)
        if srv[8] and not primary_sub_url:
            primary_sub_url = f"{srv[8].rstrip('/')}/{sub_id}"

    with sqlite3.connect(DB_PATH) as conn:
        p_cur = conn.execute("SELECT id, config_data FROM vpn_pool WHERE is_assigned = 0 LIMIT 1")
        p_row = p_cur.fetchone()
        if p_row:
            generated_links.append(p_row[1])
            conn.execute(
                "UPDATE vpn_pool SET is_assigned = 1, assigned_to = ?, assigned_at = ? WHERE id = ?",
                (user_id, now.strftime("%Y-%m-%d %H:%M:%S"), p_row[0])
            )
            conn.commit()

    global_sub_domain = get_setting("sub_domain_prefix", "")
    if global_sub_domain:
        primary_sub_url = f"{global_sub_domain.rstrip('/')}/{sub_id}"
    elif not primary_sub_url:
        primary_sub_url = f"https://sub.bot-vip.online/sub/{sub_id}"

    if not generated_links:
        generated_links.append(f"vless://{client_uuid}@ger.svoii-vpn.online:443?security=tls&type=ws#{quote(loc_name)}_3x-ui")
        generated_links.append(f"http://proxy.svoii-vpn.online:8080/{sub_id}#🌐_Web_Panel_Proxy_2.7.0")

    combined_text = "\n".join(generated_links)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE user_keys SET expires_at = ?, config_text = ?, is_active = 1, warned_24h = 0, warned_3h = 0 WHERE id = ?",
            (new_until_str, combined_text, k_id)
        )
        conn.execute("""
            UPDATE users
            SET is_vip = 1, has_expired = 0, vip_until = ?, vpn_config = ?, sub_id = ?, client_uuid = ?, failed_attempts = 0
            WHERE user_id = ?
        """, (new_until_str, combined_text, sub_id, client_uuid, user_id))
        conn.commit()

    return k_id, new_until_str, primary_sub_url, combined_text

async def build_unified_subscription_for_user(user_id: int, days: int = 30) -> tuple[str, str, str]:
    _, until_str, sub_url, combined = await create_or_extend_user_key(user_id, days=days, create_new=False)
    return until_str, sub_url, combined

# ==============================================================================
# ⏰ ФОНОВЫЕ НАПОМИНАНИЯ ОБ ИСТЕЧЕНИИ ПОДПИСКИ (ЗА 24 ЧАСА И 3 ЧАСА)
# ==============================================================================
async def check_expiry_reminders_job(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    t_24h = (now + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    t_3h = (now + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(DB_PATH) as conn:
        rows_24 = conn.execute("""
            SELECT id, user_id, key_name, expires_at FROM user_keys
            WHERE is_active = 1 AND warned_24h = 0 AND expires_at != '' AND expires_at != 'Без срока'
            AND expires_at > ? AND expires_at <= ?
        """, (now_str, t_24h)).fetchall()

        for kid, uid, kname, exp in rows_24:
            conn.execute("UPDATE user_keys SET warned_24h = 1 WHERE id = ?", (kid,))
            conn.commit()
            try:
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⏳ Продлить подписку в 1 клик", callback_data="order_vpn")],
                    [InlineKeyboardButton("🔑 Мои ключи", callback_data="client_my_keys")]
                ])
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"⚠️ <b>Напоминание: срок действия вашего ключа ({html.escape(kname)}) истекает менее чем через 24 часа (до <code>{exp}</code>).</b>\nПродлите подписку заранее, чтобы сохранить бесперебойный доступ:",
                    parse_mode="HTML",
                    reply_markup=kb
                )
            except Forbidden:
                mark_user_blocked_bot(uid, 1)
            except Exception:
                pass

        rows_3 = conn.execute("""
            SELECT id, user_id, key_name, expires_at FROM user_keys
            WHERE is_active = 1 AND warned_3h = 0 AND expires_at != '' AND expires_at != 'Без срока'
            AND expires_at > ? AND expires_at <= ?
        """, (now_str, t_3h)).fetchall()

        for kid, uid, kname, exp in rows_3:
            conn.execute("UPDATE user_keys SET warned_3h = 1 WHERE id = ?", (kid,))
            conn.commit()
            try:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("⏳ Продлить подписку сейчас", callback_data="order_vpn")]])
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"🚨 <b>Внимание! Ваш ключ ({html.escape(kname)}) отключится через 3 часа (в <code>{exp}</code>)!</b>",
                    parse_mode="HTML",
                    reply_markup=kb
                )
            except Forbidden:
                mark_user_blocked_bot(uid, 1)
            except Exception:
                pass

# ==============================================================================
# ⚙️ МОДУЛЬ "НАСТРОЙКИ БОТА" И АВТО-ОБНОВЛЕНИЕ ПРЯМО ИЗ БОТА
# ==============================================================================
def render_bot_settings_main_screen() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "⚙️ <b>Настройки бота</b>\n\n"
        "Выберите действие:"
    )
    buttons = [
        [InlineKeyboardButton("🔄 Обновления", callback_data="admin_bset_updates")],
        [InlineKeyboardButton("🌐 Веб и Mini App", callback_data="admin_bset_webapp")],
        [InlineKeyboardButton("📦 Создать бэкап", callback_data="admin_bset_backup")],
        [InlineKeyboardButton("📱 Ограничение устройств", callback_data="admin_bset_devices")],
        [InlineKeyboardButton("✏️ Изменить тексты", callback_data="admin_bset_texts")],
        [InlineKeyboardButton("📥 Скачать логи", callback_data="admin_bset_logs")],
        [InlineKeyboardButton("🛑 Остановить бота", callback_data="admin_bset_stop_confirm")],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="admin_back_main"),
            InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
        ]
    ]
    return text, InlineKeyboardMarkup(buttons)

def get_current_git_commit() -> str:
    try:
        res = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL)
        return res.decode("utf-8").strip()
    except Exception:
        return "main (stable)"

def create_manual_snapshot_backup() -> str:
    backup_root = "/opt/Bot_VIP/backup" if sys.platform.startswith("linux") else "backup"
    os.makedirs(backup_root, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    commit = get_current_git_commit()
    snap_dir = os.path.join(backup_root, f"{ts}_{commit}")
    os.makedirs(snap_dir, exist_ok=True)
    dst_db = os.path.join(snap_dir, "bot_data.db")
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, dst_db)
    with open(os.path.join(snap_dir, "commit.txt"), "w", encoding="utf-8") as f:
        f.write(commit)
    with open(os.path.join(snap_dir, "date.txt"), "w", encoding="utf-8") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    return dst_db if os.path.exists(dst_db) else DB_PATH

def perform_inbot_git_update(hard_reset: bool = False) -> tuple[bool, str]:
    """
    Создает бэкап БД, затем выполняет обновление кода с GitHub прямо из процесса бота
    (работает и на Linux-сервере, и на Windows ПК).
    """
    create_manual_snapshot_backup()
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        subprocess.run(["git", "fetch", "origin", "main"], cwd=repo_dir, check=False, timeout=20)
        if hard_reset:
            proc = subprocess.run(
                ["git", "reset", "--hard", "origin/main"],
                cwd=repo_dir, capture_output=True, text=True, timeout=20
            )
        else:
            proc = subprocess.run(
                ["git", "pull", "--ff-only", "origin", "main"],
                cwd=repo_dir, capture_output=True, text=True, timeout=20
            )
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        return proc.returncode == 0, out.strip()
    except Exception as e:
        return False, str(e)

# ==============================================================================
# 📣 МОДУЛЬ "МАРКЕТИНГ"
# ==============================================================================
def render_marketing_main_screen() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "📣 <b>Маркетинг</b>\n\n"
        "Выберите инструмент:"
    )
    buttons = [
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_mkt_broadcast_menu")],
        [InlineKeyboardButton("🔗 Реферальная система", callback_data="admin_mkt_referrals")],
        [InlineKeyboardButton("🎟 Промокоды", callback_data="admin_mkt_promocodes")],
        [InlineKeyboardButton("🎫 Купоны", callback_data="admin_mkt_coupons")],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="admin_back_main"),
            InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
        ]
    ]
    return text, InlineKeyboardMarkup(buttons)

def add_promocode_db(code: str, days: int, max_uses: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO promocodes (code, days, max_uses, used_count, created_at) VALUES (?, ?, ?, 0, ?)",
            (code.strip().upper(), days, max_uses, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()

def get_all_promocodes():
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("SELECT code, days, max_uses, used_count FROM promocodes ORDER BY created_at DESC").fetchall()

def delete_promocode_db(code: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM promocodes WHERE code = ?", (code,))
        conn.commit()

def add_coupon_db(code: str, discount_pct: int, max_uses: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO coupons (code, discount_pct, max_uses, used_count, created_at) VALUES (?, ?, ?, 0, ?)",
            (code.strip().upper(), discount_pct, max_uses, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()

def get_all_coupons():
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("SELECT code, discount_pct, max_uses, used_count FROM coupons ORDER BY created_at DESC").fetchall()

def delete_coupon_db(code: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM coupons WHERE code = ?", (code,))
        conn.commit()

async def redeem_code_universal(user_id: int, raw_code: str) -> tuple[bool, str]:
    code = raw_code.strip().upper()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(DB_PATH) as conn:
        p_row = conn.execute("SELECT days, max_uses, used_count FROM promocodes WHERE code = ?", (code,)).fetchone()
        if p_row:
            days, max_u, used_c = p_row
            if used_c >= max_u:
                return False, "❌ Лимит активаций этого промокода уже исчерпан."
            already = conn.execute("SELECT 1 FROM promo_usages WHERE code = ? AND user_id = ?", (code, user_id)).fetchone()
            if already:
                return False, "⚠️ Вы уже активировали этот промокод ранее."
            conn.execute("INSERT INTO promo_usages (code, user_id, used_at) VALUES (?, ?, ?)", (code, user_id, now_str))
            conn.execute("UPDATE promocodes SET used_count = used_count + 1 WHERE code = ?", (code,))
            conn.commit()

    if p_row:
        k_id, until, sub_url, _ = await create_or_extend_user_key(user_id, days=p_row[0], create_new=True)
        return True, (
            f"🎉 <b>Промокод <code>{html.escape(code)}</code> успешно активирован!</b>\n"
            f"🎁 Вам начислен <b>Ключ #{k_id}</b> на <b>{p_row[0]} дн.</b> (до <code>{until}</code>)\n\n"
            f"🔗 <b>Ссылка подписки:</b>\n<code>{html.escape(sub_url)}</code>"
        )

    with sqlite3.connect(DB_PATH) as conn:
        c_row = conn.execute("SELECT discount_pct, max_uses, used_count FROM coupons WHERE code = ?", (code,)).fetchone()
        if c_row:
            disc_pct, max_u, used_c = c_row
            if used_c >= max_u:
                return False, "❌ Лимит использований этого купона исчерпан."
            already_c = conn.execute("SELECT 1 FROM coupon_usages WHERE code = ? AND user_id = ?", (code, user_id)).fetchone()
            if already_c:
                return False, "⚠️ Вы уже активировали этот купон."
            conn.execute("INSERT INTO coupon_usages (code, user_id, used_at) VALUES (?, ?, ?)", (code, user_id, now_str))
            conn.execute("UPDATE coupons SET used_count = used_count + 1 WHERE code = ?", (code,))
            conn.execute("UPDATE users SET active_discount_pct = ? WHERE user_id = ?", (disc_pct, user_id))
            conn.commit()
            return True, (
                f"🎫 <b>Купон <code>{html.escape(code)}</code> активирован!</b>\n"
                f"🔥 Ваша персональная скидка <b>-{disc_pct}%</b> автоматически применится при выборе любого тарифа в разделе «🌐 Купить VPN / Подписка»!"
            )

    return await redeem_tariff_key_async(user_id, code)

# ==============================================================================
# 🔑 КЛИЕНТСКИЙ МОДУЛЬ "МОИ КЛЮЧИ" (DEEP-LINKS + QR-КОД)
# ==============================================================================
def get_user_keys_list(user_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("""
            SELECT id, key_name, client_uuid, sub_id, server_id, location_name,
                   traffic_bytes, limit_gb, expires_at, config_text, is_active
            FROM user_keys
            WHERE user_id = ?
            ORDER BY id ASC
        """, (user_id,))
        return cur.fetchall()

def get_single_user_key(key_id: int, user_id: int = 0):
    with sqlite3.connect(DB_PATH) as conn:
        if user_id > 0:
            cur = conn.execute("""
                SELECT id, user_id, key_name, client_uuid, sub_id, server_id, location_name,
                       traffic_bytes, limit_gb, expires_at, config_text, is_active
                FROM user_keys WHERE id = ? AND user_id = ?
            """, (key_id, user_id))
        else:
            cur = conn.execute("""
                SELECT id, user_id, key_name, client_uuid, sub_id, server_id, location_name,
                       traffic_bytes, limit_gb, expires_at, config_text, is_active
                FROM user_keys WHERE id = ?
            """, (key_id,))
        return cur.fetchone()

async def _old_unused_my_keys(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    keys = get_user_keys_list(user_id)
    webapp_url = get_setting("webapp_url", "")
    if not keys:
        kb_rows = [
            [InlineKeyboardButton("➕ Купить / Подключить ключ", callback_data="order_vpn")],
            [InlineKeyboardButton("🎁 Пробная подписка", callback_data="client_activate_trial_btn")]
        ]
        if webapp_url and webapp_url.startswith("https://"):
            kb_rows.append([InlineKeyboardButton("🌐 Открыть Mini App кабинет", web_app=WebAppInfo(url=webapp_url))])
        kb_rows.append([InlineKeyboardButton("🈴 На главную", callback_data="client_home")])
        return (
            "🔑 <b>Мои ключи</b>\n\n"
            "У вас пока нет активных ключей.\n"
            "Нажмите кнопку ниже, чтобы подключить единую подписку (3x-ui + Web Panel Proxy 2.7.0):",
            InlineKeyboardMarkup(kb_rows)
        )

    lines = ["🔑 <b>Мои ключи</b>\n"]
    kb_rows = []

    for k in keys:
        k_id, k_name, c_uuid, sub_id, srv_id, loc_name, tr_bytes, lim_gb, exp_at, cfg_txt, is_act = k
        email_tag = f"user_{user_id}_k{k_id}_s{srv_id or 1}"
        live_b = await fetch_key_live_traffic_bytes(email_tag, tr_bytes)
        if live_b != tr_bytes:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("UPDATE user_keys SET traffic_bytes = ? WHERE id = ?", (live_b, k_id))
                conn.commit()

        tr_str = format_bytes(live_b)
        lim_str = f"{lim_gb} GB" if lim_gb > 0 else "безлимит"
        exp_display = exp_at if exp_at else "Без срока"
        dot = "🟢" if is_act == 1 else "🔴"
        display_name = k_name if k_name else f"Ключ #{k_id}"

        lines.append(
            f"{dot} <b>{html.escape(display_name)}</b> - {tr_str} ({lim_str}) - до {html.escape(exp_display)}\n"
            f"📍 {html.escape(loc_name or '🇩🇪 Германия')}\n"
        )
        kb_rows.append([
            InlineKeyboardButton(f"{dot} {display_name}", callback_data=f"client_key_view_{k_id}")
        ])

    lines.append("Выберите ключ для управления:")
    kb_rows.append([InlineKeyboardButton("➕ Добавить ещё ключ", callback_data="order_vpn")])
    if webapp_url and webapp_url.startswith("https://"):
        kb_rows.append([InlineKeyboardButton("🌐 Открыть Mini App кабинет", web_app=WebAppInfo(url=webapp_url))])
    kb_rows.append([InlineKeyboardButton("🈴 На главную", callback_data="client_home")])

    return "\n".join(lines), InlineKeyboardMarkup(kb_rows)

async def render_single_key_control(user_id: int, key_id: int) -> tuple[str, InlineKeyboardMarkup]:
    row = get_single_user_key(key_id, user_id)
    if not row:
        return await render_my_keys_screen(user_id)

    k_id, uid, k_name, c_uuid, sub_id, srv_id, loc_name, tr_bytes, lim_gb, exp_at, cfg_txt, is_act = row
    email_tag = f"user_{user_id}_k{k_id}_s{srv_id or 1}"
    live_b = await fetch_key_live_traffic_bytes(email_tag, tr_bytes)
    tr_str = format_bytes(live_b)
    lim_str = f"{lim_gb} GB" if lim_gb > 0 else "безлимит"
    exp_display = exp_at if exp_at else "Без срока"
    dot = "🟢" if is_act == 1 else "🔴"
    dev_lim = get_setting("device_limit_ip", "2")

    sub_dom = get_setting("sub_domain_prefix", "https://sub.bot-vip.online/sub")
    sub_url = f"{sub_dom.rstrip('/')}/{sub_id}"

    text = (
        f"🔑 <b>Управление ключом: {html.escape(k_name)}</b>\n\n"
        f"📡 <b>Статус:</b> {dot} {'Активен' if is_act else 'Истёк'}\n"
        f"📍 <b>Локация:</b> {html.escape(loc_name)}\n"
        f"📊 <b>Трафик:</b> {tr_str} ({lim_str})\n"
        f"📱 <b>Лимит устройств:</b> {html.escape(dev_lim)}\n"
        f"⏳ <b>Срок действия:</b> до <code>{html.escape(exp_display)}</code>\n\n"
        f"🔗 <b>Единая ссылка подписки (3x-ui + Proxy 2.7.0):</b>\n"
        f"<code>{html.escape(sub_url)}</code>\n\n"
        f"🔐 <b>Конфигурация ключа:</b>\n"
        f"<pre>{html.escape(cfg_txt)}</pre>"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📲 Показать QR-код", callback_data=f"client_key_qr_{k_id}"),
            InlineKeyboardButton("📦 Base64 пакет", callback_data=f"client_key_b64_{k_id}")
        ],
        [
            InlineKeyboardButton("🌍 Сменить локацию", callback_data=f"client_key_loc_{k_id}"),
            InlineKeyboardButton("✏️ Переименовать", callback_data=f"client_key_ren_{k_id}")
        ],
        [
            InlineKeyboardButton("⏳ Продлить ключ", callback_data="order_vpn")
        ],
        [
            InlineKeyboardButton("⬅️ Назад к моим ключам", callback_data="client_my_keys"),
            InlineKeyboardButton("🈴 На главную", callback_data="client_home")
        ]
    ])
    return text, kb

# --- Синхронизация БД <-> Панель ---
async def sync_db_to_panels() -> tuple[int, int]:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT user_id FROM users WHERE is_vip = 1 AND is_banned = 0")
        active_uids = [r[0] for r in cur.fetchall()]
    servers = [s for s in get_all_servers_full() if s[10] == 1]
    synced_users = 0
    for uid in active_uids:
        await build_unified_subscription_for_user(uid, 0)
        synced_users += 1
    return synced_users, len(servers)

async def sync_panels_to_db() -> int:
    servers = [s for s in get_all_servers_full() if s[10] == 1 and s[4]]
    imported = 0
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for srv in servers:
        srv_id, name, host, p_type, p_url, p_user, p_pass, inb_id, sub_pref, prx_tpl, is_active = srv
        base_url = p_url.rstrip("/")
        try:
            async with httpx.AsyncClient(verify=False, timeout=6.0) as client:
                await client.post(f"{base_url}/login", data={"username": p_user, "password": p_pass})
                inb_resp = await client.get(f"{base_url}/panel/api/inbounds/list")
                if inb_resp.status_code != 200:
                    continue
                inb_list = inb_resp.json().get("obj", []) or []
                for inb in inb_list:
                    settings_str = inb.get("settings", "{}")
                    try:
                        settings_obj = json.loads(settings_str)
                    except Exception:
                        continue
                    for cl in settings_obj.get("clients", []) or []:
                        tg_id_raw = str(cl.get("tgId", "")).strip()
                        email_raw = str(cl.get("email", "")).strip()
                        c_uuid = cl.get("id", str(uuid.uuid4()))
                        c_sub = cl.get("subId", secrets.token_hex(6))
                        exp_ms = int(cl.get("expiryTime", 0) or 0)

                        uid_val = 0
                        if tg_id_raw.isdigit():
                            uid_val = int(tg_id_raw)
                        elif email_raw.startswith("user_"):
                            parts = email_raw.split("_")
                            if len(parts) > 1 and parts[1].isdigit():
                                uid_val = int(parts[1])

                        if uid_val > 0:
                            until_str = (
                                datetime.fromtimestamp(exp_ms / 1000.0).strftime("%Y-%m-%d %H:%M:%S")
                                if exp_ms > 0
                                else "Без срока"
                            )
                            with sqlite3.connect(DB_PATH) as conn:
                                conn.execute("""
                                    INSERT OR IGNORE INTO users (user_id, username, first_name, joined_at, is_vip, vip_until, sub_id, client_uuid)
                                    VALUES (?, '', ?, ?, 1, ?, ?, ?)
                                """, (uid_val, f"Imported_{uid_val}", now_str, until_str, c_sub, c_uuid))
                                conn.execute("""
                                    UPDATE users SET is_vip = 1, vip_until = ?, sub_id = ?, client_uuid = ? WHERE user_id = ?
                                """, (until_str, c_sub, c_uuid, uid_val))
                                exists_k = conn.execute("SELECT COUNT(*) FROM user_keys WHERE client_uuid = ?", (c_uuid,)).fetchone()[0]
                                if exists_k == 0:
                                    cur_k = conn.execute("""
                                        INSERT INTO user_keys (user_id, key_name, client_uuid, sub_id, server_id, location_name, expires_at, is_active, created_at)
                                        VALUES (?, '', ?, ?, ?, ?, ?, 1, ?)
                                    """, (uid_val, c_uuid, c_sub, srv_id, name, until_str, now_str))
                                    kid = cur_k.lastrowid
                                    conn.execute("UPDATE user_keys SET key_name = ? WHERE id = ?", (f"Ключ #{kid}", kid))
                                conn.commit()
                            imported += 1
        except Exception as e:
            logger.warning(f"Import from panel #{srv_id} warning: {e}")

    return imported

async def sync_cleanup_deleted_and_expired() -> int:
    check_and_expire_vips()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT user_id, client_uuid FROM users WHERE (is_vip = 0 OR is_banned = 1) AND client_uuid != ''")
        to_clean = cur.fetchall()

    servers = [s for s in get_all_servers_full() if s[10] == 1 and s[4]]
    cleaned_count = 0

    for uid, c_uuid in to_clean:
        for srv in servers:
            srv_id, name, host, p_type, p_url, p_user, p_pass, inb_id, *_ = srv
            base_url = p_url.rstrip("/")
            try:
                async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
                    await client.post(f"{base_url}/login", data={"username": p_user, "password": p_pass})
                    await client.post(f"{base_url}/panel/api/inbounds/{inb_id}/delClient/{c_uuid}")
            except Exception:
                pass
        cleaned_count += 1

    return cleaned_count

# ==============================================================================
# 👥 МОДУЛЬ "ПОЛЬЗОВАТЕЛИ"
# ==============================================================================
def get_users_detailed_stats() -> dict:
    check_and_expire_vips()
    with sqlite3.connect(DB_PATH) as conn:
        total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active_keys = conn.execute("SELECT COUNT(*) FROM users WHERE is_vip = 1").fetchone()[0]
        without_keys = conn.execute("SELECT COUNT(*) FROM users WHERE is_vip = 0 AND has_expired = 0").fetchone()[0]
        never_bought = conn.execute(
            "SELECT COUNT(*) FROM users WHERE user_id NOT IN (SELECT DISTINCT user_id FROM payments)"
        ).fetchone()[0]
        expired_keys = conn.execute("SELECT COUNT(*) FROM users WHERE is_vip = 0 AND has_expired = 1").fetchone()[0]
        trial_cnt = conn.execute("SELECT COUNT(*) FROM users WHERE trial_used = 1").fetchone()[0]
        banned_cnt = conn.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1").fetchone()[0]
        blocked_bot_cnt = conn.execute("SELECT COUNT(*) FROM users WHERE bot_blocked = 1").fetchone()[0]

    return {
        "total": total,
        "active_keys": active_keys,
        "without_keys": without_keys,
        "never_bought": never_bought,
        "expired_keys": expired_keys,
        "trial_cnt": trial_cnt,
        "banned_cnt": banned_cnt,
        "blocked_bot_cnt": blocked_bot_cnt,
    }

def render_users_admin_screen() -> tuple[str, InlineKeyboardMarkup]:
    s = get_users_detailed_stats()
    text = (
        "👥 <b>Пользователи</b>\n\n"
        "📊 <b>Статистика:</b>\n"
        f"👤 Всего: <b>{s['total']}</b>\n"
        f"С активными ключами: <b>{s['active_keys']}</b>\n"
        f"Без ключей: <b>{s['without_keys']}</b>\n"
        f"Никогда не покупали: <b>{s['never_bought']}</b>\n"
        f"Ключ истёк: <b>{s['expired_keys']}</b>\n"
        f"Пробный период: <b>{s['trial_cnt']}</b>\n"
        f"Забаненные: <b>{s['banned_cnt']}</b>\n"
        f"Заблокировали бота: <b>{s['blocked_bot_cnt']}</b>"
    )
    buttons = [
        [InlineKeyboardButton(f"📋 Все пользователи ({s['total']})", callback_data="admin_ulist_0")],
        [InlineKeyboardButton("🔍 Выбрать пользователя", callback_data="admin_usearch")],
        [InlineKeyboardButton("📤 Выгрузить в панель (БД → Панель)", callback_data="admin_usync_push")],
        [InlineKeyboardButton("📥 Загрузить из панели (Панель → БД)", callback_data="admin_usync_pull")],
        [InlineKeyboardButton("🗑 Синхронизация удалённых", callback_data="admin_usync_clean")],
        [
            InlineKeyboardButton("🕵️‍♂️ Лог вводов", callback_data="admin_view_logs"),
            InlineKeyboardButton("📥 Выгрузить вводы (.csv)", callback_data="admin_export_csv")
        ],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="admin_back_main"),
            InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
        ]
    ]
    return text, InlineKeyboardMarkup(buttons)

def render_users_page(page: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    offset = page * USERS_PER_PAGE
    with sqlite3.connect(DB_PATH) as conn:
        total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        cur = conn.execute(
            "SELECT user_id, username, first_name, is_vip, is_banned, vip_until FROM users ORDER BY joined_at DESC LIMIT ? OFFSET ?",
            (USERS_PER_PAGE, offset)
        )
        rows = cur.fetchall()

    total_pages = max(1, (total + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
    lines = [f"📋 <b>Все пользователи (Стр. {page + 1} из {total_pages})</b>\nНажмите на пользователя для управления:\n"]
    kb_rows = []

    for uid, uname, fname, is_vip, is_ban, until in rows:
        badge = "🚫" if is_ban else ("🟢" if is_vip else "⚪️")
        uname_str = f"@{uname}" if uname else f"ID:{uid}"
        kb_rows.append([
            InlineKeyboardButton(f"{badge} {fname} ({uname_str})", callback_data=f"admin_uview_{uid}")
        ])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Пред.", callback_data=f"admin_ulist_{page - 1}"))
    if offset + USERS_PER_PAGE < total:
        nav_row.append(InlineKeyboardButton("След. ➡️", callback_data=f"admin_ulist_{page + 1}"))
    if nav_row:
        kb_rows.append(nav_row)

    kb_rows.append([InlineKeyboardButton("⬅️ Назад в Пользователи", callback_data="admin_users_menu")])
    return "\n".join(lines), InlineKeyboardMarkup(kb_rows)

def find_user_by_query(q_str: str):
    q_str = q_str.strip().lstrip("@")
    with sqlite3.connect(DB_PATH) as conn:
        if q_str.isdigit():
            row = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (int(q_str),)).fetchone()
            if row:
                return row[0]
        row = conn.execute(
            "SELECT user_id FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(first_name) LIKE LOWER(?) LIMIT 1",
            (q_str, f"%{q_str}%")
        ).fetchone()
        return row[0] if row else None

def _old_unused_dossier(target_id: int) -> tuple[str, InlineKeyboardMarkup]:
    info = get_user_info(target_id)
    if not info:
        return "Пользователь не найден в БД.", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="admin_users_menu")]])

    uid, uname, fname, joined, is_vip, is_ban, until, attempts, vpn_cfg, bot_lic, srv_id, sub_id, c_uuid, trial_u, has_exp, bot_blk, ref_by, ref_cnt, ref_days, disc_pct = info

    with sqlite3.connect(DB_PATH) as conn:
        pay_row = conn.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM payments WHERE user_id = ?", (uid,)).fetchone()
        p_cnt, p_sum = (pay_row[0], int(pay_row[1])) if pay_row else (0, 0)
        logs_cnt = conn.execute("SELECT COUNT(*) FROM user_logs WHERE user_id = ?", (uid,)).fetchone()[0]
        keys_cnt = conn.execute("SELECT COUNT(*) FROM user_keys WHERE user_id = ?", (uid,)).fetchone()[0]

    st_str = "🚫 Забанен" if is_ban else ("🟢 Активен (VIP/VPN)" if is_vip else ("⏳ Ключ истёк" if has_exp else "⚪️ Без ключа"))
    blk_str = "Да 🔴" if bot_blk else "Нет 🟢"
    trial_str = "Использован" if trial_u else "Доступен"

    text = (
        f"👤 <b>Карточка пользователя: {html.escape(fname or 'User')}</b>\n\n"
        f"🆔 <b>Telegram ID:</b> <code>{uid}</code>\n"
        f"🏷 <b>Username:</b> @{html.escape(uname or 'нет')}\n"
        f"📡 <b>Статус:</b> {st_str}\n"
        f"🔑 <b>Ключей у клиента:</b> {keys_cnt} шт.\n"
        f"⏳ <b>Подписка до:</b> <code>{until or '—'}</code>\n"
        f"🎁 <b>Пробный период:</b> {trial_str}\n"
        f"🔗 <b>Пригласил рефералов:</b> {ref_cnt} чел. (+{ref_days} дн.)\n"
        f"🎫 <b>Активная скидка по купону:</b> {disc_pct}%\n"
        f"💳 <b>Покупок:</b> {p_cnt} шт. (на {p_sum} ₽)\n"
        f"🤖 <b>Заблокировал бота:</b> {blk_str}\n"
        f"👁 <b>Записей ввода в логе:</b> {logs_cnt}\n"
        f"📅 <b>Регистрация:</b> {joined}"
    )

    ban_btn_txt = "✅ Разбанить" if is_ban else "🚫 Забанить"
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Выдать новый ключ (Без срока)", callback_data=f"admin_uact_addunl_{uid}"),
            InlineKeyboardButton("➕ Ключ +30 дн.", callback_data=f"admin_uact_add30_{uid}")
        ],
        [
            InlineKeyboardButton("❌ Отключить все ключи", callback_data=f"admin_uact_revoke_{uid}"),
            InlineKeyboardButton("🎁 Сбросить пробный период", callback_data=f"admin_uact_rsttrial_{uid}")
        ],
        [
            InlineKeyboardButton(ban_btn_txt, callback_data=f"admin_uact_ban_{uid}"),
            InlineKeyboardButton("✉️ Написать клиенту", callback_data=f"admin_uact_msg_{uid}")
        ],
        [
            InlineKeyboardButton("🕵️‍♂️ Вводы этого клиента", callback_data=f"admin_uact_logs_{uid}")
        ],
        [
            InlineKeyboardButton("⬅️ К списку пользователей", callback_data="admin_ulist_0"),
            InlineKeyboardButton("👥 В меню Пользователи", callback_data="admin_users_menu")
        ]
    ])
    return text, kb

# ==============================================================================
# 💳 ДВИЖОК ОПЛАТ И ТАРИФОВ
# ==============================================================================
def get_active_tariffs():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT id, group_name, name, days, price_rub, price_stars FROM tariffs WHERE is_active = 1 ORDER BY price_rub ASC")
        return cur.fetchall()

def get_tariff_by_id(t_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT id, group_name, name, days, price_rub, price_stars FROM tariffs WHERE id = ?", (t_id,))
        return cur.fetchone()

def add_new_tariff(group_name: str, name: str, days: int, price_rub: int) -> int:
    stars_rate = float(get_setting("currency_stars_rate", "2.0") or 2.0)
    price_stars = max(1, int(price_rub / stars_rate))
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO tariffs (group_name, name, days, price_rub, price_stars, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (group_name.strip(), name.strip(), days, price_rub, price_stars)
        )
        conn.commit()
        return cur.lastrowid

def delete_tariff(t_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM tariffs WHERE id = ?", (t_id,))
        conn.commit()

def update_tariff_field(t_id: int, field: str, value):
    with sqlite3.connect(DB_PATH) as conn:
        if field == "price_rub":
            stars_rate = float(get_setting("currency_stars_rate", "2.0") or 2.0)
            price_stars = max(1, int(int(value) / stars_rate))
            conn.execute("UPDATE tariffs SET price_rub = ?, price_stars = ? WHERE id = ?", (int(value), price_stars, t_id))
        elif field == "days":
            conn.execute("UPDATE tariffs SET days = ? WHERE id = ?", (int(value), t_id))
        elif field == "name":
            conn.execute("UPDATE tariffs SET name = ? WHERE id = ?", (str(value).strip(), t_id))
        elif field == "group_name":
            conn.execute("UPDATE tariffs SET group_name = ? WHERE id = ?", (str(value).strip(), t_id))
        conn.commit()

def get_tariff_by_id(t_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("SELECT id, group_name, name, days, price_rub, price_stars FROM tariffs WHERE id = ?", (t_id,)).fetchone()


def render_payment_settings_screen() -> tuple[str, InlineKeyboardMarkup]:
    def icon_for(p_key: str) -> str:
        return "🟢" if get_setting(f"pay_{p_key}_enabled", "0") == "1" else "⚪️"

    yoo_shop = get_setting("pay_yookassa_shop_id", "1368461")
    notify_pay_icon = "🟢" if get_setting("pay_notify_enabled", "1") == "1" else "⚪️"

    text = (
        "💳 <b>Настройки оплаты</b>\n\n"
        "Здесь можно включить/выключить способы оплаты и настроить их.\n\n"
        f"{icon_for('stars')} <b>Telegram Stars</b>\n"
        f"{icon_for('cryptopay')} <b>Crypto Pay</b> (@CryptoBot)\n"
        f"{icon_for('yaseller')} <b>Крипто</b> (@Ya_SellerBot)\n"
        f"{icon_for('tgpayments')} <b>TG payments</b>\n"
        f"{icon_for('yookassa')} <b>ЮKassa</b> | Shop ID: <code>{html.escape(yoo_shop)}</code>\n"
        f"{icon_for('wata')} <b>WATA</b>\n"
        f"{icon_for('platega')} <b>Platega</b>\n"
        f"{icon_for('cardlink')} <b>Cardlink</b>\n"
        f"{icon_for('demo')} <b>Демо оплата (РФ)</b>"
    )

    buttons = [
        [
            InlineKeyboardButton(f"{icon_for('stars')} Telegram Stars", callback_data="admin_pay_cfg_stars"),
            InlineKeyboardButton(f"{icon_for('cryptopay')} Crypto Pay", callback_data="admin_pay_cfg_cryptopay")
        ],
        [
            InlineKeyboardButton(f"{icon_for('tgpayments')} TG payments", callback_data="admin_pay_cfg_tgpayments"),
            InlineKeyboardButton(f"{icon_for('yookassa')} ЮKassa", callback_data="admin_pay_cfg_yookassa")
        ],
        [
            InlineKeyboardButton(f"{icon_for('wata')} WATA", callback_data="admin_pay_cfg_wata"),
            InlineKeyboardButton(f"{icon_for('platega')} Platega", callback_data="admin_pay_cfg_platega")
        ],
        [
            InlineKeyboardButton(f"{icon_for('cardlink')} Cardlink", callback_data="admin_pay_cfg_cardlink"),
            InlineKeyboardButton(f"{icon_for('demo')} Демо оплата (РФ)", callback_data="admin_pay_cfg_demo")
        ],
        [
            InlineKeyboardButton(f"{notify_pay_icon} Сообщать об оплатах", callback_data="admin_pay_toggle_notify")
        ],
        [
            InlineKeyboardButton("💼 Привязать кошельки и ключи", callback_data="admin_bind_wallets_menu")],
            [InlineKeyboardButton("📁 Группы тарифов", callback_data="admin_tariff_groups")
        ],
        [
            InlineKeyboardButton("📋 Тарифы", callback_data="admin_tariffs_list")
        ],
        [
            InlineKeyboardButton("💱 Валюта и курсы", callback_data="admin_currency_menu")
        ],
        [
            InlineKeyboardButton("🎁 Пробная подписка", callback_data="admin_trial_menu")
        ],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="admin_back_main"),
            InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
        ]
    ]
    return text, InlineKeyboardMarkup(buttons)

# --- Функции работы с серверами и статистикой Дашборда ---
def get_all_servers_full():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("""
            SELECT id, name, host, panel_type, panel_url, panel_user, panel_pass,
                   inbound_id, sub_url_prefix, proxy_template, is_active
            FROM servers
            ORDER BY id ASC
        """)
        return cur.fetchall()

def get_server_full_by_id(server_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("""
            SELECT id, name, host, panel_type, panel_url, panel_user, panel_pass,
                   inbound_id, sub_url_prefix, proxy_template, is_active
            FROM servers WHERE id = ?
        """, (server_id,))
        return cur.fetchone()

def add_full_server(name: str, host: str, panel_type: str = "both", panel_url: str = "", panel_user: str = "", panel_pass: str = "", inbound_id: int = 1, sub_prefix: str = "", proxy_tpl: str = "") -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("""
            INSERT INTO servers (name, host, panel_type, panel_url, panel_user, panel_pass, inbound_id, sub_url_prefix, proxy_template, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (name.strip(), host.strip(), panel_type, panel_url.strip(), panel_user.strip(), panel_pass.strip(), inbound_id, sub_prefix.strip(), proxy_tpl.strip(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return cur.lastrowid

def toggle_server_active(server_id: int) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT is_active FROM servers WHERE id = ?", (server_id,))
        row = cur.fetchone()
        if not row:
            return 0
        new_val = 0 if row[0] == 1 else 1
        conn.execute("UPDATE servers SET is_active = ? WHERE id = ?", (new_val, server_id))
        conn.commit()
        return new_val

def delete_vpn_server(server_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM servers WHERE id = ?", (server_id,))
        conn.execute("DELETE FROM vpn_pool WHERE server_id = ? AND is_assigned = 0", (server_id,))
        conn.commit()

def record_payment(user_id: int, amount: float, provider: str, description: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO payments (user_id, amount, provider, description, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, provider, description, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()

def get_dashboard_metrics():
    now = datetime.now()
    day_ago_str = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    day_ahead_str = (now + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(DB_PATH) as conn:
        pay_row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM payments WHERE created_at >= ?",
            (day_ago_str,)
        ).fetchone()
        pay_count_24h = pay_row[0] if pay_row else 0
        pay_sum_24h = int(pay_row[1]) if pay_row else 0

        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active_users = conn.execute("SELECT COUNT(*) FROM users WHERE is_vip = 1").fetchone()[0]
        new_users_24h = conn.execute("SELECT COUNT(*) FROM users WHERE joined_at >= ?", (day_ago_str,)).fetchone()[0]

        active_keys = conn.execute("SELECT COUNT(*) FROM user_keys WHERE is_active = 1").fetchone()[0] or active_users
        expiring_24h = conn.execute(
            "SELECT COUNT(*) FROM user_keys WHERE is_active = 1 AND expires_at != '' AND expires_at != 'Без срока' AND expires_at > ? AND expires_at <= ?",
            (now_str, day_ahead_str)
        ).fetchone()[0]

    return {
        "pay_count_24h": pay_count_24h,
        "pay_sum_24h": pay_sum_24h,
        "total_users": total_users,
        "active_users": active_users,
        "new_users_24h": new_users_24h,
        "active_keys": active_keys,
        "expiring_24h": expiring_24h,
    }

# --- Логирование действий пользователей ---
def log_user_action_to_db(user, event_type: str, content: str):
    if not user:
        return
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO user_logs (user_id, username, first_name, event_type, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user.id, user.username or "нет", user.first_name or "User", event_type, content, now_str))
        conn.commit()

async def notify_admin_event(user, notif_key: str, event_title: str, content: str, context: ContextTypes.DEFAULT_TYPE, reply_markup=None):
    log_user_action_to_db(user, event_title, content)
    if not user or user.id == ADMIN_ID or not ADMIN_ID:
        return
    if not is_notif_enabled(notif_key):
        return

    safe_name = html.escape(user.first_name or "User")
    safe_uname = html.escape(user.username or "нет")
    safe_title = html.escape(event_title)
    safe_content = html.escape(content)

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"👁 <b>{safe_title}</b>\n"
                f"👤 <b>Клиент:</b> {safe_name} (@{safe_uname})\n"
                f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
                f"💬 <b>Данные:</b>\n<pre>{safe_content}</pre>\n"
                f"💡 <i>Сделайте Reply на это сообщение, чтобы ответить клиенту.</i>"
            ),
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.warning(f"Ошибка отправки уведомления админу: {e}")

def get_recent_logs(limit: int = 20):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "SELECT user_id, username, first_name, event_type, content, created_at FROM user_logs ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        return cur.fetchall()

def export_logs_to_csv(filepath: str):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT id, created_at, user_id, username, first_name, event_type, content FROM user_logs ORDER BY id DESC")
        rows = cur.fetchall()
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["ID записи", "Дата и время", "Telegram ID", "Username", "Имя", "Тип действия", "Введенные данные"])
        writer.writerows(rows)

def register_user(user) -> bool:
    if not user:
        return False
    with sqlite3.connect(DB_PATH) as conn:
        exists = conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user.id,)).fetchone()
        if not exists:
            conn.execute("""
                INSERT INTO users (user_id, username, first_name, joined_at, is_vip, is_banned, vip_until, failed_attempts, vpn_config, bot_license, server_id, sub_id, client_uuid, trial_used, has_expired, bot_blocked, referred_by, referrals_count, ref_bonus_days, active_discount_pct)
                VALUES (?, ?, ?, ?, 0, 0, '', 0, '', '', 0, ?, ?, 0, 0, 0, 0, 0, 0, 0)
            """, (
                user.id,
                user.username or "",
                user.first_name or "",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                secrets.token_hex(6),
                str(uuid.uuid4())
            ))
            conn.commit()
            return True
        else:
            conn.execute(
                "UPDATE users SET username = ?, first_name = ?, bot_blocked = 0 WHERE user_id = ?",
                (user.username or "", user.first_name or "", user.id)
            )
            conn.commit()
            return False

def get_user_info(user_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("""
            SELECT user_id, username, first_name, joined_at, is_vip, is_banned, vip_until,
                   failed_attempts, vpn_config, bot_license, server_id, sub_id, client_uuid,
                   trial_used, has_expired, bot_blocked, referred_by, referrals_count,
                   ref_bonus_days, active_discount_pct
            FROM users WHERE user_id = ?
        """, (user_id,))
        return cur.fetchone()

def get_all_active_users():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT user_id FROM users WHERE is_banned = 0")
        return [row[0] for row in cur.fetchall()]

def add_vpn_configs_to_pool(raw_text: str, server_id: int = 0) -> int:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return 0
    with sqlite3.connect(DB_PATH) as conn:
        for cfg in lines:
            conn.execute("INSERT INTO vpn_pool (server_id, config_data, is_assigned) VALUES (?, ?, 0)", (server_id, cfg))
        conn.commit()
    return len(lines)

def toggle_column(user_id: int, col: str) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(f"SELECT {col} FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            conn.execute(
                "INSERT INTO users (user_id, username, first_name, joined_at, is_vip, is_banned) VALUES (?, '', 'User', ?, 0, 0)",
                (user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            new_val = 1
        else:
            new_val = 0 if row[0] == 1 else 1
        if col == "is_banned" and new_val == 0:
            conn.execute("UPDATE users SET is_banned = 0, failed_attempts = 0 WHERE user_id = ?", (user_id,))
        else:
            conn.execute(f"UPDATE users SET {col} = ? WHERE user_id = ?", (new_val, user_id))
        conn.commit()
        return new_val

def create_tariff_key(key_type: str, days: int, price: float = 0) -> str:
    token_part = secrets.token_hex(4).upper()
    prefix = "VPN" if key_type == "VPN" else "BOT"
    key_code = f"{prefix}-{days}D-{token_part}"
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO license_keys (key_code, key_type, days, price, is_used) VALUES (?, ?, ?, ?, 0)",
            (key_code, prefix, days, price)
        )
        conn.commit()
    return key_code

async def redeem_tariff_key_async(user_id: int, key_code: str):
    key_code = key_code.strip().upper()
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute("SELECT key_type, days, is_used, price FROM license_keys WHERE key_code = ?", (key_code,))
        row = cur.fetchone()

        if not row or row[2] == 1:
            conn.execute("UPDATE users SET failed_attempts = failed_attempts + 1 WHERE user_id = ?", (user_id,))
            att_cur = conn.execute("SELECT failed_attempts FROM users WHERE user_id = ?", (user_id,))
            attempts = att_cur.fetchone()[0]
            if attempts >= MAX_KEY_ATTEMPTS:
                conn.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
                conn.execute("COMMIT")
                return False, "BANNED"
            conn.execute("COMMIT")
            left = MAX_KEY_ATTEMPTS - attempts
            return False, f"❌ Код недействителен или уже был использован!\nОсталось попыток до блокировки: {left}"

        k_type, days, _, price = row
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")

        conn.execute(
            "UPDATE license_keys SET is_used = 1, used_by = ?, used_at = ? WHERE key_code = ?",
            (user_id, now_str, key_code)
        )
        conn.execute("COMMIT")
        conn.close()

        if price and price > 0:
            record_payment(user_id, price, "Key", f"Активация ключа {key_code}")

        if k_type == "BOT":
            lic_token = f"LIC-BOT-{user_id}-{secrets.token_hex(3).upper()} (до {(now + timedelta(days=days)).strftime('%Y-%m-%d')})"
            with sqlite3.connect(DB_PATH) as c2:
                c2.execute("UPDATE users SET is_vip = 1, bot_license = ?, failed_attempts = 0 WHERE user_id = ?", (lic_token, user_id))
                c2.commit()
            return True, (
                f"🤖 <b>Лицензия на Бота успешно активирована на {days} дн.!</b>\n\n"
                f"🔐 Ваш токен лицензии:\n<code>{lic_token}</code>\n\n"
                f"Администратор получил уведомление и свяжется с вами для установки бота."
            )
        else:
            k_id, new_until, sub_url, _ = await create_or_extend_user_key(user_id, days=days, create_new=True)
            return True, (
                f"🔑 <b>Ключ #{k_id} (3x-ui + Web Panel Proxy 2.7.0) успешно активирован!</b>\n"
                f"📅 Действует до: <code>{new_until}</code>\n\n"
                f"🔗 <b>Единая ссылка подписки:</b>\n"
                f"<code>{html.escape(sub_url)}</code>\n\n"
                f"Управлять ключом можно в разделе <b>«🔑 Мои ключи»</b>."
            )
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
            conn.close()
        except Exception:
            pass
        logger.error(f"Ошибка активации ключа: {e}")
        return False, "⚠️ Системная ошибка при проверке ключа."

def check_and_expire_vips():
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE user_keys SET is_active = 0 WHERE is_active = 1 AND expires_at != '' AND expires_at != 'Без срока' AND expires_at <= ?",
            (now_str,)
        )
        cur = conn.execute(
            "SELECT user_id FROM users WHERE is_vip = 1 AND vip_until != '' AND vip_until != 'Без срока' AND vip_until <= ?",
            (now_str,)
        )
        expired_users = [r[0] for r in cur.fetchall()]
        if expired_users:
            conn.execute(
                "UPDATE users SET is_vip = 0, has_expired = 1, vip_until = '', vpn_config = '' WHERE is_vip = 1 AND vip_until != '' AND vip_until != 'Без срока' AND vip_until <= ?",
                (now_str,)
            )
        conn.commit()
    return expired_users

# ==============================================================================
# 🎨 ИНТЕРФЕЙСЫ И ДАШБОРДЫ
# ==============================================================================
def main_keyboard(user_id: int):
    buttons = [
        ["🔑 Мои ключи", "🌐 Купить VPN / Подписка"],
        ["🎁 Пробная подписка", "🎟 Промокод / Купон"],
        ["🔗 Реферальная программа", "🤖 Купить такого бота"],
        ["👤 Профиль", "📢 Наш канал", "🆘 Поддержка"],
        ["ℹ️ О боте"]
    ]
    if user_id == ADMIN_ID:
        buttons.append(["⚙️ Админ-панель"])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def build_admin_dashboard_text(mon_status: str = "✅ Активен (3x-ui + Proxy 2.7.0)") -> str:
    m = get_dashboard_metrics()
    return (
        f"⚙️ <b>Админ-панель</b>\n\n"
        f"📊 Мониторинг: {mon_status}\n\n"
        f"💰 <b>За 24 часа</b>\n"
        f"Оплат: {m['pay_count_24h']}\n"
        f"Сумма: {m['pay_sum_24h']}\n\n"
        f"👥 <b>Клиенты</b>\n"
        f"Всего: {m['total_users']}\n"
        f"Активных: {m['active_users']}\n"
        f"Новых за 24 часа: {m['new_users_24h']}\n\n"
        f"🔑 <b>Ключи</b>\n"
        f"Активных: {m['active_keys']}\n"
        f"Истекают за 24 часа: {m['expiring_24h']}"
    )

def admin_dashboard_keyboard():
    buttons = [
        [
            InlineKeyboardButton("🖥 Сервера", callback_data="admin_servers_menu"),
            InlineKeyboardButton("💳 Оплаты", callback_data="admin_payments_menu")
        ],
        [
            InlineKeyboardButton("👥 Пользователи", callback_data="admin_users_menu"),
            InlineKeyboardButton("📣 Маркетинг", callback_data="admin_marketing_menu")
        ],
        [
            InlineKeyboardButton("⚙️ Настройки бота", callback_data="admin_settings_menu"),
            InlineKeyboardButton("🧩 Расширения", callback_data="admin_ext_menu")
        ],
        [
            InlineKeyboardButton(
                "👥 Персонал (2 Адм / 3 Мод) " + ("💎" if staff_roles.is_pro_edition(get_setting) else "🔒 [FREE]"),
                callback_data="admin_staff_menu"
            )
        ],
        [
            InlineKeyboardButton("🔔 Настройки уведомлений (Что присылать)", callback_data="admin_notif_menu")
        ],
        [
            InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
        ]
    ]
    return InlineKeyboardMarkup(buttons)

async def render_servers_monitor_screen():
    servers = get_all_servers_full()
    now_time = datetime.now().strftime("%H:%M")
    lines = [
        f"🟢 <b>Сервера</b>",
        f"🕒 Обновлено: {now_time}\n"
    ]
    kb_rows = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin_servers_menu")],
        [InlineKeyboardButton("➕ Добавить сервер", callback_data="admin_srv_add")]
    ]

    if not servers:
        lines.append(
            "<i>Сервера еще не добавлены.\n"
            "Нажмите «➕ Добавить сервер», чтобы подключить панель 3x-ui и Web Panel Proxy 2.7.0.</i>"
        )
    else:
        for srv in servers:
            srv_id, name, host, p_type, p_url, p_user, p_pass, inb_id, sub_pref, prx_tpl, is_active = srv
            st = await poll_node_live_status(srv)
            if st.get("deactivated"):
                dot = "🔴"
                lines.append(
                    f"{dot} <b>{html.escape(name)}</b> (<code>{html.escape(host)}</code>)\n"
                    f"⏸ Деактивирован\n"
                )
            elif st["online"]:
                dot = "🟢"
                p_badge = "3x-ui + Proxy 2.7" if p_type == "both" else p_type
                lines.append(
                    f"{dot} <b>{html.escape(name)}</b> (<code>{html.escape(host)}</code>)\n"
                    f"Панель: онлайн | 🔑 {st['clients_online']} онлайн | 📊 {st['traffic_str']} | 💻 {st['cpu_str']}\n"
                    f"🌐 Ноды: {html.escape(p_badge)}\n"
                )
            else:
                dot = "🔴"
                lines.append(
                    f"{dot} <b>{html.escape(name)}</b> (<code>{html.escape(host)}</code>)\n"
                    f"⚠️ {html.escape(st['error'])}\n"
                )
            kb_rows.append([
                InlineKeyboardButton(f"{dot} {name}", callback_data=f"admin_srv_view_{srv_id}")
            ])

    kb_rows.append([
        InlineKeyboardButton("⬅️ Назад", callback_data="admin_back_main"),
        InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
    ])
    return "\n".join(lines), InlineKeyboardMarkup(kb_rows)

def notif_settings_keyboard():
    buttons = [
        [
            InlineKeyboardButton("✅ Включить всё", callback_data="notif_preset_all"),
            InlineKeyboardButton("🎯 Только важное", callback_data="notif_preset_important"),
            InlineKeyboardButton("🔕 Тихий режим", callback_data="notif_preset_none")
        ]
    ]
    for key, (label, _) in NOTIF_TYPES.items():
        enabled = is_notif_enabled(key)
        status_icon = "🟢 ВКЛ" if enabled else "🔴 ВЫКЛ"
        buttons.append([InlineKeyboardButton(f"{label}: {status_icon}", callback_data=f"toggle_notif_{key}")])
    buttons.append([InlineKeyboardButton("⬅️ Назад в Админ-панель", callback_data="admin_back_main")])
    return InlineKeyboardMarkup(buttons)

# --- Фоновые задачи ---
async def post_init(application):
    global BOT_USERNAME_CACHE
    try:
        me = await application.bot.get_me()
        BOT_USERNAME_CACHE = me.username or "Bot_VIP"
    except Exception:
        BOT_USERNAME_CACHE = "Bot_VIP"

    scan_and_load_extensions(application)
    threading.Thread(target=start_sub_aggregator_server, daemon=True).start()

    if ADMIN_ID:
        try:
            await application.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"🟢 <b>Bot_VIP запущен! (Commit: <code>{get_current_git_commit()}</code>)</b>\n"
                    f"🌐 Встроенный Sub-Aggregator слушает порт <code>{SUB_PORT}</code>.\n"
                    f"🔄 Обновление прямо из бота, QR-коды и все модули админ-панели активны.\n"
                    f"Нажмите /admin для управления."
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить стартовое сообщение админу: {e}")

async def daily_backup_job(context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_ID and os.path.exists(DB_PATH) and is_notif_enabled("notify_backup"):
        try:
            snap_file = create_manual_snapshot_backup()
            with open(snap_file, "rb") as f:
                await context.bot.send_document(
                    chat_id=ADMIN_ID,
                    document=f,
                    filename=f"auto_backup_{datetime.now().strftime('%Y%m%d')}.db",
                    caption="⏰ <b>Ежедневный автоматический бэкап базы данных</b>",
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error(f"Ошибка авто-бэкапа: {e}")

async def expire_vips_job(context: ContextTypes.DEFAULT_TYPE):
    expired = check_and_expire_vips()
    for uid in expired:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text="⏳ <b>Срок действия вашей подписки VPN истёк.</b>\nДля продления перейдите в раздел «🔑 Мои ключи».",
                parse_mode="HTML"
            )
        except Forbidden:
            mark_user_blocked_bot(uid, 1)
        except Exception:
            pass

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Ошибка при обработке обновления:", exc_info=context.error)
    if ADMIN_ID and is_notif_enabled("notify_security"):
        tb_str = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
        short_tb = html.escape(tb_str[-1500:])
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"⚠️ <b>Сбой в работе бота:</b>\n<pre>{short_tb}</pre>",
                parse_mode="HTML"
            )
        except Exception:
            pass

# --- Обработчики успешной оплаты Telegram Stars / TG Payments ---
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)


async def poll_pending_invoices_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        invoices = autopay.get_pending_invoices(DB_PATH)
        if not invoices:
            return
        yoo_shop = get_setting("pay_yookassa_shop_id", "")
        yoo_sec = get_setting("pay_yookassa_secret", "")
        cp_token = get_setting("pay_cryptopay_secret", "")

        for row in invoices:
            inv_db_id, inv_id, provider, user_id, t_id, days, price, tariff_name, is_lic = row
            is_paid = False

            if provider == "yookassa" and yoo_shop and yoo_sec:
                status = await autopay.check_yookassa_payment(yoo_shop, yoo_sec, inv_id)
                if status == "succeeded":
                    is_paid = True
                elif status in ("canceled", "expired"):
                    autopay.remove_invoice(DB_PATH, inv_id)
                    continue

            elif provider == "cryptopay" and cp_token:
                status = await autopay.check_cryptopay_payment(cp_token, inv_id)
                if status == "paid":
                    is_paid = True
                elif status in ("expired",):
                    autopay.remove_invoice(DB_PATH, inv_id)
                    continue

            if is_paid:
                if not autopay.consume_invoice_atomic(DB_PATH, inv_id):
                    continue
                record_payment(user_id, price, "RUB", f"Оплата тарифа: {tariff_name}")
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("UPDATE users SET active_discount_pct = 0 WHERE user_id = ?", (user_id,))
                    conn.commit()

                if is_lic:
                    now = datetime.now()
                    lic_token = f"LIC-BOT-{user_id}-{secrets.token_hex(3).upper()} (до {(now + timedelta(days=days)).strftime('%Y-%m-%d')})"
                    with sqlite3.connect(DB_PATH) as conn:
                        conn.execute("UPDATE users SET is_vip = 1, bot_license = ? WHERE user_id = ?", (lic_token, user_id))
                        conn.commit()
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=f"🎉 <b>Оплата прошла успешно!</b> Лицензия Бота активирована на {days} дн.\n\n🔐 Токен лицензии: <code>{lic_token}</code>",
                            parse_mode="HTML",
                            protect_content=True
                        )
                    except Exception as ex_u:
                        logger.warning(f"Send bot lic err: {ex_u}")
                else:
                    try:
                        k_id, until, sub_url, _ = await create_or_extend_user_key(user_id, days=days, create_new=True)
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=(
                                f"🎉 <b>Оплата получена!</b> Создан Ключ #{k_id} (до {until})\n\n"
                                f"🔗 <b>Единая ссылка подписки:</b>\n<code>{html.escape(sub_url)}</code>\n\n"
                                f"Все ваши ключи доступны в разделе «🔑 Мои ключи»."
                            ),
                            parse_mode="HTML",
                            protect_content=True
                        )
                    except Exception as ex_k:
                        logger.error(f"Key issue error: {ex_k}")

                if get_setting("pay_notify_enabled", "1") == "1":
                    try:
                        await context.bot.send_message(
                            chat_id=ADMIN_ID,
                            text=(
                                f"💰 <b>НОВАЯ АВТОМАТИЧЕСКАЯ ОПЛАТА ({provider.upper()})</b>\n\n"
                                f"👤 Клиент: ID <code>{user_id}</code>\n"
                                f"📋 Тариф: {html.escape(tariff_name)} ({days} дн.)\n"
                                f"💵 Сумма: {price} ₽"
                            ),
                            parse_mode="HTML"
                        )
                    except Exception as ex_a:
                        logger.warning(f"Admin notify err: {ex_a}")
    except Exception as e:
        logger.error(f"poll_pending_invoices_job error: {e}")

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    payment = update.message.successful_payment
    payload = payment.invoice_payload or ""
    total_amount = payment.total_amount
    currency = payment.currency

    days = 30
    tariff_name = "Единая подписка"
    is_bot_lic = False

    if payload.startswith("tariff_"):
        parts = payload.split("_")
        t_id = int(parts[1])
        t_row = get_tariff_by_id(t_id)
        if t_row:
            _, grp, tariff_name, days, pr_rub, _ = t_row
            if "Бота" in grp:
                is_bot_lic = True

    display_rub = total_amount if currency == "XTR" else (total_amount / 100.0)
    record_payment(user.id, display_rub, currency, f"Оплата тарифа: {tariff_name}")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET active_discount_pct = 0 WHERE user_id = ?", (user.id,))
        conn.commit()

    if is_bot_lic:
        now = datetime.now()
        lic_token = f"LIC-BOT-{user.id}-{secrets.token_hex(3).upper()} (до {(now + timedelta(days=days)).strftime('%Y-%m-%d')})"
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE users SET is_vip = 1, bot_license = ? WHERE user_id = ?", (lic_token, user.id))
            conn.commit()
        await update.message.reply_text(
            f"🎉 <b>Оплата прошла успешно! Лицензия Бота активирована на {days} дн.</b>\n\n"
            f"🔐 Токен лицензии: <code>{lic_token}</code>",
            parse_mode="HTML",
            protect_content=True
        )
    else:
        k_id, until, sub_url, _ = await create_or_extend_user_key(user.id, days=days, create_new=True)
        await update.message.reply_text(
            f"🎉 <b>Оплата получена! Создан Ключ #{k_id} (до {until})</b>\n\n"
            f"🔗 <b>Единая ссылка подписки:</b>\n<code>{html.escape(sub_url)}</code>\n\n"
            f"Все ваши ключи доступны по кнопке <b>«🔑 Мои ключи»</b>.",
            parse_mode="HTML",
            protect_content=True
        )

    if get_setting("pay_notify_enabled", "1") == "1":
        await notify_admin_event(
            user,
            "notify_orders",
            "💰 НОВАЯ АВТОМАТИЧЕСКАЯ ОПЛАТА",
            f"Тариф: {tariff_name} ({days} дн.)\nСумма: {display_rub} {currency}",
            context
        )

# --- Команды ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_flooding(user.id):
        return
    is_new = register_user(user)

    if is_new and context.args and context.args[0].startswith("ref_"):
        ref_str = context.args[0].replace("ref_", "").strip()
        if ref_str.isdigit() and int(ref_str) != user.id and get_setting("ref_enabled", "1") == "1":
            inviter_id = int(ref_str)
            inviter_info = get_user_info(inviter_id)
            if inviter_info:
                bonus_inviter = int(get_setting("ref_bonus_days", "7") or 7)
                bonus_newbie = int(get_setting("ref_NewUser_days", "3") or 3)
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("UPDATE users SET referred_by = ? WHERE user_id = ?", (inviter_id, user.id))
                    conn.execute(
                        "UPDATE users SET referrals_count = referrals_count + 1, ref_bonus_days = ref_bonus_days + ? WHERE user_id = ?",
                        (bonus_inviter, inviter_id)
                    )
                    conn.commit()
                await create_or_extend_user_key(inviter_id, days=bonus_inviter, create_new=False)
                if bonus_newbie > 0:
                    await create_or_extend_user_key(user.id, days=bonus_newbie, create_new=True)
                try:
                    await context.bot.send_message(
                        chat_id=inviter_id,
                        text=(
                            f"🎉 <b>По вашей реферальной ссылке зарегистрировался друг ({html.escape(user.first_name)})!</b>\n"
                            f"🎁 Вам автоматически начислено <b>+{bonus_inviter} дн.</b> подписки!"
                        ),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
                await notify_admin_event(user, "notify_start", "🔗 НОВЫЙ РЕФЕРАЛ", f"Пригласил ID: {inviter_id} (+{bonus_inviter} дн.)", context)

    await notify_admin_event(user, "notify_start", "🚀 Вход в бота (/start)", "/start", context)

    info = get_user_info(user.id)
    if info and info[5] == 1 and user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ заблокирован.")
        return

    context.user_data.clear()
    custom_welcome = get_setting(
        "text_welcome",
        "Добро пожаловать в <b>Bot_VIP</b>!\n\n🔑 Управляйте своими ключами в разделе <b>«🔑 Мои ключи»</b> или подключите новую подписку (<b>3x-ui + Web Panel Proxy 2.7.0</b>)."
    )
    await update.message.reply_text(
        f"Привет, <b>{html.escape(user.first_name)}</b>! {custom_welcome}",
        parse_mode="HTML",
        reply_markup=main_keyboard(user.id)
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await notify_admin_event(user, "notify_start", "📖 Команда /help", "/help", context)
    text = (
        "📖 <b>Доступные команды:</b>\n"
        "/start — Главное меню\n"
        "/help — Справка\n"
        "/admin — Админ-панель\n"
        "/vip <code>ID</code> — Выдать ключ подписки на 30 дней\n"
        "/ban <code>ID</code> — Заблокировать/разблокировать ID"
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await notify_admin_event(update.effective_user, "notify_security", "🚨 Попытка чужого входа в /admin", "/admin", context)
        await update.message.reply_text("⛔ У вас нет прав администратора.")
        return
    context.user_data.clear()
    await update.message.reply_text(
        build_admin_dashboard_text(),
        parse_mode="HTML",
        reply_markup=admin_dashboard_keyboard()
    )

async def vip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Использование: <code>/vip 123456789</code>", parse_mode="HTML")
        return
    target_id = int(context.args[0])
    k_id, until, sub_url, _ = await create_or_extend_user_key(target_id, days=30, create_new=True)
    await update.message.reply_text(
        f"✅ Пользователю <code>{target_id}</code> выдан <b>Ключ #{k_id}</b> до <code>{until}</code>\n"
        f"🔗 Ссылка: <code>{html.escape(sub_url)}</code>",
        parse_mode="HTML"
    )

async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Использование: <code>/ban 123456789</code>", parse_mode="HTML")
        return
    target_id = int(context.args[0])
    state = toggle_column(target_id, "is_banned")
    status_str = "🚫 ЗАБЛОКИРОВАН" if state == 1 else "✅ РАЗБЛОКИРОВАН"
    await update.message.reply_text(f"Статус для <code>{target_id}</code>: <b>{status_str}</b>", parse_mode="HTML")

# --- Обработка всех Callback-кнопок ---
async def callbacks_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    await query.answer()

    # ==========================================================================
    # 🔑 КЛИЕНТСКОЕ МЕНЮ "МОИ КЛЮЧИ"
    # ==========================================================================
    if data == "client_home":
        context.user_data.clear()
        await query.message.reply_text(
            "🏠 <b>Главное меню Bot_VIP:</b>",
            parse_mode="HTML",
            reply_markup=main_keyboard(user.id)
        )
        return

    if data == "client_my_keys":
        text_out, kb_out = await render_my_keys_screen(user.id)
        await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    if data.startswith("client_key_view_"):
        k_id = int(data.split("_")[-1])
        text_out, kb_out = await render_single_key_control(user.id, k_id)
        await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    if data.startswith("client_key_qr_"):
        k_id = int(data.split("_")[-1])
        row = get_single_user_key(k_id, user.id)
        if not row:
            return
        sub_id = row[4]
        sub_dom = get_setting("sub_domain_prefix", "https://sub.bot-vip.online/sub")
        sub_url = f"{sub_dom.rstrip('/')}/{sub_id}"
        qr_api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=400x400&data={quote(sub_url)}"
        try:
            await query.message.reply_photo(
                photo=qr_api_url,
                caption=(
                    f"📲 <b>QR-код для подключения ({html.escape(row[2])})</b>\n\n"
                    f"Отсканируйте этот код в приложении <b>Streisand / Hiddify / v2rayNG</b> или скопируйте ссылку:\n"
                    f"<code>{html.escape(sub_url)}</code>"
                ),
                parse_mode="HTML",
                protect_content=True
            )
        except Exception as e:
            await query.message.reply_text(f"🔗 Ссылка для подключения:\n<code>{html.escape(sub_url)}</code>", parse_mode="HTML")
        return

    if data.startswith("client_key_b64_"):
        k_id = int(data.split("_")[-1])
        row = get_single_user_key(k_id, user.id)
        if not row:
            return
        cfg_txt = row[10] or ""
        b64_str = base64.b64encode(cfg_txt.encode("utf-8")).decode("utf-8")
        await query.message.reply_text(
            f"📦 <b>Base64 пакет для {html.escape(row[2])}:</b>\n\n<code>{b64_str}</code>",
            parse_mode="HTML",
            protect_content=True
        )
        return

    if data.startswith("client_key_ren_"):
        k_id = int(data.split("_")[-1])
        context.user_data["mode"] = "rename_user_key"
        context.user_data["target_key_id"] = k_id
        await query.edit_message_text(
            f"✏️ <b>Переименование ключа #{k_id}</b>\n\n"
            f"Отправьте новое название для этого ключа (например: <code>Ключ 2</code> или <code>Мой iPhone</code>):",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Отмена", callback_data=f"client_key_view_{k_id}")]])
        )
        return

    if data.startswith("client_key_loc_"):
        k_id = int(data.split("_")[-1])
        servers = [s for s in get_all_servers_full() if s[10] == 1]
        kb_rows = []
        if servers:
            for s in servers:
                kb_rows.append([InlineKeyboardButton(f"📍 {s[1]}", callback_data=f"client_key_setloc_{k_id}_{s[0]}")])
        else:
            for loc_default in ["🇩🇪 Германия", "🇳🇱 Нидерланды", "🇷🇺 Москва", "🇺🇸 США", "🇹🇷 Турция"]:
                kb_rows.append([InlineKeyboardButton(f"📍 {loc_default}", callback_data=f"client_key_setlocname_{k_id}_{loc_default}")])
        kb_rows.append([InlineKeyboardButton("⬅️ Назад к ключу", callback_data=f"client_key_view_{k_id}")])
        await query.edit_message_text(
            "🌍 <b>Выберите новую локацию для вашего ключа:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb_rows)
        )
        return

    if data.startswith("client_key_setloc_"):
        parts = data.split("_")
        k_id = int(parts[3])
        srv_id = int(parts[4])
        srv = get_server_full_by_id(srv_id)
        if srv:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("UPDATE user_keys SET server_id = ?, location_name = ? WHERE id = ? AND user_id = ?", (srv_id, srv[1], k_id, user.id))
                conn.commit()
        text_out, kb_out = await render_single_key_control(user.id, k_id)
        await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    if data.startswith("client_key_setlocname_"):
        parts = data.split("_", 4)
        k_id = int(parts[3])
        loc_name = parts[4]
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE user_keys SET location_name = ? WHERE id = ? AND user_id = ?", (loc_name, k_id, user.id))
            conn.commit()
        text_out, kb_out = await render_single_key_control(user.id, k_id)
        await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    if data == "client_activate_trial_btn":
        sub_ok, ch_link = await verify_user_subscribed_to_channel(user.id, context)
        if not sub_ok:
            kb_sub = InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Подписаться на канал", url=ch_link)],
                [InlineKeyboardButton("✅ Я подписался (Проверить)", callback_data="client_activate_trial_btn")]
            ])
            await query.message.reply_text(
                "📢 <b>Для получения бесплатной пробной подписки подпишитесь на наш официальный канал:</b>",
                parse_mode="HTML",
                reply_markup=kb_sub
            )
            return
        if get_setting("trial_enabled", "1") != "1":
            await query.message.reply_text("⚠️ Пробный период временно отключен.")
            return
        info = get_user_info(user.id)
        if info and info[13] == 1:
            await query.message.reply_text("🔒 Вы уже использовали бесплатный пробный период ранее.")
            return
        t_days = int(get_setting("trial_days", "3") or 3)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE users SET trial_used = 1 WHERE user_id = ?", (user.id,))
            conn.commit()
        k_id, until, sub_url, _ = await create_or_extend_user_key(user.id, days=t_days, create_new=True)
        text_out, kb_out = await render_my_keys_screen(user.id)
        await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    # ==========================================================================
    # 🛒 КЛИЕНТСКАЯ ВИТРИНА ТАРИФОВ И ОПЛАТЫ
    # ==========================================================================
    if data == "order_vpn":
        await notify_admin_event(user, "notify_menu", "🔘 Открытие тарифов VPN", "Выбор тарифа VPN", context)
        info = get_user_info(user.id)
        disc_pct = info[19] if (info and len(info) > 19) else 0
        disc_line = f"\n🎫 <b>Активен купон на скидку: -{disc_pct}%!</b>\n" if disc_pct > 0 else ""

        tariffs = [t for t in get_active_tariffs() if "Бота" not in t[1]]
        kb_rows = []
        for t_id, grp, name, days, pr_rub, pr_stars in tariffs:
            final_rub = max(1, int(pr_rub * (100 - disc_pct) / 100)) if disc_pct > 0 else pr_rub
            price_str = f"{final_rub} ₽ (скидка -{disc_pct}%)" if disc_pct > 0 else f"{pr_rub} ₽"
            kb_rows.append([
                InlineKeyboardButton(f"{name} — {price_str}", callback_data=f"buy_tariff_{t_id}")
            ])
        kb_rows.append([InlineKeyboardButton("✍️ Оставить заявку вручную", callback_data="manual_order_vpn")])
        kb_rows.append([InlineKeyboardButton("🔑 Мои ключи", callback_data="client_my_keys")])
        await query.message.reply_text(
            f"📋 <b>Выберите тариф единой подписки (3x-ui + Web Panel Proxy 2.7.0):</b>{disc_line}\n"
            f"После оплаты новый ключ мгновенно появится в разделе <b>«🔑 Мои ключи»</b>:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb_rows)
        )
        return

    if data == "order_bot":
        await notify_admin_event(user, "notify_menu", "🔘 Открытие тарифов Бота", "Выбор тарифа Бота", context)
        tariffs = [t for t in get_active_tariffs() if "Бота" in t[1]]
        kb_rows = []
        for t_id, grp, name, days, pr_rub, pr_stars in tariffs:
            kb_rows.append([
                InlineKeyboardButton(f"{name} — {pr_rub} ₽", callback_data=f"buy_tariff_{t_id}")
            ])
        kb_rows.append([InlineKeyboardButton("📝 Оставить анкету на разработку под ключ", callback_data="manual_order_bot")])
        await query.message.reply_text(
            "🤖 <b>Выберите тариф аренды/покупки Бота или оставьте заявку:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb_rows)
        )
        return

    if data.startswith("buy_tariff_"):
        t_id = int(data.split("_")[-1])
        t_row = get_tariff_by_id(t_id)
        if not t_row:
            await query.message.reply_text("Тариф не найден.")
            return
        _, grp, name, days, pr_rub, pr_stars = t_row

        info = get_user_info(user.id)
        disc_pct = info[19] if (info and len(info) > 19) else 0
        if disc_pct > 0:
            pr_rub = max(1, int(pr_rub * (100 - disc_pct) / 100))
            pr_stars = max(1, int(pr_stars * (100 - disc_pct) / 100))

        pay_buttons = []
        for p_key, p_info in PAYMENT_PROVIDERS.items():
            if get_setting(f"pay_{p_key}_enabled", "0") == "1":
                pay_buttons.append([
                    InlineKeyboardButton(f"💳 Оплатить через {p_info['title']}", callback_data=f"pay_exec_{p_key}_{t_id}")
                ])
        if not pay_buttons:
            pay_buttons.append([
                InlineKeyboardButton("💳 Оплатить через реквизиты / заявку", callback_data="manual_order_vpn")
            ])

        usdt_rate = float(get_setting("currency_usdt_rate", "95.0") or 95.0)
        usdt_val = round(pr_rub / usdt_rate, 2)
        days_label = "Без срока (Безлимит)" if days == 0 else f"{days} дн."

        await query.message.reply_text(
            f"💳 <b>Оплата тарифа: {html.escape(name)}</b>\n"
            f"📂 Группа: {html.escape(grp)}\n"
            f"⏳ Срок действия: <b>{days_label}</b>\n"
            f"💰 Стоимость: <b>{pr_rub} ₽</b> (~{usdt_val} USDT / {pr_stars} ⭐️)\n\n"
            f"Выберите удобный способ оплаты:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(pay_buttons)
        )
        return

    if data.startswith("pay_exec_"):
        parts = data.split("_")
        p_key = parts[2]
        t_id = int(parts[3])
        t_row = get_tariff_by_id(t_id)
        if not t_row:
            return
        _, grp, name, days, pr_rub, pr_stars = t_row

        info = get_user_info(user.id)
        disc_pct = info[19] if (info and len(info) > 19) else 0
        if disc_pct > 0:
            pr_rub = max(1, int(pr_rub * (100 - disc_pct) / 100))
            pr_stars = max(1, int(pr_stars * (100 - disc_pct) / 100))

        await notify_admin_event(user, "notify_orders", f"💳 Выбор способа оплаты ({p_key})", f"Тариф: {name} ({pr_rub} ₽)", context)

        if p_key == "demo":
            record_payment(user.id, pr_rub, "Демо оплата (РФ)", f"Демо-оплата: {name}")
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("UPDATE users SET active_discount_pct = 0 WHERE user_id = ?", (user.id,))
                conn.commit()
            k_id, until, sub_url, _ = await create_or_extend_user_key(user.id, days=days, create_new=True)
            if get_setting("pay_notify_enabled", "1") == "1":
                await notify_admin_event(user, "notify_orders", "💰 УСПЕШНАЯ ДЕМО-ОПЛАТА", f"Тариф: {name}\nСумма: {pr_rub} ₽", context)
            text_out, kb_out = await render_my_keys_screen(user.id)
            await query.message.reply_text(
                f"✅ <b>[Демо оплата (РФ)] Оплата подтверждена! Выпущен Ключ #{k_id} (до {until})</b>\n\n{text_out}",
                parse_mode="HTML",
                reply_markup=kb_out
            )
            return

        if p_key == "stars":
            try:
                await context.bot.send_invoice(
                    chat_id=user.id,
                    title=name,
                    description=f"{grp} (3x-ui + Web Panel Proxy 2.7.0)",
                    payload=f"tariff_{t_id}_{user.id}",
                    provider_token="",
                    currency="XTR",
                    prices=[LabeledPrice(label=name, amount=int(pr_stars))]
                )
            except Exception as e:
                await query.message.reply_text(f"⚠️ Ошибка выставления счета Telegram Stars: {e}")
            return

        # 1. TG Payments (send_invoice)
        if p_key in ("tgpayments", "tg_payments"):
            prov_token = get_setting("pay_tgpayments_secret", "")
            if prov_token and ":" in prov_token:
                try:
                    await context.bot.send_invoice(
                        chat_id=user.id,
                        title=name,
                        description=f"{grp}",
                        payload=f"tariff_{t_id}_{user.id}",
                        provider_token=prov_token,
                        currency="RUB",
                        prices=[LabeledPrice(label=name, amount=int(pr_rub * 100))]
                    )
                    return
                except Exception as e:
                    logger.warning(f"TG payments invoice error: {e}")
                    await query.answer("⚠️ Ошибка формирования счета TG payments.", show_alert=True)
                    return
            else:
                await query.answer("⚠️ TG payments не настроен администратором.", show_alert=True)
                return

        # 2. ЮKassa (СБП / Карты РФ через API v3)
        if p_key == "yookassa":
            yoo_shop = get_setting("pay_yookassa_shop_id", "")
            yoo_sec = get_setting("pay_yookassa_secret", "")
            if not yoo_shop or not yoo_sec or "example" in yoo_sec:
                await query.answer("⚠️ ЮKassa временно не настроена администратором.", show_alert=True)
                return
            is_lic = 1 if "Бота" in grp else 0
            ret_url = f"https://t.me/{(await context.bot.get_me()).username}"
            pay_url, inv_id = await autopay.create_yookassa_payment(
                shop_id=yoo_shop,
                secret_key=yoo_sec,
                amount_rub=pr_rub,
                desc=f"{name} (ID {user.id})",
                return_url=ret_url,
                metadata={"user_id": user.id, "tariff_id": t_id}
            )
            if pay_url and inv_id:
                autopay.register_invoice(DB_PATH, inv_id, "yookassa", user.id, t_id, days, pr_rub, name, is_lic)
                kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"💳 Оплатить {pr_rub} ₽ (СБП / Карты)", url=pay_url)]])
                await query.message.reply_text(
                    f"💳 <b>Счет на оплату: {html.escape(name)}</b>\n\n"
                    f"💰 <b>Сумма к оплате:</b> {pr_rub} ₽\n\n"
                    f"⚡️ Оплатите по кнопке ниже через СБП или банковской картой.\n"
                    f"Ключ активируется <b>автоматически</b> сразу после зачисления средств.",
                    parse_mode="HTML",
                    reply_markup=kb
                )
                return
            else:
                await query.answer("⚠️ Ошибка связи со шлюзом ЮKassa. Проверьте Shop ID и Secret Key.", show_alert=True)
                return

        # 3. Crypto Pay (@CryptoBot)
        if p_key in ("cryptopay", "cryptobot"):
            cp_token = get_setting("pay_cryptopay_secret", "")
            usdt_rate = float(get_setting("currency_usdt_rate", "95.0") or 95.0)
            usdt_amount = round(pr_rub / usdt_rate, 2)
            if not cp_token:
                await query.answer("⚠️ Crypto Pay временно не настроен администратором.", show_alert=True)
                return
            is_lic = 1 if "Бота" in grp else 0
            pay_url, inv_id = await autopay.create_cryptopay_payment(
                token=cp_token,
                amount_usdt=usdt_amount,
                desc=f"{name} (ID {user.id})",
                payload=f"tariff_{t_id}_{user.id}"
            )
            if pay_url and inv_id:
                autopay.register_invoice(DB_PATH, inv_id, "cryptopay", user.id, t_id, days, pr_rub, name, is_lic)
                kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"💎 Оплатить {usdt_amount} USDT в @CryptoBot", url=pay_url)]])
                await query.message.reply_text(
                    f"💎 <b>Счет Crypto Pay (@CryptoBot) создан!</b>\n\n"
                    f"📋 <b>Тариф:</b> {html.escape(name)}\n"
                    f"💰 <b>Сумма:</b> {usdt_amount} USDT ({pr_rub} ₽)\n\n"
                    f"⚡️ Оплатите по кнопке ниже. Подписка активируется <b>автоматически</b> сразу после оплаты чека.",
                    parse_mode="HTML",
                    reply_markup=kb
                )
                return
            else:
                await query.answer("⚠️ Ошибка создания счёта в CryptoBot. Проверьте токен.", show_alert=True)
                return

        await query.answer("⚠️ Выбранный способ оплаты временно недоступен.", show_alert=True)
        return

    if data == "manual_order_vpn":
        context.user_data["mode"] = "order_vpn_input"
        await query.message.reply_text(
            "🌐 <b>Оформление подписки вручную</b>\n"
            "Напишите желаемый срок, ваше устройство и комментарий:",
            parse_mode="HTML"
        )
        return

    if data == "manual_order_bot":
        context.user_data["mode"] = "order_bot_input"
        await query.message.reply_text(
            "🤖 <b>Заявка на покупку / аренду Бота</b>\n"
            "Напишите ваши пожелания, токен от @BotFather (если есть) и контакт для связи:",
            parse_mode="HTML"
        )
        return

    # ==========================================================================
    # 👑 ПРОВЕРКА ПРАВ АДМИНИСТРАТОРА
    # ==========================================================================
    user_role = staff_roles.get_user_role(DB_PATH, user.id, ADMIN_ID, get_setting)
    if user_role == "user":
        await notify_admin_event(user, "notify_security", "🚨 Попытка нажать админ-кнопку", data, context)
        await query.edit_message_text("⛔ Доступ запрещён.")
        return

    if await staff_roles.handle_staff_callback(query, context, DB_PATH, ADMIN_ID, get_setting, set_setting):
        return

    allowed, deny_reason = staff_roles.check_staff_permission(DB_PATH, user.id, ADMIN_ID, data, get_setting)
    if not allowed:
        await query.answer(deny_reason, show_alert=True)
        return

    if data == "admin_back_main":
        await query.edit_message_text(
            build_admin_dashboard_text(),
            parse_mode="HTML",
            reply_markup=admin_dashboard_keyboard()
        )
        return

    # ==========================================================================
    # 🧩 МЕНЮ "ДИАГНОСТИКА РАСШИРЕНИЙ"
    # ==========================================================================
    if data == "admin_ext_menu":
        text_out, kb_out = render_extensions_diagnostics_screen(context.application)
        await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    if data == "admin_ext_load_on":
        set_setting("ext_load_enabled", "1")
        text_out, kb_out = render_extensions_diagnostics_screen(context.application)
        await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    if data == "admin_ext_load_off":
        set_setting("ext_load_enabled", "0")
        text_out, kb_out = render_extensions_diagnostics_screen(context.application)
        await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    if data == "admin_ext_core_forbid":
        set_setting("ext_core_edit_allowed", "0")
        text_out, kb_out = render_extensions_diagnostics_screen(context.application)
        await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    if data == "admin_ext_core_allow":
        set_setting("ext_core_edit_allowed", "1")
        text_out, kb_out = render_extensions_diagnostics_screen(context.application)
        await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    if data == "admin_ext_details":
        st = scan_and_load_extensions(context.application)
        details_list = "\n".join(st["details"]) if st["details"] else "<i>В папке custom_extensions пока нет файлов.</i>"
        sub_dom = get_setting("sub_domain_prefix", "https://sub.bot-vip.online/sub")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Пересканировать custom_extensions", callback_data="admin_ext_details")],
            [InlineKeyboardButton("🌐 Задать домен единой подписки (Sub URL)", callback_data="admin_set_subdom")],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="admin_ext_menu"),
                InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
            ]
        ])
        await query.edit_message_text(
            f"📋 <b>Подробности диагностики расширений</b>\n\n"
            f"📂 <b>Путь:</b> <code>{html.escape(EXTENSIONS_DIR)}</code>\n"
            f"🔗 <b>Шлюз Web Panel Proxy 2.7.0 / Sub URL:</b>\n<code>{html.escape(sub_dom)}</code>\n\n"
            f"<b>Список файлов и модулей:</b>\n{details_list}",
            parse_mode="HTML",
            reply_markup=kb
        )
        return

    # ==========================================================================
    # ⚙️ МЕНЮ "НАСТРОЙКИ БОТА" + ПРЯМОЕ ОБНОВЛЕНИЕ ИЗ БОТА
    # ==========================================================================
    if data == "admin_settings_menu":
        text_out, kb_out = render_bot_settings_main_screen()
        await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    if data == "admin_bset_updates":
        commit = get_current_git_commit()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Мягкое обновление с GitHub (git pull)", callback_data="admin_update")],
            [InlineKeyboardButton("⚠️ Жёсткая перезапись с GitHub (git reset)", callback_data="admin_hard_reset")],
            [InlineKeyboardButton("⚡ Перезапустить бота сейчас", callback_data="admin_restart")],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="admin_settings_menu"),
                InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
            ]
        ])
        await query.edit_message_text(
            f"🔄 <b>Управление обновлениями прямо из бота</b>\n\n"
            f"📌 Текущая версия (commit): <code>{html.escape(commit)}</code>\n"
            f"📦 Репозиторий: <code>Bandito2025/Bot_VIP</code>\n\n"
            f"При нажатии бот автоматически создаст бэкап БД, скачает свежий код с GitHub и перезапустится:",
            parse_mode="HTML",
            reply_markup=kb
        )
        return

    if data == "admin_update":
        await query.edit_message_text("🔄 <b>Загрузка обновления с GitHub (git pull)...</b>", parse_mode="HTML")
        ok, git_out = perform_inbot_git_update(hard_reset=False)
        if not ok and os.path.exists("/opt/Bot_VIP/install.sh"):
            subprocess.Popen(["bash", "/opt/Bot_VIP/install.sh", "update"])
            await query.message.reply_text("🔄 Запущен серверный скрипт обновления `/opt/Bot_VIP/install.sh update`.", parse_mode="HTML")
            return
        await query.message.reply_text(
            f"{'✅ <b>Обновление успешно получено!</b>' if ok else '⚠️ <b>Ответ Git:</b>'}\n"
            f"<pre>{html.escape(git_out[-1200:] or 'Already up to date.')}</pre>\n"
            f"⚡ <i>Перезапускаю процесс бота...</i>",
            parse_mode="HTML"
        )
        if sys.platform.startswith("linux") and os.path.exists("/etc/systemd/system/bot_vip.service"):
            subprocess.Popen(["systemctl", "restart", "bot_vip"])
        else:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        return

    if data == "admin_hard_reset":
        await query.edit_message_text("⚠️ <b>Выполняется жёсткая синхронизация с GitHub (git reset --hard origin/main)...</b>", parse_mode="HTML")
        ok, git_out = perform_inbot_git_update(hard_reset=True)
        await query.message.reply_text(
            f"✅ <b>Код синхронизирован с GitHub (БД сохранена)!</b>\n"
            f"<pre>{html.escape(git_out[-1200:])}</pre>\n"
            f"⚡ <i>Перезапускаю процесс бота...</i>",
            parse_mode="HTML"
        )
        if sys.platform.startswith("linux") and os.path.exists("/etc/systemd/system/bot_vip.service"):
            subprocess.Popen(["systemctl", "restart", "bot_vip"])
        else:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        return

    if data == "admin_bset_webapp":
        w_url = get_setting("webapp_url", "") or "не задан"
        s_dom = get_setting("sub_domain_prefix", "https://sub.bot-vip.online/sub")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Задать URL для Telegram Mini App", callback_data="admin_bset_set_webapp")],
            [InlineKeyboardButton("🔗 Задать домен единой подписки (Sub URL)", callback_data="admin_set_subdom")],
            [InlineKeyboardButton("🗑 Отключить кнопку Mini App", callback_data="admin_bset_clear_webapp")],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="admin_settings_menu"),
                InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
            ]
        ])
        await query.edit_message_text(
            f"🌐 <b>Настройки Веб и Telegram Mini App</b>\n\n"
            f"📱 <b>URL Mini App кабинета:</b> <code>{html.escape(w_url)}</code>\n"
            f"🔗 <b>Домен единой подписки (3x-ui + Proxy):</b>\n<code>{html.escape(s_dom)}</code>\n"
            f"🖧 <b>Локальный порт Sub-Aggregator:</b> <code>{SUB_PORT}</code>",
            parse_mode="HTML",
            reply_markup=kb
        )
        return

    if data == "admin_bset_set_webapp":
        context.user_data["mode"] = "set_webapp_url"
        await query.edit_message_text(
            "🌐 <b>Настройка Telegram Mini App (WebApp)</b>\n\n"
            "Отправьте HTTPS-ссылку на ваш веб-кабинет или страницу подписки (например: <code>https://app.svoii-vpn.online</code>):",
            parse_mode="HTML"
        )
        return

    if data == "admin_bset_clear_webapp":
        set_setting("webapp_url", "")
        text_out, kb_out = render_bot_settings_main_screen()
        await query.edit_message_text(f"✅ Кнопка Mini App отключена.\n\n{text_out}", parse_mode="HTML", reply_markup=kb_out)
        return

    if data == "admin_bset_backup":
        snap_path = create_manual_snapshot_backup()
        if os.path.exists(snap_path):
            with open(snap_path, "rb") as f:
                await query.message.reply_document(
                    document=f,
                    filename=f"backup_Bot_VIP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                    caption="📦 <b>Резервная копия базы данных успешно создана!</b>\nСнимок также сохранен в каталоге <code>backup/</code> для быстрого отката.",
                    parse_mode="HTML"
                )
        text_out, kb_out = render_bot_settings_main_screen()
        await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    if data == "admin_bset_devices":
        cur_lim = get_setting("device_limit_ip", "2")
        lim_txt = "Безлимит (0)" if cur_lim == "0" else f"{cur_lim} устр."
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("1 устр.", callback_data="admin_bset_dev_1"),
                InlineKeyboardButton("2 устр.", callback_data="admin_bset_dev_2"),
                InlineKeyboardButton("3 устр.", callback_data="admin_bset_dev_3")
            ],
            [
                InlineKeyboardButton("5 устр.", callback_data="admin_bset_dev_5"),
                InlineKeyboardButton("♾ Безлимит", callback_data="admin_bset_dev_0")
            ],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="admin_settings_menu"),
                InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
            ]
        ])
        await query.edit_message_text(
            f"📱 <b>Ограничение одновременных устройств (limitIp)</b>\n\n"
            f"🔒 Текущий лимит на 1 ключ: <b>{html.escape(lim_txt)}</b>\n\n"
            f"Это значение автоматически передается в панель <b>3x-ui</b> при создании ключей:",
            parse_mode="HTML",
            reply_markup=kb
        )
        return

    if data.startswith("admin_bset_dev_"):
        new_lim = data.split("_")[-1]
        set_setting("device_limit_ip", new_lim)
        lim_txt = "Безлимит (0)" if new_lim == "0" else f"{new_lim} устр."
        text_out, kb_out = render_bot_settings_main_screen()
        await query.edit_message_text(
            f"✅ <b>Ограничение устройств установлено на: {lim_txt}</b>\n\n{text_out}",
            parse_mode="HTML",
            reply_markup=kb_out
        )
        return

    if data == "admin_bset_texts":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👋 Текст приветствия (/start)", callback_data="admin_bset_txt_welcome")],
            [InlineKeyboardButton("ℹ️ Текст раздела «О боте»", callback_data="admin_bset_txt_about")],
            [InlineKeyboardButton("🆘 Текст раздела «Поддержка»", callback_data="admin_bset_txt_support")],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="admin_settings_menu"),
                InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
            ]
        ])
        await query.edit_message_text(
            "✏️ <b>Редактор текстов бота</b>\n\n"
            "Выберите, какой текст вы хотите изменить (поддерживается HTML-форматирование <code>&lt;b&gt;</code>, <code>&lt;i&gt;</code>, <code>&lt;code&gt;</code>):",
            parse_mode="HTML",
            reply_markup=kb
        )
        return

    if data.startswith("admin_bset_txt_"):
        t_type = data.replace("admin_bset_txt_", "")
        setting_key = f"text_{t_type}"
        cur_txt = get_setting(setting_key, "")
        context.user_data["mode"] = "edit_bot_text"
        context.user_data["target_text_key"] = setting_key
        await query.edit_message_text(
            f"✏️ <b>Изменение текста ({html.escape(t_type)})</b>\n\n"
            f"<b>Текущий текст:</b>\n{cur_txt}\n\n"
            f"Отправьте новый текст одним сообщением:",
            parse_mode="HTML"
        )
        return

    if data == "admin_bset_logs":
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, "rb") as f:
                await query.message.reply_document(
                    document=f,
                    filename=f"bot_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
                    caption="📥 <b>Системный журнал работы бота (bot.log)</b>",
                    parse_mode="HTML"
                )
        csv_path = "user_inputs_export.csv"
        export_logs_to_csv(csv_path)
        if os.path.exists(csv_path):
            with open(csv_path, "rb") as f:
                await query.message.reply_document(
                    document=f,
                    filename=f"user_inputs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    caption="📥 <b>Полный архив всех вводов пользователей (.csv)</b>",
                    parse_mode="HTML"
                )
        return

    if data == "admin_bset_stop_confirm":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛑 Да, остановить бота", callback_data="admin_bset_stop_exec")],
            [InlineKeyboardButton("⬅️ Отмена", callback_data="admin_settings_menu")]
        ])
        await query.edit_message_text(
            "⚠️ <b>Вы действительно хотите остановить работу бота?</b>\n\n"
            "После остановки бот перестанет отвечать на команды до тех пор, пока вы не запустите его на сервере (<code>systemctl start bot_vip</code>).",
            parse_mode="HTML",
            reply_markup=kb
        )
        return

    if data == "admin_bset_stop_exec":
        await query.edit_message_text("🛑 <b>Служба бота останавливается...</b>", parse_mode="HTML")
        if sys.platform.startswith("linux"):
            subprocess.Popen(["systemctl", "stop", "bot_vip"])
        else:
            os._exit(0)
        return

    # ==========================================================================
    # 📣 МЕНЮ "МАРКЕТИНГ"
    # ==========================================================================
    if data == "admin_marketing_menu":
        text_out, kb_out = render_marketing_main_screen()
        await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    if data == "admin_mkt_broadcast_menu":
        ch_url = get_setting("channel_url", "не задана")
        req_sub = get_setting("require_channel_sub", "0") == "1"
        req_icon = "🟢 ВКЛ" if req_sub else "⚪️ ВЫКЛ"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Запустить рассылку всем пользователям", callback_data="admin_broadcast")],
            [InlineKeyboardButton("📰 Опубликовать новость канала (с закрепом)", callback_data="admin_news")],
            [InlineKeyboardButton("🔗 Настроить ссылку на канал", callback_data="admin_set_channel")],
            [InlineKeyboardButton(f"🔒 Обязательная подписка на канал: {req_icon}", callback_data="admin_toggle_req_sub")],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="admin_marketing_menu"),
                InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
            ]
        ])
        await query.edit_message_text(
            f"📢 <b>Инструмент: Рассылка и Канал</b>\n\n"
            f"🔗 Текущий канал: <code>{html.escape(ch_url)}</code>\n"
            f"🔒 Обязательная подписка для теста/промо: <b>{req_icon}</b>\n\n"
            f"Выберите действие:",
            parse_mode="HTML",
            reply_markup=kb
        )
        return

    if data == "admin_toggle_req_sub":
        cur_v = get_setting("require_channel_sub", "0")
        set_setting("require_channel_sub", "0" if cur_v == "1" else "1")
        ch_url = get_setting("channel_url", "не задана")
        req_sub = get_setting("require_channel_sub", "0") == "1"
        req_icon = "🟢 ВКЛ" if req_sub else "⚪️ ВЫКЛ"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Запустить рассылку всем пользователям", callback_data="admin_broadcast")],
            [InlineKeyboardButton("📰 Опубликовать новость канала (с закрепом)", callback_data="admin_news")],
            [InlineKeyboardButton("🔗 Настроить ссылку на канал", callback_data="admin_set_channel")],
            [InlineKeyboardButton(f"🔒 Обязательная подписка на канал: {req_icon}", callback_data="admin_toggle_req_sub")],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="admin_marketing_menu"),
                InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
            ]
        ])
        await query.edit_message_text(
            f"📢 <b>Инструмент: Рассылка и Канал</b>\n\n"
            f"🔗 Текущий канал: <code>{html.escape(ch_url)}</code>\n"
            f"🔒 Обязательная подписка для теста/промо: <b>{req_icon}</b>",
            parse_mode="HTML",
            reply_markup=kb
        )
        return

    if data == "admin_mkt_referrals":
        ref_on = get_setting("ref_enabled", "1") == "1"
        st_icon = "🟢 Включена" if ref_on else "🔴 Выключена"
        b_inv = get_setting("ref_bonus_days", "7")
        b_new = get_setting("ref_NewUser_days", "3")
        with sqlite3.connect(DB_PATH) as conn:
            total_refs = conn.execute("SELECT COALESCE(SUM(referrals_count), 0) FROM users").fetchone()[0]

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Включить / Выключить реф. систему", callback_data="admin_mkt_ref_toggle")],
            [InlineKeyboardButton("🎁 Изменить бонусные дни (Пригласившему | Другу)", callback_data="admin_mkt_ref_edit")],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="admin_marketing_menu"),
                InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
            ]
        ])
        await query.edit_message_text(
            f"🔗 <b>Реферальная система</b>\n\n"
            f"📡 Статус: <b>{st_icon}</b>\n"
            f"🎁 Бонус пригласившему: <b>+{html.escape(b_inv)} дн. подписки</b>\n"
            f"🎉 Бонус приглашенному другу: <b>+{html.escape(b_new)} дн. подписки</b>\n"
            f"👥 Всего приглашено по реф. ссылкам: <b>{total_refs} чел.</b>",
            parse_mode="HTML",
            reply_markup=kb
        )
        return

    if data == "admin_mkt_ref_toggle":
        cur_v = get_setting("ref_enabled", "1")
        set_setting("ref_enabled", "0" if cur_v == "1" else "1")
        ref_on = get_setting("ref_enabled", "1") == "1"
        st_icon = "🟢 Включена" if ref_on else "🔴 Выключена"
        b_inv = get_setting("ref_bonus_days", "7")
        b_new = get_setting("ref_NewUser_days", "3")
        with sqlite3.connect(DB_PATH) as conn:
            total_refs = conn.execute("SELECT COALESCE(SUM(referrals_count), 0) FROM users").fetchone()[0]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Включить / Выключить реф. систему", callback_data="admin_mkt_ref_toggle")],
            [InlineKeyboardButton("🎁 Изменить бонусные дни (Пригласившему | Другу)", callback_data="admin_mkt_ref_edit")],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="admin_marketing_menu"),
                InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
            ]
        ])
        await query.edit_message_text(
            f"🔗 <b>Реферальная система</b>\n\n"
            f"📡 Статус: <b>{st_icon}</b>\n"
            f"🎁 Бонус пригласившему: <b>+{html.escape(b_inv)} дн. подписки</b>\n"
            f"🎉 Бонус приглашенному другу: <b>+{html.escape(b_new)} дн. подписки</b>\n"
            f"👥 Всего приглашено по реф. ссылкам: <b>{total_refs} чел.</b>",
            parse_mode="HTML",
            reply_markup=kb
        )
        return

    if data == "admin_mkt_ref_edit":
        context.user_data["mode"] = "edit_ref_days"
        await query.edit_message_text(
            "🔗 <b>Настройка бонусов реферальной системы</b>\n\n"
            "Отправьте через вертикальную черту <code>|</code> сколько дней начислять пригласившему и сколько приглашенному другу:\n"
            "Пример: <code>7 | 3</code>",
            parse_mode="HTML"
        )
        return

    if data == "admin_mkt_promocodes":
        promos = get_all_promocodes()
        lines = ["🎟 <b>Управление промокодами (на бесплатные дни)</b>\n"]
        kb_rows = [[InlineKeyboardButton("➕ Создать промокод", callback_data="admin_mkt_promo_add")]]
        if not promos:
            lines.append("<i>Активных промокодов пока нет.</i>")
        else:
            for code, days, max_u, used_c in promos:
                lines.append(f"• <code>{html.escape(code)}</code> — <b>+{days} дн.</b> (Активаций: {used_c}/{max_u})")
                kb_rows.append([InlineKeyboardButton(f"🗑 Удалить {code} ({used_c}/{max_u})", callback_data=f"admin_mkt_promo_del_{code}")])
        kb_rows.append([
            InlineKeyboardButton("⬅️ Назад", callback_data="admin_marketing_menu"),
            InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
        ])
        await query.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))
        return

    if data == "admin_mkt_promo_add":
        context.user_data["mode"] = "add_promocode"
        await query.edit_message_text(
            "➕ <b>Создание промокода на дни подписки</b>\n\n"
            "Отправьте параметры через вертикальную черту <code>|</code>:\n"
            "<code>КОД | Дней подписки | Лимит активаций</code>\n\n"
            "<b>Пример:</b>\n"
            "<code>VIP2026 | 7 | 50</code>",
            parse_mode="HTML"
        )
        return

    if data.startswith("admin_mkt_promo_del_"):
        code = data.replace("admin_mkt_promo_del_", "")
        delete_promocode_db(code)
        promos = get_all_promocodes()
        lines = ["🎟 <b>Управление промокодами (на бесплатные дни)</b>\n"]
        kb_rows = [[InlineKeyboardButton("➕ Создать промокод", callback_data="admin_mkt_promo_add")]]
        for c_val, days, max_u, used_c in promos:
            lines.append(f"• <code>{html.escape(c_val)}</code> — <b>+{days} дн.</b> (Активаций: {used_c}/{max_u})")
            kb_rows.append([InlineKeyboardButton(f"🗑 Удалить {c_val}", callback_data=f"admin_mkt_promo_del_{c_val}")])
        kb_rows.append([
            InlineKeyboardButton("⬅️ Назад", callback_data="admin_marketing_menu"),
            InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
        ])
        await query.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))
        return

    if data == "admin_mkt_coupons":
        coupons = get_all_coupons()
        lines = ["🎫 <b>Управление скидочными купонами (%)</b>\n"]
        kb_rows = [[InlineKeyboardButton("➕ Создать купон на скидку", callback_data="admin_mkt_coupon_add")]]
        if not coupons:
            lines.append("<i>Активных купонов пока нет.</i>")
        else:
            for code, disc_pct, max_u, used_c in coupons:
                lines.append(f"• <code>{html.escape(code)}</code> — скидка <b>-{disc_pct}%</b> (Использовано: {used_c}/{max_u})")
                kb_rows.append([InlineKeyboardButton(f"🗑 Удалить купон {code} (-{disc_pct}%)", callback_data=f"admin_mkt_coupon_del_{code}")])
        kb_rows.append([
            InlineKeyboardButton("⬅️ Назад", callback_data="admin_marketing_menu"),
            InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
        ])
        await query.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))
        return

    if data == "admin_mkt_coupon_add":
        context.user_data["mode"] = "add_coupon"
        await query.edit_message_text(
            "➕ <b>Создание скидочного купона</b>\n\n"
            "Отправьте параметры через вертикальную черту <code>|</code>:\n"
            "<code>КОД_КУПОНА | Процент скидки (1-90) | Лимит активаций</code>\n\n"
            "<b>Пример:</b>\n"
            "<code>SALE30 | 30 | 100</code>",
            parse_mode="HTML"
        )
        return

    if data.startswith("admin_mkt_coupon_del_"):
        code = data.replace("admin_mkt_coupon_del_", "")
        delete_coupon_db(code)
        coupons = get_all_coupons()
        lines = ["🎫 <b>Управление скидочными купонами (%)</b>\n"]
        kb_rows = [[InlineKeyboardButton("➕ Создать купон на скидку", callback_data="admin_mkt_coupon_add")]]
        for c_val, disc_pct, max_u, used_c in coupons:
            lines.append(f"• <code>{html.escape(c_val)}</code> — скидка <b>-{disc_pct}%</b> (Использовано: {used_c}/{max_u})")
            kb_rows.append([InlineKeyboardButton(f"🗑 Удалить купон {c_val}", callback_data=f"admin_mkt_coupon_del_{c_val}")])
        kb_rows.append([
            InlineKeyboardButton("⬅️ Назад", callback_data="admin_marketing_menu"),
            InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
        ])
        await query.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))
        return

    # ==========================================================================
    # 👥 МЕНЮ "ПОЛЬЗОВАТЕЛИ"
    # ==========================================================================
    if data == "admin_users_menu":
        text_out, kb_out = render_users_admin_screen()
        await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    if data.startswith("admin_ulist_"):
        page = int(data.split("_")[-1])
        text_out, kb_out = render_users_page(page)
        await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    if data == "admin_usearch":
        context.user_data["mode"] = "search_user"
        await query.edit_message_text(
            "🔍 <b>Поиск пользователя</b>\n\n"
            "Отправьте <code>Telegram ID</code>, <code>@username</code> или имя пользователя:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад в Пользователи", callback_data="admin_users_menu")]])
        )
        return

    if data.startswith("admin_uview_"):
        target_id = int(data.split("_")[-1])
        text_out, kb_out = render_single_user_dossier(target_id)
        await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    if data.startswith("admin_uact_"):
        parts = data.split("_")
        act = parts[2]
        target_id = int(parts[3])

        if act == "add30":
            k_id, until, _, _ = await create_or_extend_user_key(target_id, days=30, create_new=True)
            text_out, kb_out = render_single_user_dossier(target_id)
            await query.edit_message_text(f"✅ <b>Выдан Ключ #{k_id} на 30 дн. (до {until})!</b>\n\n{text_out}", parse_mode="HTML", reply_markup=kb_out)
            return

        if act == "addunl":
            k_id, until, _, _ = await create_or_extend_user_key(target_id, days=0, create_new=True)
            text_out, kb_out = render_single_user_dossier(target_id)
            await query.edit_message_text(f"✅ <b>Выдан безлимитный Ключ #{k_id} (до Без срока)!</b>\n\n{text_out}", parse_mode="HTML", reply_markup=kb_out)
            return

        if act == "revoke":
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("UPDATE users SET is_vip = 0, has_expired = 1, vip_until = '', vpn_config = '' WHERE user_id = ?", (target_id,))
                conn.execute("UPDATE user_keys SET is_active = 0 WHERE user_id = ?", (target_id,))
                conn.commit()
            text_out, kb_out = render_single_user_dossier(target_id)
            await query.edit_message_text(f"❌ <b>Все ключи пользователя отключены!</b>\n\n{text_out}", parse_mode="HTML", reply_markup=kb_out)
            return

        if act == "rsttrial":
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("UPDATE users SET trial_used = 0 WHERE user_id = ?", (target_id,))
                conn.commit()
            text_out, kb_out = render_single_user_dossier(target_id)
            await query.edit_message_text(f"🎁 <b>Пробный период сброшен!</b>\n\n{text_out}", parse_mode="HTML", reply_markup=kb_out)
            return

        if act == "ban":
            toggle_column(target_id, "is_banned")
            text_out, kb_out = render_single_user_dossier(target_id)
            await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
            return

        if act == "msg":
            context.user_data["mode"] = "direct_msg_user"
            context.user_data["target_user_id"] = target_id
            await query.edit_message_text(
                f"✉️ <b>Отправка личного сообщения пользователю <code>{target_id}</code></b>\n\n"
                f"Напишите текст сообщения:",
                parse_mode="HTML"
            )
            return

        if act == "logs":
            with sqlite3.connect(DB_PATH) as conn:
                rows = conn.execute(
                    "SELECT event_type, content, created_at FROM user_logs WHERE user_id = ? ORDER BY id DESC LIMIT 15",
                    (target_id,)
                ).fetchall()
            if not rows:
                await query.message.reply_text("У этого пользователя пока нет записей ввода.")
                return
            lines = [f"🕵️‍♂️ <b>Последние вводы пользователя <code>{target_id}</code>:</b>\n"]
            for ev, cnt, cat in rows:
                lines.append(f"• <code>{cat}</code> [{html.escape(ev)}]: <code>{html.escape(cnt[:100])}</code>")
            await query.message.reply_text("\n".join(lines), parse_mode="HTML")
            return

    if data == "admin_usync_push":
        await query.edit_message_text("⏳ <b>Выгрузка активных пользователей из БД во все панели 3x-ui...</b>", parse_mode="HTML")
        u_cnt, s_cnt = await sync_db_to_panels()
        text_out, kb_out = render_users_admin_screen()
        await query.edit_message_text(
            f"✅ <b>Выгрузка завершена (БД → Панель):</b> синхронизировано <b>{u_cnt}</b> клиентов на <b>{s_cnt}</b> серверах!\n\n{text_out}",
            parse_mode="HTML",
            reply_markup=kb_out
        )
        return

    if data == "admin_usync_pull":
        await query.edit_message_text("⏳ <b>Загрузка клиентов из панелей 3x-ui в БД бота...</b>", parse_mode="HTML")
        imp_cnt = await sync_panels_to_db()
        text_out, kb_out = render_users_admin_screen()
        await query.edit_message_text(
            f"✅ <b>Импорт завершен (Панель → БД):</b> загружено/обновлено <b>{imp_cnt}</b> ключей!\n\n{text_out}",
            parse_mode="HTML",
            reply_markup=kb_out
        )
        return

    if data == "admin_usync_clean":
        await query.edit_message_text("⏳ <b>Синхронизация удалённых и истёкших ключей...</b>", parse_mode="HTML")
        cl_cnt = await sync_cleanup_deleted_and_expired()
        text_out, kb_out = render_users_admin_screen()
        await query.edit_message_text(
            f"🗑 <b>Синхронизация удалённых выполнена:</b> очищено <b>{cl_cnt}</b> неактивных профилей!\n\n{text_out}",
            parse_mode="HTML",
            reply_markup=kb_out
        )
        return

    # ==========================================================================
    # 💳 МЕНЮ "НАСТРОЙКИ ОПЛАТЫ"
    # ==========================================================================
    
    if data == "admin_bind_wallets_menu":
        y_sh = get_setting("pay_yookassa_shop_id", "Не задан")
        y_sk = "✅ Привязан" if get_setting("pay_yookassa_secret", "") else "❌ Не привязан"
        cp_tk = "✅ Привязан" if get_setting("pay_cryptopay_secret", "") else "❌ Не привязан"
        tg_tk = "✅ Привязан" if get_setting("pay_tgpayments_secret", "") else "❌ Не привязан"

        txt = (
            "💼 <b>Привязка кошельков и ключей оплаты</b>\n\n"
            f"💳 <b>ЮKassa:</b>\n• Shop ID: <code>{y_sh}</code>\n• Secret Key: {y_sk}\n\n"
            f"💎 <b>Crypto Pay (@CryptoBot):</b>\n• API Token: {cp_tk}\n\n"
            f"🤖 <b>Telegram Payments:</b>\n• Provider Token: {tg_tk}\n\n"
            "<i>Нажмите на кнопку ниже, чтобы ввести или изменить ключ:</i>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 ЮKassa Shop ID", callback_data="admin_set_key_yoo_shop"),
             InlineKeyboardButton("🔑 ЮKassa Secret Key", callback_data="admin_set_key_yoo_secret")],
            [InlineKeyboardButton("💎 CryptoBot API Token", callback_data="admin_set_key_cp_token"),
             InlineKeyboardButton("🤖 TG Payments Token", callback_data="admin_set_key_tg_token")],
            [InlineKeyboardButton("⬅️ Назад в Оплаты", callback_data="admin_payments_menu")]
        ])
        await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
        return

    if data.startswith("admin_set_key_"):
        key_type = data.replace("admin_set_key_", "")
        context.user_data["mode"] = f"input_paykey_{key_type}"
        prompts = {
            "yoo_shop": "💳 <b>Введите ЮKassa Shop ID</b> (число из ЛК):",
            "yoo_secret": "🔑 <b>Введите ЮKassa Secret Key</b> (вида live_... или test_...):",
            "cp_token": "💎 <b>Введите API-токен из @CryptoBot</b> (Crypto Pay):",
            "tg_token": "🤖 <b>Введите токен провайдера Telegram Payments</b> (из @BotFather):"
        }
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_bind_wallets_menu")]])
        await query.edit_message_text(prompts.get(key_type, "Введите ключ:"), parse_mode="HTML", reply_markup=kb)
        return

    if data == "admin_payments_menu":
        text_out, kb_out = render_payment_settings_screen()
        await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    if data == "admin_pay_toggle_notify":
        cur_v = get_setting("pay_notify_enabled", "1")
        set_setting("pay_notify_enabled", "0" if cur_v == "1" else "1")
        text_out, kb_out = render_payment_settings_screen()
        await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    if await handle_payment_admin_callback(query, context, get_setting, set_setting):
        return

    if data.startswith("admin_pay_secret_"):
        p_key = data.replace("admin_pay_secret_", "")
        context.user_data["mode"] = "set_pay_secret"
        context.user_data["target_pay_key"] = p_key
        hint = (
            "Для ЮKassa отправьте <code>SHOP_ID | SECRET_KEY</code> (например: <code>1368461 | live_xxxx</code>) или реквизиты:"
            if p_key == "yookassa"
            else "Отправьте API-токен (от @CryptoBot / @BotFather / кассы) или платежные реквизиты:"
        )
        await query.edit_message_text(
            f"🔑 <b>Настройка параметров для {html.escape(p_key)}</b>\n\n{hint}",
            parse_mode="HTML"
        )
        return

    if data == "admin_tariff_groups":
        tariffs = get_active_tariffs()
        groups = sorted(list({t[1] for t in tariffs}))
        grp_lines = "\n".join([f"• 📁 <b>{html.escape(g)}</b>" for g in groups]) if groups else "Нет групп"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Перейти к списку тарифов", callback_data="admin_tariffs_list")],
            [InlineKeyboardButton("🔑 Создать одноразовый ключ VPN (30д)", callback_data="admin_gen_VPN_30")],
            [InlineKeyboardButton("🤖 Создать ключ Лицензии Бота (365д)", callback_data="admin_gen_BOT_365")],
            [InlineKeyboardButton("⬅️ Назад в Настройки оплаты", callback_data="admin_payments_menu")]
        ])
        await query.edit_message_text(
            f"📁 <b>Группы тарифов</b>\n\n"
            f"Активные группы в витрине бота:\n{grp_lines}",
            parse_mode="HTML",
            reply_markup=kb
        )
        return

    if data == "admin_tariffs_list":
        tariffs = get_active_tariffs()
        lines = []
        lines.append("📋 <b>Управление тарифами</b>\n")
        lines.append("<i>Выберите тариф для настройки:</i>\n")
        kb_rows = [[InlineKeyboardButton("➕ Добавить новый тариф", callback_data="admin_tariff_add")]]
        for t_id, grp, name, days, pr_rub, pr_stars in tariffs:
            d_lbl = "Без срока" if days == 0 else f"{days} дн."
            lines.append(f"• #{t_id} <b>{html.escape(name)}</b> ({d_lbl}) — <code>{pr_rub} ₽</code> [{html.escape(grp)}]")
            kb_rows.append([
                InlineKeyboardButton(f"✏️ #{t_id} {name[:16]} ({pr_rub}₽)", callback_data=f"admin_tedit_view_{t_id}"),
                InlineKeyboardButton("🗑", callback_data=f"admin_tariff_del_{t_id}")
            ])
        kb_rows.append([InlineKeyboardButton("⬅️ Назад в Настройки оплаты", callback_data="admin_payments_menu")])
        await query.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))
        return

    if data.startswith("admin_tedit_view_"):
        t_id = int(data.split("_")[-1])
        t_row = get_tariff_by_id(t_id)
        if not t_row:
            await query.answer("Тариф не найден!", show_alert=True)
            return
        _, grp, name, days, pr_rub, pr_stars = t_row
        d_lbl = "Без срока" if days == 0 else f"{days} дн."
        t_text = f"⚙️ <b>Редактирование тарифа #{t_id}</b>\n\n📁 Группа: {html.escape(grp)}\n🏷 Название: {html.escape(name)}\n⏳ Длительность: {d_lbl}\n💰 Цена: {pr_rub} ₽ ({pr_stars} ⭐️)\n\nВыберите параметр для изменения:"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Изменить цену (₽)", callback_data=f"admin_tedit_param_price_{t_id}"),
             InlineKeyboardButton("⏳ Изменить срок", callback_data=f"admin_tedit_param_days_{t_id}")],
            [InlineKeyboardButton("🏷 Переименовать", callback_data=f"admin_tedit_param_name_{t_id}"),
             InlineKeyboardButton("📁 Сменить группу", callback_data=f"admin_tedit_param_grp_{t_id}")],
            [InlineKeyboardButton("🗑 Удалить тариф", callback_data=f"admin_tariff_del_{t_id}")],
            [InlineKeyboardButton("⬅️ К списку тарифов", callback_data="admin_tariffs_list")]
        ])
        await query.edit_message_text(t_text, parse_mode="HTML", reply_markup=kb)
        return

    if data.startswith("admin_tedit_param_"):
        parts = data.split("_")
        action = parts[3]
        t_id = int(parts[4])
        context.user_data["mode"] = f"tedit_{action}_{t_id}"
        prompts = {
            "price": "💰 <b>Введите новую цену в рублях</b> (например, <code>250</code>):",
            "days": "⏳ <b>Введите количество дней</b> (<code>0</code> = Без срока, например <code>30</code>):",
            "name": "🏷 <b>Введите новое название тарифа</b> (например, <code>🔥 1 Месяц VIP</code>):",
            "grp": "📁 <b>Введите группу тарифа</b> (например, <code>Акции</code> или <code>Стандарт</code>):"
        }
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data=f"admin_tedit_view_{t_id}")]])
        await query.edit_message_text(prompts.get(action, "Введите новое значение:"), parse_mode="HTML", reply_markup=kb)
        return

    if data == "admin_tariff_add":
        context.user_data["mode"] = "add_tariff"
        await query.edit_message_text(
            "➕ <b>Добавление нового тарифа</b>\n\n"
            "Отправьте параметры тарифа через вертикальную черту <code>|</code>:\n"
            "<code>Группа | Название тарифа | Дней (0 = Без срока) | Цена в рублях</code>\n\n"
            "<b>Пример:</b>\n"
            "<code>Единая подписка (3x-ui + Proxy) | 🔥 2 месяца | 60 | 349</code>",
            parse_mode="HTML"
        )
        return

    if data.startswith("admin_tariff_del_"):
        t_id = int(data.split("_")[-1])
        delete_tariff(t_id)
        tariffs = get_active_tariffs()
        lines = []
        lines.append("📋 <b>Управление тарифами</b>\n")
        lines.append("<i>Тариф успешно удален!</i>\n")
        kb_rows = [[InlineKeyboardButton("➕ Добавить новый тариф", callback_data="admin_tariff_add")]]
        for tid, grp, name, days, pr_rub, pr_stars in tariffs:
            d_lbl = "Без срока" if days == 0 else f"{days} дн."
            lines.append(f"• #{tid} <b>{html.escape(name)}</b> ({d_lbl}) — <code>{pr_rub} ₽</code> [{html.escape(grp)}]")
            kb_rows.append([
                InlineKeyboardButton(f"✏️ #{tid} {name[:16]} ({pr_rub}₽)", callback_data=f"admin_tedit_view_{tid}"),
                InlineKeyboardButton("🗑", callback_data=f"admin_tariff_del_{tid}")
            ])
        kb_rows.append([InlineKeyboardButton("⬅️ Назад в Настройки оплаты", callback_data="admin_payments_menu")])
        await query.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))
        return

    if data == "admin_currency_menu":
        cur_main = get_setting("currency_main", "RUB (₽)")
        usdt_r = get_setting("currency_usdt_rate", "95.0")
        stars_r = get_setting("currency_stars_rate", "2.0")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💵 Изменить курс USDT и Stars", callback_data="admin_currency_edit")],
            [InlineKeyboardButton("⬅️ Назад в Настройки оплаты", callback_data="admin_payments_menu")]
        ])
        await query.edit_message_text(
            f"💱 <b>Валюта и курсы конвертации</b>\n\n"
            f"🏦 Основная валюта: <b>{html.escape(cur_main)}</b>\n"
            f"💎 Курс 1 USDT: <code>{html.escape(usdt_r)} ₽</code>\n"
            f"⭐️ Курс 1 Telegram Star: <code>{html.escape(stars_r)} ₽</code>",
            parse_mode="HTML",
            reply_markup=kb
        )
        return

    if data == "admin_currency_edit":
        context.user_data["mode"] = "edit_currency"
        await query.edit_message_text(
            "💱 <b>Изменение курсов валют</b>\n\n"
            "Отправьте курс USDT и курс Stars через вертикальную черту <code>|</code>:\n"
            "Пример: <code>96.5 | 2.0</code>",
            parse_mode="HTML"
        )
        return

    if data == "admin_trial_menu":
        t_on = get_setting("trial_enabled", "1") == "1"
        t_days = get_setting("trial_days", "3")
        st_icon = "🟢 Включена" if t_on else "🔴 Выключена"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Включить / Выключить пробный период", callback_data="admin_trial_toggle")],
            [InlineKeyboardButton("⏳ Изменить число дней теста", callback_data="admin_trial_days_edit")],
            [InlineKeyboardButton("⬅️ Назад в Настройки оплаты", callback_data="admin_payments_menu")]
        ])
        await query.edit_message_text(
            f"🎁 <b>Настройки пробной подписки</b>\n\n"
            f"📡 Статус: <b>{st_icon}</b>\n"
            f"⏳ Длительность теста: <b>{html.escape(t_days)} дн.</b>\n"
            f"🛡 Защита от абуза: <code>Строго 1 раз на один Telegram ID</code>",
            parse_mode="HTML",
            reply_markup=kb
        )
        return

    if data == "admin_trial_toggle":
        cur_v = get_setting("trial_enabled", "1")
        set_setting("trial_enabled", "0" if cur_v == "1" else "1")
        t_on = get_setting("trial_enabled", "1") == "1"
        t_days = get_setting("trial_days", "3")
        st_icon = "🟢 Включена" if t_on else "🔴 Выключена"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Включить / Выключить пробный период", callback_data="admin_trial_toggle")],
            [InlineKeyboardButton("⏳ Изменить число дней теста", callback_data="admin_trial_days_edit")],
            [InlineKeyboardButton("⬅️ Назад в Настройки оплаты", callback_data="admin_payments_menu")]
        ])
        await query.edit_message_text(
            f"🎁 <b>Настройки пробной подписки</b>\n\n"
            f"📡 Статус: <b>{st_icon}</b>\n"
            f"⏳ Длительность теста: <b>{html.escape(t_days)} дн.</b>\n"
            f"🛡 Защита от абуза: <code>Строго 1 раз на один Telegram ID</code>",
            parse_mode="HTML",
            reply_markup=kb
        )
        return

    if data == "admin_trial_days_edit":
        context.user_data["mode"] = "edit_trial_days"
        await query.edit_message_text("⏳ Отправьте количество дней для пробной подписки (например: <code>3</code>):", parse_mode="HTML")
        return

    if data.startswith("approve_pay_"):
        parts = data.split("_")
        target_id = int(parts[2])
        days = int(parts[3])
        price = float(parts[4])
        record_payment(target_id, price, "Confirmed", f"Подтвержденная оплата ({days} дн.)")
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE users SET active_discount_pct = 0 WHERE user_id = ?", (target_id,))
            conn.commit()
        k_id, until, sub_url, _ = await create_or_extend_user_key(target_id, days=days, create_new=True)
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    f"🎉 <b>Ваша оплата подтверждена! Выпущен Ключ #{k_id} (до {until})</b>\n\n"
                    f"🔗 <b>Единая ссылка подписки:</b>\n<code>{html.escape(sub_url)}</code>\n\n"
                    f"Откройте раздел <b>«🔑 Мои ключи»</b> для управления."
                ),
                parse_mode="HTML",
                protect_content=True
            )
        except Exception:
            pass
        await query.message.reply_text(
            f"✅ Оплата зачислена (<code>+{int(price)} ₽</code>), <b>Ключ #{k_id}</b> отправлен клиенту <code>{target_id}</code>!",
            parse_mode="HTML"
        )
        return

    # ==========================================================================
    # 🖥 ЭКРАН "СЕРВЕРА"
    # ==========================================================================
    if data == "admin_servers_menu":
        text_out, kb_out = await render_servers_monitor_screen()
        await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    if data == "admin_srv_add":
        context.user_data["mode"] = "add_server"
        await query.edit_message_text(
            "➕ <b>Добавление сервера (3x-ui + Web Panel Proxy 2.7.0)</b>\n\n"
            "Отправьте данные сервера одной строкой через вертикальную черту <code>|</code>:\n\n"
            "<b>Формат 1 (Полная интеграция по API):</b>\n"
            "<code>Флаг Название | host:port | http://ip:port/path | login | password | inbound_id | https://sub.domain/sub</code>\n\n"
            "<b>Формат 2 (Быстрое добавление ноды):</b>\n"
            "<code>🇳🇱 Нидерланды | nl.svoii-vpn.online:5005</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад к серверам", callback_data="admin_servers_menu")]])
        )
        return

    if data.startswith("admin_srv_view_"):
        srv_id = int(data.split("_")[-1])
        srv = get_server_full_by_id(srv_id)
        if not srv:
            await query.edit_message_text("Сервер не найден.", reply_markup=admin_dashboard_keyboard())
            return
        srv_id, name, host, p_type, p_url, p_user, p_pass, inb_id, sub_pref, prx_tpl, is_active = srv
        st = await poll_node_live_status(srv)
        status_line = "⏸ Деактивирован" if not is_active else ("🟢 Онлайн" if st["online"] else f"🔴 {st['error']}")
        toggle_label = "⏸ Деактивировать сервер" if is_active else "▶️ Активировать сервер"

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_label, callback_data=f"admin_srv_toggle_{srv_id}")],
            [InlineKeyboardButton("🔗 Задать шаблон Web Panel Proxy 2.7.0", callback_data=f"admin_srv_tpl_{srv_id}")],
            [InlineKeyboardButton("➕ Загрузить доп. ключи в пул сервера", callback_data=f"admin_add_vpn_{srv_id}")],
            [InlineKeyboardButton("🗑 Удалить сервер", callback_data=f"admin_srv_del_{srv_id}")],
            [InlineKeyboardButton("⬅️ Назад к списку серверов", callback_data="admin_servers_menu")]
        ])
        await query.edit_message_text(
            f"🖥 <b>Управление сервером #{srv_id}: {html.escape(name)}</b>\n\n"
            f"🌐 <b>Хост:</b> <code>{html.escape(host)}</code>\n"
            f"🔌 <b>Режим:</b> <code>{html.escape(p_type)}</code> (Inbound ID: <code>{inb_id}</code>)\n"
            f"🔗 <b>URL панели:</b> <code>{html.escape(p_url or 'TCP/Proxy режим')}</code>\n"
            f"📡 <b>Статус:</b> {html.escape(status_line)}\n"
            f"🔑 <b>Онлайн:</b> {st.get('clients_online', 0)} | 📊 <b>Трафик:</b> {st.get('traffic_str', '0 GB')}\n"
            f"🧩 <b>Шаблон Proxy 2.7.0:</b> <code>{html.escape(prx_tpl or 'Авто VLESS+WS')}</code>",
            parse_mode="HTML",
            reply_markup=kb
        )
        return

    if data.startswith("admin_srv_toggle_"):
        srv_id = int(data.split("_")[-1])
        toggle_server_active(srv_id)
        text_out, kb_out = await render_servers_monitor_screen()
        await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    if data.startswith("admin_srv_tpl_"):
        srv_id = int(data.split("_")[-1])
        context.user_data["mode"] = "set_proxy_tpl"
        context.user_data["target_server_id"] = srv_id
        await query.edit_message_text(
            f"🧩 <b>Шаблон Web Panel Proxy 2.7.0 для сервера #{srv_id}</b>\n\n"
            f"Доступные переменные: <code>{{UUID}}</code>, <code>{{SUB_ID}}</code>, <code>{{USER_ID}}</code>, <code>{{HOST}}</code>, <code>{{PORT}}</code>, <code>{{NAME}}</code>.",
            parse_mode="HTML"
        )
        return

    if data.startswith("admin_srv_del_"):
        srv_id = int(data.split("_")[-1])
        delete_vpn_server(srv_id)
        text_out, kb_out = await render_servers_monitor_screen()
        await query.edit_message_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    if data.startswith("admin_add_vpn_"):
        srv_id = int(data.split("_")[-1])
        context.user_data["mode"] = "add_vpn_pool"
        context.user_data["target_server_id"] = srv_id
        await query.edit_message_text(
            f"➕ <b>Загрузка ключей в пул сервера #{srv_id}</b>\n"
            f"Отправьте список конфигураций (каждая с новой строки):",
            parse_mode="HTML"
        )
        return

    if data == "admin_set_subdom":
        context.user_data["mode"] = "set_subdom"
        await query.edit_message_text(
            "🌐 <b>Настройка единого домена подписки (Subscription URL)</b>\n\n"
            "Отправьте базовый URL (например: <code>https://sub.svoii-vpn.online:2097/sub</code>):",
            parse_mode="HTML"
        )
        return

    if data == "admin_notif_menu":
        await query.edit_message_text(
            "🔔 <b>Персональные настройки уведомлений</b>\n\n"
            "Выберите, какие события присылать вам в личные сообщения:",
            parse_mode="HTML",
            reply_markup=notif_settings_keyboard()
        )
        return

    if data.startswith("toggle_notif_"):
        notif_key = data.replace("toggle_notif_", "")
        if notif_key in NOTIF_TYPES:
            cur_state = is_notif_enabled(notif_key)
            set_setting(notif_key, "0" if cur_state else "1")
        await query.edit_message_reply_markup(reply_markup=notif_settings_keyboard())
        return

    if data == "notif_preset_all":
        for k in NOTIF_TYPES:
            set_setting(k, "1")
        await query.edit_message_reply_markup(reply_markup=notif_settings_keyboard())
        return

    if data == "notif_preset_important":
        important_keys = {"notify_orders", "notify_support", "notify_keys", "notify_security", "notify_backup"}
        for k in NOTIF_TYPES:
            set_setting(k, "1" if k in important_keys else "0")
        await query.edit_message_reply_markup(reply_markup=notif_settings_keyboard())
        return

    if data == "notif_preset_none":
        for k in NOTIF_TYPES:
            set_setting(k, "0")
        await query.edit_message_reply_markup(reply_markup=notif_settings_keyboard())
        return

    if data == "admin_view_logs":
        rows = get_recent_logs(15)
        if not rows:
            await query.message.reply_text("Лог вводов пока пуст.")
            return
        lines = ["🕵️‍♂️ <b>Последние 15 действий пользователей в БД:</b>\n"]
        for r in rows:
            uid, uname, fname, ev_type, content, c_at = r
            short_c = html.escape(content[:120])
            lines.append(f"• <code>{c_at}</code> | <b>{html.escape(fname)}</b> (@{html.escape(uname)}, <code>{uid}</code>)\n  [{html.escape(ev_type)}]: <code>{short_c}</code>")
        await query.message.reply_text("\n".join(lines), parse_mode="HTML")

    elif data == "admin_export_csv":
        csv_path = "user_inputs_export.csv"
        export_logs_to_csv(csv_path)
        with open(csv_path, "rb") as f:
            await query.message.reply_document(
                document=f,
                filename=f"user_inputs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                caption="📥 <b>Полный архив всех данных, введенных пользователями</b>",
                parse_mode="HTML"
            )

    elif data.startswith("admin_gen_"):
        parts = data.split("_")
        k_type = parts[2]
        days = int(parts[3])
        new_key = create_tariff_key(k_type, days)
        label = "🌐 Единая подписка (3x-ui + Proxy 2.7.0)" if k_type == "VPN" else "🤖 Лицензия Бота"
        await query.message.reply_text(
            f"🔑 <b>Одноразовый ключ ({label} на {days} дн.) создан:</b>\n\n"
            f"<code>{new_key}</code>",
            parse_mode="HTML"
        )

    elif data.startswith("quick_vpn_"):
        target_id = int(data.split("_")[-1])
        k_id, until, sub_url, _ = await create_or_extend_user_key(target_id, days=30, create_new=True)
        record_payment(target_id, 199, "QuickApprove", "Одобрение заявки VPN (30 дн.)")
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    f"🎉 <b>Ваш заказ одобрен! Выпущен Ключ #{k_id} (до {until})</b>\n\n"
                    f"🔗 <b>Единая ссылка подписки:</b>\n<code>{html.escape(sub_url)}</code>\n\n"
                    f"Откройте раздел <b>«🔑 Мои ключи»</b> для управления."
                ),
                parse_mode="HTML",
                protect_content=True
            )
        except Exception:
            pass
        await query.message.reply_text(
            f"✅ Пользователю <code>{target_id}</code> выпущен <b>Ключ #{k_id}</b> на 30 дней!",
            parse_mode="HTML"
        )

    elif data == "admin_set_channel":
        context.user_data["mode"] = "set_channel"
        ch_url = get_setting("channel_url", "не задана")
        await query.edit_message_text(
            f"🔗 <b>Настройка ссылки на канал</b>\n\nТекущая: <code>{html.escape(ch_url)}</code>\nОтправьте новую ссылку:",
            parse_mode="HTML"
        )
    elif data == "admin_news":
        context.user_data["mode"] = "news_text"
        ch_url = get_setting("channel_url", "")
        await query.edit_message_text(
            f"📰 <b>Публикация новости с авто-закрепом в ЛС</b>\n"
            f"Канал по умолчанию: <code>{html.escape(ch_url or 'не задан')}</code>\n\n"
            f"Отправьте текст новости:",
            parse_mode="HTML"
        )
    elif data == "admin_broadcast":
        context.user_data["mode"] = "broadcast"
        await query.edit_message_text("📢 Отправьте текст для рассылки всем пользователям:")
    elif data == "admin_vip":
        context.user_data["mode"] = "toggle_vip"
        await query.edit_message_text("⭐ Отправьте Telegram ID пользователя для выпуска ключа подписки на 30 дней:")
    elif data == "admin_ban":
        context.user_data["mode"] = "toggle_ban"
        await query.edit_message_text("🚫 Отправьте Telegram ID пользователя для бана/разбана:")
    elif data == "admin_backup":
        snap_path = create_manual_snapshot_backup()
        if os.path.exists(snap_path):
            with open(snap_path, "rb") as f:
                await query.message.reply_document(
                    document=f,
                    filename=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                    caption="💾 Актуальная копия базы данных"
                )
    elif data == "admin_logs":
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, "rb") as f:
                await query.message.reply_document(document=f, filename="bot.log", caption="📜 Системный лог (bot.log)")
    elif data == "admin_restart":
        await query.edit_message_text("⚡ <b>Перезапуск службы бота...</b>", parse_mode="HTML")
        if sys.platform.startswith("linux") and os.path.exists("/etc/systemd/system/bot_vip.service"):
            subprocess.Popen(["systemctl", "restart", "bot_vip"])
        else:
            os.execv(sys.executable, [sys.executable] + sys.argv)

# --- Обработка текстовых сообщений ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_payment_admin_text(update.message, update.effective_user, context, set_setting, get_setting, ADMIN_ID):
        return
    user = update.effective_user
    msg = update.message
    text = msg.text or ""

    if is_flooding(user.id):
        return

    register_user(user)
    check_and_expire_vips()

    info = get_user_info(user.id)
    if info and info[5] == 1 and user.id != ADMIN_ID:
        log_user_action_to_db(user, "Попытка ввода (Забанен)", text)
        await msg.reply_text("⛔ Доступ к боту заблокирован системой безопасности.")
        return

    # 1. Ответ Админа через Reply
    if user.id == ADMIN_ID and msg.reply_to_message:
        replied_text = msg.reply_to_message.text or ""
        if "ID:" in replied_text:
            try:
                target_id_str = replied_text.split("ID:")[1].split()[0].strip("()`")
                target_id = int(target_id_str)
                await context.bot.send_message(
                    chat_id=target_id,
                    text=f"✉️ <b>Сообщение от Администратора:</b>\n\n{html.escape(text)}",
                    parse_mode="HTML"
                )
                await msg.reply_text(f"✅ Ответ доставлен пользователю <code>{target_id}</code>.", parse_mode="HTML")
                return
            except Forbidden:
                mark_user_blocked_bot(target_id, 1)
                await msg.reply_text(f"⚠️ Пользователь <code>{target_id}</code> заблокировал бота.", parse_mode="HTML")
                return
            except Exception as e:
                await msg.reply_text(f"❌ Не удалось отправить ответ: {e}")
                return

    mode = context.user_data.get("mode")

    if mode == "rename_user_key":
        context.user_data["mode"] = None
        k_id = context.user_data.get("target_key_id", 0)
        new_name = text.strip()[:35]
        if new_name:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("UPDATE user_keys SET key_name = ? WHERE id = ? AND user_id = ?", (new_name, k_id, user.id))
                conn.commit()
        await notify_admin_event(user, "notify_keys", f"✏️ Переименование ключа #{k_id}", new_name, context)
        text_out, kb_out = await render_my_keys_screen(user.id)
        await msg.reply_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    # 2. Режимы ввода Администратора
    if user.id == ADMIN_ID and mode:
        if mode == "set_webapp_url":
            context.user_data["mode"] = None
            set_setting("webapp_url", text.strip())
            text_out, kb_out = render_bot_settings_main_screen()
            await msg.reply_text(
                f"✅ URL для Telegram Mini App сохранен:\n<code>{html.escape(text.strip())}</code>\n\n{text_out}",
                parse_mode="HTML",
                reply_markup=kb_out
            )
            return

        elif mode == "edit_bot_text":
            context.user_data["mode"] = None
            target_key = context.user_data.get("target_text_key", "text_about")
            set_setting(target_key, text)
            text_out, kb_out = render_bot_settings_main_screen()
            await msg.reply_text(f"✅ Текст успешно обновлен!\n\n{text_out}", parse_mode="HTML", reply_markup=kb_out)
            return

        elif mode == "edit_ref_days":
            context.user_data["mode"] = None
            if "|" in text:
                b1, b2 = [x.strip() for x in text.split("|", 1)]
                if b1.isdigit():
                    set_setting("ref_bonus_days", b1)
                if b2.isdigit():
                    set_setting("ref_NewUser_days", b2)
            elif text.strip().isdigit():
                set_setting("ref_bonus_days", text.strip())
            text_out, kb_out = render_marketing_main_screen()
            await msg.reply_text(f"✅ Бонусы реферальной программы обновлены!\n\n{text_out}", parse_mode="HTML", reply_markup=kb_out)
            return

        elif mode == "add_promocode":
            context.user_data["mode"] = None
            parts = [p.strip() for p in text.split("|")]
            if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
                add_promocode_db(parts[0], int(parts[1]), int(parts[2]))
                await msg.reply_text(f"✅ Промокод <code>{html.escape(parts[0].upper())}</code> на +{parts[1]} дн. создан!", parse_mode="HTML")
            else:
                await msg.reply_text("⚠️ Формат: <code>КОД | Дней | Лимит</code>", parse_mode="HTML")
            text_out, kb_out = render_marketing_main_screen()
            await msg.reply_text(text_out, parse_mode="HTML", reply_markup=kb_out)
            return

        elif mode == "add_coupon":
            context.user_data["mode"] = None
            parts = [p.strip() for p in text.split("|")]
            if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
                pct = max(1, min(95, int(parts[1])))
                add_coupon_db(parts[0], pct, int(parts[2]))
                await msg.reply_text(f"✅ Купон <code>{html.escape(parts[0].upper())}</code> на скидку -{pct}% создан!", parse_mode="HTML")
            else:
                await msg.reply_text("⚠️ Формат: <code>КОД | Скидка% | Лимит</code>", parse_mode="HTML")
            text_out, kb_out = render_marketing_main_screen()
            await msg.reply_text(text_out, parse_mode="HTML", reply_markup=kb_out)
            return

        elif mode == "search_user":
            context.user_data["mode"] = None
            found_id = find_user_by_query(text)
            if not found_id:
                text_out, kb_out = render_users_admin_screen()
                await msg.reply_text(f"⚠️ Пользователь по запросу <code>{html.escape(text)}</code> не найден.\n\n{text_out}", parse_mode="HTML", reply_markup=kb_out)
            else:
                text_out, kb_out = render_single_user_dossier(found_id)
                await msg.reply_text(text_out, parse_mode="HTML", reply_markup=kb_out)
            return

        elif mode == "direct_msg_user":
            context.user_data["mode"] = None
            target_id = context.user_data.get("target_user_id", 0)
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=f"✉️ <b>Сообщение от Администратора:</b>\n\n{html.escape(text)}",
                    parse_mode="HTML"
                )
                await msg.reply_text(f"✅ Сообщение доставлено пользователю <code>{target_id}</code>!", parse_mode="HTML")
            except Forbidden:
                mark_user_blocked_bot(target_id, 1)
                await msg.reply_text(f"⚠️ Пользователь <code>{target_id}</code> заблокировал бота.", parse_mode="HTML")
            except Exception as e:
                await msg.reply_text(f"❌ Ошибка отправки: {e}")
            text_out, kb_out = render_single_user_dossier(target_id)
            await msg.reply_text(text_out, parse_mode="HTML", reply_markup=kb_out)
            return

        elif mode == "set_pay_secret":
            context.user_data["mode"] = None
            p_key = context.user_data.get("target_pay_key", "yookassa")
            if p_key == "yookassa" and "|" in text:
                sh_id, sec_k = [x.strip() for x in text.split("|", 1)]
                set_setting("pay_yookassa_shop_id", sh_id)
                set_setting("pay_yookassa_secret", sec_k)
            else:
                if p_key == "yookassa" and text.strip().isdigit():
                    set_setting("pay_yookassa_shop_id", text.strip())
                set_setting(f"pay_{p_key}_secret", text.strip())
            set_setting(f"pay_{p_key}_enabled", "1")
            text_out, kb_out = render_payment_settings_screen()
            await msg.reply_text(f"✅ Настройки для <b>{html.escape(p_key)}</b> сохранены!\n\n{text_out}", parse_mode="HTML", reply_markup=kb_out)
            return
        elif mode and mode.startswith("tedit_"):
            context.user_data["mode"] = None
            _, action, t_id_str = mode.split("_", 2)
            t_id = int(t_id_str)
            val = text.strip()
            
            if action == "price":
                if val.isdigit():
                    update_tariff_field(t_id, "price_rub", int(val))
                    await msg.reply_text("✅ Цена тарифа успешно обновлена!", parse_mode="HTML")
                else:
                    await msg.reply_text("⚠️ Ошибка: цена должна быть целым числом.", parse_mode="HTML")
            elif action == "days":
                if val.isdigit():
                    update_tariff_field(t_id, "days", int(val))
                    await msg.reply_text("✅ Срок действия тарифа обновлен!", parse_mode="HTML")
                else:
                    await msg.reply_text("⚠️ Ошибка: срок должен быть числом дней.", parse_mode="HTML")
            elif action == "name":
                update_tariff_field(t_id, "name", val)
                await msg.reply_text("✅ Название тарифа успешно изменено!", parse_mode="HTML")
            elif action == "grp":
                update_tariff_field(t_id, "group_name", val)
                await msg.reply_text("✅ Группа тарифа изменена!", parse_mode="HTML")

            t_row = get_tariff_by_id(t_id)
            if t_row:
                _, grp, name, days, pr_rub, pr_stars = t_row
                d_lbl = "Без срока" if days == 0 else f"{days} дн."
                t_text = f"⚙️ <b>Редактирование тарифа #{t_id}</b>\n\n📁 Группа: {html.escape(grp)}\n🏷 Название: {html.escape(name)}\n⏳ Длительность: {d_lbl}\n💰 Цена: {pr_rub} ₽ ({pr_stars} ⭐️)\n\nВыберите параметр для изменения:"
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 Изменить цену (₽)", callback_data=f"admin_tedit_param_price_{t_id}"),
                     InlineKeyboardButton("⏳ Изменить срок", callback_data=f"admin_tedit_param_days_{t_id}")],
                    [InlineKeyboardButton("🏷 Переименовать", callback_data=f"admin_tedit_param_name_{t_id}"),
                     InlineKeyboardButton("📁 Сменить группу", callback_data=f"admin_tedit_param_grp_{t_id}")],
                    [InlineKeyboardButton("🗑 Удалить тариф", callback_data=f"admin_tariff_del_{t_id}")],
                    [InlineKeyboardButton("⬅️ К списку тарифов", callback_data="admin_tariffs_list")]
                ])
                await msg.reply_text(t_text, parse_mode="HTML", reply_markup=kb)
            return



        elif mode == "add_tariff":
            context.user_data["mode"] = None
            parts = [p.strip() for p in text.split("|")]
            if len(parts) >= 4 and parts[2].isdigit() and parts[3].isdigit():
                add_new_tariff(parts[0], parts[1], int(parts[2]), int(parts[3]))
                await msg.reply_text("✅ Новый тариф успешно добавлен в витрину!", parse_mode="HTML")
            else:
                await msg.reply_text("⚠️ Неверный формат. Используйте: <code>Группа | Название | Дней | Цена</code>", parse_mode="HTML")
            text_out, kb_out = render_payment_settings_screen()
            await msg.reply_text(text_out, parse_mode="HTML", reply_markup=kb_out)
            return

        elif mode == "edit_currency":
            context.user_data["mode"] = None
            if "|" in text:
                u_r, s_r = [x.strip() for x in text.split("|", 1)]
                set_setting("currency_usdt_rate", u_r)
                set_setting("currency_stars_rate", s_r)
            else:
                set_setting("currency_usdt_rate", text.strip())
            text_out, kb_out = render_payment_settings_screen()
            await msg.reply_text(f"✅ Курсы валют обновлены!\n\n{text_out}", parse_mode="HTML", reply_markup=kb_out)
            return

        elif mode == "edit_trial_days":
            context.user_data["mode"] = None
            if text.strip().isdigit():
                set_setting("trial_days", text.strip())
            text_out, kb_out = render_payment_settings_screen()
            await msg.reply_text(f"✅ Длительность пробной подписки обновлена!\n\n{text_out}", parse_mode="HTML", reply_markup=kb_out)
            return

        elif mode == "add_server":
            context.user_data["mode"] = None
            parts = [p.strip() for p in text.split("|")]
            name_p = parts[0] if len(parts) > 0 else "🇩🇪 Сервер"
            host_p = parts[1] if len(parts) > 1 else "127.0.0.1:443"
            url_p = parts[2] if len(parts) > 2 else ""
            user_p = parts[3] if len(parts) > 3 else ""
            pass_p = parts[4] if len(parts) > 4 else ""
            inb_p = int(parts[5]) if (len(parts) > 5 and parts[5].isdigit()) else 1
            sub_p = parts[6] if len(parts) > 6 else ""

            srv_id = add_full_server(name_p, host_p, "both", url_p, user_p, pass_p, inb_p, sub_p, "")
            text_out, kb_out = await render_servers_monitor_screen()
            await msg.reply_text(
                f"✅ <b>Сервер #{srv_id} ({html.escape(name_p)}) успешно подключен к единой подписке!</b>\n\n{text_out}",
                parse_mode="HTML",
                reply_markup=kb_out
            )
            return

        elif mode == "set_proxy_tpl":
            context.user_data["mode"] = None
            srv_id = context.user_data.get("target_server_id", 0)
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("UPDATE servers SET proxy_template = ? WHERE id = ?", (text.strip(), srv_id))
                conn.commit()
            await msg.reply_text(f"✅ Шаблон Web Panel Proxy 2.7.0 сохранен для сервера #{srv_id}!", reply_markup=admin_dashboard_keyboard())
            return

        elif mode == "set_subdom":
            context.user_data["mode"] = None
            set_setting("sub_domain_prefix", text.strip())
            text_out, kb_out = render_bot_settings_main_screen()
            await msg.reply_text(f"✅ Глобальный URL единой подписки сохранен:\n<code>{html.escape(text.strip())}</code>\n\n{text_out}", parse_mode="HTML", reply_markup=kb_out)
            return

        elif mode == "add_vpn_pool":
            context.user_data["mode"] = None
            target_srv = context.user_data.get("target_server_id", 0)
            added = add_vpn_configs_to_pool(text, target_srv)
            await msg.reply_text(f"✅ Успешно загружено <b>{added}</b> конфигов!", parse_mode="HTML", reply_markup=admin_dashboard_keyboard())
            return

        elif mode == "set_channel":
            context.user_data["mode"] = None
            url = text.strip()
            if not url.startswith("http"):
                url = "https://t.me/" + url.lstrip("@")
            set_setting("channel_url", url)
            await msg.reply_text(f"✅ Ссылка сохранена:\n<code>{html.escape(url)}</code>", parse_mode="HTML", reply_markup=admin_dashboard_keyboard())
            return

        elif mode == "news_text":
            context.user_data["news_body"] = text
            context.user_data["mode"] = "news_link"
            default_url = get_setting("channel_url", "")
            await msg.reply_text(
                "🔗 <b>Укажите ссылку на новость/пост:</b>\n"
                "• Отправьте прямую ссылку на пост\n"
                f"• Или отправьте <code>+</code>, чтобы использовать <code>{html.escape(default_url or 'не задана')}</code>",
                parse_mode="HTML"
            )
            return

        elif mode == "news_link":
            context.user_data["mode"] = None
            news_body = context.user_data.get("news_body", "")
            link_input = text.strip()
            post_url = get_setting("channel_url", "") if link_input == "+" else (link_input if link_input.startswith("http") else "https://t.me/" + link_input.lstrip("@"))
            reply_kb = InlineKeyboardMarkup([[InlineKeyboardButton("👉 Читать на канале", url=post_url)]]) if (post_url and post_url.startswith("http")) else None

            users = get_all_active_users()
            sent, pinned = 0, 0
            for uid in users:
                try:
                    sent_msg = await context.bot.send_message(
                        chat_id=uid,
                        text=f"🔥 <b>Новость на канале!</b>\n\n{html.escape(news_body)}",
                        parse_mode="HTML",
                        reply_markup=reply_kb,
                        protect_content=True
                    )
                    sent += 1
                    try:
                        await context.bot.pin_chat_message(chat_id=uid, message_id=sent_msg.message_id, disable_notification=False)
                        pinned += 1
                    except Exception:
                        pass
                except Forbidden:
                    mark_user_blocked_bot(uid, 1)
                except Exception:
                    pass

            text_out, kb_out = render_marketing_main_screen()
            await msg.reply_text(
                f"✅ <b>Новость опубликована!</b>\n📬 Доставлено: <code>{sent}</code> | 📌 Закреплено: <code>{pinned}</code>\n\n{text_out}",
                parse_mode="HTML",
                reply_markup=kb_out
            )
            return

        elif mode == "broadcast":
            context.user_data["mode"] = None
            users = get_all_active_users()
            sent = 0
            for uid in users:
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"📢 <b>Объявление:</b>\n\n{html.escape(text)}",
                        parse_mode="HTML",
                        protect_content=True
                    )
                    sent += 1
                except Forbidden:
                    mark_user_blocked_bot(uid, 1)
                except Exception:
                    pass
            text_out, kb_out = render_marketing_main_screen()
            await msg.reply_text(f"✅ Рассылка завершена! Доставлено: {sent} из {len(users)}.\n\n{text_out}", parse_mode="HTML", reply_markup=kb_out)
            return

        elif mode == "toggle_vip" and text.strip().isdigit():
            context.user_data["mode"] = None
            target_id = int(text.strip())
            k_id, until, sub_url, _ = await create_or_extend_user_key(target_id, days=30, create_new=True)
            await msg.reply_text(
                f"✅ Пользователю <code>{target_id}</code> выпущен <b>Ключ #{k_id}</b> до <code>{until}</code>\n"
                f"🔗 <code>{html.escape(sub_url)}</code>",
                parse_mode="HTML",
                reply_markup=admin_dashboard_keyboard()
            )
            return

        elif mode == "toggle_ban" and text.strip().isdigit():
            context.user_data["mode"] = None
            target_id = int(text.strip())
            state = toggle_column(target_id, "is_banned")
            status = "🚫 ЗАБЛОКИРОВАН" if state == 1 else "✅ РАЗБЛОКИРОВАН"
            await msg.reply_text(f"Статус для <code>{target_id}</code>: <b>{status}</b>", parse_mode="HTML", reply_markup=admin_dashboard_keyboard())
            return

    # 3. Заявки от клиентов
    if mode == "order_vpn_input":
        context.user_data["mode"] = None
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Выдать ключ (30 дн.) в 1 клик", callback_data=f"quick_vpn_{user.id}")]])
        await notify_admin_event(user, "notify_orders", "🛒 ЗАЯВКА НА ПОДПИСКУ VPN", text, context, reply_markup=kb)
        await msg.reply_text(
            "✅ <b>Заявка принята!</b>\nАдминистратор скоро активирует вам ключ в разделе «🔑 Мои ключи».",
            parse_mode="HTML",
            reply_markup=main_keyboard(user.id)
        )
        return

    if mode == "order_bot_input":
        context.user_data["mode"] = None
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🤖 Создать ключ лицензии БОТА (365д)", callback_data="admin_gen_BOT_365")]])
        await notify_admin_event(user, "notify_orders", "🤖 ЗАЯВКА НА ПОКУПКУ БОТА", text, context, reply_markup=kb)
        await msg.reply_text(
            "✅ <b>Заявка на покупку/аренду бота отправлена!</b>\nМы свяжемся с вами в этом чате.",
            parse_mode="HTML",
            reply_markup=main_keyboard(user.id)
        )
        return

    if mode == "activate_key":
        context.user_data["mode"] = None
        sub_ok, ch_link = await verify_user_subscribed_to_channel(user.id, context)
        if not sub_ok:
            kb_sub = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Подписаться на наш канал", url=ch_link)]])
            await msg.reply_text(
                "📢 <b>Для активации промокодов и ключей необходимо быть подписчиком нашего канала!</b>\nПодпишитесь по кнопке ниже и повторите ввод:",
                parse_mode="HTML",
                reply_markup=kb_sub
            )
            return
        ok, result_msg = await redeem_code_universal(user.id, text)
        if not ok and result_msg == "BANNED":
            await notify_admin_event(user, "notify_security", "🚨 АВТО-БАН (5 попыток подбора кода)", f"Последний ввод: {text}", context)
            await msg.reply_text("⛔ Вы заблокированы за попытку перебора кодов.")
            return
        status_title = "🎟 УСПЕШНАЯ АКТИВАЦИЯ КОДА/ПРОМО" if ok else "🎟 Неудачный ввод кода/промо"
        await notify_admin_event(user, "notify_keys", status_title, text, context)
        await msg.reply_text(result_msg, parse_mode="HTML", reply_markup=main_keyboard(user.id), protect_content=True)
        return

    if mode == "support":
        context.user_data["mode"] = None
        await notify_admin_event(user, "notify_support", "🆘 ТИКЕТ В ПОДДЕРЖКУ", text, context)
        await msg.reply_text("✅ Ваше сообщение передано в поддержку! Ожидайте ответа в этом чате.", reply_markup=main_keyboard(user.id))
        return

    # 4. Логирование меню vs свободного текста
    if text in MENU_BUTTONS:
        await notify_admin_event(user, "notify_menu", "🔘 Нажатие кнопки меню", text, context)
    else:
        await notify_admin_event(user, "notify_text", "💬 Свободный текст в чате", text, context)

    # 5. Разделы главного меню
    if text == "🔑 Мои ключи":
        text_out, kb_out = await render_my_keys_screen(user.id)
        await msg.reply_text(text_out, parse_mode="HTML", reply_markup=kb_out)
        return

    if text == "🔗 Реферальная программа":
        info = get_user_info(user.id)
        ref_cnt = info[17] if (info and len(info) > 17) else 0
        ref_days = info[18] if (info and len(info) > 18) else 0
        b_inv = get_setting("ref_bonus_days", "7")
        b_new = get_setting("ref_NewUser_days", "3")
        bot_uname = BOT_USERNAME_CACHE or (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_uname}?start=ref_{user.id}"

        await msg.reply_text(
            f"🔗 <b>Партнерская (реферальная) программа</b>\n\n"
            f"Приглашайте друзей по вашей персональной ссылке и получайте бесплатные дни подписки:\n"
            f"• Вам за каждого друга: <b>+{html.escape(b_inv)} дн.</b>\n"
            f"• Вашему другу при старте: <b>+{html.escape(b_new)} дн.</b>\n\n"
            f"🔗 <b>Ваша реферальная ссылка (нажмите для копирования):</b>\n"
            f"<code>{ref_link}</code>\n\n"
            f"📊 <b>Ваша статистика:</b>\n"
            f"👥 Приглашено друзей: <b>{ref_cnt} чел.</b>\n"
            f"🎁 Заработано бонусных дней: <b>+{ref_days} дн.</b>",
            parse_mode="HTML"
        )
        return

    if text == "🎁 Пробная подписка":
        sub_ok, ch_link = await verify_user_subscribed_to_channel(user.id, context)
        if not sub_ok:
            kb_sub = InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Подписаться на канал", url=ch_link)],
                [InlineKeyboardButton("✅ Я подписался (Проверить)", callback_data="client_activate_trial_btn")]
            ])
            await msg.reply_text(
                "📢 <b>Для получения бесплатной пробной подписки подпишитесь на наш официальный канал:</b>",
                parse_mode="HTML",
                reply_markup=kb_sub
            )
            return
        if get_setting("trial_enabled", "1") != "1":
            await msg.reply_text("⚠️ Пробный период временно отключен администратором. Выберите тариф в разделе «🌐 Купить VPN / Подписка».")
            return
        info = get_user_info(user.id)
        trial_used = info[13] if (info and len(info) > 13) else 0
        if trial_used == 1:
            await msg.reply_text(
                "🔒 <b>Вы уже использовали бесплатный пробный период ранее.</b>\n"
                "Ваши существующие ключи находятся в разделе <b>«🔑 Мои ключи»</b>.",
                parse_mode="HTML"
            )
            return
        t_days = int(get_setting("trial_days", "3") or 3)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE users SET trial_used = 1 WHERE user_id = ?", (user.id,))
            conn.commit()
        k_id, until, sub_url, _ = await create_or_extend_user_key(user.id, days=t_days, create_new=True)
        await notify_admin_event(user, "notify_keys", f"🎁 Активация пробного Ключа #{k_id} ({t_days} дн.)", f"До {until}", context)
        text_out, kb_out = await render_my_keys_screen(user.id)
        await msg.reply_text(
            f"🎁 <b>Пробный Ключ #{k_id} активирован на {t_days} дн.!</b>\n\n{text_out}",
            parse_mode="HTML",
            reply_markup=kb_out
        )
        return

    if text in ("🌐 Купить VPN / Подписка", "🌐 Мой VPN / Подписка", "🌐 Мой VPN / Купить VPN"):
        info = get_user_info(user.id)
        disc_pct = info[19] if (info and len(info) > 19) else 0
        disc_line = f"\n🎫 <b>Активна ваша скидка по купону: -{disc_pct}%!</b>\n" if disc_pct > 0 else ""

        tariffs = [t for t in get_active_tariffs() if "Бота" not in t[1]]
        kb_rows = []
        for t_id, grp, name, days, pr_rub, pr_stars in tariffs:
            final_rub = max(1, int(pr_rub * (100 - disc_pct) / 100)) if disc_pct > 0 else pr_rub
            price_str = f"{final_rub} ₽ (-{disc_pct}%)" if disc_pct > 0 else f"{pr_rub} ₽"
            kb_rows.append([InlineKeyboardButton(f"{name} — {price_str}", callback_data=f"buy_tariff_{t_id}")])
        kb_rows.append([InlineKeyboardButton("🔑 Мои ключи", callback_data="client_my_keys")])
        await msg.reply_text(
            f"🌐 <b>Единая подписка Bot_VIP (3x-ui + Web Panel Proxy 2.7.0)</b>{disc_line}\n\n"
            f"✅ Безлимитный трафик и высокая скорость\n"
            f"✅ Возможность иметь несколько ключей для разных устройств в разделе <b>«🔑 Мои ключи»</b>\n\n"
            f"Выберите подходящий тариф для покупки нового ключа:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb_rows)
        )
        return

    elif text == "🤖 Купить такого бота":
        info = get_user_info(user.id)
        bot_lic = info[9] if (info and info[9]) else ""
        lic_line = f"\n🔐 <b>Ваша активная лицензия:</b> <code>{html.escape(bot_lic)}</code>\n" if bot_lic else ""
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📋 Тарифы и покупка Бота", callback_data="order_bot")]])
        await msg.reply_text(
            "🤖 <b>Продажа и аренда защищенного бота (Bot_VIP)</b>\n"
            f"{lic_line}\n"
            "• Мульти-ключевая система «🔑 Мои ключи» с QR-кодами и подсчетом трафика\n"
            "• Встроенный сервер единой подписки Sub-Aggregator (:2097)\n"
            "• Обновление кода с GitHub прямо из панели бота в 1 клик\n"
            "• Встроенные платежные шлюзы: ЮKassa, Telegram Stars, CryptoPay, WATA, Platega, Cardlink\n"
            "• Аппаратная защита лицензии (HWID Lock) и защита ядра\n\n"
            "Нажмите кнопку ниже для выбора тарифа:",
            parse_mode="HTML",
            reply_markup=kb
        )

    elif text == "👤 Профиль":
        info = get_user_info(user.id)
        joined = info[3] if info else "только что"
        is_vip = info[4] if info else 0
        bot_lic = info[9] if (info and info[9]) else "Нет"
        ref_cnt = info[17] if (info and len(info) > 17) else 0
        disc_pct = info[19] if (info and len(info) > 19) else 0
        keys_cnt = len(get_user_keys_list(user.id))
        role = "Администратор 👑" if user.id == ADMIN_ID else ("Активный клиент ⭐" if is_vip else "Пользователь")
        kb_rows = [[InlineKeyboardButton("🔑 Открыть мои ключи", callback_data="client_my_keys")]]
        webapp_url = get_setting("webapp_url", "")
        if webapp_url and webapp_url.startswith("https://"):
            kb_rows.append([InlineKeyboardButton("🌐 Открыть Mini App кабинет", web_app=WebAppInfo(url=webapp_url))])
        await msg.reply_text(
            f"👤 <b>Ваш профиль:</b>\n\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"🏷 Имя: {html.escape(user.first_name)}\n"
            f"🛡 Статус: {role}\n"
            f"🔑 Активных ключей: <b>{keys_cnt} шт.</b>\n"
            f"🔗 Приглашено друзей: <b>{ref_cnt} чел.</b>\n"
            f"🎫 Активная скидка: <b>{disc_pct}%</b>\n"
            f"🤖 Лицензия бота: <code>{html.escape(bot_lic)}</code>\n"
            f"📅 Регистрация: {joined}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb_rows)
        )

    elif text in ("🎟 Промокод / Купон", "🎟 Активировать промокод", "🔑 Активировать ключ"):
        context.user_data["mode"] = "activate_key"
        await msg.reply_text(
            "🎟 <b>Активация промокода, скидочного купона или ключа</b>\n\n"
            "Отправьте ваш код (например: промокод на дни, купон на скидку или ключ <code>VPN-30D-XXXX</code>):",
            parse_mode="HTML"
        )

    elif text == "📢 Наш канал":
        ch_url = get_setting("channel_url", "")
        if ch_url:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("👉 Перейти на канал", url=ch_url)]])
            await msg.reply_text("📢 Подписывайтесь на наш официальный канал:", reply_markup=kb)
        else:
            await msg.reply_text("📢 Ссылка на официальный канал скоро появится!")

    elif text == "⭐ VIP-раздел":
        info = get_user_info(user.id)
        is_vip = info[4] if info else 0
        vip_until = info[6] if (info and info[6]) else "Без срока"
        if is_vip == 1 or user.id == ADMIN_ID:
            await msg.reply_text(
                f"🌟 <b>Закрытый VIP-раздел</b>\n\n"
                f"Ваш доступ активен (до <code>{vip_until}</code>).\n"
                f"🔒 Пересылка и копирование материалов заблокированы.",
                parse_mode="HTML",
                protect_content=True
            )
        else:
            await msg.reply_text("🔒 <b>Доступ закрыт.</b>\nПриобретите ключ в разделе «🌐 Купить VPN / Подписка».", parse_mode="HTML")

    elif text == "ℹ️ О боте":
        custom_about = get_setting(
            "text_about",
            "🤖 <b>Bot_VIP</b> — единая система подключения 3x-ui + Web Panel Proxy 2.7.0 и продажи защищенных Telegram-ботов."
        )
        await msg.reply_text(custom_about, parse_mode="HTML")

    elif text == "🆘 Поддержка":
        context.user_data["mode"] = "support"
        custom_sup = get_setting("text_support", "✉️ <b>Напишите ваш вопрос одним сообщением:</b>")
        await msg.reply_text(custom_sup, parse_mode="HTML")

    elif text in ("⚙️ Админ-панель", "🛠 Админ-панель") and user.id == ADMIN_ID:
        await admin_cmd(update, context)

    else:
        await msg.reply_text("Выберите нужный раздел в меню ниже:", reply_markup=main_keyboard(user.id))



# ==============================================================================
# 🚀 ЕДИНЫЙ МОДУЛЬ: ГЛАВНОЕ МЕНЮ, РЕФЕРАЛКА, КЛЮЧИ КЛИЕНТА, ДОСЬЕ И МАСТЕР 3X-UI
# ==============================================================================
import os
from datetime import datetime, timedelta
from telegram import BotCommand, MenuButtonCommands, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

def is_any_admin_ckm(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = 'extra_admins'").fetchone()
            if row and str(user_id) in [x.strip() for x in row[0].split(",") if x.strip()]:
                return True
    except Exception:
        pass
    return False

CMS_SECTIONS = {
    "main": ("📝 Главная страница", "cms_main_text", "cms_main_media"),
    "help": ("📝 Справка (текст)", "cms_help_text", "cms_help_media"),
    "ref": ("👥 Реферальная программа", "cms_ref_text", "cms_ref_media"),
    "prepay": ("📝 Текст перед оплатой", "cms_prepay_text", "cms_prepay_media"),
    "keyout": ("📝 Текст выдачи ключа", "cms_keyout_text", "cms_keyout_media"),
    "news": ("📢 Ссылка: Новости", "cms_news_url", ""),
    "support": ("💬 Ссылка: Поддержка", "cms_support_url", ""),
}

def build_tariffs_block() -> str:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("SELECT name, days, price_rub FROM tariffs WHERE is_active = 1 ORDER BY id ASC").fetchall()
        if rows:
            lines = ["📋 <b>Тарифы:</b>"]
            for name, days, rub in rows:
                clean_name = name if name.startswith("📱") else f"📱 {name}"
                lines.append(f"• {clean_name} — <b>{rub} ₽</b>")
            return "\n".join(lines)
    except Exception:
        pass
    return (
        "📋 <b>Тарифы:</b>\n"
        "• 📱 30 Дней 1 Устр. — <b>200 ₽</b>\n"
        "• 📱 60 Дней 1 Устр. — <b>350 ₽</b>\n"
        "• 📱 90 Дней 1 Устр. — <b>500 ₽</b>\n"
        "• 📱 180 Дней 1 Устр. — <b>999 ₽</b>\n"
        "• 📱 365 Дней 1 Устр. — <b>1799 ₽</b>\n"
        "• 📱 Акция 30дней 2Устроиства — <b>150 ₽</b>\n"
        "• 📱 Акция 60дней 2Устроиства — <b>250 ₽</b>"
    )

def build_custom_start_content(user_id: int):
    raw_tpl = get_setting("cms_main_text", "")
    if not raw_tpl:
        raw_tpl = (
            "🔐 <b>Добро пожаловать в VPN-бот!</b>\n\n"
            "Быстрый, безопасный и анонимный доступ к интернету.\n"
            "Без логов, без ограничений, без проблем! 🚀\n\n"
            "%тарифы%\n\n"
            "✍️ <a href='https://telegra.ph/Polzovatelskoe-soglashenie-01-01'>ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ</a> ✍️\n\n"
            "✍️ <a href='https://telegra.ph/Politika-konfidencialnosti-01-01'>ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ</a> ✍️"
        )
    caption = raw_tpl.replace("%тарифы%", build_tariffs_block())

    rows = [
        [
            InlineKeyboardButton("🔑 Мои ключи", callback_data="client_my_keys"),
            InlineKeyboardButton("💳 Купить ключ", callback_data="order_vpn")
        ],
        [
            InlineKeyboardButton("🎁 Пробная подписка", callback_data="claim_trial")
        ],
        [
            InlineKeyboardButton("🔗 Реферальная ссылка", callback_data="start_ref_link"),
            InlineKeyboardButton("❓ Справка", callback_data="start_help_box")
        ]
    ]
    if is_any_admin_ckm(user_id):
        rows.append([InlineKeyboardButton("⚙️ Админ-панель", callback_data="start_open_admin")])

    return caption, InlineKeyboardMarkup(rows)

async def send_or_replace_main_menu(bot, chat_id: int, user_id: int, old_message=None):
    caption, kb = build_custom_start_content(user_id)
    banner_file_id = get_setting("cms_main_media", "") or get_setting("welcome_banner_id", "")
    banner_path = "/opt/Bot_VIP/welcome.jpg"

    if old_message:
        try:
            await old_message.delete()
        except Exception:
            pass

    try:
        if banner_file_id:
            await bot.send_photo(chat_id=chat_id, photo=banner_file_id, caption=caption, parse_mode="HTML", reply_markup=kb)
            return
        elif os.path.exists(banner_path):
            with open(banner_path, "rb") as ph:
                await bot.send_photo(chat_id=chat_id, photo=ph, caption=caption, parse_mode="HTML", reply_markup=kb)
                return
    except Exception:
        pass

    await bot.send_message(chat_id=chat_id, text=caption, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)

# ------------------------------------------------------------------------------
# 🔑 ЭКРАН КЛЮЧЕЙ КЛИЕНТА (ТОЧНО КАК НА СКРИНШОТЕ #9)
# ------------------------------------------------------------------------------
def render_client_keys_list_screen(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, key_name, location_name, expires_at, is_active FROM user_keys WHERE user_id = ? ORDER BY id DESC",
            (user_id,)
        ).fetchall()

    if not rows:
        txt = (
            "🔑 <b>Мои ключи</b>\n\n"
            "У вас пока нет активных VPN-ключей.\n"
            "Нажмите <b>«💳 Купить ключ»</b> или активируйте <b>«🎁 Пробную подписку»</b>!"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Купить ключ", callback_data="order_vpn")],
            [InlineKeyboardButton("🎁 Пробная подписка", callback_data="claim_trial")],
            [InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")]
        ])
        return txt, kb

    txt = f"🔑 <b>Мои ключи ({len(rows)} шт.)</b>\n\nВыберите ключ для управления и просмотра подписки:"
    kb_rows = []
    now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for kid, kname, loc, exp, act in rows:
        is_ok = act == 1 and (not exp or exp == "Без срока" or exp > now_s)
        st = "🟢" if is_ok else "🔴"
        title = kname or f"Ключ #{kid}"
        exp_s = "Без срока" if (not exp or exp == "Без срока") else exp[:10]
        kb_rows.append([InlineKeyboardButton(f"{st} {title} | {loc or '🇩🇪 Германия'} (до {exp_s})", callback_data=f"ckey_view_{kid}")])

    kb_rows.append([InlineKeyboardButton("➕ Купить еще ключ", callback_data="order_vpn")])
    kb_rows.append([InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")])
    return txt, InlineKeyboardMarkup(kb_rows)

def render_client_single_key_screen(kid: int, user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, key_name, location_name, COALESCE(traffic_bytes, 0), COALESCE(limit_gb, 0), COALESCE(limit_ip, 1), expires_at, is_active, COALESCE(group_name, 'Индивидуальный тариф'), COALESCE(history_log, '') FROM user_keys WHERE id = ? AND user_id = ?",
            (kid, user_id)
        ).fetchone()

    if not row:
        return "❌ Ключ не найден.", InlineKeyboardMarkup([[InlineKeyboardButton("🔑 Мои ключи", callback_data="client_my_keys")]])

    kid, kname, loc, t_bytes, lgb, lip, exp, act, grp, h_log = row
    now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    is_ok = act == 1 and (not exp or exp == "Без срока" or exp > now_s)
    st_icon = "🟢" if is_ok else "🔴"

    used_gb = float(t_bytes or 0) / (1024 ** 3)
    gb_str = f"{used_gb:.2f} GB (безлимит)" if not lgb or lgb <= 0 else f"{used_gb:.2f} / {lgb} GB"
    exp_str = "Без срока" if not exp or exp == "Без срока" else exp
    k_title = html.escape(kname or f"Ключ #{kid}")
    tariff_title = "Индивидуальный тариф" if grp in ("Основная", "", None) else html.escape(grp)

    if not h_log:
        today_d = datetime.now().strftime("%Y-%m-%d")
        h_log = f"• {today_d}: Переоформление на произвольный тариф"

    text = (
        f"🔑 <b>{k_title}</b>\n\n"
        f"<b>Статус:</b> {st_icon}\n"
        f"<b>Сервер:</b> {html.escape(loc or '🇩🇪 Германия')}\n"
        f"<b>Тариф:</b> {tariff_title}\n"
        f"<b>Устройств:</b> {lip}\n"
        f"<b>Трафик:</b> {gb_str}\n"
        f"<b>Действует до:</b> {exp_str}\n\n"
        f"📜 <b>История операций:</b>\n"
        f"{h_log}"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Показать подписку", callback_data=f"ckey_sub_{kid}"),
            InlineKeyboardButton("📈 Продлить", callback_data="order_vpn")
        ],
        [
            InlineKeyboardButton("🔄 Заменить", callback_data=f"key_loc_{kid}"),
            InlineKeyboardButton("✏️ Переименовать", callback_data=f"key_ren_{kid}")
        ],
        [
            InlineKeyboardButton("📱 Мои устройства", callback_data=f"ckey_devs_{kid}")
        ],
        [
            InlineKeyboardButton("🔑 Мои ключи", callback_data="client_my_keys"),
            InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")
        ]
    ])
    return text, kb

# ------------------------------------------------------------------------------
# 👤 ДОСЬЕ ПОЛЬЗОВАТЕЛЯ В АДМИНКЕ И ПОШАГОВЫЙ МАСТЕР КЛЮЧЕЙ
# ------------------------------------------------------------------------------
def render_single_user_dossier(target_id: int) -> tuple[str, InlineKeyboardMarkup]:
    info = get_user_info(target_id)
    if not info:
        return "Пользователь не найден в БД.", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="admin_users_menu")]])

    uid, uname, fname, joined, is_vip, is_ban, until, attempts, vpn_cfg, bot_lic, srv_id, sub_id, c_uuid, trial_u, has_exp, bot_blk, ref_by, ref_cnt, ref_days, disc_pct = info

    with sqlite3.connect(DB_PATH) as conn:
        u_extra = conn.execute("SELECT COALESCE(balance, 0), COALESCE(ref_coeff, 1.0) FROM users WHERE user_id = ?", (uid,)).fetchone()
        balance, ref_coeff = (int(u_extra[0]), float(u_extra[1])) if u_extra else (0, 1.0)

        pay_row = conn.execute("SELECT COUNT(*), MAX(created_at) FROM payments WHERE user_id = ?", (uid,)).fetchone()
        p_cnt = pay_row[0] if pay_row and pay_row[0] else 0
        p_last = pay_row[1] if pay_row and pay_row[1] else "нет"

        key_rows = conn.execute(
            "SELECT id, expires_at, is_active FROM user_keys WHERE user_id = ? ORDER BY id DESC",
            (uid,)
        ).fetchall()

    uname_str = f"@{html.escape(uname)}" if uname else "<i>_не указан_</i>"
    deliv_str = "<b>недоступен (блок)</b>" if bot_blk else "<b>доступен для сообщений</b>"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    keys_lines = []
    for kid, kexp, kact in key_rows:
        is_ok = kact == 1 and (not kexp or kexp == "Без срока" or kexp > now_str)
        icon = "🟢" if is_ok else "🔴"
        exp_disp = "без срока" if (not kexp or kexp == "Без срока") else kexp
        keys_lines.append(f"  {icon} Ключ #{kid} (до {exp_disp})")

    keys_block = "\n".join(keys_lines) if keys_lines else "  <i>Нет ключей</i>"

    text = (
        f"👤 Username: {uname_str}\n"
        f"📱 Telegram ID: <code>{uid}</code>\n"
        f"📨 Статус доставки: {deliv_str}\n"
        f"📧 E-mail в панели: <code>user_{uid}_</code>\n"
        f"📅 Зарегистрирован: {joined}\n"
        f"💰 Баланс: <b>{balance} ₽</b>\n"
        f"📊 Реферальный коэффициент: <b>{ref_coeff:.1f}x</b>\n\n"
        f"🔑 <b>VPN-ключи ({len(key_rows)}):</b>\n"
        f"{keys_block}\n\n"
        f"💳 <b>Оплаты:</b>\n"
        f"  📊 Всего платежей: {p_cnt}\n"
        f"  📅 Последняя оплата: {p_last}"
    )

    kb_rows = []
    for kid, _, _ in key_rows[:15]:
        kb_rows.append([InlineKeyboardButton(f"🔑 Ключ #{kid}", callback_data=f"ckm_kview_{kid}_{uid}")])

    kb_rows.append([InlineKeyboardButton("➕ Добавить ключ", callback_data=f"ckm_wgrp_{uid}")])
    kb_rows.append([InlineKeyboardButton("💬 Написать", callback_data=f"admin_uact_msg_{uid}")])
    kb_rows.append([
        InlineKeyboardButton(f"💰 Баланс: {balance} ₽", callback_data=f"ckm_balinfo_{uid}"),
        InlineKeyboardButton("➕ Пополнить", callback_data=f"ckm_baladd_{uid}"),
        InlineKeyboardButton("➖ Списать", callback_data=f"ckm_balsub_{uid}")
    ])
    kb_rows.append([InlineKeyboardButton(f"📊 Реферальный коэффициент: {ref_coeff:.1f}x", callback_data=f"ckm_refc_{uid}")])

    ban_txt = "✅ Разблокировать" if is_ban else "🚫 Заблокировать"
    kb_rows.append([InlineKeyboardButton(ban_txt, callback_data=f"admin_uact_ban_{uid}")])
    kb_rows.append([
        InlineKeyboardButton("⬅️ Назад", callback_data="admin_ulist_0"),
        InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")
    ])

    return text, InlineKeyboardMarkup(kb_rows)

def render_ckm_key_detail(kid: int, uid: int):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, COALESCE(group_name, 'Основная'), location_name, limit_gb, COALESCE(limit_ip, 1), expires_at, is_active, sub_id, config_text FROM user_keys WHERE id = ?",
            (kid,)
        ).fetchone()
    if not row:
        return "❌ Ключ не найден.", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_back_u_{uid}")]])

    kid, grp, loc, lgb, lip, exp, act, sub_id, cfg = row
    st = "🟢 Активен" if act else "🔴 Отключен"
    gb_str = "без лимита" if not lgb or lgb <= 0 else f"{lgb} ГБ"
    exp_str = "без срока" if not exp or exp == "Без срока" else exp

    txt = (
        f"🔑 <b>Управление ключом #{kid}</b> (Клиент: <code>{uid}</code>)\n\n"
        f"📡 Статус: <b>{st}</b>\n"
        f"📁 Группа: <b>{html.escape(grp)}</b>\n"
        f"🖥 Сервер: <b>{html.escape(loc or '🇩🇪 Германия')}</b>\n"
        f"📊 Трафик: <b>{gb_str}</b>\n"
        f"📅 Срок: <b>{exp_str}</b>\n"
        f"💻 Устройств: <b>{lip}</b>"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 Изменить срок (дни)", callback_data=f"ckm_ked_{kid}_{uid}_days"),
            InlineKeyboardButton("📊 Изменить трафик (ГБ)", callback_data=f"ckm_ked_{kid}_{uid}_gb")
        ],
        [
            InlineKeyboardButton("💻 Изменить устр-ва", callback_data=f"ckm_ked_{kid}_{uid}_ip"),
            InlineKeyboardButton("🔄 Вкл / Выкл", callback_data=f"ckm_ktog_{kid}_{uid}")
        ],
        [InlineKeyboardButton("📋 Показать ссылку / конфиг", callback_data=f"ckey_sub_{kid}")],
        [InlineKeyboardButton("🗑 Удалить ключ", callback_data=f"ckm_kdel_{kid}_{uid}")],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_back_u_{uid}"),
            InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")
        ]
    ])
    return txt, kb

async def show_ckm_confirm_screen(message, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    wiz = context.user_data.get("ckm_wiz", {})
    uid = wiz.get("uid", 0)
    grp = wiz.get("group", "Основная")
    srv_name = wiz.get("srv_name", "🇩🇪 Германия")
    gb = wiz.get("gb", 0)
    days = wiz.get("days", 0)
    ips = wiz.get("ips", 1)

    gb_str = "без лимита" if gb == 0 else f"{gb} ГБ"
    days_str = "без срока" if days == 0 else f"{days} дн."

    txt = (
        "✅ <b>Подтверждение создания ключа</b>\n\n"
        f"📁 Группа: {html.escape(grp)}\n"
        f"🖥 Сервер: {html.escape(srv_name)}\n"
        f"📊 Трафик: {gb_str}\n"
        f"📅 Срок: {days_str}\n"
        f"💻 Устройств: {ips}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Создать ключ", callback_data=f"ckm_wcreate_{uid}")],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wstep_ip_{uid}"),
            InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
        ]
    ])
    if edit:
        await message.edit_text(txt, parse_mode="HTML", reply_markup=kb)
    else:
        await message.reply_text(txt, parse_mode="HTML", reply_markup=kb)

# ------------------------------------------------------------------------------
# ✏️ РЕДАКТОР ТЕКСТОВ И МЕДИА (CMS)
# ------------------------------------------------------------------------------
def render_cms_main_menu():
    txt = "✏️ <b>Редактирование текстов</b>\n\nВыберите, что хотите изменить:"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Главная страница", callback_data="cms_edit_main")],
        [InlineKeyboardButton("👥 Реферальная программа", callback_data="cms_edit_ref")],
        [InlineKeyboardButton("📝 Справка (текст)", callback_data="cms_edit_help")],
        [InlineKeyboardButton("📝 Текст перед оплатой", callback_data="cms_edit_prepay")],
        [InlineKeyboardButton("📝 Текст выдачи ключа", callback_data="cms_edit_keyout")],
        [InlineKeyboardButton("📢 Ссылка: Новости", callback_data="cms_edit_news")],
        [InlineKeyboardButton("💬 Ссылка: Поддержка", callback_data="cms_edit_support")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="admin_bot_settings")]
    ])
    return txt, kb

async def send_cms_section_preview(message, sec_key: str):
    title, text_key, media_key = CMS_SECTIONS[sec_key]
    cur_text = get_setting(text_key, "")
    cur_media = get_setting(media_key, "") if media_key else ""

    if not cur_text:
        if sec_key == "main":
            cur_text = (
                "🔐 <b>Добро пожаловать в VPN-бот!</b>\n\n"
                "Быстрый, безопасный и анонимный доступ к интернету.\n"
                "Без логов, без ограничений, без проблем! 🚀\n\n"
                "%тарифы%\n\n"
                "✍️ <a href='https://telegra.ph/Polzovatelskoe-soglashenie-01-01'>ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ</a> ✍️\n\n"
                "✍️ <a href='https://telegra.ph/Politika-konfidencialnosti-01-01'>ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ</a> ✍️"
            )
        else:
            cur_text = f"<i>({title} — отправьте новое сообщение или фото с подписью)</i>"

    kb_rows = [
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="cms_open_menu"),
            InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")
        ]
    ]
    if media_key and cur_media:
        kb_rows.append([InlineKeyboardButton("🗑 Удалить медиа", callback_data=f"cms_delmedia_{sec_key}")])
    kb_rows.append([InlineKeyboardButton("📝 Отправьте новое сообщение ⬇️", callback_data="cms_noop")])
    kb = InlineKeyboardMarkup(kb_rows)

    try:
        if cur_media:
            await message.reply_photo(photo=cur_media, caption=cur_text, parse_mode="HTML", reply_markup=kb)
            return
    except Exception:
        pass
    await message.reply_text(cur_text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)

# ------------------------------------------------------------------------------
# 🎯 ОБРАБОТЧИКИ КОМАНД И КНОПОК
# ------------------------------------------------------------------------------
async def custom_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["mode"] = None
    if "ensure_user" in globals():
        try:
            ensure_user(user.id, user.username or "", user.first_name or "User")
        except Exception:
            pass
    await send_or_replace_main_menu(context.bot, update.effective_chat.id, user.id)
    raise ApplicationHandlerStop

async def cmd_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")]])
    await update.effective_message.reply_text(
        f"🆔 <b>Ваш Telegram ID</b>\n\n<code>{u.id}</code>",
        parse_mode="HTML",
        reply_markup=kb
    )
    raise ApplicationHandlerStop

async def cmd_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    with sqlite3.connect(DB_PATH) as conn:
        srvs = conn.execute("SELECT COUNT(*) FROM servers WHERE is_active = 1").fetchone()[0]
        keys = conn.execute("SELECT COUNT(*) FROM user_keys WHERE user_id = ? AND is_active = 1", (u.id,)).fetchone()[0]
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")]])
    await update.effective_message.reply_text(
        f"🟢 <b>Статус бота: Работает в штатном режиме</b>\n\n"
        f"🖥 Активных серверов: <b>{srvs} шт.</b>\n"
        f"🔑 Ваших активных ключей: <b>{keys} шт.</b>",
        parse_mode="HTML",
        reply_markup=kb
    )
    raise ApplicationHandlerStop

async def cmd_help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")]])
    await update.effective_message.reply_text(
        "ℹ️ <b>Справка по командам бота:</b>\n\n"
        "/start — Показать главное меню\n"
        "/help — Справка по боту\n"
        "/status — Проверить статус бота и ключей\n"
        "/id — Показать ваш Telegram ID",
        parse_mode="HTML",
        reply_markup=kb
    )
    raise ApplicationHandlerStop

async def handle_all_custom_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data

    # 1. Возврат на главную (обрабатываем и start_back_main, и старый back_to_main!)
    if data in ("start_back_main", "back_to_main", "main_menu"):
        await query.answer()
        context.user_data["mode"] = None
        await send_or_replace_main_menu(context.bot, query.message.chat_id, user.id, old_message=query.message)
        raise ApplicationHandlerStop

    # 2. Реферальная программа (как на скриншоте с баннером и статистикой)
    if data in ("start_ref_link", "ref_program", "client_ref"):
        await query.answer()
        bot_me = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_me.username}?start=ref_{user.id}"
        with sqlite3.connect(DB_PATH) as conn:
            u_inf = get_user_info(user.id) if "get_user_info" in globals() else None
            if u_inf and len(u_inf) >= 19:
                r_cnt, r_days = int(u_inf[17] or 0), int(u_inf[18] or 0)
            else:
                row = conn.execute("SELECT COALESCE(ref_count, 0), COALESCE(ref_bonus_days, 0) FROM users WHERE user_id = ?", (user.id,)).fetchone()
                r_cnt, r_days = (row[0], row[1]) if row else (0, 0)

        custom_ref_tpl = get_setting("cms_ref_text", "")
        if custom_ref_tpl:
            caption = (
                custom_ref_tpl
                .replace("%ссылка%", ref_link)
                .replace("%рефералы%", str(r_cnt))
                .replace("%дни%", str(r_days))
            )
        else:
            caption = (
                "👥 <b>ПРИГЛАШАЙ ДРУЗЕЙ В SVOII VPN — ПОЛУЧАЙ ДНИ ПОДПИСКИ!</b> 🎁\n\n"
                "Пользуйся быстрым интернетом бесплатно! Делись ссылкой с друзьями и сразу получай бонусные дни к своей подписке.\n\n"
                "📎 <b>Твоя персональная ссылка:</b>\n"
                f"{ref_link}\n"
                "───────────────────\n"
                "🚀 <b>Как это работает:</b>\n"
                "1️⃣ Отправь ссылку другу.\n"
                "2️⃣ Друг регистрируется и оплачивает подписку.\n"
                "3️⃣ Тебе СРАЗУ начисляются бонусные дни доступа! ⚡️\n\n"
                "Чем больше друзей подключается — тем дольше твой VPN работает абсолютно бесплатно! 🛡\n"
                "───────────────────\n"
                "📊 <b>Твоя статистика:</b>\n\n"
                f"✅ Уровень 1 (10%): {r_cnt} чел. — {r_days} дн."
            )

        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")]])
        ref_media = get_setting("cms_ref_media", "")
        try:
            await query.message.delete()
        except Exception:
            pass
        if ref_media:
            try:
                await context.bot.send_photo(chat_id=user.id, photo=ref_media, caption=caption, parse_mode="HTML", reply_markup=kb)
                raise ApplicationHandlerStop
            except Exception:
                pass
        await context.bot.send_message(chat_id=user.id, text=caption, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
        raise ApplicationHandlerStop

    # 3. Справка
    if data == "start_help_box":
        await query.answer()
        help_txt = get_setting("cms_help_text", "") or (
            "❓ <b>Справка и помощь по подключению</b>\n\n"
            "1️⃣ Нажмите <b>«💳 Купить ключ»</b> или <b>«🎁 Пробная подписка»</b>.\n"
            "2️⃣ Откройте раздел <b>«🔑 Мои ключи»</b> → выберите ваш ключ → нажмите <b>«📋 Показать подписку»</b>.\n"
            "3️⃣ Скопируйте ссылку подписки и вставьте её в приложение <b>Happ</b>, <b>v2rayTun</b>, <b>Hiddify</b> или <b>Streisand</b>."
        )
        help_media = get_setting("cms_help_media", "")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")]])
        try:
            await query.message.delete()
        except Exception:
            pass
        if help_media:
            try:
                await context.bot.send_photo(chat_id=user.id, photo=help_media, caption=help_txt, parse_mode="HTML", reply_markup=kb)
                raise ApplicationHandlerStop
            except Exception:
                pass
        await context.bot.send_message(chat_id=user.id, text=help_txt, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
        raise ApplicationHandlerStop

    # 4. Открытие Админ-панели с главного экрана
    if data == "start_open_admin":
        await query.answer()
        if not is_any_admin_ckm(user.id):
            await query.answer("⛔ Нет прав администратора.", show_alert=True)
            raise ApplicationHandlerStop
        try:
            await query.message.delete()
        except Exception:
            pass
        if "build_admin_dashboard_text" in globals() and "admin_dashboard_keyboard" in globals():
            txt = build_admin_dashboard_text()
            kb = admin_dashboard_keyboard()
            kb_rows = [list(row) for row in kb.inline_keyboard]
            kb_rows.append([InlineKeyboardButton("✏️ Редактирование текстов и баннеров", callback_data="cms_open_menu")])
            kb_rows.append([InlineKeyboardButton("🔐 Лицензии на бота (Продажи)", callback_data="lic_admin_menu")])
            kb_rows.append([InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")])
            await context.bot.send_message(chat_id=user.id, text=txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))
        elif "admin_cmd" in globals():
            await admin_cmd(update, context)
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
                text="⚙️ <b>Панель управления администратора</b>\n\nВыберите нужный раздел:",
                parse_mode="HTML",
                reply_markup=kb
            )
        raise ApplicationHandlerStop

    # 5. Клиентский раздел "🔑 Мои ключи" и карточка ключа (#9 на скриншоте)
    if data == "client_my_keys":
        await query.answer()
        with sqlite3.connect(DB_PATH) as conn:
            k_ids = [r[0] for r in conn.execute("SELECT id FROM user_keys WHERE user_id = ? ORDER BY id ASC", (user.id,)).fetchall()]
        try:
            await query.message.delete()
        except Exception:
            pass
        if len(k_ids) == 1:
            txt, kb = render_client_single_key_screen(k_ids[0], user.id)
        else:
            txt, kb = render_client_keys_list_screen(user.id)
        await context.bot.send_message(chat_id=user.id, text=txt, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    if data.startswith(("ckey_view_", "key_open_", "mykey_", "key_info_", "key_manage_", "view_key_", "u_key_")):
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
        raise ApplicationHandlerStop

    if data.startswith("ckey_sub_"):
        await query.answer()
        kid = int(data.split("_")[-1])
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT user_id, key_name, sub_id FROM user_keys WHERE id = ?", (kid,)).fetchone()
        if not row:
            return
        k_uid, kname, sub_id = row
        sub_prefix = get_setting("sub_domain_prefix", "") or "https://pl.svoii-vpn.online:2097/sub"
        sub_url = f"{sub_prefix.rstrip('/')}/{sub_id}"
        qr_payload = sub_url

        txt = (
            f"📋 <b>Подписка для {html.escape(kname or f'Ключ #{kid}')}</b>\n\n"
            f"🔗 <b>Единая ссылка подписки (нажмите для копирования):</b>\n"
            f"<code>{sub_url}</code>\n\n"
            f"📱 <i>Отсканируйте QR-код выше или вставьте ссылку в приложение (Happ, v2rayTun, Hiddify, Streisand) — все доступные серверы загрузятся автоматически.</i>"
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
        raise ApplicationHandlerStop

    if data.startswith("ckey_devs_"):
        kid = int(data.split("_")[-1])
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT COALESCE(limit_ip, 1) FROM user_keys WHERE id = ?", (kid,)).fetchone()
        lip = row[0] if row else 1
        await query.answer(f"📱 Лимит устройств по этому ключу: {lip} шт.", show_alert=True)
        raise ApplicationHandlerStop

    # 6. Редактор текстов и медиа (CMS)
    if data == "cms_noop":
        await query.answer("Просто отправьте в чат новое фото с подписью или текст!", show_alert=True)
        raise ApplicationHandlerStop

    if data == "cms_open_menu":
        await query.answer()
        if not is_any_admin_ckm(user.id):
            return
        context.user_data["mode"] = None
        txt, kb = render_cms_main_menu()
        try:
            await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await query.message.reply_text(txt, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    if data.startswith("cms_edit_"):
        await query.answer()
        if not is_any_admin_ckm(user.id):
            return
        sec_key = data.split("_", 2)[2]
        if sec_key in CMS_SECTIONS:
            context.user_data["mode"] = f"cms_wait_{sec_key}"
            await send_cms_section_preview(query.message, sec_key)
        raise ApplicationHandlerStop

    if data.startswith("cms_delmedia_"):
        await query.answer()
        if not is_any_admin_ckm(user.id):
            return
        sec_key = data.split("_", 2)[2]
        if sec_key in CMS_SECTIONS:
            _, _, media_key = CMS_SECTIONS[sec_key]
            if media_key:
                set_setting(media_key, "")
            if sec_key == "main":
                set_setting("welcome_banner_id", "")
            context.user_data["mode"] = f"cms_wait_{sec_key}"
            await query.message.reply_text("🗑 Медиафайл удалён!")
            await send_cms_section_preview(query.message, sec_key)
        raise ApplicationHandlerStop


    # 8. Управление лицензиями проданных копий бота
    if data == "lic_admin_menu":
        await query.answer()
        if not is_any_admin_ckm(user.id):
            return
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("SELECT id, lic_key, bound_ip, bound_admin_id, is_active FROM bot_licenses ORDER BY id DESC LIMIT 15").fetchall()
        lines = ["🔐 <b>Управление лицензиями Bot_VIP</b>\n"]
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
        await query.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))
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
            f"✅ <b>Новая лицензия для покупателя готова:</b>\n\n<code>{new_k}</code>\n\n"
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

    # 7. Пошаговый мастер ключей и управление карточкой пользователя (ckm_)
    if data.startswith("ckm_"):
        if not is_any_admin_ckm(user.id):
            await query.answer("⛔ Нет прав администратора.", show_alert=True)
            raise ApplicationHandlerStop
        await query.answer()

        if data.startswith("ckm_back_u_") or data.startswith("ckm_menu_"):
            context.user_data["mode"] = None
            uid = int(data.split("_")[-1])
            txt, kb = render_single_user_dossier(uid)
            await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        # Шаг 1: Выбор группы тарифов
        if data.startswith("ckm_wgrp_"):
            uid = int(data.split("_")[2])
            context.user_data["mode"] = None
            context.user_data["ckm_wiz"] = {"uid": uid}
            with sqlite3.connect(DB_PATH) as conn:
                g_rows = [r[0] for r in conn.execute("SELECT DISTINCT group_name FROM tariffs WHERE group_name != ''").fetchall()]
            groups = ["Основная"]
            for g in g_rows:
                if g not in groups:
                    groups.append(g)
            context.user_data["ckm_groups_list"] = groups
            kb_rows = [[InlineKeyboardButton(f"📁 {g}", callback_data=f"ckm_wselgrp_{uid}_{idx}")] for idx, g in enumerate(groups)]
            kb_rows.append([InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")])
            txt = f"➕ <b>Добавление ключа для ID:</b> <code>{uid}</code>\n\nВыберите группу тарифов:"
            await query.edit_message_text(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))
            raise ApplicationHandlerStop

        # Шаг 2: Выбор сервера
        if data.startswith("ckm_wselgrp_"):
            parts = data.split("_")
            uid, g_idx = int(parts[2]), int(parts[3])
            groups = context.user_data.get("ckm_groups_list", ["Основная"])
            grp_name = groups[g_idx] if g_idx < len(groups) else "Основная"
            wiz = context.user_data.setdefault("ckm_wiz", {"uid": uid})
            wiz["group"] = grp_name

            servers = get_all_servers_full() if "get_all_servers_full" in globals() else []
            kb_rows = []
            if servers:
                for s in servers:
                    kb_rows.append([InlineKeyboardButton(f"🖥 {s[1]}", callback_data=f"ckm_wselsrv_{uid}_{s[0]}")])
            else:
                kb_rows.append([InlineKeyboardButton("🖥 🇩🇪 Германия", callback_data=f"ckm_wselsrv_{uid}_0")])
            kb_rows.append([InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")])
            txt = f"🖥 <b>Группа: {html.escape(grp_name)}</b>\n\nВыберите сервер:"
            await query.edit_message_text(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))
            raise ApplicationHandlerStop

        # Шаг 3: Ввод лимита трафика (ГБ)
        if data.startswith("ckm_wselsrv_") or data.startswith("ckm_wstep_gb_"):
            parts = data.split("_")
            if data.startswith("ckm_wselsrv_"):
                uid, srv_id = int(parts[2]), int(parts[3])
                srv_name = "🇩🇪 Германия"
                if "get_all_servers_full" in globals():
                    for s in get_all_servers_full():
                        if s[0] == srv_id:
                            srv_name = s[1]
                            break
                wiz = context.user_data.setdefault("ckm_wiz", {"uid": uid})
                wiz["srv_id"] = srv_id
                wiz["srv_name"] = srv_name
            else:
                uid = int(parts[3])
                wiz = context.user_data.setdefault("ckm_wiz", {"uid": uid})

            context.user_data["mode"] = "ckm_wiz_gb"
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wgrp_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]])
            await query.edit_message_text("📊 <b>Лимит трафика</b>\n\nВведите лимит в ГБ (0 = без лимита):", parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        # Шаг 4: Срок действия
        if data.startswith("ckm_wstep_days_"):
            uid = int(data.split("_")[3])
            context.user_data["mode"] = "ckm_wiz_days"
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wstep_gb_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]])
            days_prompt = "📅 <b>Срок действия</b>\n\nВведите количество дней (0 = без срока):" if is_pro_version() else "📅 <b>Срок действия (FREE: от 1 до 60 дней)</b>\n\nВведите количество дней (максимум 60):"
            await query.edit_message_text(days_prompt, parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        # Шаг 5: Лимит устройств
        if data.startswith("ckm_wstep_ip_"):
            uid = int(data.split("_")[3])
            context.user_data["mode"] = "ckm_wiz_ip"
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wstep_days_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]])
            ip_prompt = "💻 <b>Лимит устройств</b>\n\nВведите число от 1 до 999:" if is_pro_version() else "💻 <b>Лимит устройств (FREE: 1 или 2)</b>\n\nВведите количество устройств (от 1 до 2):"
            await query.edit_message_text(ip_prompt, parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        # Шаг 6: Создание ключа в БД и на выбранном сервере 3X-UI
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
            await query.edit_message_text(f"✅ <b>Ключ #{k_id} успешно создан!</b>\n\n{txt}", parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if data.startswith("ckm_kview_"):
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
            raise ApplicationHandlerStop

        if data.startswith("ckm_ktog_"):
            _, _, kid_s, uid_s = data.split("_")
            kid, uid = int(kid_s), int(uid_s)
            with sqlite3.connect(DB_PATH) as conn:
                row = conn.execute("SELECT is_active FROM user_keys WHERE id = ?", (kid,)).fetchone()
                if row:
                    conn.execute("UPDATE user_keys SET is_active = ? WHERE id = ?", (0 if row[0] else 1, kid))
                    conn.commit()
            txt, kb = render_ckm_key_detail(kid, uid)
            await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if data.startswith("ckm_kdel_"):
            _, _, kid_s, uid_s = data.split("_")
            kid, uid = int(kid_s), int(uid_s)
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("DELETE FROM user_keys WHERE id = ?", (kid,))
                conn.commit()
            txt, kb = render_single_user_dossier(uid)
            await query.edit_message_text(f"🗑 Ключ #{kid} удалён!\n\n{txt}", parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if data.startswith("ckm_ked_"):
            _, _, kid_s, uid_s, field = data.split("_")
            kid, uid = int(kid_s), int(uid_s)
            context.user_data["mode"] = f"ckm_edit_{field}"
            context.user_data["ckm_kid"] = kid
            context.user_data["ckm_uid"] = uid
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_kview_{kid}_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]])
            prompts = {
                "days": f"📅 <b>Срок действия Ключа #{kid}</b>\n\nВведите количество дней (0 = без срока, можно <code>+10</code> или <code>-5</code>):",
                "gb": f"📊 <b>Лимит трафика Ключа #{kid}</b>\n\nВведите лимит в ГБ (0 = без лимита, можно <code>+20</code> или <code>-10</code>):",
                "ip": f"💻 <b>Лимит устройств Ключа #{kid}</b>\n\nВведите число от 1 до 999 (можно <code>+1</code> или <code>-1</code>):"
            }
            await query.edit_message_text(prompts[field], parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if data.startswith("ckm_balinfo_"):
            await query.answer("Используйте кнопки ➕ Пополнить или ➖ Списать рядом с балансом.", show_alert=True)
            raise ApplicationHandlerStop

        if data.startswith("ckm_baladd_") or data.startswith("ckm_balsub_"):
            uid = int(data.split("_")[2])
            act = "add" if "baladd" in data else "sub"
            context.user_data["mode"] = f"ckm_bal_{act}"
            context.user_data["ckm_uid"] = uid
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")]])
            title = "➕ <b>Пополнение баланса</b>" if act == "add" else "➖ <b>Списание с баланса</b>"
            await query.edit_message_text(f"{title} (ID: <code>{uid}</code>)\n\nВведите сумму в рублях:", parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if data.startswith("ckm_refc_"):
            uid = int(data.split("_")[2])
            context.user_data["mode"] = "ckm_ref_coeff"
            context.user_data["ckm_uid"] = uid
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")]])
            await query.edit_message_text(
                f"📊 <b>Реферальный коэффициент (ID: <code>{uid}</code>)</b>\n\n"
                f"Введите новое значение коэффициента (например: <code>1.0</code>, <code>1.5</code> или <code>2.0</code>):",
                parse_mode="HTML",
                reply_markup=kb
            )
            raise ApplicationHandlerStop

async def handle_all_custom_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    user = update.effective_user
    msg = update.effective_message

    # Перехватываем нажатия на старые нижние кнопки Reply-клавиатуры
    if msg and msg.text and not mode:
        t_clean = msg.text.strip()
        if "Мои ключи" in t_clean:
            with sqlite3.connect(DB_PATH) as conn:
                k_ids = [r[0] for r in conn.execute("SELECT id FROM user_keys WHERE user_id = ? ORDER BY id ASC", (user.id,)).fetchall()]
            if len(k_ids) == 1:
                txt, kb = render_client_single_key_screen(k_ids[0], user.id)
            else:
                txt, kb = render_client_keys_list_screen(user.id)
            await msg.reply_text(txt, parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if "Реферальная программа" in t_clean or "Реферальная ссылка" in t_clean:
            bot_me = await context.bot.get_me()
            ref_link = f"https://t.me/{bot_me.username}?start=ref_{user.id}"
            with sqlite3.connect(DB_PATH) as conn:
                u_inf = get_user_info(user.id) if "get_user_info" in globals() else None
                if u_inf and len(u_inf) >= 19:
                    r_cnt, r_days = int(u_inf[17] or 0), int(u_inf[18] or 0)
                else:
                    row = conn.execute("SELECT COALESCE(ref_count, 0), COALESCE(ref_bonus_days, 0) FROM users WHERE user_id = ?", (user.id,)).fetchone()
                    r_cnt, r_days = (row[0], row[1]) if row else (0, 0)
            caption = (
                "👥 <b>ПРИГЛАШАЙ ДРУЗЕЙ В SVOII VPN — ПОЛУЧАЙ ДНИ ПОДПИСКИ!</b> 🎁\n\n"
                "Пользуйся быстрым интернетом бесплатно! Делись ссылкой с друзьями и сразу получай бонусные дни к своей подписке.\n\n"
                "📎 <b>Твоя персональная ссылка:</b>\n"
                f"{ref_link}\n"
                "───────────────────\n"
                "🚀 <b>Как это работает:</b>\n"
                "1️⃣ Отправь ссылку другу.\n"
                "2️⃣ Друг регистрируется и оплачивает подписку.\n"
                "3️⃣ Тебе СРАЗУ начисляются бонусные дни доступа! ⚡️\n\n"
                "Чем больше друзей подключается — тем дольше твой VPN работает абсолютно бесплатно! 🛡\n"
                "───────────────────\n"
                "📊 <b>Твоя статистика:</b>\n\n"
                f"✅ Уровень 1 (10%): {r_cnt} чел. — {r_days} дн."
            )
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")]])
            ref_media = get_setting("cms_ref_media", "")
            if ref_media:
                try:
                    await msg.reply_photo(photo=ref_media, caption=caption, parse_mode="HTML", reply_markup=kb)
                    raise ApplicationHandlerStop
                except Exception:
                    pass
            await msg.reply_text(caption, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
            raise ApplicationHandlerStop

    # Быстрая установка баннера по подписи /setbanner
    if msg and msg.photo and msg.caption and msg.caption.strip().lower() == "/setbanner" and is_any_admin_ckm(user.id):
        file_id = msg.photo[-1].file_id
        set_setting("cms_main_media", file_id)
        set_setting("welcome_banner_id", file_id)
        await msg.reply_text("✅ Баннер главного меню сохранен! Нажмите /start для проверки.")
        raise ApplicationHandlerStop

    if not mode:
        return

    # Ввод для редактора текстов и медиа (CMS)
    if mode.startswith("cms_wait_") and is_any_admin_ckm(user.id):
        sec_key = mode.split("cms_wait_", 1)[1]
        if sec_key in CMS_SECTIONS:
            title, text_key, media_key = CMS_SECTIONS[sec_key]
            new_text = msg.caption_html if (msg.photo and msg.caption) else (msg.text_html if msg.text else "")
            if msg.photo and media_key:
                fid = msg.photo[-1].file_id
                set_setting(media_key, fid)
                if sec_key == "main":
                    set_setting("welcome_banner_id", fid)
            if new_text:
                set_setting(text_key, new_text)
            await msg.reply_text(f"✅ Раздел <b>{title}</b> успешно обновлён!", parse_mode="HTML")
            await send_cms_section_preview(msg, sec_key)
            raise ApplicationHandlerStop

    # Ввод для пошагового мастера ключей и карточки клиента (ckm_)
    if mode.startswith("ckm_") and is_any_admin_ckm(user.id) and msg.text:
        text = msg.text.strip()
        wiz = context.user_data.setdefault("ckm_wiz", {})
        uid = wiz.get("uid") or context.user_data.get("ckm_uid", user.id)

        if mode == "ckm_wiz_gb":
            if not text.isdigit():
                await msg.reply_text("❌ Введите целое число (0 = без лимита):")
                raise ApplicationHandlerStop
            wiz["gb"] = int(text)
            context.user_data["mode"] = "ckm_wiz_days"
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wstep_gb_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]])
            d_txt = "📅 <b>Срок действия</b>\n\nВведите количество дней (0 = без срока):" if is_pro_version() else "📅 <b>Срок действия (FREE-версия)</b>\n\nВведите количество дней <b>от 1 до 60</b>:"
            await msg.reply_text(d_txt, parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if mode == "ckm_wiz_days":
            if not text.isdigit():
                await msg.reply_text("❌ Введите количество дней числом:")
                raise ApplicationHandlerStop
            d_val = int(text)
            if not is_pro_version() and not (1 <= d_val <= 60):
                kb_up = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💎 Активировать PRO (Безлимит дней)", callback_data="lic_enter_pro")],
                    [InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")]
                ])
                await msg.reply_text(
                    "🔒 <b>Ограничение FREE-версии:</b> срок ключа можно выбрать только <b>от 1 до 60 дней</b> (без вечных ключей).\n\n"
                    "Введите число от 1 до 60 или активируйте PRO-лицензию:",
                    parse_mode="HTML",
                    reply_markup=kb_up
                )
                raise ApplicationHandlerStop
            wiz["days"] = d_val
            context.user_data["mode"] = "ckm_wiz_ip"
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wstep_days_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]])
            ip_txt = "💻 <b>Лимит устройств</b>\n\nВведите число от 1 до 999:" if is_pro_version() else "💻 <b>Лимит устройств (FREE-версия)</b>\n\nВведите количество устройств <b>от 1 до 2</b>:"
            await msg.reply_text(ip_txt, parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if mode == "ckm_wiz_ip":
            if not text.isdigit():
                await msg.reply_text("❌ Введите целое число:")
                raise ApplicationHandlerStop
            ip_val = int(text)
            if not is_pro_version() and not (1 <= ip_val <= 2):
                kb_up = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💎 Активировать PRO (До 999 устройств)", callback_data="lic_enter_pro")],
                    [InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")]
                ])
                await msg.reply_text(
                    "🔒 <b>Ограничение FREE-версии:</b> можно выбрать только <b>1 или 2 устройства</b> на ключ.\n\n"
                    "Введите 1 или 2, либо активируйте PRO-лицензию:",
                    parse_mode="HTML",
                    reply_markup=kb_up
                )
                raise ApplicationHandlerStop
            if is_pro_version() and not (1 <= ip_val <= 999):
                await msg.reply_text("❌ Введите число от 1 до 999:")
                raise ApplicationHandlerStop
            wiz["ips"] = ip_val
            context.user_data["mode"] = None
            await show_ckm_confirm_screen(msg, context, edit=False)
            raise ApplicationHandlerStop

        if mode.startswith("ckm_edit_"):
            field = mode.split("ckm_edit_")[1]
            kid = context.user_data.get("ckm_kid", 0)
            context.user_data["mode"] = None
            now = datetime.now()
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    row = conn.execute("SELECT limit_gb, COALESCE(limit_ip, 1), expires_at FROM user_keys WHERE id = ?", (kid,)).fetchone()
                    if row:
                        cur_gb, cur_ip, cur_exp = row
                        if field == "days":
                            if text == "0":
                                new_exp = "Без срока"
                            elif text.startswith("+") or text.startswith("-"):
                                base_dt = now
                                if cur_exp and cur_exp != "Без срока":
                                    try:
                                        p = datetime.strptime(cur_exp, "%Y-%m-%d %H:%M:%S")
                                        if p > now:
                                            base_dt = p
                                    except Exception:
                                        pass
                                new_exp = max(now, base_dt + timedelta(days=int(text))).strftime("%Y-%m-%d %H:%M:%S")
                            else:
                                new_exp = (now + timedelta(days=int(text))).strftime("%Y-%m-%d %H:%M:%S")
                            conn.execute("UPDATE user_keys SET expires_at = ?, is_active = 1 WHERE id = ?", (new_exp, kid))
                        elif field == "gb":
                            val = max(0, (cur_gb or 0) + int(text)) if (text.startswith("+") or text.startswith("-")) else max(0, int(text))
                            conn.execute("UPDATE user_keys SET limit_gb = ? WHERE id = ?", (val, kid))
                        elif field == "ip":
                            val = max(1, (cur_ip or 1) + int(text)) if (text.startswith("+") or text.startswith("-")) else max(1, int(text))
                            conn.execute("UPDATE user_keys SET limit_ip = ? WHERE id = ?", (val, kid))
                        conn.commit()
            except Exception:
                await msg.reply_text("❌ Некорректное число.")
                raise ApplicationHandlerStop

            txt, kb = render_ckm_key_detail(kid, uid)
            await msg.reply_text(f"✅ Изменения сохранены!\n\n{txt}", parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if mode in ("ckm_bal_add", "ckm_bal_sub"):
            context.user_data["mode"] = None
            try:
                amt = abs(int(text))
                delta = amt if mode == "ckm_bal_add" else -amt
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("UPDATE users SET balance = MAX(0, COALESCE(balance, 0) + ?) WHERE user_id = ?", (delta, uid))
                    conn.commit()
            except Exception:
                await msg.reply_text("❌ Введите сумму целым числом.")
                raise ApplicationHandlerStop
            txt, kb = render_single_user_dossier(uid)
            await msg.reply_text(txt, parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if mode == "ckm_ref_coeff":
            context.user_data["mode"] = None
            try:
                coeff = max(0.1, float(text.replace(",", ".")))
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("UPDATE users SET ref_coeff = ? WHERE user_id = ?", (coeff, uid))
                    conn.commit()
            except Exception:
                await msg.reply_text("❌ Введите число (например 1.5).")
                raise ApplicationHandlerStop
            txt, kb = render_single_user_dossier(uid)
            await msg.reply_text(txt, parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

_orig_run_polling = Application.run_polling
def _patched_run_polling(self, *args, **kwargs):
    self.add_handler(CommandHandler("start", custom_start_command), group=-10)
    self.add_handler(CommandHandler("id", cmd_id_handler), group=-10)
    self.add_handler(CommandHandler("status", cmd_status_handler), group=-10)
    self.add_handler(CommandHandler("help", cmd_help_handler), group=-10)
    self.add_handler(
        CallbackQueryHandler(
            handle_all_custom_callbacks,
            pattern=r"^(lic_|start_|back_to_main|main_menu|ref_program|client_ref|client_my_keys|ckey_|key_open_|mykey_|key_info_|key_manage_|view_key_|u_key_|cms_|ckm_)"
        ),
        group=-10
    )
    self.add_handler(MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.COMMAND, handle_all_custom_messages), group=-10)
    return _orig_run_polling(self, *args, **kwargs)

Application.run_polling = _patched_run_polling



async def render_my_keys_screen(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    with sqlite3.connect(DB_PATH) as conn:
        k_ids = [r[0] for r in conn.execute("SELECT id FROM user_keys WHERE user_id = ? ORDER BY id ASC", (user_id,)).fetchall()]
    if len(k_ids) == 1:
        return render_client_single_key_screen(k_ids[0], user_id)
    return render_client_keys_list_screen(user_id)


if __name__ == "__main__":
    init_db()
    verify_server_lock()
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    if app.job_queue:
        app.job_queue.run_daily(daily_backup_job, time=time(hour=3, minute=0))
        app.job_queue.run_repeating(expire_vips_job, interval=3600, first=60)
        app.job_queue.run_repeating(check_expiry_reminders_job, interval=1800, first=45)
    app.job_queue.run_repeating(poll_pending_invoices_job, interval=5, first=10)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("vip", vip_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app.add_handler(CallbackQueryHandler(callbacks_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    logger.info("Bot_VIP успешно запущен...")
    app.run_polling()