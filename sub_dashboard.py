import base64
import io
import urllib.parse

def build_sub_dashboard_html(sub_url: str, sub_id: str, user_info: dict, configs_raw: str) -> str:
    """Генерирует веб-дашборд подписки с расширенным набором программ для ПК, iOS и Android"""
    # 1. Генерация QR-кода
    qr_b64 = ""
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=6, border=1)
        qr.add_data(sub_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        qr_b64 = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        qr_b64 = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={urllib.parse.quote(sub_url)}"

    # 2. Конфигурации серверов
    cfg_lines = [l.strip() for l in configs_raw.strip().splitlines() if l.strip() and not l.strip().startswith("#")]
    cfg_count = len(cfg_lines)

    cfg_items_html = ""
    for idx, c in enumerate(cfg_lines, 1):
        name = f"Конфигурация #{idx}"
        if "#" in c:
            name = urllib.parse.unquote(c.split("#")[-1])
        proto = c.split("://")[0].upper() if "://" in c else "VPN"
        cfg_items_html += f"""
        <div class="cfg-item">
            <div class="cfg-info">
                <span class="badge-proto">{proto}</span>
                <span class="cfg-name">{name}</span>
            </div>
            <button class="btn-copy-small" onclick="navigator.clipboard.writeText('{c}'); alert('Конфигурация скопирована!');">📋 Копировать</button>
        </div>
        """

    # 3. Данные пользователя
    u_name = user_info.get("name", "Клиент")
    up_gb = user_info.get("up_gb", "0.00")
    down_gb = user_info.get("down_gb", "0.00")
    total_used = user_info.get("total_gb", "0.00")
    limit_gb = user_info.get("limit_gb", "Неограниченно")
    days_left = user_info.get("days_left", "∞")
    expire_str = user_info.get("expire_str", "Бессрочно")
    status_text = user_info.get("status", "Неограниченно")
    last_online = user_info.get("last_online", "Недавно")

    b64_sub = base64.b64encode(sub_url.encode()).decode()

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SVOII_VPN — Личный кабинет</title>
    <style>
        :root {{
            --bg-color: #0b111e;
            --card-bg: #141c2e;
            --card-sub: #1a253a;
            --border-color: #23314d;
            --text-main: #f8fafc;
            --text-muted: #8e9fb5;
            --accent-blue: #2563eb;
            --accent-btn: #1d4ed8;
            --accent-green: #10b981;
            --accent-purple: #8b5cf6;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        body {{ background: var(--bg-color); color: var(--text-main); display: flex; justify-content: center; min-height: 100vh; padding: 24px 16px; }}
        .wrapper {{ width: 100%; max-width: 820px; }}
        
        .header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }}
        .user-block {{ display: flex; align-items: center; gap: 14px; }}
        .avatar {{ width: 44px; height: 44px; background: var(--accent-blue); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 20px; }}
        .user-title {{ font-size: 18px; font-weight: 700; }}
        .user-sub {{ font-size: 12px; color: var(--text-muted); font-family: monospace; }}
        
        .banner {{ background: rgba(37, 99, 235, 0.12); border: 1px solid rgba(37, 99, 235, 0.3); border-radius: 12px; padding: 12px 16px; font-size: 13px; display: flex; align-items: center; gap: 10px; margin-bottom: 24px; color: #93c5fd; }}
        .banner a {{ color: #60a5fa; text-decoration: none; font-weight: 600; }}
        
        .main-stats {{ background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 20px; padding: 28px 24px; margin-bottom: 24px; }}
        .gauge-section {{ display: flex; align-items: center; gap: 32px; margin-bottom: 28px; }}
        .meter-circle {{ width: 110px; height: 110px; border-radius: 50%; border: 7px solid var(--card-sub); border-top-color: var(--accent-blue); display: flex; flex-direction: column; align-items: center; justify-content: center; }}
        .meter-circle .inf {{ font-size: 28px; line-height: 1; }}
        .meter-circle .sub {{ font-size: 10px; color: var(--text-muted); margin-top: 4px; }}
        .gauge-text .label {{ font-size: 13px; color: var(--text-muted); margin-bottom: 4px; }}
        .gauge-text .val {{ font-size: 38px; font-weight: 800; letter-spacing: -0.5px; line-height: 1.1; }}
        .gauge-text .limit {{ font-size: 14px; color: var(--text-muted); margin-top: 4px; }}
        
        .stat-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
        @media (max-width: 600px) {{ .stat-grid {{ grid-template-columns: repeat(2, 1fr); }} .gauge-section {{ gap: 20px; }} }}
        .stat-card {{ background: var(--card-sub); border: 1px solid var(--border-color); border-radius: 12px; padding: 14px 16px; }}
        .stat-card .c-label {{ font-size: 12px; color: var(--text-muted); margin-bottom: 6px; }}
        .stat-card .c-val {{ font-size: 15px; font-weight: 600; }}
        .badge-purple {{ display: inline-block; background: var(--accent-purple); color: #fff; font-size: 12px; padding: 2px 10px; border-radius: 6px; font-weight: 600; }}
        
        .tabs {{ display: flex; gap: 12px; border-bottom: 1px solid var(--border-color); margin-bottom: 20px; padding-bottom: 8px; }}
        .tab-btn {{ background: none; border: none; color: var(--text-muted); font-size: 15px; font-weight: 600; padding: 8px 14px; cursor: pointer; border-radius: 8px; display: flex; align-items: center; gap: 8px; transition: 0.15s; }}
        .tab-btn.active {{ color: #fff; background: var(--card-sub); border-bottom: 2px solid var(--accent-blue); }}
        .tab-pane {{ display: none; }}
        .tab-pane.active {{ display: block; }}
        
        /* Вкладка 1: Подписка */
        .sub-box {{ background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 16px; padding: 18px 20px; display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 16px; }}
        .sub-badge {{ background: rgba(16, 185, 129, 0.15); color: var(--accent-green); font-size: 12px; font-weight: 700; padding: 6px 12px; border-radius: 8px; }}
        .sub-content {{ flex: 1; min-width: 0; }}
        .sub-title {{ font-size: 13px; font-weight: 600; margin-bottom: 2px; }}
        .sub-link {{ font-size: 13px; color: var(--text-muted); font-family: monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .btn-act {{ width: 36px; height: 36px; background: var(--card-sub); border: 1px solid var(--border-color); border-radius: 8px; display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--text-main); font-size: 15px; }}
        
        .qr-card {{ background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 16px; padding: 24px; display: flex; align-items: center; gap: 24px; margin-bottom: 20px; }}
        .qr-img {{ width: 140px; height: 140px; border-radius: 12px; background: white; padding: 6px; flex-shrink: 0; }}
        .qr-text h3 {{ font-size: 16px; font-weight: 700; margin-bottom: 6px; }}
        .qr-text p {{ font-size: 13px; color: var(--text-muted); line-height: 1.5; }}
        
        /* Вкладка 2: Приложения и переключатели ОС */
        .os-selector {{ display: flex; gap: 8px; margin-bottom: 18px; flex-wrap: wrap; }}
        .os-btn {{ background: var(--card-bg); border: 1px solid var(--border-color); color: var(--text-muted); border-radius: 20px; padding: 7px 16px; font-size: 13px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 6px; transition: 0.15s; }}
        .os-btn.active {{ background: var(--card-sub); color: #fff; border-color: var(--accent-blue); }}
        .os-pane {{ display: none; }}
        .os-pane.active {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }}
        @media (max-width: 640px) {{ .os-pane.active {{ grid-template-columns: 1fr; }} }}
        
        .app-row {{ background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 14px; padding: 12px 14px; display: flex; align-items: center; justify-content: space-between; gap: 10px; }}
        .app-meta {{ display: flex; align-items: center; gap: 12px; min-width: 0; }}
        .app-logo {{ width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 15px; font-weight: 700; flex-shrink: 0; }}
        .app-name-box {{ min-width: 0; }}
        .app-title {{ font-size: 14px; font-weight: 600; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .app-dl-link {{ font-size: 11px; color: #60a5fa; text-decoration: none; display: inline-flex; align-items: center; gap: 2px; margin-top: 2px; }}
        .app-dl-link:hover {{ text-decoration: underline; }}
        
        .btn-add-primary {{ background: var(--accent-btn); color: #fff; text-decoration: none; font-size: 13px; font-weight: 600; padding: 8px 16px; border-radius: 8px; border: none; cursor: pointer; transition: 0.15s; white-space: nowrap; }}
        .btn-add-primary:hover {{ background: #2563eb; }}
        
        /* Вкладка 3: Конфиги */
        .cfg-item {{ background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 12px; padding: 14px 18px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; gap: 12px; }}
        .cfg-info {{ display: flex; align-items: center; gap: 12px; min-width: 0; }}
        .badge-proto {{ background: var(--card-sub); border: 1px solid var(--border-color); font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 6px; color: #93c5fd; }}
        .cfg-name {{ font-size: 14px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .btn-copy-small {{ background: var(--card-sub); border: 1px solid var(--border-color); color: var(--text-main); font-size: 12px; padding: 6px 12px; border-radius: 8px; cursor: pointer; flex-shrink: 0; }}
    </style>
</head>
<body>
    <div class="wrapper">
        <div class="header">
            <div class="user-block">
                <div class="avatar">S</div>
                <div>
                    <div class="user-title">SVOII_VPN</div>
                    <div class="user-sub">{sub_id} — {u_name}</div>
                </div>
            </div>
        </div>

        <div class="banner">
            <span>ℹ️</span>
            <span>Добро победит <a href="https://t.me/SVOII_VPN_BOT" target="_blank">https://t.me/SVOII_VPN_BOT</a></span>
        </div>

        <div class="main-stats">
            <div class="gauge-section">
                <div class="meter-circle">
                    <div class="inf">∞</div>
                    <div class="sub">Неограниченно</div>
                </div>
                <div class="gauge-text">
                    <div class="label">Использование</div>
                    <div class="val">{total_used} <span style="font-size: 20px; font-weight: 600;">GB</span></div>
                    <div class="limit">{limit_gb}</div>
                </div>
            </div>

            <div class="stat-grid">
                <div class="stat-card">
                    <div class="c-label">Осталось дней</div>
                    <div class="c-val">{days_left}</div>
                </div>
                <div class="stat-card">
                    <div class="c-label">Срок действия</div>
                    <div class="c-val">{expire_str}</div>
                </div>
                <div class="stat-card">
                    <div class="c-label">Статус</div>
                    <div class="c-val"><span class="badge-purple">{status_text}</span></div>
                </div>
                <div class="stat-card">
                    <div class="c-label">Загружено</div>
                    <div class="c-val">{down_gb} GB</div>
                </div>
                <div class="stat-card">
                    <div class="c-label">Отправлено</div>
                    <div class="c-val">{up_gb} GB</div>
                </div>
                <div class="stat-card">
                    <div class="c-label">Общий лимит</div>
                    <div class="c-val">{limit_gb}</div>
                </div>
                <div class="stat-card" style="grid-column: span 3;">
                    <div class="c-label">Был(а) в сети</div>
                    <div class="c-val">{last_online}</div>
                </div>
            </div>
        </div>

        <!-- ОСНОВНЫЕ ВКЛАДКИ -->
        <div class="tabs">
            <button class="tab-btn active" onclick="switchMainTab('sub', this)">🔗 Подписка</button>
            <button class="tab-btn" onclick="switchMainTab('apps', this)">🪟 Приложения</button>
            <button class="tab-btn" onclick="switchMainTab('cfgs', this)">📋 Конфиги ({cfg_count})</button>
        </div>

        <!-- 1. ПОДПИСКА -->
        <div id="main-sub" class="tab-pane active">
            <div class="sub-box">
                <div class="sub-badge">SUB</div>
                <div class="sub-content">
                    <div class="sub-title">Подписка</div>
                    <div class="sub-link">{sub_url}</div>
                </div>
                <button class="btn-act" onclick="navigator.clipboard.writeText('{sub_url}'); alert('Ссылка скопирована!');" title="Скопировать">📋</button>
            </div>

            <div class="qr-card">
                <img src="{qr_b64}" class="qr-img" alt="QR Code">
                <div class="qr-text">
                    <h3>Сканируйте телефоном</h3>
                    <p>Отсканируйте этот код в приложении (Happ, v2rayTun, Hiddify, Karing, Streisand) для мгновенного добавления всех серверов.</p>
                </div>
            </div>
        </div>

        <!-- 2. ПРИЛОЖЕНИЯ -->
        <div id="main-apps" class="tab-pane">
            <div class="os-selector">
                <button class="os-btn active" onclick="switchOS('windows', this)">💻 Windows / ПК</button>
                <button class="os-btn" onclick="switchOS('android', this)">🤖 Android</button>
                <button class="os-btn" onclick="switchOS('ios', this)">🍏 iOS</button>
                <button class="os-btn" onclick="switchOS('macos', this)">🍎 macOS</button>
            </div>

            <!-- 💻 WINDOWS / ПК -->
            <div id="os-windows" class="os-pane active">
                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#0284c7; color:#fff;">H</div>
                        <div class="app-name-box">
                            <div class="app-title">Happ (ПК / Windows)</div>
                            <a href="https://github.com/happ-proxy/happ-desktop/releases/latest" target="_blank" class="app-dl-link">Скачать EXE / MSIX ↗</a>
                        </div>
                    </div>
                    <a href="happ://import/{sub_url}" class="btn-add-primary">Добавить</a>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#0d9488; color:#fff;">🐰</div>
                        <div class="app-name-box">
                            <div class="app-title">Hiddify (Windows)</div>
                            <a href="https://github.com/hiddify/hiddify-app/releases/latest" target="_blank" class="app-dl-link">Скачать установщик ↗</a>
                        </div>
                    </div>
                    <a href="hiddify://install-sub?url={sub_url}" class="btn-add-primary">Добавить</a>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#4338ca; color:#fff;">K</div>
                        <div class="app-name-box">
                            <div class="app-title">Karing (Windows)</div>
                            <a href="https://github.com/KaringX/karing/releases/latest" target="_blank" class="app-dl-link">Скачать EXE / Store ↗</a>
                        </div>
                    </div>
                    <a href="karing://install-sub?url={sub_url}" class="btn-add-primary">Добавить</a>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#1e3a8a; color:#fff;">v2N</div>
                        <div class="app-name-box">
                            <div class="app-title">v2rayN (Windows)</div>
                            <a href="https://github.com/2dust/v2rayN/releases/latest" target="_blank" class="app-dl-link">Скачать ZIP ↗</a>
                        </div>
                    </div>
                    <button class="btn-add-primary" onclick="navigator.clipboard.writeText('{sub_url}'); alert('Ссылка скопирована! Вставьте в v2rayN через подписки.');">Копировать</button>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#3b82f6; color:#fff;">⚡</div>
                        <div class="app-name-box">
                            <div class="app-title">FlClash (Windows)</div>
                            <a href="https://github.com/chen08209/FlClash/releases/latest" target="_blank" class="app-dl-link">Скачать EXE ↗</a>
                        </div>
                    </div>
                    <a href="clash://install-config?url={sub_url}" class="btn-add-primary">Добавить</a>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#7c3aed; color:#fff;">🐱</div>
                        <div class="app-name-box">
                            <div class="app-title">NekoBox / NekoRay</div>
                            <a href="https://github.com/MatsuriDayo/nekoray/releases/latest" target="_blank" class="app-dl-link">Скачать ZIP ↗</a>
                        </div>
                    </div>
                    <button class="btn-add-primary" onclick="navigator.clipboard.writeText('{sub_url}'); alert('Ссылка скопирована! Вставьте в NekoBox из буфера.');">Копировать</button>
                </div>
            </div>

            <!-- 🤖 ANDROID -->
            <div id="os-android" class="os-pane">
                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#0284c7; color:#fff;">H</div>
                        <div class="app-name-box">
                            <div class="app-title">Happ</div>
                            <a href="https://github.com/happ-proxy/happ-android/releases/latest" target="_blank" class="app-dl-link">Скачать APK ↗</a>
                        </div>
                    </div>
                    <a href="happ://import/{sub_url}" class="btn-add-primary">Добавить</a>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#0f172a; border: 1px solid #38bdf8; color:#38bdf8;">V2</div>
                        <div class="app-name-box">
                            <div class="app-title">V2RayTun</div>
                            <a href="https://play.google.com/store/apps/details?id=com.v2raytun.android" target="_blank" class="app-dl-link">Google Play ↗</a>
                        </div>
                    </div>
                    <a href="v2raytun://install-sub?url={sub_url}" class="btn-add-primary">Добавить</a>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#1e3a8a; color:#fff;">V</div>
                        <div class="app-name-box">
                            <div class="app-title">V2RayNG</div>
                            <a href="https://github.com/2dust/v2rayNG/releases/latest" target="_blank" class="app-dl-link">Скачать APK ↗</a>
                        </div>
                    </div>
                    <a href="v2rayng://install-config?url={sub_url}" class="btn-add-primary">Добавить</a>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#4338ca; color:#fff;">K</div>
                        <div class="app-name-box">
                            <div class="app-title">Karing</div>
                            <a href="https://play.google.com/store/apps/details?id=com.karing.app" target="_blank" class="app-dl-link">Google Play ↗</a>
                        </div>
                    </div>
                    <a href="karing://install-sub?url={sub_url}" class="btn-add-primary">Добавить</a>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#0d9488; color:#fff;">🐰</div>
                        <div class="app-name-box">
                            <div class="app-title">Hiddify</div>
                            <a href="https://play.google.com/store/apps/details?id=app.hiddify.com" target="_blank" class="app-dl-link">Google Play ↗</a>
                        </div>
                    </div>
                    <a href="hiddify://install-sub?url={sub_url}" class="btn-add-primary">Добавить</a>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#0369a1; color:#fff;">📦</div>
                        <div class="app-name-box">
                            <div class="app-title">Sing-box</div>
                            <a href="https://github.com/SagerNet/sing-box/releases/latest" target="_blank" class="app-dl-link">GitHub APK ↗</a>
                        </div>
                    </div>
                    <a href="sing-box://import-remote-profile?url={sub_url}" class="btn-add-primary">Добавить</a>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#0f172a; border: 1px solid #475569; color:#f8fafc;">V2</div>
                        <div class="app-name-box">
                            <div class="app-title">V2Box</div>
                            <a href="https://play.google.com/store/apps/details?id=dev.hexasoftware.v2box" target="_blank" class="app-dl-link">Google Play ↗</a>
                        </div>
                    </div>
                    <a href="v2box://install-sub?url={sub_url}" class="btn-add-primary">Добавить</a>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#064e3b; color:#34d399; font-size:11px;">INCY</div>
                        <div class="app-name-box">
                            <div class="app-title">Incy</div>
                            <a href="https://play.google.com/store/apps/details?id=com.incy.vpn" target="_blank" class="app-dl-link">Google Play ↗</a>
                        </div>
                    </div>
                    <a href="incy://subscribe?url={sub_url}" class="btn-add-primary">Добавить</a>
                </div>
            </div>

            <!-- 🍏 IOS -->
            <div id="os-ios" class="os-pane">
                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#0284c7; color:#fff;">H</div>
                        <div class="app-name-box">
                            <div class="app-title">Happ</div>
                            <a href="https://apps.apple.com/app/happ-proxy-utility/id6504287215" target="_blank" class="app-dl-link">App Store ↗</a>
                        </div>
                    </div>
                    <a href="happ://import/{sub_url}" class="btn-add-primary">Добавить</a>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#1e1b4b; border: 1px solid #a855f7; color:#c084fc;">🚀</div>
                        <div class="app-name-box">
                            <div class="app-title">Streisand</div>
                            <a href="https://apps.apple.com/app/streisand/id6450534064" target="_blank" class="app-dl-link">App Store ↗</a>
                        </div>
                    </div>
                    <a href="streisand://import/{sub_url}" class="btn-add-primary">Добавить</a>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#0f172a; border: 1px solid #38bdf8; color:#38bdf8;">V2</div>
                        <div class="app-name-box">
                            <div class="app-title">V2RayTun</div>
                            <a href="https://apps.apple.com/app/v2raytun/id6476628186" target="_blank" class="app-dl-link">App Store ↗</a>
                        </div>
                    </div>
                    <a href="v2raytun://install-sub?url={sub_url}" class="btn-add-primary">Добавить</a>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#4338ca; color:#fff;">K</div>
                        <div class="app-name-box">
                            <div class="app-title">Karing</div>
                            <a href="https://apps.apple.com/app/karing/id6472431552" target="_blank" class="app-dl-link">App Store ↗</a>
                        </div>
                    </div>
                    <a href="karing://install-sub?url={sub_url}" class="btn-add-primary">Добавить</a>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#b45309; color:#fff;">🦊</div>
                        <div class="app-name-box">
                            <div class="app-title">FoXray</div>
                            <a href="https://apps.apple.com/app/foxray/id6448898396" target="_blank" class="app-dl-link">App Store ↗</a>
                        </div>
                    </div>
                    <button class="btn-add-primary" onclick="navigator.clipboard.writeText('{sub_url}'); alert('Ссылка скопирована! Вставьте в FoXray через кнопку +');">Копировать</button>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#3b82f6; color:#fff;">🚀</div>
                        <div class="app-name-box">
                            <div class="app-title">Shadowrocket</div>
                            <a href="https://apps.apple.com/app/shadowrocket/id932747118" target="_blank" class="app-dl-link">App Store ↗</a>
                        </div>
                    </div>
                    <a href="sub://{b64_sub}" class="btn-add-primary">Добавить</a>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#0f172a; border: 1px solid #475569; color:#f8fafc;">V2</div>
                        <div class="app-name-box">
                            <div class="app-title">V2Box</div>
                            <a href="https://apps.apple.com/app/v2box-v2ray-client/id6446814690" target="_blank" class="app-dl-link">App Store ↗</a>
                        </div>
                    </div>
                    <a href="v2box://install-sub?url={sub_url}" class="btn-add-primary">Добавить</a>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#064e3b; color:#34d399; font-size:11px;">INCY</div>
                        <div class="app-name-box">
                            <div class="app-title">Incy</div>
                            <a href="https://apps.apple.com/app/incy/id6477755359" target="_blank" class="app-dl-link">App Store ↗</a>
                        </div>
                    </div>
                    <a href="incy://subscribe?url={sub_url}" class="btn-add-primary">Добавить</a>
                </div>
            </div>

            <!-- 🍎 MACOS -->
            <div id="os-macos" class="os-pane">
                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#0284c7; color:#fff;">H</div>
                        <div class="app-name-box">
                            <div class="app-title">Happ (macOS)</div>
                            <a href="https://apps.apple.com/app/happ-proxy-utility/id6504287215" target="_blank" class="app-dl-link">Mac App Store ↗</a>
                        </div>
                    </div>
                    <a href="happ://import/{sub_url}" class="btn-add-primary">Добавить</a>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#0d9488; color:#fff;">🐰</div>
                        <div class="app-name-box">
                            <div class="app-title">Hiddify (macOS)</div>
                            <a href="https://github.com/hiddify/hiddify-app/releases/latest" target="_blank" class="app-dl-link">Скачать DMG ↗</a>
                        </div>
                    </div>
                    <a href="hiddify://install-sub?url={sub_url}" class="btn-add-primary">Добавить</a>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#4338ca; color:#fff;">K</div>
                        <div class="app-name-box">
                            <div class="app-title">Karing (macOS)</div>
                            <a href="https://apps.apple.com/app/karing/id6472431552" target="_blank" class="app-dl-link">Mac App Store ↗</a>
                        </div>
                    </div>
                    <a href="karing://install-sub?url={sub_url}" class="btn-add-primary">Добавить</a>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#0f172a; border: 1px solid #38bdf8; color:#38bdf8;">V2</div>
                        <div class="app-name-box">
                            <div class="app-title">V2RayTun (macOS)</div>
                            <a href="https://apps.apple.com/app/v2raytun/id6476628186" target="_blank" class="app-dl-link">Mac App Store ↗</a>
                        </div>
                    </div>
                    <a href="v2raytun://install-sub?url={sub_url}" class="btn-add-primary">Добавить</a>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#b45309; color:#fff;">🦊</div>
                        <div class="app-name-box">
                            <div class="app-title">FoXray (macOS)</div>
                            <a href="https://apps.apple.com/app/foxray/id6448898396" target="_blank" class="app-dl-link">Mac App Store ↗</a>
                        </div>
                    </div>
                    <button class="btn-add-primary" onclick="navigator.clipboard.writeText('{sub_url}'); alert('Ссылка скопирована!');">Копировать</button>
                </div>

                <div class="app-row">
                    <div class="app-meta">
                        <div class="app-logo" style="background:#3b82f6; color:#fff;">⚡</div>
                        <div class="app-name-box">
                            <div class="app-title">FlClash (macOS)</div>
                            <a href="https://github.com/chen08209/FlClash/releases/latest" target="_blank" class="app-dl-link">Скачать DMG ↗</a>
                        </div>
                    </div>
                    <a href="clash://install-config?url={sub_url}" class="btn-add-primary">Добавить</a>
                </div>
            </div>
        </div>

        <!-- 3. КОНФИГИ -->
        <div id="main-cfgs" class="tab-pane">
            {cfg_items_html}
        </div>
    </div>

    <script>
        function switchMainTab(name, btn) {{
            document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById('main-' + name).classList.add('active');
            btn.classList.add('active');
        }}

        function switchOS(osName, btn) {{
            document.querySelectorAll('.os-pane').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.os-btn').forEach(el => el.classList.remove('active'));
            document.getElementById('os-' + osName).classList.add('active');
            btn.classList.add('active');
        }}
    </script>
</body>
</html>"""
