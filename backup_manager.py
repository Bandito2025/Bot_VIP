import os
import glob
import sqlite3
import logging

logger = logging.getLogger("Bot_VIP")
DB_PATH = "/opt/Bot_VIP/bot_data.db"

def is_pro_version() -> bool:
    return True

def get_backups_list():
    patterns = [
        "/opt/Bot_VIP/backup/*/bot_data.db",
        "backup/*/bot_data.db",
        "/root/backups/*.db",
        "/opt/Bot_VIP/*.db"
    ]
    files = []
    for p in patterns:
        files.extend(glob.glob(p))
    valid = []
    for f in set(files):
        abs_f = os.path.abspath(f)
        if abs_f == os.path.abspath(DB_PATH) or "release_snapshot" in f:
            continue
        valid.append(f)
    return sorted(valid, key=lambda x: os.path.getmtime(x), reverse=True)

def auto_migrate_db(db_path=None):
    """Проверяет и добавляет недостающие колонки в user_keys"""
    target = db_path or DB_PATH
    if not os.path.exists(target):
        return
    try:
        with sqlite3.connect(target) as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='user_keys'")
            if cur.fetchone()[0] > 0:
                cols = [c[1] for c in cur.execute("PRAGMA table_info(user_keys)").fetchall()]
                needed = {
                    "group_name": "TEXT DEFAULT ''",
                    "server_id": "INTEGER DEFAULT NULL",
                    "location_name": "TEXT DEFAULT ''",
                    "limit_gb": "REAL DEFAULT 0",
                    "limit_ip": "INTEGER DEFAULT 1",
                    "history_log": "TEXT DEFAULT ''",
                    "sub_id": "TEXT DEFAULT ''",
                    "config_text": "TEXT DEFAULT ''"
                }
                for c_name, c_def in needed.items():
                    if c_name not in cols:
                        cur.execute(f"ALTER TABLE user_keys ADD COLUMN {c_name} {c_def}")
            conn.commit()
    except Exception as e:
        logger.error(f"Ошибка auto_migrate_db: {e}")

