import html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

def mask_val(val: str, prefix_len=4, suffix_len=4) -> str:
    if not val or val.strip() in ("", "не задан", "live_E51Y_example"):
        return "❌ Не задан"
    val = val.strip()
    if len(val) <= prefix_len + suffix_len:
        return "Установлен ✅"
    return f"Установлен ✅ ({val[:prefix_len]}...{val[-suffix_len:]})"

def render_gateway_card(p_key: str, get_setting_fn) -> tuple[str, InlineKeyboardMarkup]:
    is_on = get_setting_fn(f"pay_{p_key}_enabled", "0") == "1"
    st_icon = "🟢" if is_on else "⚪️"
    st_text = "включено" if is_on else "выключено"

    btn_on = InlineKeyboardButton("🟢 Включено" if is_on else "⚪️ Включено", callback_data=f"admin_pay_toggle_{p_key}_1")
    btn_off = InlineKeyboardButton("⚪️ Выключено" if is_on else "🔴 Выключено", callback_data=f"admin_pay_toggle_{p_key}_0")
    nav_row = [
        InlineKeyboardButton("⬅️ Назад", callback_data="admin_payments_menu"),
        InlineKeyboardButton("🈴 На главную", callback_data="admin_back_main")
    ]

    if p_key in ("tgpayments", "tg_payments"):
        token = get_setting_fn("pay_tgpayments_secret", "")
        text = (
            "💳 <b>TG payments</b>\n\n"
            "Для работы этого способа необходимо настроить Telegram Payments через провайдера ЮKassa.\n\n"
            "❗️ <b>ШАГ 1: РЕГИСТРАЦИЯ</b>\n"
            'Обязательно <a href="https://yookassa.ru">зарегистрируйте магазин в ЮКассе по этой ссылке</a>\n\n'
            "После проверки документов ЮКассой переходите к настройке токена.\n\n"
            f"{st_icon} <b>Статус:</b> {st_text}\n"
            f"🔑 <b>Provider Token:</b> {mask_val(token)}\n\n"
            "Выберите действие:"
        )
        kb = InlineKeyboardMarkup([
            [btn_on, btn_off],
            [InlineKeyboardButton("🔗 Изменить Provider Token", callback_data="admin_pay_inp_tgpayments_token")],
            nav_row
        ])
        return text, kb

    elif p_key in ("cryptopay", "cryptobot"):
        token = get_setting_fn("pay_cryptopay_secret", "")
        text = (
            "💎 <b>Crypto Pay (@CryptoBot)</b>\n\n"
            "Счёт создаётся через официальный Crypto Pay API в текущей базовой валюте RUB или USD. "
            "Crypto Pay самостоятельно рассчитывает сумму во всех доступных монетах.\n\n"
            "⏱ Счёт действует <b>60 минут</b>. Автоматические проверки выполняются до 30-й минуты, "
            "затем пользователь может проверить оплату кнопкой «Я оплатил».\n\n"
            "🔒 Webhook настраивать не нужно — бот его не принимает.\n\n"
            "📋 <b>Подключение:</b>\n"
            "1. Откройте @CryptoBot → Crypto Pay → Create App.\n"
            "2. Скопируйте API-токен приложения и укажите его здесь.\n"
            "3. Включите способ оплаты.\n\n"
            f"{st_icon} <b>Статус:</b> {st_text}\n"
            f"🔐 <b>API-токен:</b> {mask_val(token)}\n\n"
            "Выберите действие:"
        )
        kb = InlineKeyboardMarkup([
            [btn_on, btn_off],
            [InlineKeyboardButton("🔐 Изменить API-токен", callback_data="admin_pay_inp_cryptopay_token")],
            nav_row
        ])
        return text, kb

    elif p_key == "yookassa":
        shop_id = get_setting_fn("pay_yookassa_shop_id", "")
        secret = get_setting_fn("pay_yookassa_secret", "")
        shop_val = shop_id if shop_id else "❌ Не задан"
        text = (
            "📱 <b>ЮKassa</b>\n\n"
            "Позволяет принимать оплату картами и через СБП по QR-коду, без Telegram Payments.\n\n"
            "📋 <b>Как получить доступ:</b>\n"
            "1. Зарегистрируйте магазин: yookassa.ru\n"
            "2. Перейдите: Настройки → API-интеграция\n"
            "3. Скопируйте Shop ID и сгенерируйте новый Secret Key\n\n"
            f"{st_icon} <b>Статус:</b> {st_text}\n"
            f"🏦 <b>Shop ID:</b> {html.escape(shop_val)}\n"
            f"🔑 <b>Secret Key:</b> {mask_val(secret)}\n\n"
            "Выберите действие:"
        )
        kb = InlineKeyboardMarkup([
            [btn_on, btn_off],
            [InlineKeyboardButton("🏢 Изменить Shop ID", callback_data="admin_pay_inp_yookassa_shop")],
            [InlineKeyboardButton("🔐 Изменить Secret Key", callback_data="admin_pay_inp_yookassa_secret")],
            nav_row
        ])
        return text, kb

    elif p_key == "wata":
        token = get_setting_fn("pay_wata_secret", "")
        text = (
            "🌊 <b>WATA</b>\n\n"
            "Приём платежей через WATA — российский эквайринг (карты + СБП).\n"
            "Минимальная сумма платежа: <b>10 ₽</b>.\n\n"
            "📋 <b>Инструкция по подключению:</b>\n"
            "1. Зарегистрируйтесь на сайте wata.pro\n"
            "2. В личном кабинете создайте JWT-токен (Профиль → API) и укажите его здесь.\n\n"
            f"{st_icon} <b>Статус:</b> {st_text}\n"
            f"🔑 <b>JWT-токен:</b> {mask_val(token)}\n\n"
            "Выберите действие:"
        )
        kb = InlineKeyboardMarkup([
            [btn_on, btn_off],
            [InlineKeyboardButton("🔑 Изменить JWT-токен", callback_data="admin_pay_inp_wata_token")],
            nav_row
        ])
        return text, kb

    elif p_key == "cardlink":
        shop_id = get_setting_fn("pay_cardlink_shop_id", "")
        token = get_setting_fn("pay_cardlink_secret", "")
        text = (
            "🔗 <b>Cardlink</b>\n\n"
            "Приём платежей картой и через СБП по прямой интеграции с cardlink.link.\n"
            "Минимальная сумма платежа: <b>10 ₽</b>.\n\n"
            f"{st_icon} <b>Статус:</b> {st_text}\n"
            f"🆔 <b>Shop ID:</b> {html.escape(shop_id if shop_id else '❌ Не задан')}\n"
            f"🔐 <b>API-токен:</b> {mask_val(token)}\n\n"
            "Выберите действие:"
        )
        kb = InlineKeyboardMarkup([
            [btn_on, btn_off],
            [InlineKeyboardButton("🆔 Изменить Shop ID", callback_data="admin_pay_inp_cardlink_shop")],
            [InlineKeyboardButton("🔐 Изменить API-токен", callback_data="admin_pay_inp_cardlink_token")],
            nav_row
        ])
        return text, kb

    else:
        title = p_key.capitalize()
        token = get_setting_fn(f"pay_{p_key}_secret", "")
        text = (
            f"💳 <b>{html.escape(title)}</b>\n\n"
            f"{st_icon} <b>Статус:</b> {st_text}\n"
            f"🔐 <b>Ключ / Токен:</b> {mask_val(token)}\n\n"
            "Выберите действие:"
        )
        kb = InlineKeyboardMarkup([
            [btn_on, btn_off],
            [InlineKeyboardButton("🔑 Изменить токен", callback_data=f"admin_pay_inp_{p_key}_token")],
            nav_row
        ])
        return text, kb

