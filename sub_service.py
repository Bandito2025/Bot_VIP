import re
import base64
import sqlite3
import urllib.parse
import asyncio
import aiohttp
from aiohttp import web

DB_PATH = "/opt/Bot_VIP/bot_data.db"

def clean_cfg(line: str):
    line = line.strip()
    # Отсекаем нерабочие локальные заглушки 127.0.0.1
    if not line or "@127.0.0.1" in line or "host=127.0.0.1" in line:
        return None
    # Очищаем название (#remarks) от ссылок на панель
    if "#" in line:
        base_part, remark = line.split("#", 1)
        text = urllib.parse.unquote(remark)
        text = re.sub(r'https?://\S+', '', text).strip()
        line = f"{base_part}#{urllib.parse.quote(text or 'VPN')}"
    return line

async def fetch_one(session: aiohttp.ClientSession, url: str):
    try:
        async with session.get(url, timeout=4, ssl=False) as resp:
            if resp.status == 200:
                raw = await resp.text()
                try:
                    return base64.b64decode(raw.strip()).decode('utf-8', errors='ignore').splitlines()
                except Exception:
                    return raw.splitlines()
    except Exception as e:
        print(f"[-] Ошибка опроса {url}: {e}")
    return []

async def handle_sub(request):
    token = request.match_info.get("token")
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        key = conn.execute("SELECT * FROM unified_keys WHERE sub_token = ? AND is_active = 1", (token,)).fetchone()
        backends = [dict(b) for b in conn.execute("SELECT * FROM panel_backends WHERE is_active = 1").fetchall()]
        
    headers = {"User-Agent": "Unified-Sub-Aggregator/2.0"}
    all_lines = []
    
    async with aiohttp.ClientSession(headers=headers) as session:
        tasks = [fetch_one(session, f"{b['sub_base_url'].rstrip('/')}/{token}") for b in backends]
        results = await asyncio.gather(*tasks)
        for r in results:
            all_lines.extend(r)
            
    valid_configs = []
    seen = set()
    for raw in all_lines:
        clean = clean_cfg(raw)
        if clean and clean not in seen:
            seen.add(clean)
            valid_configs.append(clean)
            
    if not valid_configs:
        return web.Response(status=502, text="No active nodes available")
        
    encoded = base64.b64encode("\n".join(valid_configs).encode("utf-8")).decode("utf-8")
    
    resp_headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "Profile-Update-Interval": "1"
    }
    if key:
        resp_headers["Subscription-Userinfo"] = f"upload=0; download={key['traffic_used_bytes']}; total={key['traffic_limit_bytes']}; expire={key['expires_at'] or 0}"
        
    return web.Response(text=encoded, headers=resp_headers)

app = web.Application()
app.router.add_get('/sub/{token}', handle_sub)

if __name__ == '__main__':
    web.run_app(app, host='127.0.0.1', port=2097)
