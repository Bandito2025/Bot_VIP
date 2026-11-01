#!/usr/bin/env bash
set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

clear
echo -e "${CYAN}======================================================${NC}"
echo -e "${GREEN}   🚀 УНИВЕРСАЛЬНЫЙ УСТАНОВЩИК BOT_VIP                ${NC}"
echo -e "${CYAN}======================================================${NC}"
echo ""

LICENSE_SERVER="http://pl.svoii-vpn.online:2097"
SERVER_IP=$(curl -s https://api.ipify.org || hostname -I | awk '{print $1}')

echo -e "${YELLOW}🔑 Введите лицензионный ключ (VIP-XXXX-XXXX-XXXX) для PRO-версии${NC}"
echo -e "${YELLOW}   или введите FREE (нажмите Enter) для бесплатной версии:${NC}"
read -p "Ключ лицензии [FREE]: " LIC_KEY < /dev/tty
LIC_KEY=${LIC_KEY:-FREE}

read -p "🤖 Введите токен вашего Telegram-бота: " BOT_TOKEN < /dev/tty
if [[ -z "$BOT_TOKEN" ]]; then
    echo -e "${RED}❌ Токен бота обязателен!${NC}"
    exit 1
fi

read -p "🆔 Введите ваш Telegram ID Администратора: " ADMIN_ID < /dev/tty
if [[ -z "$ADMIN_ID" ]]; then
    echo -e "${RED}❌ ID администратора обязателен!${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}⏳ Проверка лицензии...${NC}"
VERIFY_RESP=$(curl -s "${LICENSE_SERVER}/api/verify_license?key=${LIC_KEY}&ip=${SERVER_IP}&admin_id=${ADMIN_ID}" || echo '{"status":"error"}')

if [[ "$VERIFY_RESP" != *'"status":"ok"'* ]]; then
    echo -e "${RED}⛔ ОШИБКА: Ключ недействителен, отключен или привязан к другому IP!${NC}"
    echo -e "${YELLOW}Ответ: ${VERIFY_RESP}${NC}"
    exit 1
fi

if [[ "$VERIFY_RESP" == *'"tier":"pro"'* ]]; then
    LIC_TIER="pro"
    echo -e "${GREEN}💎 PRO-лицензия активна!${NC}"
else
    LIC_TIER="free"
    echo -e "${CYAN}🆓 Активирована FREE-версия (до 5 серверов / 50 ключей).${NC}"
fi

echo -e "${YELLOW}📦 Установка базовых пакетов...${NC}"
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git sqlite3 curl tar

INSTALL_DIR="/opt/Bot_VIP"
mkdir -p "$INSTALL_DIR"

# Выбор источника файлов: GitHub Token или Прямой архив с сервера
DOWNLOAD_SUCCESS=false

if [[ -n "$GH_TOKEN" ]]; then
    echo -e "${YELLOW}📥 Обнаружен GitHub Token, клонирую из приватного репозитория...${NC}"
    if git clone "https://${GH_TOKEN}@github.com/Bandito2025/Bot_VIP.git" "$INSTALL_DIR"; then
        DOWNLOAD_SUCCESS=true
    fi
fi

if [[ "$DOWNLOAD_SUCCESS" != "true" ]]; then
    echo -e "${YELLOW}📥 Скачивание архива бота с сервера обновлений (порт 2096)...${NC}"
    ARCHIVE_URL="${LICENSE_SERVER}/api/download_bot?key=${LIC_KEY}"
    if curl -sSL -f "$ARCHIVE_URL" -o /tmp/bot.tar.gz; then
        tar -xzf /tmp/bot.tar.gz -C "$INSTALL_DIR"
        rm -f /tmp/bot.tar.gz
        DOWNLOAD_SUCCESS=true
        echo -e "${GREEN}✅ Файлы бота успешно распакованы!${NC}"
    else
        echo -e "${RED}❌ Не удалось скачать архив с мастер-сервера.${NC}"
        echo -e "${YELLOW}Если хотите скачать из GitHub, введите ваш Personal Access Token (PAT):${NC}"
        read -p "GitHub Token (или оставьте пустым для отмены): " MANUAL_GH_TOKEN < /dev/tty
        if [[ -n "$MANUAL_GH_TOKEN" ]]; then
            git clone "https://${MANUAL_GH_TOKEN}@github.com/Bandito2025/Bot_VIP.git" "$INSTALL_DIR"
            DOWNLOAD_SUCCESS=true
        fi
    fi
fi

if [[ "$DOWNLOAD_SUCCESS" != "true" ]]; then
    echo -e "${RED}❌ Ошибка: не удалось получить файлы бота ни одним из способов.${NC}"
    exit 1
fi

echo -e "${YELLOW}🐍 Сборка Python окружения...${NC}"
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" --disable-pip-version-check install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" --disable-pip-version-check install "python-telegram-bot>=21.0" httpx qrcode[pil] pillow aiohttp cryptography

cat << ENVEOF > "$INSTALL_DIR/.env"
BOT_TOKEN=${BOT_TOKEN}
ADMIN_ID=${ADMIN_ID}
LICENSE_KEY=${LIC_KEY}
SUB_PORT=2096
ENVEOF

python3 - << PYEOF
import re, sqlite3
bot_file = "$INSTALL_DIR/bot.py"
db_file = "$INSTALL_DIR/bot_data.db"
try:
    with open(bot_file, "r", encoding="utf-8") as f:
        c = f.read()
    c = re.sub(r'ADMIN_ID\s*=\s*int\(os\.getenv\("ADMIN_ID",\s*"\d+"\)\)', f'ADMIN_ID = int(os.getenv("ADMIN_ID", "${ADMIN_ID}"))', c)
    with open(bot_file, "w", encoding="utf-8") as f:
        f.write(c)
except Exception:
    pass

with sqlite3.connect(db_file) as conn:
    conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('license_tier', ?)", ("${LIC_TIER}",))
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('license_key', ?)", ("${LIC_KEY}",))
    conn.commit()
PYEOF

cat << SVCEOF > /etc/systemd/system/bot_vip.service
[Unit]
Description=Bot_VIP Telegram & VPN Manager Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/Bot_VIP
EnvironmentFile=/opt/Bot_VIP/.env
ExecStart=/opt/Bot_VIP/venv/bin/python3 /opt/Bot_VIP/bot.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable bot_vip.service
systemctl restart bot_vip.service

echo ""
echo -e "${GREEN}======================================================${NC}"
echo -e "${GREEN}🎉 УСТАНОВКА УСПЕШНО ЗАВЕРШЕНА! БОТ ЗАПУЩЕН!${NC}"
echo -e "${CYAN}• Редакция:${NC} ${LIC_TIER^^} (${LIC_KEY})"
echo -e "${CYAN}• ID Администратора:${NC} ${ADMIN_ID}"
echo -e "${CYAN}• Проверка статуса:${NC} systemctl status bot_vip"
echo -e "${GREEN}======================================================${NC}"
