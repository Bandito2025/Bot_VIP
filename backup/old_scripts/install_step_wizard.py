import sqlite3, re

db_path = "/opt/Bot_VIP/bot_data.db"
bot_path = "/opt/Bot_VIP/bot.py"

# 1. Добавляем недостающие колонки в БД (баланс, реф. коэффициент, лимит устройств, группа)
with sqlite3.connect(db_path) as conn:
    for sql in [
        "ALTER TABLE users ADD COLUMN balance INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN ref_coeff REAL DEFAULT 1.0",
        "ALTER TABLE user_keys ADD COLUMN limit_ip INTEGER DEFAULT 1",
        "ALTER TABLE user_keys ADD COLUMN group_name TEXT DEFAULT 'Основная'",
    ]:
        try:
            conn.execute(sql)
        except Exception:
            pass
    conn.commit()

with open(bot_path, "r", encoding="utf-8") as f:
    code = f.read()

# 2. Очищаем старый модуль ckm_, если он есть
code = re.sub(r"# =+\n# ⚙️ МОДУЛЬ КАСТОМНЫХ КЛЮЧЕЙ.*?# =+\n# 🔵 КНОПКА", "# ==============================================================================\n# 🔵 КНОПКА", code, flags=re.DOTALL)

wizard_module = '''
# ==============================================================================
# 👤 НОВАЯ КАРТОЧКА КЛИЕНТА И ПОШАГОВЫЙ МАСТЕР КЛЮЧЕЙ (КАК НА СКРИНШОТАХ)
# ==============================================================================
def is_any_admin_ckm(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = 'extra_admins'").fetchone()
            if row and str(user_id) in row[0].split(","):
                return True
    except Exception:
        pass
    return False

def render_single_user_dossier(target_id: int) -> tuple[str, InlineKeyboardMarkup]:
    info = get_user_info(target_id)
    if not info:
        return "Пользователь не найден в БД.", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="admin_users_menu")]])

    uid, uname, fname, joined, is_vip, is_ban, until, attempts, vpn_cfg, bot_lic, srv_id, sub_id, c_uuid, trial_u, has_exp, bot_blk, ref_by, ref_cnt, ref_days, disc_pct = info

    with sqlite3.connect(DB_PATH) as conn:
        for sql in [
            "ALTER TABLE users ADD COLUMN balance INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN ref_coeff REAL DEFAULT 1.0",
            "ALTER TABLE user_keys ADD COLUMN limit_ip INTEGER DEFAULT 1",
            "ALTER TABLE user_keys ADD COLUMN group_name TEXT DEFAULT 'Основная'",
        ]:
            try:
                conn.execute(sql)
            except Exception:
                pass

        u_extra = conn.execute("SELECT COALESCE(balance, 0), COALESCE(ref_coeff, 1.0) FROM users WHERE user_id = ?", (uid,)).fetchone()
        balance, ref_coeff = (int(u_extra[0]), float(u_extra[1])) if u_extra else (0, 1.0)

        pay_row = conn.execute("SELECT COUNT(*), MAX(created_at) FROM payments WHERE user_id = ?", (uid,)).fetchone()
        p_cnt = pay_row[0] if pay_row and pay_row[0] else 0
        p_last = pay_row[1] if pay_row and pay_row[1] else "нет"

        key_rows = conn.execute(
            "SELECT id, expires_at, is_active FROM user_keys WHERE user_id = ? ORDER BY id ASC",
            (uid,)
        ).fetchall()

    uname_str = f"@{html.escape(uname)}" if uname else "<i>_не указан_</i>"
    deliv_str = "<b>недоступен (блок)</b>" if bot_blk else "<b>доступен для сообщений</b>"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    keys_lines = []
    for kid, kexp, kact in key_rows:
        is_ok = kact == 1 and (not kexp or kexp == "Без срока" or kexp > now_str)
        icon = "🟢" if is_ok else "🔴"
        exp_disp = "без срока" if (not kexp or kexp == "Без срока") else kexp
        keys_lines.append(f"  {icon} Ключ #{kid} (до {exp_disp})")

    keys_block = "\\n".join(keys_lines) if keys_lines else "  <i>Нет ключей</i>"

    text = (
        f"👤 Username: {uname_str}\\n"
        f"📱 Telegram ID: <code>{uid}</code>\\n"
        f"📨 Статус доставки: {deliv_str}\\n"
        f"📧 E-mail в панели: <code>user_{uid}_</code>\\n"
        f"📅 Зарегистрирован: {joined}\\n"
        f"💰 Баланс: <b>{balance} ₽</b>\\n"
        f"📊 Реферальный коэффициент: <b>{ref_coeff:.1f}x</b>\\n\\n"
        f"🔑 <b>VPN-ключи ({len(key_rows)}):</b>\\n"
        f"{keys_block}\\n\\n"
        f"💳 <b>Оплаты:</b>\\n"
        f"  📊 Всего платежей: {p_cnt}\\n"
        f"  📅 Последняя оплата: {p_last}"
    )

    kb_rows = []
    for kid, _, _ in key_rows[:15]:
        kb_rows.append([InlineKeyboardButton(f"🔑 Ключ #{kid}", callback_data=f"ckm_kview_{kid}_{uid}")])

    kb_rows.append([InlineKeyboardButton("➕ Добавить ключ", callback_data=f"ckm_wgrp_{uid}")])
    kb_rows.append([InlineKeyboardButton("💬 Написать", callback_data=f"admin_uact_msg_{uid}")])
    kb_rows.append([
        InlineKeyboardButton(f"💰 Баланс: {balance} ₽", callback_data=f"ckm_balinfo_{uid}"),
        InlineKeyboardButton("➕ Пополнить", callback_data=f"ckm_baladd_{uid}"),
        InlineKeyboardButton("➖ Списать", callback_data=f"ckm_balsub_{uid}")
    ])
    kb_rows.append([InlineKeyboardButton(f"📊 Реферальный коэффициент: {ref_coeff:.1f}x", callback_data=f"ckm_refc_{uid}")])

    ban_txt = "✅ Разблокировать" if is_ban else "🚫 Заблокировать"
    kb_rows.append([InlineKeyboardButton(ban_txt, callback_data=f"admin_uact_ban_{uid}")])
    kb_rows.append([
        InlineKeyboardButton("⬅️ Назад", callback_data="admin_ulist_0"),
        InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")
    ])

    return text, InlineKeyboardMarkup(kb_rows)

def render_ckm_key_detail(kid: int, uid: int):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, COALESCE(group_name, 'Основная'), location_name, limit_gb, COALESCE(limit_ip, 1), expires_at, is_active, config_text FROM user_keys WHERE id = ?",
            (kid,)
        ).fetchone()
    if not row:
        return "❌ Ключ не найден.", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_back_u_{uid}")]])

    kid, grp, loc, lgb, lip, exp, act, cfg = row
    st = "🟢 Активен" if act else "🔴 Отключен / Истёк"
    gb_str = "без лимита" if not lgb or lgb <= 0 else f"{lgb} ГБ"
    exp_str = "без срока" if not exp or exp == "Без срока" else exp

    txt = (
        f"🔑 <b>Управление ключом #{kid}</b> (Клиент: <code>{uid}</code>)\\n\\n"
        f"📡 Статус: <b>{st}</b>\\n"
        f"📁 Группа: <b>{html.escape(grp)}</b>\\n"
        f"🖥 Сервер: <b>{html.escape(loc or 'Не указан')}</b>\\n"
        f"📊 Трафик: <b>{gb_str}</b>\\n"
        f"📅 Срок: <b>{exp_str}</b>\\n"
        f"💻 Устройств: <b>{lip}</b>"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 Изменить срок (дни)", callback_data=f"ckm_ked_{kid}_{uid}_days"),
            InlineKeyboardButton("📊 Изменить трафик (ГБ)", callback_data=f"ckm_ked_{kid}_{uid}_gb")
        ],
        [
            InlineKeyboardButton("💻 Изменить устр-ва", callback_data=f"ckm_ked_{kid}_{uid}_ip"),
            InlineKeyboardButton("🔄 Вкл / Выкл", callback_data=f"ckm_ktog_{kid}_{uid}")
        ],
        [InlineKeyboardButton("🗑 Удалить ключ", callback_data=f"ckm_kdel_{kid}_{uid}")],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_back_u_{uid}"),
            InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")
        ]
    ])
    return txt, kb

async def show_ckm_confirm_screen(message, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    wiz = context.user_data.get("ckm_wiz", {})
    uid = wiz.get("uid", 0)
    grp = wiz.get("group", "Основная")
    srv_name = wiz.get("srv_name", "🇩🇪 Германия")
    gb = wiz.get("gb", 0)
    days = wiz.get("days", 0)
    ips = wiz.get("ips", 1)

    gb_str = "без лимита" if gb == 0 else f"{gb} ГБ"
    days_str = "без срока" if days == 0 else f"{days} дн."

    txt = (
        "✅ <b>Подтверждение создания ключа</b>\\n\\n"
        f"📁 Группа: {html.escape(grp)}\\n"
        f"🖥 Сервер: {html.escape(srv_name)}\\n"
        f"📊 Трафик: {gb_str}\\n"
        f"📅 Срок: {days_str}\\n"
        f"💻 Устройств: {ips}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Создать ключ", callback_data=f"ckm_wcreate_{uid}")],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wstep_ip_{uid}"),
            InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
        ]
    ])
    if edit:
        await message.edit_text(txt, parse_mode="HTML", reply_markup=kb)
    else:
        await message.reply_text(txt, parse_mode="HTML", reply_markup=kb)

async def handle_ckm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    if not is_any_admin_ckm(user.id):
        await query.answer("⛔ Нет прав администратора.", show_alert=True)
        return
    data = query.data
    await query.answer()

    # Возврат в карточку пользователя
    if data.startswith("ckm_back_u_"):
        context.user_data["mode"] = None
        uid = int(data.split("_")[3])
        txt, kb = render_single_user_dossier(uid)
        await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    # Шаг 1: Выбор группы тарифов
    if data.startswith("ckm_wgrp_"):
        uid = int(data.split("_")[2])
        context.user_data["mode"] = None
        context.user_data["ckm_wiz"] = {"uid": uid}

        with sqlite3.connect(DB_PATH) as conn:
            g_rows = [r[0] for r in conn.execute("SELECT DISTINCT group_name FROM tariffs WHERE group_name != ''").fetchall()]
        groups = ["Основная"]
        for g in g_rows:
            if g not in groups:
                groups.append(g)

        kb_rows = []
        for idx, g in enumerate(groups):
            kb_rows.append([InlineKeyboardButton(f"📁 {g}", callback_data=f"ckm_wselgrp_{uid}_{idx}")])
        context.user_data["ckm_groups_list"] = groups
        kb_rows.append([InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")])

        txt = (
            f"➕ <b>Добавление ключа для ID:</b> <code>{uid}</code>\\n\\n"
            f"Выберите группу тарифов:"
        )
        await query.edit_message_text(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))
        raise ApplicationHandlerStop

    # Шаг 2: Выбор сервера
    if data.startswith("ckm_wselgrp_"):
        parts = data.split("_")
        uid, g_idx = int(parts[2]), int(parts[3])
        groups = context.user_data.get("ckm_groups_list", ["Основная"])
        grp_name = groups[g_idx] if g_idx < len(groups) else "Основная"

        wiz = context.user_data.setdefault("ckm_wiz", {"uid": uid})
        wiz["group"] = grp_name

        servers = get_all_servers_full() if "get_all_servers_full" in globals() else []
        kb_rows = []
        if servers:
            for s in servers:
                srv_id, srv_name = s[0], s[1]
                kb_rows.append([InlineKeyboardButton(f"🖥 {srv_name}", callback_data=f"ckm_wselsrv_{uid}_{srv_id}")])
        else:
            kb_rows.append([InlineKeyboardButton("🖥 🇩🇪 Германия", callback_data=f"ckm_wselsrv_{uid}_0")])

        kb_rows.append([InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")])
        txt = f"🖥 <b>Группа: {html.escape(grp_name)}</b>\\n\\nВыберите сервер:"
        await query.edit_message_text(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))
        raise ApplicationHandlerStop

    # Шаг 3: Ввод лимита трафика (ГБ)
    if data.startswith("ckm_wselsrv_") or data.startswith("ckm_wstep_gb_"):
        parts = data.split("_")
        if data.startswith("ckm_wselsrv_"):
            uid, srv_id = int(parts[2]), int(parts[3])
            srv_name = "🇩🇪 Германия"
            if "get_all_servers_full" in globals():
                for s in get_all_servers_full():
                    if s[0] == srv_id:
                        srv_name = s[1]
                        break
            wiz = context.user_data.setdefault("ckm_wiz", {"uid": uid})
            wiz["srv_id"] = srv_id
            wiz["srv_name"] = srv_name
        else:
            uid = int(parts[3])
            wiz = context.user_data.setdefault("ckm_wiz", {"uid": uid})

        context.user_data["mode"] = "ckm_wiz_gb"
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wgrp_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]
        ])
        txt = "📊 <b>Лимит трафика</b>\\n\\nВведите лимит в ГБ (0 = без лимита):"
        await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    # Возврат на шаг 4: Срок действия
    if data.startswith("ckm_wstep_days_"):
        uid = int(data.split("_")[3])
        context.user_data["mode"] = "ckm_wiz_days"
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wstep_gb_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]
        ])
        txt = "📅 <b>Срок действия</b>\\n\\nВведите количество дней (0 = без срока):"
        await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    # Возврат на шаг 5: Лимит устройств
    if data.startswith("ckm_wstep_ip_"):
        uid = int(data.split("_")[3])
        context.user_data["mode"] = "ckm_wiz_ip"
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wstep_days_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]
        ])
        txt = "💻 <b>Лимит устройств</b>\\n\\nВведите число от 1 до 999:"
        await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    # Шаг 6: Финальное создание ключа
    if data.startswith("ckm_wcreate_"):
        uid = int(data.split("_")[2])
        wiz = context.user_data.get("ckm_wiz", {})
        grp = wiz.get("group", "Основная")
        srv_id = wiz.get("srv_id", 0)
        srv_name = wiz.get("srv_name", "🇩🇪 Германия")
        gb = wiz.get("gb", 0)
        days = wiz.get("days", 0)
        ips = wiz.get("ips", 1)

        k_id, until_s, _, _ = await create_or_extend_user_key(uid, days=days, create_new=True)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE user_keys SET group_name = ?, server_id = ?, location_name = ?, limit_gb = ?, limit_ip = ? WHERE id = ?",
                (grp, srv_id, srv_name, gb, ips, k_id)
            )
            conn.commit()

        context.user_data["mode"] = None
        txt, kb = render_single_user_dossier(uid)
        await query.edit_message_text(f"✅ <b>Ключ #{k_id} успешно создан!</b>\\n\\n{txt}", parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    # Просмотр и управление конкретным ключом
    if data.startswith("ckm_kview_"):
        _, _, kid_s, uid_s = data.split("_")
        txt, kb = render_ckm_key_detail(int(kid_s), int(uid_s))
        await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    if data.startswith("ckm_ktog_"):
        _, _, kid_s, uid_s = data.split("_")
        kid, uid = int(kid_s), int(uid_s)
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT is_active FROM user_keys WHERE id = ?", (kid,)).fetchone()
            if row:
                conn.execute("UPDATE user_keys SET is_active = ? WHERE id = ?", (0 if row[0] else 1, kid))
                conn.commit()
        txt, kb = render_ckm_key_detail(kid, uid)
        await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    if data.startswith("ckm_kdel_"):
        _, _, kid_s, uid_s = data.split("_")
        kid, uid = int(kid_s), int(uid_s)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM user_keys WHERE id = ?", (kid,))
            conn.commit()
        txt, kb = render_single_user_dossier(uid)
        await query.edit_message_text(f"🗑 Ключ #{kid} удалён!\\n\\n{txt}", parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    if data.startswith("ckm_ked_"):
        _, _, kid_s, uid_s, field = data.split("_")
        kid, uid = int(kid_s), int(uid_s)
        context.user_data["mode"] = f"ckm_edit_{field}"
        context.user_data["ckm_kid"] = kid
        context.user_data["ckm_uid"] = uid
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_kview_{kid}_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]
        ])
        prompts = {
            "days": f"📅 <b>Срок действия Ключа #{kid}</b>\\n\\nВведите количество дней (0 = без срока, можно <code>+10</code> или <code>-5</code>):",
            "gb": f"📊 <b>Лимит трафика Ключа #{kid}</b>\\n\\nВведите лимит в ГБ (0 = без лимита, можно <code>+20</code> или <code>-10</code>):",
            "ip": f"💻 <b>Лимит устройств Ключа #{kid}</b>\\n\\nВведите число от 1 до 999 (можно <code>+1</code> или <code>-1</code>):"
        }
        await query.edit_message_text(prompts[field], parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    # Баланс и Реф. коэффициент
    if data.startswith("ckm_balinfo_"):
        await query.answer("Используйте кнопки ➕ Пополнить или ➖ Списать рядом с балансом.", show_alert=True)
        raise ApplicationHandlerStop

    if data.startswith("ckm_baladd_") or data.startswith("ckm_balsub_"):
        uid = int(data.split("_")[2])
        act = "add" if "baladd" in data else "sub"
        context.user_data["mode"] = f"ckm_bal_{act}"
        context.user_data["ckm_uid"] = uid
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")]])
        title = "➕ <b>Пополнение баланса</b>" if act == "add" else "➖ <b>Списание с баланса</b>"
        await query.edit_message_text(f"{title} (ID: <code>{uid}</code>)\\n\\nВведите сумму в рублях:", parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    if data.startswith("ckm_refc_"):
        uid = int(data.split("_")[2])
        context.user_data["mode"] = "ckm_ref_coeff"
        context.user_data["ckm_uid"] = uid
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")]])
        await query.edit_message_text(
            f"📊 <b>Реферальный коэффициент (ID: <code>{uid}</code>)</b>\\n\\n"
            f"Введите новое значение коэффициента (например: <code>1.0</code>, <code>1.5</code> или <code>2.0</code>):",
            parse_mode="HTML",
            reply_markup=kb
        )
        raise ApplicationHandlerStop

async def handle_ckm_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    if not mode or not mode.startswith("ckm_"):
        return
    user = update.effective_user
    if not is_any_admin_ckm(user.id):
        return

    text = update.message.text.strip()
    wiz = context.user_data.setdefault("ckm_wiz", {})
    uid = wiz.get("uid") or context.user_data.get("ckm_uid", user.id)

    # Шаг 3 -> Шаг 4 (после ввода ГБ спрашиваем Дни)
    if mode == "ckm_wiz_gb":
        if not text.isdigit():
            await update.message.reply_text("❌ Введите целое число (0 = без лимита):")
            raise ApplicationHandlerStop
        wiz["gb"] = int(text)
        context.user_data["mode"] = "ckm_wiz_days"
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wstep_gb_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]
        ])
        await update.message.reply_text("📅 <b>Срок действия</b>\\n\\nВведите количество дней (0 = без срока):", parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    # Шаг 4 -> Шаг 5 (после ввода Дней спрашиваем Устройства)
    if mode == "ckm_wiz_days":
        if not text.isdigit():
            await update.message.reply_text("❌ Введите количество дней числом (0 = без срока):")
            raise ApplicationHandlerStop
        wiz["days"] = int(text)
        context.user_data["mode"] = "ckm_wiz_ip"
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⬅️ Назад", callback_data=f"ckm_wstep_days_{uid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"ckm_back_u_{uid}")
            ]
        ])
        await update.message.reply_text("💻 <b>Лимит устройств</b>\\n\\nВведите число от 1 до 999:", parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    # Шаг 5 -> Шаг 6 (после ввода Устройств показываем окно Подтверждения)
    if mode == "ckm_wiz_ip":
        if not text.isdigit() or not (1 <= int(text) <= 999):
            await update.message.reply_text("❌ Введите число от 1 до 999:")
            raise ApplicationHandlerStop
        wiz["ips"] = int(text)
        context.user_data["mode"] = None
        await show_ckm_confirm_screen(update.message, context, edit=False)
        raise ApplicationHandlerStop

    # Редактирование существующего ключа
    if mode.startswith("ckm_edit_"):
        field = mode.split("ckm_edit_")[1]
        kid = context.user_data.get("ckm_kid", 0)
        context.user_data["mode"] = None
        now = datetime.now()
        try:
            with sqlite3.connect(DB_PATH) as conn:
                row = conn.execute("SELECT limit_gb, COALESCE(limit_ip, 1), expires_at FROM user_keys WHERE id = ?", (kid,)).fetchone()
                if row:
                    cur_gb, cur_ip, cur_exp = row
                    if field == "days":
                        if text == "0":
                            new_exp = "Без срока"
                        elif text.startswith("+") or text.startswith("-"):
                            base_dt = now
                            if cur_exp and cur_exp != "Без срока":
                                try:
                                    p = datetime.strptime(cur_exp, "%Y-%m-%d %H:%M:%S")
                                    if p > now:
                                        base_dt = p
                                except Exception:
                                    pass
                            new_exp = max(now, base_dt + timedelta(days=int(text))).strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            new_exp = (now + timedelta(days=int(text))).strftime("%Y-%m-%d %H:%M:%S")
                        conn.execute("UPDATE user_keys SET expires_at = ?, is_active = 1 WHERE id = ?", (new_exp, kid))
                    elif field == "gb":
                        val = max(0, (cur_gb or 0) + int(text)) if (text.startswith("+") or text.startswith("-")) else max(0, int(text))
                        conn.execute("UPDATE user_keys SET limit_gb = ? WHERE id = ?", (val, kid))
                    elif field == "ip":
                        val = max(1, (cur_ip or 1) + int(text)) if (text.startswith("+") or text.startswith("-")) else max(1, int(text))
                        conn.execute("UPDATE user_keys SET limit_ip = ? WHERE id = ?", (val, kid))
                    conn.commit()
        except Exception:
            await update.message.reply_text("❌ Некорректное число.")
            raise ApplicationHandlerStop

        txt, kb = render_ckm_key_detail(kid, uid)
        await update.message.reply_text(f"✅ Изменения сохранены!\\n\\n{txt}", parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    # Пополнение / списание баланса
    if mode in ("ckm_bal_add", "ckm_bal_sub"):
        context.user_data["mode"] = None
        try:
            amt = abs(int(text))
            delta = amt if mode == "ckm_bal_add" else -amt
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("UPDATE users SET balance = MAX(0, COALESCE(balance, 0) + ?) WHERE user_id = ?", (delta, uid))
                conn.commit()
        except Exception:
            await update.message.reply_text("❌ Введите сумму целым числом.")
            raise ApplicationHandlerStop
        txt, kb = render_single_user_dossier(uid)
        await update.message.reply_text(txt, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop

    # Изменение реферального коэффициента
    if mode == "ckm_ref_coeff":
        context.user_data["mode"] = None
        try:
            coeff = max(0.1, float(text.replace(",", ".")))
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("UPDATE users SET ref_coeff = ? WHERE user_id = ?", (coeff, uid))
                conn.commit()
        except Exception:
            await update.message.reply_text("❌ Введите число (например 1.5).")
            raise ApplicationHandlerStop
        txt, kb = render_single_user_dossier(uid)
        await update.message.reply_text(txt, parse_mode="HTML", reply_markup=kb)
        raise ApplicationHandlerStop
'''

# 3. Также обновляем команду /id, чтобы она выглядела как на скриншоте (с кнопкой На главную)
code = re.sub(
    r"async def cmd_id_handler\(update: Update, context: ContextTypes\.DEFAULT_TYPE\):.*?raise ApplicationHandlerStop",
    '''async def cmd_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🈴 На главную", callback_data="start_back_main")]])
    await update.effective_message.reply_text(
        f"🆔 <b>Ваш Telegram ID</b>\\n\\n<code>{u.id}</code>",
        parse_mode="HTML",
        reply_markup=kb
    )
    raise ApplicationHandlerStop''',
    code,
    flags=re.DOTALL
)

# Вставляем модуль перед блоком КНОПКА "МЕНЮ" (чтобы функция render_single_user_dossier переопределила старую)
if "# 🔵 КНОПКА" in code:
    code = code.replace("# ==============================================================================\n# 🔵 КНОПКА", wizard_module + "\n# ==============================================================================\n# 🔵 КНОПКА", 1)
else:
    code = code + "\n" + wizard_module

with open(bot_path, "w", encoding="utf-8") as f:
    f.write(code)

print("✅ Новая карточка клиента и пошаговый мастер создания ключей успешно установлены!")
