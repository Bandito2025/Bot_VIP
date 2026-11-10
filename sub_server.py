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
_CACHED_PREFIX = None

def get_public_ip() -> str:
    endpoints = ["https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"]
    for ep in endpoints:
        try:
            req = urllib.request.Request(ep, headers={"User-Agent": "curl/7.68.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                ip = resp.read().decode().strip()
                if ip and len(ip.split(".")) == 4:
                    return ip
        except Exception:
            continue
    return "127.0.0.1"

def patch_caddy_if_needed() -> str:
    """Находит домен в Caddyfile, встраивает reverse_proxy для /sub/* и перезагружает Caddy"""
    caddy_file = "/etc/caddy/Caddyfile"
    if not os.path.exists(caddy_file):
        return None

    try:
        with open(caddy_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Находим первый домен ноды (nl.svoii-vpn.online, pl.svoii-vpn.online и т.д.)
        domains = re.findall(r'^\s*([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(?::\d+)?\s*\{', content, re.M)
        target_domain = None
        for d in domains:
            if not d.startswith("sub."):
                target_domain = d
                break
        if not target_domain and domains:
            target_domain = domains[0]

        # Если проброса на 2097 ещё нет — вставляем перед wpp-api или перед закрывающей скобкой
        if "2097" not in content and target_domain:
            rule = "\n        handle /sub/* {\n                reverse_proxy 127.0.0.1:2097\n        }\n"
            new_content = content
            if "handle /wpp-api/*" in new_content:
                new_content = new_content.replace("handle /wpp-api/*", rule.strip() + "\n\n        handle /wpp-api/*", 1)
            else:
                pos = new_content.find("}")
                if pos != -1:
                    new_content = new_content[:pos] + rule + new_content[pos:]

            with open(caddy_file, "w", encoding="utf-8") as f:
                f.write(new_content)

            subprocess.run(["systemctl", "reload", "caddy"], capture_output=True)
            logger.info(f"✅ Caddy успешно настроен: домен {target_domain} проксирует /sub/* на 2097")

        return target_domain
    except Exception as e:
        logger.error(f"Ошибка настройки Caddy: {e}")
        return None

def get_effective_sub_prefix(db_path: str = DB_PATH) -> str:
    """Определяет корректный HTTPS адрес без ошибочного порта 2097"""
    global _CACHED_PREFIX
    if _CACHED_PREFIX:
        return _CACHED_PREFIX

    caddy_domain = patch_caddy_if_needed()

    # 1. Проверяем текущее значение в базе данных
    current_val = ""
    try:
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                row = conn.execute("SELECT value FROM settings WHERE key='sub_domain_prefix'").fetchone()
                if row and row[0]:
                    current_val = row[0].strip().rstrip("/")
    except Exception:
        pass

    # 2. Если в базе было ошибочное значение с доменом и портом :2097 — вычищаем порт
    if current_val and any(ext in current_val for ext in [".online", ".ru", ".com", ".net", ".org", ".io"]):
        clean = current_val.replace(":2097", "")
        if clean.startswith("http://"):
            clean = "https://" + clean[7:]
        if not clean.endswith("/sub"):
            clean = clean + "/sub"
        _CACHED_PREFIX = clean
    elif caddy_domain:
        _CACHED_PREFIX = f"https://{caddy_domain}/sub"
    else:
        # Fallback на IP-адрес сервера (для IP порт 2097 работает без SSL-ошибок)
        ip = get_public_ip()
        _CACHED_PREFIX = f"http://{ip}:2097/sub"
        try:
            subprocess.run(["ufw", "allow", "2097/tcp"], capture_output=True)
        except Exception:
            pass

    # 3. Сохраняем исправленный URL в базу данных
    try:
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('sub_domain_prefix', ?)", (_CACHED_PREFIX,))
                conn.commit()
    except Exception:
        pass

    return _CACHED_PREFIX

def format_sub_url(sub_id: str, db_path: str = DB_PATH) -> str:
    prefix = get_effective_sub_prefix(db_path)
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
                    sub_url = format_sub_url(sub_id, DB_PATH)
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
            logger.error(f"Ошибка запроса подписки: {e}")
            try:
                self.send_error(500, "Internal Server Error")
            except Exception:
                pass

def start_sub_server(port: int = 2097, db_path: str = DB_PATH):
    global DB_PATH
    DB_PATH = db_path
    threading.Thread(target=get_effective_sub_prefix, args=(db_path,), daemon=True).start()

    def run():
        try:
            srv = HTTPServer(("0.0.0.0", port), SubServerHandler)
            srv.serve_forever()
        except Exception as e:
            logger.error(f"Ошибка запуска sub_server: {e}")

    t = threading.Thread(target=run, daemon=True, name="SubServerThread")
    t.start()
    return t
