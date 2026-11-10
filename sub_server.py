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

def auto_configure_webserver(db_path: str = DB_PATH) -> str:
    """Автоматически находит домен сервера, прописывает проксирование в Caddy и возвращает чистый HTTPS URL"""
    global _CACHED_PREFIX
    if _CACHED_PREFIX:
        return _CACHED_PREFIX

    caddy_file = "/etc/caddy/Caddyfile"
    discovered_domain = None

    if os.path.exists(caddy_file):
        try:
            with open(caddy_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Находим домены в Caddyfile (например: nl.svoii-vpn.online или pl.svoii-vpn.online)
            domains = re.findall(r'^\s*([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(?::\d+)?\s*\{', content, re.M)
            for d in domains:
                if not d.startswith("sub."):
                    discovered_domain = d
                    break
            if not discovered_domain and domains:
                discovered_domain = domains[0]

            # Если правило проксирования еще не добавлено в Caddy
            if "2097" not in content and discovered_domain:
                rule = "\n    # SVOII_VPN SUB ROUTE\n    handle /sub/* {\n        reverse_proxy 127.0.0.1:2097\n    }\n"
                new_content = content
                if "handle /wpp-api/*" in new_content:
                    new_content = new_content.replace("handle /wpp-api/*", rule.strip() + "\n\n    handle /wpp-api/*", 1)
                else:
                    last_brace = new_content.rfind("}")
                    if last_brace != -1:
                        new_content = new_content[:last_brace] + rule + new_content[last_brace:]

                # Безопасная валидация перед сохранением
                test_file = "/tmp/Caddyfile.test"
                with open(test_file, "w", encoding="utf-8") as tf:
                    tf.write(new_content)
                val_res = subprocess.run(["caddy", "validate", "--config", test_file], capture_output=True, text=True)
                if val_res.returncode == 0:
                    with open(caddy_file, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    subprocess.run(["systemctl", "reload", "caddy"], capture_output=True)
                    logger.info("✅ Caddy успешно настроен на проксирование /sub/* на порт 2097")

            if discovered_domain:
                _CACHED_PREFIX = f"https://{discovered_domain}/sub"
                # Синхронизируем базу данных
                try:
                    if os.path.exists(db_path):
                        with sqlite3.connect(db_path) as conn:
                            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('sub_domain_prefix', ?)", (_CACHED_PREFIX,))
                            conn.commit()
                except Exception:
                    pass
                return _CACHED_PREFIX

        except Exception as e:
            logger.error(f"Ошибка автонастройки Caddy: {e}")

    # Fallback: если Caddy нет — используем прямой IP (без HSTS) и открываем файрвол
    try:
        subprocess.run(["ufw", "allow", "2097/tcp"], capture_output=True)
    except Exception:
        pass
    ip = get_public_ip()
    _CACHED_PREFIX = f"http://{ip}:2097/sub"
    return _CACHED_PREFIX

def format_sub_url(sub_id: str, db_path: str = DB_PATH) -> str:
    prefix = auto_configure_webserver(db_path)
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

            # Браузер -> отдаем HTML-дашборд
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

            # VPN-клиент -> чистый Base64
            b64_body = base64.b64encode(cfg.encode("utf-8"))
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(b64_body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b64_body)

        except Exception as e:
            logger.error(f"Ошибка запроса: {e}")
            try:
                self.send_error(500, "Internal Server Error")
            except Exception:
                pass

def start_sub_server(port: int = 2097, db_path: str = DB_PATH):
    global DB_PATH
    DB_PATH = db_path
    # Фоновая автонастройка Caddy при запуске
    threading.Thread(target=auto_configure_webserver, args=(db_path,), daemon=True).start()

    def run():
        try:
            srv = HTTPServer(("0.0.0.0", port), SubServerHandler)
            srv.serve_forever()
        except Exception as e:
            logger.error(f"Ошибка запуска sub_server: {e}")

    t = threading.Thread(target=run, daemon=True, name="SubServerThread")
    t.start()
    return t
