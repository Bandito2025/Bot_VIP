import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

DB_PATH = "/opt/Bot_VIP/bot_data.db"

def is_user_admin(user_id: int) -> bool:
    if not user_id:
        return False
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        # Проверяем в bot_staff и settings
        cur.execute("SELECT role FROM bot_staff WHERE user_id = ?", (user_id,))
        if cur.fetchone():
            conn.close()
            return True
        cur.execute("SELECT value FROM settings WHERE key IN ('admin_id', 'admin_ids', 'owner_id')")
        for row in cur.fetchall():
            if str(user_id) in str(row[0]):
                conn.close()
                return True
        conn.close()
    except Exception:
        pass
    # Фолбэк на глобальные переменные главного модуля
    import __main__
    for attr in ('ADMIN_IDS', 'ADMINS', 'ADMIN_ID', 'OWNER_ID', 'staff_roles'):
        val = getattr(__main__, attr, None)
        if isinstance(val, (list, set, tuple, dict)) and user_id in val:
            return True
        elif str(val) == str(user_id):
            return True
    return False


# Глобальное хранилище сессий мастера по user_id (не сбрасывается сторонними хендлерами)
ACTIVE_TARIFF_WIZ = {}

MENU_BUTTONS = (
    "⚙️ Админ-панель", "Админ-панель", "🔑 Мои ключи", "Мои ключи",
    "🎁 Пробная подписка", "Пробная подписка", "💳 Купить", "👤 Профиль",
    "Профиль", "📖 Инструкция", "🆘 Поддержка", "/start", "/admin"
)

def get_cancel_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="tariff_wiz_cancel")]])

def get_existing_groups():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT group_name FROM tariffs WHERE group_name IS NOT NULL AND group_name != ''")
        groups = [r[0] for r in cur.fetchall()]
        conn.close()
        return groups if groups else ["Стандарт", "Акции"]
    except Exception:
        return ["Стандарт", "Акции"]

async def start_tariff_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not is_user_admin(update.effective_user.id):
        return
    query = update.callback_query
    user = update.effective_user
    if query:
        try:
            await query.answer()
        except Exception:
            pass

    context.user_data.pop("awaiting", None)
    state = {"step": 1, "group": "Стандарт"}
    context.user_data["tariff_wiz"] = state
    if user:
        ACTIVE_TARIFF_WIZ[user.id] = state

    text = (
        "📝 <b>Добавление тарифа (1/5)</b>\n\n"
        "Введите <b>название</b>:\n"
        "<i>(например: Месяц, Полгода, Год)</i>"
    )
    if query:
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=get_cancel_kb())
    elif update.message:
        await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=get_cancel_kb())

