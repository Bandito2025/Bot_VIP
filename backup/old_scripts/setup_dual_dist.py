import re

bot_path = "/opt/Bot_VIP/bot.py"
with open(bot_path, "r", encoding="utf-8") as f:
    code = f.read()

# Добавляем маршруты /install.sh и /api/download_bot в обработчик веб-сервера
old_route_anchor = 'if path.startswith("/api/verify_license"):'

new_routes = '''if path == "/install.sh":
                import os
                f_path = "/opt/Bot_VIP/install.sh"
                if os.path.exists(f_path):
                    with open(f_path, "rb") as sh_file:
                        data = sh_file.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    self.send_response(404)
                    self.end_headers()
                return

            if path.startswith("/api/download_bot"):
                from urllib.parse import parse_qs, urlparse
                qs = parse_qs(urlparse(self.path).query)
                l_key = (qs.get("key", [""])[0]).strip()
                # Разрешаем скачивание по валидному ключу или для FREE-редакции
                is_allowed = False
                if l_key.upper() == "FREE" or l_key == "VIP-MASTER-OWNER-777":
                    is_allowed = True
                else:
                    with sqlite3.connect(DB_PATH) as conn:
                        row = conn.execute("SELECT id, is_active FROM bot_licenses WHERE lic_key = ?", (l_key,)).fetchone()
                        if row and row[1] == 1:
                            is_allowed = True
                
                archive_path = "/opt/Bot_VIP/bot.tar.gz"
                if is_allowed and os.path.exists(archive_path):
                    with open(archive_path, "rb") as af:
                        data = af.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/gzip")
                    self.send_header("Content-Disposition", 'attachment; filename="bot.tar.gz"')
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    self.send_response(403)
                    self.end_headers()
                    self.wfile.write(b'{"status":"error","msg":"Access denied or file missing"}')
                return

            if path.startswith("/api/verify_license"):'''

if "/install.sh" not in code:
    code = code.replace(old_route_anchor, new_routes, 1)
    with open(bot_path, "w", encoding="utf-8") as f:
        f.write(code)
    print("✅ Раздача install.sh и архива встроена в веб-сервер!")
else:
    print("ℹ️ Раздача уже была добавлена.")
