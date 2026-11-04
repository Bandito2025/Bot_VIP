import uuid
import base64
import sqlite3
import logging
import asyncio
import httpx

logger = logging.getLogger(__name__)
_POLLING_LOCK = asyncio.Lock()

def init_autopay_db(db_path: str):
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inv_id TEXT UNIQUE,
                provider TEXT,
                user_id INTEGER,
                t_id INTEGER,
                days INTEGER,
                price REAL,
                tariff_name TEXT,
                is_bot_lic INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()

def register_invoice(db_path: str, inv_id: str, provider: str, user_id: int, t_id: int, days: int, price: float, tariff_name: str, is_bot_lic: int = 0):
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO pending_invoices (inv_id, provider, user_id, t_id, days, price, tariff_name, is_bot_lic)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(inv_id), provider, user_id, t_id, days, price, tariff_name, is_bot_lic))
        conn.commit()

def remove_invoice(db_path: str, inv_id: str):
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM pending_invoices WHERE inv_id = ?", (str(inv_id),))
        conn.commit()

def consume_invoice_atomic(db_path: str, inv_id: str) -> bool:
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("DELETE FROM pending_invoices WHERE inv_id = ?", (str(inv_id),))
        conn.commit()
        return cur.rowcount > 0

def cleanup_expired_invoices(db_path: str, hours: int = 24):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "DELETE FROM pending_invoices WHERE created_at < datetime('now', ?)",
            (f"-{int(hours)} hours",)
        )
        conn.commit()

def get_pending_invoices(db_path: str):
    cleanup_expired_invoices(db_path, hours=24)
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "SELECT id, inv_id, provider, user_id, t_id, days, price, tariff_name, is_bot_lic "
            "FROM pending_invoices ORDER BY id ASC"
        )
        return cur.fetchall()

async def create_yookassa_payment(shop_id: str, secret_key: str, amount_rub: float, desc: str, return_url: str = "https://t.me", metadata: dict = None):
    auth_str = base64.b64encode(f"{shop_id}:{secret_key}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_str}",
        "Idempotence-Key": str(uuid.uuid4()),
        "Content-Type": "application/json"
    }
    body = {
        "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": desc[:128],
        "metadata": metadata or {}
    }
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.post("https://api.yookassa.ru/v3/payments", headers=headers, json=body)
        data = resp.json()
        if resp.status_code in (200, 201) and "confirmation" in data:
            return data["confirmation"]["confirmation_url"], data["id"]
        logger.error(f"YooKassa error: {data}")
        return None, None

async def check_yookassa_payment(shop_id: str, secret_key: str, inv_id: str) -> str:
    auth_str = base64.b64encode(f"{shop_id}:{secret_key}".encode()).decode()
    headers = {"Authorization": f"Basic {auth_str}"}
    async with httpx.AsyncClient(timeout=6.0) as client:
        resp = await client.get(f"https://api.yookassa.ru/v3/payments/{inv_id}", headers=headers)
        if resp.status_code == 200:
            return resp.json().get("status", "pending")
        return "error"

async def create_cryptopay_payment(token: str, amount_usdt: float, desc: str, payload: str):
    headers = {"Crypto-Pay-API-Token": token}
    body = {
        "asset": "USDT",
        "amount": str(amount_usdt),
        "description": desc[:128],
        "payload": payload
    }
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.post("https://pay.crypt.bot/api/createInvoice", headers=headers, json=body)
        data = resp.json()
        if data.get("ok"):
            res = data["result"]
            return res["pay_url"], str(res["invoice_id"])
        logger.error(f"CryptoPay error: {data}")
        return None, None

async def check_cryptopay_payment(token: str, inv_id: str) -> str:
    headers = {"Crypto-Pay-API-Token": token}
    async with httpx.AsyncClient(timeout=6.0) as client:
        resp = await client.get(f"https://pay.crypt.bot/api/getInvoices?invoice_ids={inv_id}", headers=headers)
        data = resp.json()
        if data.get("ok") and data["result"]["items"]:
            return data["result"]["items"][0].get("status", "active")
        return "error"
