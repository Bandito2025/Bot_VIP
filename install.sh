#!/usr/bin/env bash
set -e

INSTALL_DIR="/opt/tg_vpn_bot"
SERVICE_NAME="tg_vpn_bot"

echo "=========================================="
echo "   Установка Telegram VPN Bot (WPP)       "
echo "=========================================="

# 1. Системные пакеты
apt-get update -y
apt-get install -y python3 python3-venv python3-pip curl git sqlite3

# 2. Создание рабочей директории
mkdir -p "$INSTALL_DIR"
cp -r ./* "$INSTALL_DIR/"
cd "$INSTALL_DIR"

# 3. Настройка виртуального окружения Python
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# 4. Настройка .env если файла нет
if [ ! -f .env ]; then
    echo ""
    read -rp "Введите токен бота из @BotFather: " input_token
    read -rp "Введите ваш Telegram ID: " input_admin_id
    read -rp "Введите URL Web-Panel-Proxy (например, https://vpn.site:2096): " input_url

    cat << ENV_EOF > .env
BOT_TOKEN=${input_token}
ADMIN_ID=${input_admin_id}
WPP_BASE_URL=${input_url}
DB_PATH=${INSTALL_DIR}/bot_data.db
ENV_EOF
    echo "✅ Файл .env сгенерирован."
fi

# 5. Регистрация и запуск службы systemd
cat << SERVICE_EOF > /etc/systemd/system/${SERVICE_NAME}.service
[Unit]
Description=Telegram VPN Bot Production Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python3 ${INSTALL_DIR}/bot.py
Restart=always
RestartSec=3
EnvironmentFile=${INSTALL_DIR}/.env

[Install]
WantedBy=multi-user.target
SERVICE_EOF

systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
systemctl restart ${SERVICE_NAME}

echo "=========================================="
echo "✅ Бот успешно установлен и запущен!"
echo "Статус службы: systemctl status ${SERVICE_NAME}"
echo "Логи бота: journalctl -u ${SERVICE_NAME} -f"
echo "=========================================="
