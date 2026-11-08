import html
import base64
from urllib.parse import quote

def build_sub_html_page(sub_url: str, key_name: str, expires_at: str, traffic_str: str, raw_config: str) -> bytes:
    enc_url = quote(sub_url, safe="")
    b64_url = base64.b64encode(sub_url.encode("utf-8")).decode("utf-8")
    safe_name = html.escape(key_name or "VIP Client")
    safe_exp = html.escape(expires_at or "Бессрочно")
    safe_tr = html.escape(traffic_str or "Без ограничений")
    qr_img_url = f"https://api.qrserver.com/v1/create-qr-code/?size=280x280&data={enc_url}"

    page = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Подписка {safe_name} | Личный кабинет VPN</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
  :root {{
    --bg-main: #12131a;
    --bg-card: #1c1e29;
    --text-primary: #ffffff;
    --text-secondary: #8c90a4;
    --accent: #3b82f6;
  }}
  body {{
    background: var(--bg-main);
    color: var(--text-primary);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    margin: 0;
    padding: 24px;
    display: flex;
    justify-content: center;
  }}
  .card {{
    background: var(--bg-card);
    max-width: 420px;
    width: 100%;
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    text-align: center;
  }}
  .qr-box {{
    background: #ffffff;
    padding: 12px;
    border-radius: 12px;
    display: inline-block;
    margin: 16px 0;
  }}
  .qr-box img {{ display: block; width: 220px; height: 220px; }}
  .info {{ text-align: left; margin: 16px 0; font-size: 14px; color: var(--text-secondary); }}
  .info b {{ color: var(--text-primary); }}
  .btn {{
    display: block;
    background: var(--accent);
    color: #fff;
    padding: 12px;
    border-radius: 10px;
    text-decoration: none;
    font-weight: 600;
    margin-top: 12px;
  }}
</style>
</head>
<body>
  <div class="card">
    <h2>Ваша VPN-подписка</h2>
    <div class="qr-box">
      <img src="{qr_img_url}" alt="QR-код подключения">
    </div>
    <div class="info">
      <p>Имя профиля: <b>{safe_name}</b></p>
      <p>Срок действия: <b>{safe_exp}</b></p>
      <p>Трафик: <b>{safe_tr}</b></p>
    </div>
    <a href="{sub_url}" class="btn">Импортировать в приложение</a>
  </div>
</body>
</html>"""
    return page.encode("utf-8")
