import sqlite3
import glob
import os

def run_migrations():
    base_dir = "/opt/Bot_VIP"
    patterns = [
        os.path.join(base_dir, "*.db"),
        os.path.join(base_dir, "data", "*.db"),
        "*.db",
        "data/*.db"
    ]
    
    db_files = set()
    for pattern in patterns:
        for f in glob.glob(pattern):
            db_files.add(os.path.abspath(f))

    for db_path in db_files:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS key_devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_id INTEGER NOT NULL,
                    hwid TEXT NOT NULL,
                    device_name TEXT,
                    ip TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_key_devices_key_id ON key_devices(key_id)")
            conn.commit()
            conn.close()
            print(f"[OK] Миграция выполнена для: {db_path}")
        except Exception as e:
            print(f"[ERR] Ошибка миграции {db_path}: {e}")

if __name__ == "__main__":
    run_migrations()
