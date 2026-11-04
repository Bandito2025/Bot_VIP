import json
import time
import aiohttp
import asyncio

async def add_to_3xui(session: aiohttp.ClientSession, backend: dict, uuid: str, email: str, sub_id: str, limit_ip: int, expiry_ms: int, total_gb_bytes: int):
    login_url = f"{backend['base_url'].rstrip('/')}/login"
    add_url = f"{backend['base_url'].rstrip('/')}/panel/api/inbounds/addClient"
    
    # 1. Авторизация
    login_data = {"username": backend["auth_login"], "password": backend["auth_password"]}
    async with session.post(login_url, data=login_data, ssl=False, timeout=5) as resp:
        if resp.status != 200:
            return False, f"3X-UI Login failed: {resp.status}"
            
    # 2. Добавление клиента
    client_payload = {
        "id": backend.get("inbound_id", 1),
        "settings": json.dumps({
            "clients": [{
                "id": uuid,
                "email": email,
                "subId": sub_id,
                "limitIp": limit_ip,
                "totalGB": total_gb_bytes,
                "expiryTime": expiry_ms,
                "enable": True
            }]
        })
    }
    async with session.post(add_url, json=client_payload, ssl=False, timeout=5) as resp:
        data = await resp.json()
        return data.get("success", False), data.get("msg", "")

async def add_to_wpp(session: aiohttp.ClientSession, backend: dict, uuid: str, email: str, sub_id: str, limit_ip: int, expiry_ms: int, total_gb_bytes: int):
    url = f"{backend['base_url'].rstrip('/')}/api/clients/add"
    headers = {"Authorization": f"Bearer {backend['api_token']}", "Content-Type": "application/json"}
    payload = {
        "uuid": uuid,
        "email": email,
        "sub_id": sub_id,
        "limit_ip": limit_ip,
        "expire_time": expiry_ms // 1000,
        "traffic_limit": total_gb_bytes
    }
    async with session.post(url, json=payload, headers=headers, ssl=False, timeout=5) as resp:
        return resp.status in (200, 201), await resp.text()

async def sync_client_to_all_backends(backends: list, uuid: str, sub_token: str, user_id: int, days: int, limit_ip: int, traffic_gb: int = 1000):
    expiry_ms = int((time.time() + (days * 86400)) * 1000) if days > 0 else 0
    total_bytes = traffic_gb * 1024 * 1024 * 1024
    email = f"u{user_id}_{sub_token[:6]}"
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for b in backends:
            if not b.get("is_active"):
                continue
            if b["panel_type"] == "3xui":
                tasks.append(add_to_3xui(session, b, uuid, email, sub_token, limit_ip, expiry_ms, total_bytes))
            elif b["panel_type"] == "web_panel_proxy":
                tasks.append(add_to_wpp(session, b, uuid, email, sub_token, limit_ip, expiry_ms, total_bytes))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
