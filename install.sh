#!/usr/bin/env bash
set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

clear
echo -e "${CYAN}======================================================${NC}"
echo -e "${GREEN}   🚀 АВТОУСТАНОВЩИК BOT_VIP (3X-UI + PROXY 2.7.0)    ${NC}"
echo -e "${CYAN}======================================================${NC}"
echo ""

# 1. Запрос и проверка лицензии (проверка покупки)
LICENSE_SERVER="http://pl.svoii-vpn.online:2096"
SERVER_IP=$(curl -s https://api.ipify.org || hostname -I | awk '{print $1}')

read -p "🔑 Введите ключ лицензии (покупки) бота: " LIC_KEY < /dev/tty
if [[ -z "$LIC_KEY" ]]; then
    echo -e "${RED}❌ Ошибка: Ключ лицензии не может быть пустым!${NC}"
    exit 1
fi

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
    echo -e "${RED}⛔ ОШИБКА ЛИЦЕНЗИИ: Ключ недействителен, не оплачен или уже привязан к другому IP!${NC}"
    echo -e "${YELLOW}Ответ сервера: ${VERIFY_RESP}${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Лицензия подтверждена! Привязка к IP ${SERVER_IP} выполнена.${NC}"

# 2. Установка системных пакетов
echo -e "${YELLOW}📦 Установка системных пакетов (Python 3, venv, git, sqlite3)...${NC}"
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git sqlite3 curl

# 3. Загрузка кода бота
INSTALL_DIR="/opt/Bot_VIP"
if [[ -d "$INSTALL_DIR/.git" ]]; then
    echo -e "${YELLOW}🔄 Обновление существующей папки $INSTALL_DIR...${NC}"
    cd "$INSTALL_DIR"
    git pull origin main || true
else
    echo -e "${YELLOW}📥 Загрузка Bot_VIP в $INSTALL_DIR...${NC}"
    rm -rf "$INSTALL_DIR"
    git clone https://github.com/Bandito2025/Bot_VIP.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# 4. Настройка виртуального окружения и зависимостей
echo -e "${YELLOW}🐍 Настройка виртуального окружения Python и библиотек...${NC}"
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
if [[ -f "$INSTALL_DIR/requirements.txt" ]]; then
    "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
fi
"$INSTALL_DIR/venv/bin/pip" install "python-telegram-bot>=21.0" httpx qrcode[pil] pillow aiohttp cryptography

# 5. Запись конфигурации .env
cat << ENVEOF > "$INSTALL_DIR/.env"
BOT_TOKEN=${BOT_TOKEN}
ADMIN_ID=${ADMIN_ID}
LICENSE_KEY=${LIC_KEY}
SUB_PORT=2096
ENVEOF

# Также обновляем дефолтные значения внутри bot.py под введенные BOT_TOKEN и ADMIN_ID
python3 - << PYEOF
bot_file = "$INSTALL_DIR/bot.py"
with open(bot_file, "r", encoding="utf-8") as f:
    c = f.read()
import re
c = re.sub(r'ADMIN_ID\s*=\s*int\(os\.getenv\("ADMIN_ID",\s*"\d+"\)\)', f'ADMIN_ID = int(os.getenv("ADMIN_ID", "${ADMIN_ID}"))', c)
with open(bot_file, "w", encoding="utf-8") as f:
    f.write(c)
PYEOF

# 6. Создание и запуск службы systemd
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
echo -e "${CYAN}• Папка бота:${NC} /opt/Bot_VIP"
echo -e "${CYAN}• ID Администратора:${NC} ${ADMIN_ID}"
echo -e "${CYAN}• Лицензия:${NC} ${LIC_KEY} (IP: ${SERVER_IP})"
echo -e "${CYAN}• Проверка статуса:${NC} systemctl status bot_vip"
echo -e "${GREEN}======================================================${NC}"
