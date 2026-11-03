import re

bot_path = "/opt/Bot_VIP/bot.py"
with open(bot_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Меняем дефолтный порт веб-агрегатора лицензий с 2096 на 2097
code = re.sub(r'SUB_PORT\s*=\s*int\(os\.getenv\("SUB_PORT",\s*"2096"\)\)', 'SUB_PORT = int(os.getenv("SUB_PORT", "2097"))', code)
code = re.sub(r'SUB_PORT\s*=\s*2096', 'SUB_PORT = 2097', code)
code = code.replace(':2096/api/verify_license', ':2097/api/verify_license')

# 2. Гарантируем корректную обработку маршрутов /install.sh и /api/download_bot в классе Handler
# Ищем метод do_GET
if "def do_GET(" in code:
    get_handler_anchor = "def do_GET(self):"
    routes_replacement = '''def do_GET(self):
        import os, sqlite3
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == "/install.sh":
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
                self.wfile.write(b"install.sh not found")
            return

        if path == "/api/download_bot":
            qs = parse_qs(parsed_url.query)
            l_key = (qs.get("key", [""])[0]).strip()
            is_allowed = (l_key.upper() == "FREE" or l_key == "VIP-MASTER-OWNER-777")
            if not is_allowed and "DB_PATH" in globals():
                try:
                    with sqlite3.connect(DB_PATH) as conn:
                        row = conn.execute("SELECT id, is_active FROM bot_licenses WHERE lic_key = ?", (l_key,)).fetchone()
                        if row and row[1] == 1:
                            is_allowed = True
                except Exception:
                    pass

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
'''
    code = code.replace(get_handler_anchor, routes_replacement, 1)

with open(bot_path, "w", encoding="utf-8") as f:
    f.write(code)

# Обновляем .env
with open("/opt/Bot_VIP/.env", "a", encoding="utf-8") as f:
    f.write("\nSUB_PORT=2097\n")

print("✅ Сервер лицензий и установщика перенесен на свободный порт 2097!")