async def handle_payment_admin_callback(query, context, get_setting, set_setting) -> bool:
    data = query.data or ""

    if data.startswith("admin_pay_cfg_"):
        p_key = data.replace("admin_pay_cfg_", "")
        t_card, kb_card = render_gateway_card(p_key, get_setting)
        await query.edit_message_text(t_card, parse_mode="HTML", reply_markup=kb_card, disable_web_page_preview=True)
        return True

    if data.startswith("admin_pay_toggle_"):
        parts = data.split("_")
        p_key = parts[3]
        target_state = parts[4]
        set_setting(f"pay_{p_key}_enabled", target_state)
        t_card, kb_card = render_gateway_card(p_key, get_setting)
        await query.edit_message_text(t_card, parse_mode="HTML", reply_markup=kb_card, disable_web_page_preview=True)
        return True

    if data.startswith("admin_pay_inp_"):
        parts = data.split("_")
        p_key = parts[3]
        field = parts[4]
        context.user_data["admin_mode"] = "input_pay_param"
        target_setting = f"pay_{p_key}_shop_id" if field == "shop" else f"pay_{p_key}_secret"
        context.user_data["pay_target_key"] = target_setting
        context.user_data["pay_current_gateway"] = p_key

        name_map = {"shop": "Shop ID", "token": "API-токен / токен провайдера", "secret": "Secret Key"}
        f_name = name_map.get(field, "значение")
        prompt = (
            f"✏️ <b>Введите {f_name} для шлюза {p_key}:</b>\n\n"
            "Отправьте новое значение ответным текстовым сообщением в чат."
        )
        await query.message.reply_text(prompt, parse_mode="HTML")
        return True

    return False

async def handle_payment_admin_text(msg, user, context, set_setting, get_setting, admin_id) -> bool:
    if not msg or not msg.text:
        return False

    if user.id == admin_id and context.user_data.get("admin_mode") == "input_pay_param":
        target_k = context.user_data.pop("pay_target_key", None)
        curr_gw = context.user_data.pop("pay_current_gateway", "yookassa")
        context.user_data.pop("admin_mode", None)
        if target_k:
            val = msg.text.strip()
            set_setting(target_k, val)
            await msg.reply_text("✅ <b>Параметр успешно сохранён!</b>", parse_mode="HTML")
            t_card, kb_card = render_gateway_card(curr_gw, get_setting)
            await msg.reply_text(t_card, parse_mode="HTML", reply_markup=kb_card, disable_web_page_preview=True)
            return True
    return False
