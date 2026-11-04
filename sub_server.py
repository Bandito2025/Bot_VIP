import os
import sys
import time
import base64
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

DB_PATH = "/opt/Bot_VIP/bot_data.db"
SERVER_PORT = 8080
SERVER_HOST = "0.0.0.0"

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class SubscriptionHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Ожидаемый путь: /sub/<token>
        path_parts = self.path.strip("/").split("/")
        if len(path_parts) != 2 or path_parts[0] != "sub":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        sub_token = path_parts[1].strip()
        if not sub_token or not os.path.exists(DB_PATH):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid Token or Database not ready")
            return

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # 1. Поиск пользователя по sub_token
        cur.execute("PRAGMA table_info(users)")
        cols = [c[1] for c in cur.fetchall()]
        uid_col = next((c for c in ("user_id", "telegram_id", "tg_id", "id") if c in cols), "user_id")

        cur.execute(f"SELECT {uid_col} FROM users WHERE sub_token = ?", (sub_token,))
        user_row = cur.fetchone()
        if not user_row:
            conn.close()
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Access Denied: Invalid Subscription Token")
            return

        user_id = user_row[0]

        # 2. Проверка активных подписок и даты окончания
        now_ts = int(time.time())
        cur.execute("SELECT expires_at FROM keys WHERE user_id = ? ORDER BY expires_at DESC LIMIT 1", (user_id,))
        key_exp = cur.fetchone()
        expire_ts = key_exp[0] if (key_exp and key_exp[0]) else (now_ts + 86400 * 3)

        if expire_ts < now_ts:
            conn.close()
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Subscription Expired")
            return

        # 3. Сбор активных серверов
        cur.execute("SELECT name, host, ip_port, inbound_id FROM servers WHERE is_active = 1")
        servers = cur.fetchall()

        # 4. Формирование VLESS-ссылок для каждого активного сервера
        configs = []
        cur.execute("SELECT key FROM keys WHERE user_id = ? AND is_trial = 0 LIMIT 1", (user_id,))
        custom_key = cur.fetchone()

        for srv in servers:
            s_name, s_host, s_ipport, _ = srv
            host_val = s_host or s_ipport.split(":")[0] if s_ipport else "177.202.68.108"
            port_val = s_ipport.split(":")[1] if (s_ipport and ":" in s_ipport) else "443"
            
            # Генерация UUID для клиента (на основе user_id)
            import hashlib
            client_uuid = hashlib.md5(f"{user_id}-{s_name}".encode()).hexdigest()
            client_uuid = f"{client_uuid[:8]}-{client_uuid[8:12]}-{client_uuid[12:16]}-{client_uuid[16:20]}-{client_uuid[20:32]}"
            
            vless_link = f"vless://{client_uuid}@{host_val}:{port_val}?security=reality&type=tcp&headerType=none&sni=google.com#{s_name}"
            configs.append(vless_link)

        conn.close()

        # Если в базе нет серверов, отдаем резервный узел
        if not configs:
            configs.append(f"vless://00000000-0000-0000-0000-000000000000@177.202.68.108:443?security=reality#VIP-Node-Standby")

        # 5. Кодирование списка серверов в Base64
        payload_raw = "\n".join(configs)
        payload_b64 = base64.b64encode(payload_raw.encode("utf-8"))

        # 6. Отправка ответа клиенту
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Profile-Update-Interval", "6")
        self.send_header("Subscription-Userinfo", f"upload=0; download=0; total=107374182400; expire={expire_ts}")
        self.send_header("Content-Disposition", 'inline; filename="VIP-VPN.txt"')
        self.end_headers()
        self.wfile.write(payload_b64)

    def log_message(self, format, *args):
        # Отключаем вывод спама GET-запросов в консоль
        pass

def run_server():
    server = ThreadedHTTPServer((SERVER_HOST, SERVER_PORT), SubscriptionHandler)
    print(f"🚀 Сервис подписок запущен на http://{SERVER_HOST}:{SERVER_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

if __name__ == "__main__":
    run_server()