def auto_heal_empty_servers(conn):
    """Автоматическое восстановление серверов при запуске бота"""
    try:
        auto_migrate_db(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='servers'")
        if cur.fetchone()[0] == 0:
            return

        real_cnt = cur.execute(
            "SELECT COUNT(*) FROM servers WHERE host NOT LIKE '%127.0.0.1%' AND name NOT LIKE '%Наш канал%'"
        ).fetchone()[0]

        if real_cnt > 0:
            return

        cur.execute("DELETE FROM servers WHERE host LIKE '%127.0.0.1%' OR name LIKE '%Наш канал%'")
        backups = get_backups_list()

        for bf in backups:
            try:
                b_conn = sqlite3.connect(f"file:{bf}?mode=ro", uri=True)
                t_check = b_conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='servers'").fetchone()[0]
                if t_check == 0:
                    b_conn.close()
                    continue
                b_rows = b_conn.execute(
                    "SELECT * FROM servers WHERE host NOT LIKE '%127.0.0.1%' AND name NOT LIKE '%Наш канал%'"
                ).fetchall()
                b_cols = [c[1] for c in b_conn.execute("PRAGMA table_info(servers)").fetchall()]
                b_conn.close()

                if b_rows:
                    m_cols = [c[1] for c in cur.execute("PRAGMA table_info(servers)").fetchall()]
                    common = [c for c in b_cols if c in m_cols]
                    if not common:
                        continue
                    col_str = ", ".join(common)
                    ph_str = ", ".join(["?"] * len(common))
                    for r in b_rows:
                        row_dict = dict(zip(b_cols, r))
                        vals = [row_dict[c] for c in common]
                        if "is_active" in common:
                            vals[common.index("is_active")] = 1
                        cur.execute(f"INSERT OR REPLACE INTO servers ({col_str}) VALUES ({ph_str})", vals)
                    conn.commit()
                    logger.info(f"✅ Auto-heal: восстановлено {len(b_rows)} серверов из {bf}")
                    break
            except Exception:
                continue
    except Exception as e:
        logger.error(f"Ошибка auto_heal_empty_servers: {e}")

def restore_database_from_best_backup():
    """Ручное восстановление базы данных из лучшего архива"""
    backups = get_backups_list()
    if not backups:
        return False, "❌ В папке backup не найдено ни одного файла резервной копии."

    restored_srv = 0
    restored_users = 0
    src_folder = ""

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()

            # 1. Серверы
            for bf in backups:
                try:
                    b_conn = sqlite3.connect(f"file:{bf}?mode=ro", uri=True)
                    t_check = b_conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='servers'").fetchone()[0]
                    if t_check == 0:
                        b_conn.close()
                        continue
                    b_rows = b_conn.execute(
                        "SELECT * FROM servers WHERE host NOT LIKE '%127.0.0.1%' AND name NOT LIKE '%Наш канал%'"
                    ).fetchall()
                    b_cols = [c[1] for c in b_conn.execute("PRAGMA table_info(servers)").fetchall()]
                    b_conn.close()

                    if b_rows:
                        cur.execute("DELETE FROM servers WHERE host LIKE '%127.0.0.1%' OR name LIKE '%Наш канал%'")
                        m_cols = [c[1] for c in cur.execute("PRAGMA table_info(servers)").fetchall()]
                        common = [c for c in b_cols if c in m_cols]
                        col_str = ", ".join(common)
                        ph_str = ", ".join(["?"] * len(common))
                        for r in b_rows:
                            row_dict = dict(zip(b_cols, r))
                            vals = [row_dict[c] for c in common]
                            if "is_active" in common:
                                vals[common.index("is_active")] = 1
                            cur.execute(f"INSERT OR REPLACE INTO servers ({col_str}) VALUES ({ph_str})", vals)
                        restored_srv = len(b_rows)
                        src_folder = os.path.basename(os.path.dirname(bf)) or os.path.basename(bf)
                        break
                except Exception:
                    continue

            # 2. Клиенты
            cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='users'")
            if cur.fetchone()[0] > 0:
                u_cnt = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                if u_cnt == 0:
                    for bf in backups:
                        try:
                            b_conn = sqlite3.connect(f"file:{bf}?mode=ro", uri=True)
                            u_rows = b_conn.execute("SELECT * FROM users").fetchall()
                            u_cols = [c[1] for c in b_conn.execute("PRAGMA table_info(users)").fetchall()]
                            b_conn.close()
                            if u_rows:
                                m_cols = [c[1] for c in cur.execute("PRAGMA table_info(users)").fetchall()]
                                common = [c for c in u_cols if c in m_cols]
                                col_str = ", ".join(common)
                                ph_str = ", ".join(["?"] * len(common))
                                for r in u_rows:
                                    row_dict = dict(zip(u_cols, r))
                                    vals = [row_dict[c] for c in common]
                                    cur.execute(f"INSERT OR IGNORE INTO users ({col_str}) VALUES ({ph_str})", vals)
                                restored_users = len(u_rows)
                                break
                        except Exception:
                            continue

            conn.commit()

        auto_migrate_db(DB_PATH)

        if restored_srv > 0 or restored_users > 0:
            text = (
                "✅ <b>База данных успешно восстановлена!</b>\n\n"
                f"📁 <b>Архив:</b> <code>{src_folder}</code>\n"
                f"🌐 <b>Серверов восстановлено:</b> {restored_srv} шт. (все активированы)\n"
                f"👥 <b>Клиентов восстановлено:</b> {restored_users} чел.\n\n"
                "Все серверы сразу доступны в меню управления и в единой подписке."
            )
            return True, text
        else:
            return False, "⚠️ В найденных архивах не обнаружено рабочих серверов."
    except Exception as e:
        return False, f"❌ Ошибка при восстановлении: {e}"
