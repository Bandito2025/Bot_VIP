import os
import re
import sqlite3
import base64
import logging
import threading
import subprocess
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger("Bot_VIP")
DB_PATH = "/opt/Bot_VIP/bot_data.db"

def auto_repair_caddy() -> str:
    # Автоматическое открытие портов 80, 443 и 2097 для выпуска SSL Caddy
    try:
        subprocess.run(["ufw", "allow", "80/tcp"], capture_output=True)
        subprocess.run(["ufw", "allow", "443/tcp"], capture_output=True)
        subprocess.run(["ufw", "allow", "2097/tcp"], capture_output=True)
        subprocess.run(["ufw", "reload"], capture_output=True)
    except Exception:
        pass
    """Находит домен сервера в Caddyfile и гарантирует наличие reverse_proxy для /sub/*"""
    caddy_path = "/etc/caddy/Caddyfile"
    if not os.path.exists(caddy_path):
        return None
    try:
        with open(caddy_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Ищем домен узла (nl.svoii-vpn.online, pl.svoii-vpn.online и др.)
        domains = re.findall(r'^\s*([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(?::\d+)?\s*\{', content, re.M)
        domain = None
        for d in domains:
            if not d.startswith("sub."):
                domain = d
                break
        if not domain and domains:
            domain = domains[0]

        # Если маршрут /sub/* отсутствует — встраиваем его
        if "2097" not in content and domain:
            rule = "\n        handle /sub/* {\n                reverse_proxy 127.0.0.1:2097\n        }\n"
            if "handle /wpp-api/*" in content:
                new_content = content.replace("handle /wpp-api/*", rule.strip() + "\n\n        handle /wpp-api/*", 1)
            elif "handle_path" in content:
                pos = content.find("handle_path")
                new_content = content[:pos] + rule.strip() + "\n\n        " + content[pos:]
            else:
                pos = content.find("}")
                new_content = content[:pos] + rule + content[pos:] if pos != -1 else content + rule

            with open(caddy_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            subprocess.run(["systemctl", "reload", "caddy"], capture_output=True)
            logger.info(f"✅ Caddyfile обновлен: /sub/* направлен на 2097 для {domain}")

        return domain
    except Exception as e:
        logger.error(f"Ошибка auto_repair_caddy: {e}")
        return None

def auto_heal_sub_database(db_path: str = DB_PATH):
    """Вычищает порт 2097 из настроек базы данных и переводит домен на чистый https://"""
    if not os.path.exists(db_path):
        return
    try:
        discovered_domain = auto_repair_caddy()
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("SELECT value FROM settings WHERE key='sub_domain_prefix'").fetchone()
            current_val = row[0].strip() if (row and row[0]) else ""

            # Если значение содержит :2097 или ошибочный http://
            clean_val = current_val
            if ":2097" in clean_val:
                clean_val = clean_val.replace(":2097", "")
            if clean_val.startswith("http://") and any(ext in clean_val for ext in [".online", ".ru", ".com", ".net", ".org"]):
                clean_val = "https://" + clean_val[7:]

            if not clean_val or "sub.bot-vip.online" in clean_val:
                if discovered_domain:
                    clean_val = f"https://{discovered_domain}/sub"

            if clean_val and not clean_val.endswith("/sub"):
                clean_val = clean_val.rstrip("/") + "/sub"

            if clean_val != current_val and clean_val:
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('sub_domain_prefix', ?)", (clean_val,))
                conn.commit()
                logger.info(f"✅ Sub URL в базе исправлен: {clean_val}")
    except Exception as e:
        logger.error(f"Ошибка auto_heal_sub_database: {e}")

def get_clean_sub_url(sub_id: str, db_path: str = DB_PATH) -> str:
    """Формирует гарантированно чистый HTTPS URL подписки без порта 2097"""
    prefix = ""
    try:
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                row = conn.execute("SELECT value FROM settings WHERE key='sub_domain_prefix'").fetchone()
                if row and row[0]:
                    prefix = row[0].strip()
    except Exception:
        pass

    if not prefix or ":2097" in prefix or "bot-vip.online" in prefix:
        caddy_domain = auto_repair_caddy()
        if caddy_domain:
            prefix = f"https://{caddy_domain}/sub"
        else:
            prefix = prefix.replace(":2097", "") if prefix else "https://sub.svoii-vpn.online/sub"

    if prefix.startswith("http://") and any(ext in prefix for ext in [".online", ".ru", ".com", ".net", ".org"]):
        prefix = "https://" + prefix[7:]

    prefix = prefix.rstrip("/")
    if not prefix.endswith("/sub"):
        prefix = prefix + "/sub"

    return f"{prefix}/{sub_id}"

class SubServerHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        try:
            parts = [p for p in self.path.split("?")[0].split("/") if p]
            if not parts:
                self.send_error(404, "Not Found")
                return

            sub_id = parts[-1]
            cfg = ""

            if os.path.exists(DB_PATH):
                with sqlite3.connect(DB_PATH) as conn:
                    r_k = conn.execute("SELECT config_text FROM user_keys WHERE sub_id = ? AND is_active = 1", (sub_id,)).fetchone()
                    if r_k and r_k[0]:
                        cfg = r_k[0]
                    else:
                        r_u = conn.execute("SELECT vpn_config FROM users WHERE sub_id = ? AND is_vip = 1", (sub_id,)).fetchone()
                        if r_u and r_u[0]:
                            cfg = r_u[0]

            if not cfg:
                self.send_error(404, "Subscription not found")
                return

            acc_hdr = (self.headers.get("Accept") or "").lower()
            ua_hdr = (self.headers.get("User-Agent") or "").lower()
            is_vpn = any(app in ua_hdr for app in [
                "v2ray", "happ", "streisand", "hiddify", "shadowrocket",
                "sing-box", "clash", "nekobox", "karing", "flclash", "curl", "wget"
            ])
            is_browser = ("text/html" in acc_hdr or "mozilla" in ua_hdr) and not is_vpn

            if is_browser and "raw=1" not in self.path:
                try:
                    import sub_dashboard
                    sub_url = get_clean_sub_url(sub_id, DB_PATH)
                    html_bytes = sub_dashboard.build_sub_dashboard_html(sub_url, sub_id, {}, cfg).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(html_bytes)))
                    self.send_header("Connection", "close")
                    self.end_headers()
                    self.wfile.write(html_bytes)
                    return
                except Exception as e:
                    logger.error(f"Ошибка дашборда: {e}")

            b64_body = base64.b64encode(cfg.encode("utf-8"))
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(b64_body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b64_body)

        except Exception as e:
            logger.error(f"Ошибка обработки: {e}")
            try:
                self.send_error(500, "Internal Server Error")
            except Exception:
                pass

def start_sub_server(port: int = 2097, db_path: str = DB_PATH):
    global DB_PATH
    DB_PATH = db_path
    auto_heal_sub_database(db_path)

    def run():
        try:
            srv = HTTPServer(("0.0.0.0", port), SubServerHandler)
            srv.serve_forever()
        except Exception as e:
            logger.error(f"Ошибка старта sub_server: {e}")

    t = threading.Thread(target=run, daemon=True, name="SubServerThread")
    t.start()
    return t

# Алиас для обратной совместимости с bot.py
format_sub_url = get_clean_sub_url