async def handle_tariff_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.message or not update.message.text or not update.effective_user:
        return False

    uid = update.effective_user.id
    wiz = ACTIVE_TARIFF_WIZ.get(uid) or context.user_data.get("tariff_wiz")
    if not wiz:
        return False

    raw_text = update.message.text.strip()

    # Если пользователь нажал кнопку главного меню — выходим из мастера и передаем управление меню
    if any(raw_text.startswith(b) or raw_text == b for b in MENU_BUTTONS):
        ACTIVE_TARIFF_WIZ.pop(uid, None)
        context.user_data.pop("tariff_wiz", None)
        return False

    context.user_data.pop("awaiting", None)
    step = wiz.get("step", 1)

    if step == 1:
        wiz["name"] = raw_text
        wiz["step"] = 2
        ACTIVE_TARIFF_WIZ[uid] = wiz
        text = (
            "📝 <b>Добавление тарифа (2/5)</b>\n\n"
            f"✅ Название: {wiz['name']}\n\n"
            "Введите <b>цена в базовой валюте</b>:\n"
            "<i>(положительное число, не более двух знаков после запятой)</i>\n\n"
            "Курс Stars и USDT применяется автоматически в настройках оплаты."
        )
        await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=get_cancel_kb())
        return True

    elif step == 2:
        try:
            price = float(raw_text.replace(",", "."))
            if price <= 0:
                raise ValueError
            wiz["price"] = int(price) if price.is_integer() else round(price, 2)
        except ValueError:
            text = (
                "📝 <b>Добавление тарифа (2/5)</b>\n\n"
                "❌ <b>Введите корректное положительное число!</b>\n\n"
                f"✅ Название: {wiz.get('name', '')}\n\n"
                "Введите <b>цена в базовой валюте</b>:\n"
                "<i>(положительное число, не более двух знаков после запятой)</i>"
            )
            await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=get_cancel_kb())
            return True

        wiz["step"] = 3
        ACTIVE_TARIFF_WIZ[uid] = wiz
        text = (
            "📝 <b>Добавление тарифа (3/5)</b>\n\n"
            f"✅ Название: {wiz['name']}\n"
            f"✅ Цена в базовой валюте: {wiz['price']} ₽\n\n"
            "Введите <b>длительность</b>:\n"
            "<i>(в днях (0 = без срока, максимум 99999))</i>"
        )
        await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=get_cancel_kb())
        return True

    elif step == 3:
        try:
            days = int(raw_text)
            if days < 0 or days > 99999:
                raise ValueError
            wiz["days"] = days
        except ValueError:
            text = (
                "📝 <b>Добавление тарифа (3/5)</b>\n\n"
                "❌ <b>Длительность от 0 до 99999 дней</b>\n\n"
                f"✅ Название: {wiz.get('name', '')}\n"
                f"✅ Цена в базовой валюте: {wiz.get('price', '')} ₽\n\n"
                "Введите <b>длительность</b>:\n"
                "<i>(в днях (0 = без срока, максимум 99999))</i>"
            )
            await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=get_cancel_kb())
            return True

        wiz["step"] = 4
        ACTIVE_TARIFF_WIZ[uid] = wiz
        text = (
            "📝 <b>Добавление тарифа (4/5)</b>\n\n"
            f"✅ Название: {wiz['name']}\n"
            f"✅ Цена в базовой валюте: {wiz['price']} ₽\n"
            f"✅ Длительность: {wiz['days']} дн.\n\n"
            "Введите <b>лимит трафика (гб)</b>:\n"
            "<i>(0 = безлимит, иначе число ГБ)</i>"
        )
        await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=get_cancel_kb())
        return True

    elif step == 4:
        try:
            traffic = int(raw_text)
            if traffic < 0:
                raise ValueError
            wiz["traffic"] = traffic
        except ValueError:
            text = (
                "📝 <b>Добавление тарифа (4/5)</b>\n\n"
                "❌ <b>Введите число 0 или больше!</b>\n\n"
                f"✅ Название: {wiz.get('name', '')}\n"
                f"✅ Цена в базовой валюте: {wiz.get('price', '')} ₽\n"
                f"✅ Длительность: {wiz.get('days', '')} дн.\n\n"
                "Введите <b>лимит трафика (гб)</b>:\n"
                "<i>(0 = безлимит, иначе число ГБ)</i>"
            )
            await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=get_cancel_kb())
            return True

        wiz["step"] = 5
        ACTIVE_TARIFF_WIZ[uid] = wiz
        text = (
            "📝 <b>Добавление тарифа (5/5)</b>\n\n"
            f"✅ Название: {wiz['name']}\n"
            f"✅ Цена в базовой валюте: {wiz['price']} ₽\n"
            f"✅ Длительность: {wiz['days']} дн.\n"
            f"✅ Лимит трафика (ГБ): {wiz['traffic']} ГБ\n\n"
            "Введите <b>лимит устройств</b>:\n"
            "<i>(Минимум 1 устройство)</i>"
        )
        await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=get_cancel_kb())
        return True

    elif step == 5:
        try:
            devices = int(raw_text)
            if devices < 1:
                raise ValueError
            wiz["devices"] = devices
        except ValueError:
            text = (
                "📝 <b>Добавление тарифа (5/5)</b>\n\n"
                "❌ <b>Минимум 1 устройство!</b>\n\n"
                f"✅ Название: {wiz.get('name', '')}\n"
                f"✅ Цена в базовой валюте: {wiz.get('price', '')} ₽\n"
                f"✅ Длительность: {wiz.get('days', '')} дн.\n"
                f"✅ Лимит трафика (ГБ): {wiz.get('traffic', '')} ГБ\n\n"
                "Введите <b>лимит устройств</b>:\n"
                "<i>(Минимум 1 устройство)</i>"
            )
            await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=get_cancel_kb())
            return True

        wiz["step"] = "confirm"
        ACTIVE_TARIFF_WIZ[uid] = wiz
        await render_confirm(update.message, wiz, is_edit=False)
        return True

    return False

