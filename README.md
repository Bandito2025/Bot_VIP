# ⚡ Telegram VPN Bot — Enterprise Multi-Panel Edition

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue?style=for-the-badge&logo=python" alt="Python Version" />
  <img src="https://img.shields.io/badge/Architecture-3X--UI%20%2B%20Web%20Panel%20Proxy-success?style=for-the-badge" alt="Architecture" />
  <img src="https://img.shields.io/badge/Protocols-VLESS%20%7C%20Hysteria%202%20%7C%20Trojan%20%7C%20Shadowsocks-orange?style=for-the-badge" alt="Protocols" />
  <img src="https://img.shields.io/badge/Database-SQLite%20WAL%20(Leak--Free)-lightgrey?style=for-the-badge&logo=sqlite" alt="SQLite" />
  <img src="https://img.shields.io/badge/OS-Ubuntu%20%2F%20Debian-E95420?style=for-the-badge&logo=ubuntu" alt="Ubuntu" />
</p>

---

## 📌 О проекте

**Telegram VPN Bot (Enterprise Edition)** — высокопроизводительный модульный Telegram-бот для коммерческой автоматизации VPN-сервисов любого масштаба. 

Архитектура системы объединяет классические панели **3X-UI** и движок **Web Panel Proxy (WPP v2.8+)**, обеспечивая одновременную работу с передовыми протоколами обхода блокировок: **VLESS (XTLS Reality, XHTTP)** и **Hysteria 2 (UDP-ускорение)**.

Включает встроенную защиту от утечек файловых дескрипторов (AutoClose SQLite Connection Factory), поддержку пулов соединений HTTPX и полностью автономный установщик в один клик.

---

## ✨ Ключевые возможности

### 🌐 Мульти-панельная гибридная маршрутизация
* **Одновременная работа с 3X-UI и Web Panel Proxy**: распределение пользователей по локациям и нодам без ручной перенастройки.
* **Поддержка протоколов**:
  * **VLESS + Reality / XHTTP** — маскировка под доверенный HTTPS-трафик.
  * **Hysteria 2** — высокая скорость на мобильных и нестабильных сетях.
  * **Trojan & Shadowsocks** — проверенная совместимость с широким спектром клиентов.
* **Единые Smart-подписки**: генерация ссылок и QR-кодов под клиенты Happ, V2rayN, Shadowrocket, Streisand, Nekobox, Sing-Box, Clash.

### 💳 Автоматизированный биллинг и эквайринг
* **Модуль фонового автоплатежа (`autopay.py`)**: циклическая верификация счетов без задержек интерфейса.
* **Поддержка методов оплаты**: Банковские карты (ЮKassa, Cardlink, WATA, Platega), Криптовалюты (CryptoBot), Telegram Stars.
* **Уведомления о продлении**: напоминания клиентам за 3, 2 и 1 день до окончания подписки.

### ⚙️ Интерактивные мастера управления (Wizard-система)
* **Мастер серверов (`server_wizard.py`)**: добавление, диагностика пинга, проверка API и отключение нод через инлайн-кнопки.
* **Мастер тарифов (`tariff_wizard.py`)**: создание тарифных планов (периоды, лимиты устройств, лимиты трафика, привязка к странам).
* **Ролевая модель (`staff_roles.py`)**: разграничение прав (Суперадмин, Администратор, Техподдержка).

### 🛡 Отказоустойчивость
* **FD Leak Protection**: исключение ошибки `[Errno 24] Too many open files`.
* **SQLite WAL-Mode**: режим параллельности чтения и записи без взаимных блокировок.
* **Изолированный сервис Systemd**: автоматический перезапуск при сбоях и расширенные лимиты (`LimitNOFILE=65535`).

---

## 📂 Структура проекта

