import uuid
import html
import sqlite3
import secrets
import logging
from datetime import datetime, timedelta
import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger("AutoPay")

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
            )
        """)
        conn.commit()

async def process_auto_fulfillment(user_id: int, days: int, price: float, tariff_name: str, is_bot_lic: bool, bot_instance, db_path: str, admin_id: int, create_key_fn, record_pay_fn, get_set_fn):
    record_pay_fn(user_id, price, "AutoPay", f"Оплата: {tariff_name}")
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE users SET active_discount_pct = 0 WHERE user_id = ?", (user_id,))
        conn.commit()

    if is_bot_lic:
        now = datetime.now()
        lic_token = f"LIC-BOT-{user_id}-{secrets.token_hex(3).upper()} (до {(now + timedelta(days=days)).strftime('%Y-%m-%d')})"
        with sqlite3.connect(db_path) as conn:
            conn.execute("UPDATE users SET is_vip = 1, bot_license = ? WHERE user_id = ?", (lic_token, user_id))
            conn.commit()
        try:
            await bot_instance.send_message(
                chat_id=user_id,
                text=f"🎉 <b>Оплата получена! Лицензия активирована!</b>\n\n🔑 <b>Ваш ключ лицензии:</b>\n<code>{lic_token}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass
    else:
        k_id, until, sub_url, _ = await create_key_fn(user_id, days=days, create_new=True)
        try:
            await bot_instance.send_message(
                chat_id=user_id,
                text=(
                    f"🎉 <b>Оплата успешно получена!</b>\n\n"
                    f"🔑 <b>Ключ #{k_id} активен до {until}</b>\n\n"
                    f"🔗 <b>Единая ссылка подписки:</b>\n<code>{sub_url}</code>\n\n"
                    f"<i>Все ваши подключения доступны в меню «🔑 Мои ключи».</i>"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

    if get_set_fn("pay_notify_enabled", "1") == "1":
        try:
            await bot_instance.send_message(
                chat_id=admin_id,
                text=f"💰 <b>АВТООПЛАТА УСПЕШНА</b>\n👤 Клиент: <code>{user_id}</code>\n📋 Тариф: {tariff_name}\n💵 Сумма: {price} ₽",
                parse_mode="HTML"
            )
        except Exception:
            pass

async def auto_poll_invoices_worker(app, db_path: str, admin_id: int, create_key_fn, record_pay_fn, get_set_fn):
    with sqlite3.connect(db_path) as conn:
        invoices = conn.execute("SELECT id, inv_id, provider, user_id, days, price, tariff_name, is_bot_lic FROM pending_invoices").fetchall()
    if not invoices:
        return

    yoo_shop = get_set_fn("pay_yookassa_shop_id", "")
    yoo_sec = get_set_fn("pay_yookassa_secret", "")
    cp_token = get_set_fn("pay_cryptopay_secret", "")

    for row_id, inv_id, prov, u_id, days, price, t_name, is_lic in invoices:
        is_paid = False
        try:
            if prov == "yookassa" and yoo_shop and yoo_sec:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.get(f"https://api.yookassa.ru/v1/payments/{inv_id}", auth=(yoo_shop, yoo_sec))
                    if resp.status_code == 200 and resp.json().get("status") == "succeeded":
                        is_paid = True
            elif prov == "cryptopay" and cp_token:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.get(
                        "https://pay.crypt.bot/api/getInvoices",
                        headers={"Crypto-Pay-API-Token": cp_token},
                        params={"invoice_ids": inv_id}
                    )
                    r = resp.json()
                    if r.get("ok") and r.get("result", {}).get("items", []) and r["result"]["items"][0].get("status") == "paid":
                        is_paid = True
        except Exception:
            pass

        if is_paid:
            with sqlite3.connect(db_path) as conn:
                conn.execute("DELETE FROM pending_invoices WHERE id = ?", (row_id,))
                conn.commit()
            await process_auto_fulfillment(u_id, days, price, t_name, bool(is_lic), app.bot, db_path, admin_id, create_key_fn, record_pay_fn, get_set_fn)