async def render_confirm(target, wiz, is_edit=False):
    grp = wiz.get("group", "Стандарт")
    text = (
        "✅ <b>Все данные введены!</b>\n\n"
        f"📌 Название: <code>{wiz['name']}</code>\n"
        f"💰 Цена: <code>{wiz['price']} ₽</code>\n"
        f"📅 Длительность: <code>{wiz['days']} дн.</code>\n"
        f"📦 Лимит трафика: <code>{wiz['traffic']} ГБ</code>\n"
        f"💻 Лимит устройств: <code>{wiz['devices']} устр.</code>\n"
        f"📁 Группа тарифа: <b>{grp}</b>\n\n"
        "Сохранить тариф?"
    )
    groups = get_existing_groups()
    grp_btns = [
        InlineKeyboardButton(f"{'🟢' if g == grp else '⚪️'} {g}", callback_data=f"tariff_wiz_grp_{g}")
        for g in groups[:3]
    ]
    rows = []
    if grp_btns:
        rows.append(grp_btns)
    rows.append([InlineKeyboardButton("✅ Сохранить", callback_data="tariff_wiz_save")])
    rows.append([InlineKeyboardButton("❌ Отмена", callback_data="tariff_wiz_cancel")])
    kb = InlineKeyboardMarkup(rows)

    if is_edit:
        await target.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.reply_text(text=text, parse_mode="HTML", reply_markup=kb)

async def handle_tariff_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_user or not is_user_admin(update.effective_user.id):
        return False
    query = update.callback_query
    user = update.effective_user
    if not query or not query.data:
        return False
    data = query.data
    uid = user.id if user else 0

    if data == "tariff_wiz_cancel":
        ACTIVE_TARIFF_WIZ.pop(uid, None)
        context.user_data.pop("tariff_wiz", None)
        context.user_data.pop("awaiting", None)
        try:
            await query.answer("Отменено")
        except Exception:
            pass
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ К тарифам", callback_data="admin_tariffs_list")]])
        await query.edit_message_text("❌ Создание тарифа отменено.", reply_markup=kb)
        return True

    if data.startswith("tariff_wiz_grp_"):
        wiz = ACTIVE_TARIFF_WIZ.get(uid) or context.user_data.get("tariff_wiz")
        if wiz:
            wiz["group"] = data.replace("tariff_wiz_grp_", "", 1)
            ACTIVE_TARIFF_WIZ[uid] = wiz
            await query.answer(f"Группа: {wiz['group']}")
            await render_confirm(query, wiz, is_edit=True)
        return True

    if data == "tariff_wiz_save":
        wiz = ACTIVE_TARIFF_WIZ.pop(uid, None) or context.user_data.pop("tariff_wiz", None)
        context.user_data.pop("tariff_wiz", None)
        if not wiz:
            await query.answer("Сессия истекла, создайте тариф заново", show_alert=True)
            return True

        name = wiz.get("name", "Тариф")
        price = wiz.get("price", 100)
        days = wiz.get("days", 30)
        traffic = wiz.get("traffic", 0)
        devices = wiz.get("devices", 1)
        group_name = wiz.get("group", "Стандарт")
        stars = max(1, int(round(price * 0.5)))

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(tariffs)")
        cols = [c[1] for c in cur.fetchall()]

        if "traffic_gb" not in cols:
            try:
                cur.execute("ALTER TABLE tariffs ADD COLUMN traffic_gb INTEGER DEFAULT 0")
                cols.append("traffic_gb")
            except Exception:
                pass
        if "device_limit" not in cols:
            try:
                cur.execute("ALTER TABLE tariffs ADD COLUMN device_limit INTEGER DEFAULT 1")
                cols.append("device_limit")
            except Exception:
                pass

        if "is_bot" not in cols:
            try:
                cur.execute("ALTER TABLE tariffs ADD COLUMN is_bot INTEGER DEFAULT 0")
                cols.append("is_bot")
            except Exception:
                pass

        insert_cols = ["group_name", "name", "days", "price_rub", "price_stars", "is_active", "device_limit", "traffic_gb", "is_bot"]
        vals = [group_name, name, days, price, stars, 1, devices, traffic, 0]

        cur.execute(
            f"INSERT INTO tariffs ({', '.join(insert_cols)}) VALUES ({', '.join(['?']*len(vals))})",
            tuple(vals)
        )
        conn.commit()
        conn.close()

        try:
            await query.answer("✅ Тариф сохранён!")
        except Exception:
            pass

        text = (
            "✅ <b>Тариф успешно сохранён!</b>\n\n"
            f"📌 Название: <code>{name}</code>\n"
            f"💰 Цена: <code>{price} ₽</code>\n"
            f"📅 Длительность: <code>{days} дн.</code>\n"
            f"📦 Лимит трафика: <code>{traffic} ГБ</code>\n"
            f"💻 Лимит устройств: <code>{devices} устр.</code>\n"
            f"📁 Группа: <b>{group_name}</b>"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📋 К списку тарифов", callback_data="admin_tariffs_list")]])
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)
        return True

    return False
