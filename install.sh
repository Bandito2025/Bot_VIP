#!/usr/bin/env bash
set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

clear
echo -e "${CYAN}======================================================${NC}"
echo -e "${GREEN}   🚀 АВТОУСТАНОВЩИК BOT_VIP (FREE & PRO EDITION)     ${NC}"
echo -e "${CYAN}======================================================${NC}"
echo ""

LICENSE_SERVER="http://pl.svoii-vpn.online:2096"
SERVER_IP=$(curl -s https://api.ipify.org || hostname -I | awk '{print $1}')

echo -e "${YELLOW}💡 Введите купленный ключ (VIP-XXXX-XXXX-XXXX) для PRO-версии${NC}"
echo -e "${YELLOW}   или введите FREE (или нажмите Enter) для бесплатной версии (до 5 серверов / 50 ключей):${NC}"
read -p "🔑 Ключ лицензии [FREE]: " LIC_KEY < /dev/tty
LIC_KEY=${LIC_KEY:-FREE}

read -p "🤖 Введите токен вашего Telegram-бота (от @BotFather): " BOT_TOKEN < /dev/tty
if [[ -z "$BOT_TOKEN" ]]; then
    echo -e "${RED}❌ Ошибка: Токен бота обязателен!${NC}"
    exit 1
fi

read -p "🆔 Введите ваш Telegram ID Администратора: " ADMIN_ID < /dev/tty
if [[ -z "$ADMIN_ID" ]]; then
    echo -e "${RED}❌ Ошибка: ID администратора обязателен!${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}⏳ Проверка лицензии на сервере авторизации...${NC}"
VERIFY_RESP=$(curl -s "${LICENSE_SERVER}/api/verify_license?key=${LIC_KEY}&ip=${SERVER_IP}&admin_id=${ADMIN_ID}" || echo '{"status":"error"}')

if [[ "$VERIFY_RESP" != *'"status":"ok"'* ]]; then
    echo -e "${RED}⛔ ОШИБКА ЛИЦЕНЗИИ: Ключ недействителен, отключен или уже привязан к другому IP!${NC}"
    echo -e "${YELLOW}Ответ сервера: ${VERIFY_RESP}${NC}"
    exit 1
fi

if [[ "$VERIFY_RESP" == *'"tier":"pro"'* ]]; then
    LIC_TIER="pro"
    echo -e "${GREEN}💎 PRO-лицензия подтверждена! Привязка к IP ${SERVER_IP} выполнена (Без ограничений).${NC}"
else
    LIC_TIER="free"
    echo -e "${CYAN}🆓 Активирована FREE-версия (До 5 серверов, до 50 ключей, шаблон 60 дн. / 2 устр.).${NC}"
fi

echo -e "${YELLOW}📦 Установка системных пакетов (Python 3, venv, git, sqlite3)...${NC}"
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git sqlite3 curl

INSTALL_DIR="/opt/Bot_VIP"
if [[ -d "$INSTALL_DIR/.git" ]]; then
    cd "$INSTALL_DIR"
    git pull origin main || true
else
    rm -rf "$INSTALL_DIR"
    git clone https://github.com/Bandito2025/Bot_VIP.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

echo -e "${YELLOW}🐍 Настройка виртуального окружения Python и библиотек...${NC}"
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
with open(bot_file, "r", encoding="utf-8") as f:
    c = f.read()
c = re.sub(r'ADMIN_ID\s*=\s*int\(os\.getenv\("ADMIN_ID",\s*"\d+"\)\)', f'ADMIN_ID = int(os.getenv("ADMIN_ID", "${ADMIN_ID}"))', c)
with open(bot_file, "w", encoding="utf-8") as f:
    f.write(c)

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
