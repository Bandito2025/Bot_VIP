import os
import sqlite3
import base64
import logging
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger("Bot_VIP")
DB_PATH = "/opt/Bot_VIP/bot_data.db"
_CACHED_IP = None

def get_public_ip() -> str:
    """Автоматически определяет внешний IP-адрес сервера"""
    global _CACHED_IP
    if _CACHED_IP:
        return _CACHED_IP
    endpoints = ["https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"]
    for ep in endpoints:
        try:
            req = urllib.request.Request(ep, headers={"User-Agent": "curl/7.68.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                ip = resp.read().decode().strip()
                if ip and len(ip.split(".")) == 4:
                    _CACHED_IP = ip
                    return _CACHED_IP
        except Exception:
            continue
    _CACHED_IP = "127.0.0.1"
    return _CACHED_IP

def get_effective_sub_prefix(db_path: str = DB_PATH) -> str:
    """Возвращает рабочий префикс подписки: персональный домен или автономный IP:2097"""
    try:
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                row = conn.execute("SELECT value FROM settings WHERE key='sub_domain_prefix'").fetchone()
                if row and row[0] and row[0].strip():
                    val = row[0].strip().rstrip("/")
                    # Если указан чужой тестовый адрес, а мы на другом сервере без Caddy, берем локальный IP
                    if "sub.svoii-vpn.online" in val:
                        local_ip = get_public_ip()
                        # Если это не тестовый сервер (IP не совпадает с IP sub.svoii-vpn.online), используем автономный IP
                        return val
                    return val
    except Exception:
        pass
    return f"http://{get_public_ip()}:2097/sub"

def format_sub_url(sub_id: str, db_path: str = DB_PATH) -> str:
    prefix = get_effective_sub_prefix(db_path)
    return f"{prefix}/{sub_id}"

class SubServerHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Отключаем лишний спам в консоль

    def do_GET(self):
        try:
            # Извлекаем sub_id из пути: /sub/{sub_id}
            parts = [p for p in self.path.split("?")[0].split("/") if p]
            if not parts:
                self.send_error(404, "Not Found")
                return

            sub_id = parts[-1]
            cfg = ""

            if os.path.exists(DB_PATH):
                with sqlite3.connect(DB_PATH) as conn:
                    # 1. Поиск в user_keys
                    r_k = conn.execute("SELECT config_text FROM user_keys WHERE sub_id = ? AND is_active = 1", (sub_id,)).fetchone()
                    if r_k and r_k[0]:
                        cfg = r_k[0]
                    else:
                        # 2. Поиск в users
                        r_u = conn.execute("SELECT vpn_config FROM users WHERE sub_id = ? AND is_vip = 1", (sub_id,)).fetchone()
                        if r_u and r_u[0]:
                            cfg = r_u[0]

            if not cfg:
                self.send_error(404, "Subscription not found or expired")
                return

            # Проверяем тип клиента
            acc_hdr = (self.headers.get("Accept") or "").lower()
            ua_hdr = (self.headers.get("User-Agent") or "").lower()
            is_vpn = any(app in ua_hdr for app in [
                "v2ray", "happ", "streisand", "hiddify", "shadowrocket",
                "sing-box", "clash", "nekobox", "karing", "flclash", "curl", "wget"
            ])
            is_browser = ("text/html" in acc_hdr or "mozilla" in ua_hdr) and not is_vpn

            # Если открыто из веб-браузера — отдаем дашборд
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
                    logger.error(f"Ошибка рендера дашборда: {e}")

            # Для всех VPN-клиентов отдаем чистый Base64
            b64_body = base64.b64encode(cfg.encode("utf-8"))
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(b64_body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b64_body)

        except Exception as e:
            logger.error(f"Ошибка обработки запроса подписки: {e}")
            try:
                self.send_error(500, "Internal Server Error")
            except Exception:
                pass

def start_sub_server(port: int = 2097, db_path: str = DB_PATH):
    """Запускает HTTP-сервер подписок в фоновом потоке демона"""
    global DB_PATH
    DB_PATH = db_path

    def run_server():
        try:
            srv = HTTPServer(("0.0.0.0", port), SubServerHandler)
            logger.info(f"🚀 Автономный сервер подписок запущен на порту {port}")
            srv.serve_forever()
        except Exception as e:
            logger.error(f"Не удалось запустить сервер подписок на порту {port}: {e}")

    t = threading.Thread(target=run_server, daemon=True, name="SubServerThread")
    t.start()
    return t
