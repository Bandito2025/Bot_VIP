import re

bot_path = "/opt/Bot_VIP/bot.py"
with open(bot_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Вырезаем наш блок из самого низа (после main()), где он не успевал выполниться
marker = "# 🚀 ЕДИНЫЙ МОДУЛЬ: ГЛАВНОЕ МЕНЮ, РЕФЕРАЛКА, КЛЮЧИ КЛИЕНТА, ДОСЬЕ И МАСТЕР 3X-UI"
if marker not in code:
    print("❌ Сначала запусти apply_full_rebuild.py!")
    exit(1)

sep_idx = code.rfind("# ====", 0, code.index(marker))
module_code = code[sep_idx:]
base_code = code[:sep_idx].rstrip()

# 2. Внутри нашего модуля добавляем перехват текстовых кнопок ("🔑 Мои ключи", "🔗 Реферальная программа" и т.д.)
# и убираем нижнюю Reply-клавиатуру, чтобы работало чистое меню как на твоих скриншотах
old_msg_start = '''async def handle_all_custom_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    user = update.effective_user
    msg = update.effective_message'''

new_msg_start = '''async def handle_all_custom_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    user = update.effective_user
    msg = update.effective_message

    # Перехватываем нажатия на старые нижние кнопки Reply-клавиатуры
    if msg and msg.text and not mode:
        t_clean = msg.text.strip()
        if "Мои ключи" in t_clean:
            with sqlite3.connect(DB_PATH) as conn:
                k_ids = [r[0] for r in conn.execute("SELECT id FROM user_keys WHERE user_id = ? ORDER BY id ASC", (user.id,)).fetchall()]
            if len(k_ids) == 1:
                txt, kb = render_client_single_key_screen(k_ids[0], user.id)
            else:
                txt, kb = render_client_keys_list_screen(user.id)
            await msg.reply_text(txt, parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if "Реферальная программа" in t_clean or "Реферальная ссылка" in t_clean:
            bot_me = await context.bot.get_me()
            ref_link = f"https://t.me/{bot_me.username}?start=ref_{user.id}"
            with sqlite3.connect(DB_PATH) as conn:
                row = conn.execute("SELECT ref_count, ref_bonus_days FROM users WHERE user_id = ?", (user.id,)).fetchone()
                r_cnt, r_days = (row[0] or 0, row[1] or 0) if row else (0, 0)
            caption = (
                "👥 <b>ПРИГЛАШАЙ ДРУЗЕЙ В SVOII VPN — ПОЛУЧАЙ ДНИ ПОДПИСКИ!</b> 🎁\\n\\n"
                "Пользуйся быстрым интернетом бесплатно! Делись ссылкой с друзьями и сразу получай бонусные дни к своей подписке.\\n\\n"
                "📎 <b>Твоя персональная ссылка:</b>\\n"
                f"{ref_link}\\n"
                "───────────────────\\n"
                "🚀 <b>Как это работает:</b>\\n"
                "1️⃣ Отправь ссылку другу.\\n"
                "2️⃣ Друг регистрируется и оплачивает подписку.\\n"
                "3️⃣ Тебе СРАЗУ начисляются бонусные дни доступа! ⚡️\\n\\n"
                "Чем больше друзей подключается — тем дольше твой VPN работает абсолютно бесплатно! 🛡\\n"
                "───────────────────\\n"
                "📊 <b>Твоя статистика:</b>\\n\\n"
                f"✅ Уровень 1 (10%): {r_cnt} чел. — {r_days} дн."
            )
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")]])
            ref_media = get_setting("cms_ref_media", "")
            if ref_media:
                try:
                    await msg.reply_photo(photo=ref_media, caption=caption, parse_mode="HTML", reply_markup=kb)
                    raise ApplicationHandlerStop
                except Exception:
                    pass
            await msg.reply_text(caption, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
            raise ApplicationHandlerStop'''

module_code = module_code.replace(old_msg_start, new_msg_start, 1)

# 3. Также перехватываем стандартные callback-кнопки ключей из старого кода (key_manage_, my_key_, view_key_ и т.д.)
module_code = module_code.replace(
    'if data.startswith("ckey_view_") or data.startswith("key_open_") or data.startswith("mykey_"):',
    'if data.startswith(("ckey_view_", "key_open_", "mykey_", "key_info_", "key_manage_", "view_key_", "u_key_")):'
)
module_code = module_code.replace(
    'pattern=r"^(start_|back_to_main|main_menu|ref_program|client_ref|client_my_keys|ckey_|key_open_|mykey_|cms_|ckm_)"',
    'pattern=r"^(start_|back_to_main|main_menu|ref_program|client_ref|client_my_keys|ckey_|key_open_|mykey_|key_info_|key_manage_|view_key_|u_key_|cms_|ckm_)"'
)

# 4. Переименовываем старую функцию render_single_user_dossier в базовом коде, чтобы использовалась ТОЛЬКО наша новая!
base_code = base_code.replace("def render_single_user_dossier(", "def _old_unused_dossier(")
base_code = base_code.replace("async def render_my_keys_screen(", "async def _old_unused_my_keys(")

# Добавляем совместимую обертку render_my_keys_screen в наш модуль
compat_wrapper = '''
async def render_my_keys_screen(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    with sqlite3.connect(DB_PATH) as conn:
        k_ids = [r[0] for r in conn.execute("SELECT id FROM user_keys WHERE user_id = ? ORDER BY id ASC", (user_id,)).fetchall()]
    if len(k_ids) == 1:
        return render_client_single_key_screen(k_ids[0], user_id)
    return render_client_keys_list_screen(user_id)
'''
module_code = module_code + "\n" + compat_wrapper

# 5. САМОЕ ГЛАВНОЕ: Вставляем наш модуль ПЕРЕД def main(), чтобы он загружался ДО старта polling!
if "def main(" in base_code:
    idx_main = base_code.rfind("def main(")
    final_code = base_code[:idx_main] + "\n\n" + module_code + "\n\n" + base_code[idx_main:]
elif 'if __name__ ==' in base_code:
    idx_main = base_code.rfind('if __name__ ==')
    final_code = base_code[:idx_main] + "\n\n" + module_code + "\n\n" + base_code[idx_main:]
else:
    final_code = base_code + "\n\n" + module_code

with open(bot_path, "w", encoding="utf-8") as f:
    f.write(final_code)

print("✅ Модуль успешно перенесен ПЕРЕД функцией main() и активирован!")
