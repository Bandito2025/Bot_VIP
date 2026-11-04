# Telegram VPN Bot (WPP Edition)

Коммерческий Telegram-бот для продажи и управления VPN-подписками на базе Web Panel Proxy (VLESS XHTTP + Hysteria 2).

## Установка в 1 клик

Выполните на чистом сервере под управлением Ubuntu или Debian:
```bash
git clone [https://github.com/Bandito2025/Bot_VIP.git](https://github.com/Bandito2025/Bot_VIP.git) /opt/tg_vpn_bot && cd /opt/tg_vpn_bot && ./install.sh
```

## Что входит в установку
* Автоматическое создание изолированного окружения Python venv
* Развертывание базы данных SQLite bot_data.db
* Интерактивная настройка переменных окружения .env
* Автозапуск и регистрация службы tg_vpn_bot в systemd
