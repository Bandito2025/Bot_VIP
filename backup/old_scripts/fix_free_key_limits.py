bot_path = "/opt/Bot_VIP/bot.py"
with open(bot_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Исправляем синтаксическую опечатку из прошлого скрипта (old_step3_ tail) и возвращаем пошаговый выбор для FREE
bad_free_skip = '''            if not is_pro_version():
                # Фиксированный шаблон для FREE-версии: 60 дней / 2 устройства / безлимит трафика
                wiz["gb"] = 0
                wiz["days"] = 60
                wiz["ips"] = 2
                context.user_data["mode"] = None
                await show_ckm_confirm_screen(query.message, context, edit=True)
                raise ApplicationHandlerStop'''

code = code.replace(bad_free_skip, "")

# 2. Обновляем подсказки в кнопках Назад (шаги 4 и 5), чтобы админ видел лимиты FREE/PRO
code = code.replace(
    'await query.edit_message_text("📅 <b>Срок действия</b>\\n\\nВведите количество дней (0 = без срока):", parse_mode="HTML", reply_markup=kb)',
    'days_prompt = "📅 <b>Срок действия</b>\\n\\nВведите количество дней (0 = без срока):" if is_pro_version() else "📅 <b>Срок действия (FREE: от 1 до 60 дней)</b>\\n\\nВведите количество дней (максимум 60):"\n            await query.edit_message_text(days_prompt, parse_mode="HTML", reply_markup=kb)'
)

code = code.replace(
    'await query.edit_message_text("💻 <b>Лимит устройств</b>\\n\\nВведите число от 1 до 999:", parse_mode="HTML", reply_markup=kb)',
    'ip_prompt = "💻 <b>Лимит устройств</b>\\n\\nВведите число от 1 до 999:" if is_pro_version() else "💻 <b>Лимит устройств (FREE: 1 или 2)</b>\\n\\nВведите количество устройств (от 1 до 2):"\n            await query.edit_message_text(ip_prompt, parse_mode="HTML", reply_markup=kb)'
)

# 3. Обновляем проверку ввода текста в мастере создания ключей (ckm_wiz_gb -> ckm_wiz_days -> ckm_wiz_ip)
old_wiz_inputs = '''        if mode == "ckm_wiz_gb":
            if not text.isdigit():
                await msg.reply_text("❌ Введите целое число (0 = без лимита):")
                raise ApplicationHandlerStop
            wiz["gb"] = int(text)
            context.user_data["mode"] = "ckm_wiz_days"
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wstep_gb_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]])
            await msg.reply_text("📅 <b>Срок действия</b>\\n\\nВведите количество дней (0 = без срока):", parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if mode == "ckm_wiz_days":
            if not text.isdigit():
                await msg.reply_text("❌ Введите количество дней числом (0 = без срока):")
                raise ApplicationHandlerStop
            wiz["days"] = int(text)
            context.user_data["mode"] = "ckm_wiz_ip"
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wstep_days_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]])
            await msg.reply_text("💻 <b>Лимит устройств</b>\\n\\nВведите число от 1 до 999:", parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if mode == "ckm_wiz_ip":
            if not text.isdigit() or not (1 <= int(text) <= 999):
                await msg.reply_text("❌ Введите число от 1 до 999:")
                raise ApplicationHandlerStop
            wiz["ips"] = int(text)
            context.user_data["mode"] = None
            await show_ckm_confirm_screen(msg, context, edit=False)
            raise ApplicationHandlerStop'''

new_wiz_inputs = '''        if mode == "ckm_wiz_gb":
            if not text.isdigit():
                await msg.reply_text("❌ Введите целое число (0 = без лимита):")
                raise ApplicationHandlerStop
            wiz["gb"] = int(text)
            context.user_data["mode"] = "ckm_wiz_days"
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wstep_gb_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]])
            d_txt = "📅 <b>Срок действия</b>\\n\\nВведите количество дней (0 = без срока):" if is_pro_version() else "📅 <b>Срок действия (FREE-версия)</b>\\n\\nВведите количество дней <b>от 1 до 60</b>:"
            await msg.reply_text(d_txt, parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if mode == "ckm_wiz_days":
            if not text.isdigit():
                await msg.reply_text("❌ Введите количество дней числом:")
                raise ApplicationHandlerStop
            d_val = int(text)
            if not is_pro_version() and not (1 <= d_val <= 60):
                kb_up = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💎 Активировать PRO (Безлимит дней)", callback_data="lic_enter_pro")],
                    [InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")]
                ])
                await msg.reply_text(
                    "🔒 <b>Ограничение FREE-версии:</b> срок ключа можно выбрать только <b>от 1 до 60 дней</b> (без вечных ключей).\\n\\n"
                    "Введите число от 1 до 60 или активируйте PRO-лицензию:",
                    parse_mode="HTML",
                    reply_markup=kb_up
                )
                raise ApplicationHandlerStop
            wiz["days"] = d_val
            context.user_data["mode"] = "ckm_wiz_ip"
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wstep_days_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]])
            ip_txt = "💻 <b>Лимит устройств</b>\\n\\nВведите число от 1 до 999:" if is_pro_version() else "💻 <b>Лимит устройств (FREE-версия)</b>\\n\\nВведите количество устройств <b>от 1 до 2</b>:"
            await msg.reply_text(ip_txt, parse_mode="HTML", reply_markup=kb)
            raise ApplicationHandlerStop

        if mode == "ckm_wiz_ip":
            if not text.isdigit():
                await msg.reply_text("❌ Введите целое число:")
                raise ApplicationHandlerStop
            ip_val = int(text)
            if not is_pro_version() and not (1 <= ip_val <= 2):
                kb_up = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💎 Активировать PRO (До 999 устройств)", callback_data="lic_enter_pro")],
                    [InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")]
                ])
                await msg.reply_text(
                    "🔒 <b>Ограничение FREE-версии:</b> можно выбрать только <b>1 или 2 устройства</b> на ключ.\\n\\n"
                    "Введите 1 или 2, либо активируйте PRO-лицензию:",
                    parse_mode="HTML",
                    reply_markup=kb_up
                )
                raise ApplicationHandlerStop
            if is_pro_version() and not (1 <= ip_val <= 999):
                await msg.reply_text("❌ Введите число от 1 до 999:")
                raise ApplicationHandlerStop
            wiz["ips"] = ip_val
            context.user_data["mode"] = None
            await show_ckm_confirm_screen(msg, context, edit=False)
            raise ApplicationHandlerStop'''

code = code.replace(old_wiz_inputs, new_wiz_inputs, 1)

# 4. Обновляем плашку в админке
code = code.replace(
    "🆓 FREE (Лимит: 5 серверов / 50 ключей / Шаблон 60д-2устр)",
    "🆓 FREE (До 5 серверов / 50 ключей / Выбор до 60 дн. и до 2 устр.)"
)

with open(bot_path, "w", encoding="utf-8") as f:
    f.write(code)

print("✅ Выбор дней (1–60) и устройств (1–2) для FREE-версии успешно настроен!")