```text
├── bot.py                  # Главная точка входа, диспетчер хэндлеров и Telegram API
├── server_wizard.py        # Интерактивное управление нодами (3X-UI / WPP)
├── tariff_wizard.py        # Управление тарифами, ценами и лимитами трафика
├── staff_roles.py          # Модуль RBAC (права персонала и саппорта)
├── panel_manager.py        # Унифицированный слой управления панелями
├── wpp_client.py           # Асинхронный клиент для REST API Web Panel Proxy
├── sub_server.py           # Сервер отдачи конфигураций подписок (FastAPI/Aiohttp)
├── sub_service.py          # Бизнес-логика формирования конфигов (Sing-Box/Clash/V2ray)
├── sub_web_ui.py           # Веб-страница отображения подписки пользователя
├── autopay.py              # Фоновый воркер опроса платежных шлюзов
├── payment_cards.py        # Обработка эквайринга и процессинга карт
├── bot_data.db             # Очищенная схема базы данных SQLite (23 таблицы)
├── install.sh              # Скрипт автоматического развертывания в 1 клик
├── requirements.txt        # Список production-зависимостей Python
└── .env.example            # Шаблон переменных окружения
🚀 Быстрая установка и запуск (в 1 клик)1. Требования к серверуОперационная система: Ubuntu 22.04 / 24.04 / 26.04 или Debian 11 / 12Права доступа: пользователь rootОкружение: чистый сервер со свободными портами под веб-сервер и подписки2. Команда установки в один кликПодключитесь к чистому серверу по SSH и запустите установщик одной строкой:Bashgit clone https://github.com/Bandito2025/Bot_VIP.git /opt/tg_vpn_bot && cd /opt/tg_vpn_bot && chmod +x install.sh && ./install.sh
3. Что делает скрипт установкиУстанавливает системные пакеты (python3-venv, sqlite3, curl, git).Разворачивает виртуальное окружение venv и компилирует зависимости из requirements.txt.Запрашивает токен вашего бота из @BotFather и ID администратора для генерации .env.Инициализирует базу данных bot_data.db с готовой чистой схемой таблиц.Регистрирует и запускает системную службу tg_vpn_bot.service с автозапуском при перезагрузке ОС.⚙️ Конфигурация (.env)Файл .env располагается в корневой папке проекта. Основные параметры:ПеременнаяОписаниеПример значенияBOT_TOKENHTTP API токен бота от BotFather1234567890:ABCdefGHIjklMNOpqrsTUVwxyzADMIN_IDTelegram ID главного администратора123456789DB_PATHАбсолютный путь к файлу SQLite базы данных/opt/tg_vpn_bot/bot_data.dbWPP_BASE_URLБазовый URL панели Web Panel Proxy[https://vpn.example.com:2096](https://vpn.example.com:2096)WPP_API_TOKENAPI-токен авторизации в панели WPPyour_secret_wpp_token_hereSUB_PORTПорт встроенного веб-сервера подписок8080DEFAULT_PREFIXПрефикс клиентских ключей в инбаундахvpn_🛠 Команды управления (Systemd)Bash# Проверить текущий статус работы
systemctl status tg_vpn_bot.service

# Посмотреть живые логи бота
journalctl -u tg_vpn_bot.service -f -n 50

# Перезапустить сервис
systemctl restart tg_vpn_bot.service

# Остановить бота
systemctl stop tg_vpn_bot.service
📋 Первоначальная настройка после запускаОткройте диалог с ботом в Telegram и отправьте команду /admin.Перейдите в раздел «Серверы» ➔ «Добавить сервер»:Для ноды 3X-UI: укажите IP, Порт панели, Логин, Пароль и выберите целевой Inbound.Для ноды Web Panel Proxy: укажите базовый URL панели и секретный токен доступа к API.Перейдите в «Тарифы» ➔ настройте стоимость, доступные периоды и привяжите к ним добавленные ноды.В разделе «Платежные системы» подключите необходимые платежные шлюзы, введя выданные мерчант-ключи.💾 Резервное копированиеДля создания полного бэкапа базы данных клиентов, подписок и конфигурации:Bashtar --exclude='venv' -czvf /root/bot_backup_$(date +%F).tar.gz -C /opt tg_vpn_bot

После вставки нажмите зеленую кнопку **«Commit changes...»** в правом верхнем углу страницы на GitHub, чтобы сохранить полный файл.

<ElicitationsGroup message="Что делаем дальше:">
  <Elicitation label="Синхронизировать сервер" query="Я нажал Commit changes на GitHub. Как подтянуть изменения на сервер через git pull?" />
  <Elicitation label="Начать установку" query="README сохранен. Давай протестируем установку бота по команде из инструкции." />
  <Elicitation label="Проверить разметку" query="Как проверить, правильно ли отображается сохраненный README на странице GitHub?" />
</ElicitationsGroup>
