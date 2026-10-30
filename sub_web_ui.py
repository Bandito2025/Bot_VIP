import html
import base64
from urllib.parse import quote

def build_sub_html_page(sub_url: str, key_name: str, expires_at: str, traffic_str: str, raw_config: str) -> bytes:
    enc_url = quote(sub_url, safe="")
    b64_url = base64.b64encode(sub_url.encode("utf-8")).decode("utf-8")
    safe_name = html.escape(key_name or "Bot_VIP")
    safe_exp = html.escape(expires_at or "Без срока")
    safe_tr = html.escape(traffic_str or "0.00 GB")

    page = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Подписка {safe_name} — Bot_VIP</title>
<style>
  :root {{
    --bg-main: #181920;
    --bg-card: #22242e;
    --bg-card-hover: #1b2e4b;
    --border-color: #323544;
    --border-active: #2563eb;
    --btn-blue: #1d6bf3;
    --btn-blue-hover: #3b82f6;
    --text-primary: #f3f4f6;
    --text-muted: #9ca3af;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, sans-serif; }}
  body {{ background: var(--bg-main); color: var(--text-primary); padding: 28px 16px; max-width: 860px; margin: 0 auto; }}
  .header-box {{ background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 14px; padding: 18px 20px; margin-bottom: 22px; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 14px; }}
  .header-title {{ font-size: 18px; font-weight: 600; margin-bottom: 4px; }}
  .header-meta {{ font-size: 13px; color: var(--text-muted); }}
  .copy-sub-btn {{ background: #2d303e; color: #fff; border: 1px solid #3f4356; padding: 9px 16px; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 500; transition: 0.2s; }}
  .copy-sub-btn:hover {{ background: #383c4e; }}

  /* Переключатель платформ (Android | iOS | Windows | macOS) */
  .tabs-bar {{ display: inline-flex; background: #121318; border: 1px solid #282a36; border-radius: 10px; padding: 4px; margin-bottom: 18px; flex-wrap: wrap; gap: 4px; }}
  .tab-btn {{ background: transparent; color: var(--text-muted); border: none; padding: 8px 16px; border-radius: 7px; font-size: 14px; font-weight: 500; cursor: pointer; display: flex; align-items: center; gap: 8px; transition: 0.18s; }}
  .tab-btn.active {{ background: #262936; color: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.4); }}
  .tab-btn:hover:not(.active) {{ color: #e5e7eb; }}

  /* Сетка карточек приложений 2 колонки как на скриншоте */
  .apps-grid {{ display: none; grid-template-columns: repeat(2, 1fr); gap: 12px; }}
  .apps-grid.active {{ display: grid; }}
  @media (max-width: 640px) {{ .apps-grid {{ grid-template-columns: 1fr; }} }}

  .app-card {{ background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 13px 16px; display: flex; align-items: center; justify-content: space-between; transition: 0.18s; }}
  .app-card:hover {{ background: var(--bg-card-hover); border-color: var(--border-active); }}
  .app-left {{ display: flex; align-items: center; gap: 13px; }}
  .app-icon {{ width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; flex-shrink: 0; }}
  .app-name {{ font-size: 15px; font-weight: 500; color: var(--text-primary); }}
  .app-sub {{ font-size: 11px; color: var(--text-muted); margin-top: 2px; }}
  .app-actions {{ display: flex; align-items: center; gap: 8px; }}
  .dl-link {{ color: var(--text-muted); text-decoration: none; font-size: 12px; padding: 6px 8px; border-radius: 6px; border: 1px solid transparent; }}
  .dl-link:hover {{ color: #fff; border-color: #3f4356; background: #2b2e3b; }}
  .add-btn {{ background: var(--btn-blue); color: #fff; text-decoration: none; border: none; padding: 7px 15px; border-radius: 7px; font-size: 13px; font-weight: 500; cursor: pointer; transition: 0.18s; white-space: nowrap; }}
  .add-btn:hover {{ background: var(--btn-blue-hover); }}

  /* Цвета иконок под скриншот */
  .ic-v2box {{ background: #000; color: #fff; border: 1px solid #333; }}
  .ic-v2rayng {{ background: #1e293b; color: #38bdf8; border: 1px solid #334155; }}
  .ic-singbox {{ background: #172554; color: #60a5fa; border: 1px solid #1e3a8a; }}
  .ic-v2raytun {{ background: #172554; color: #3b82f6; border: 1px solid #1d4ed8; }}
  .ic-happ {{ background: #1e3a8a; color: #60a5fa; }}
  .ic-incy {{ background: #064e3b; color: #34d399; border: 1px solid #047857; }}
  .ic-shadow {{ background: #fff; color: #4f46e5; }}
  .ic-streisand {{ background: #1e1b4b; color: #c084fc; border: 1px solid #4338ca; }}
  .ic-hiddify {{ background: #0f172a; color: #38bdf8; border: 1px solid #0284c7; }}
  .ic-clash {{ background: #1e293b; color: #f472b6; border: 1px solid #475569; }}
  .ic-flclash {{ background: #1f2937; color: #a78bfa; border: 1px solid #374151; }}
  .ic-karing {{ background: #14532d; color: #4ade80; }}
  .ic-throne {{ background: #31102f; color: #f43f5e; }}

  .toast {{ position: fixed; bottom: 22px; right: 22px; background: #10b981; color: #fff; padding: 11px 18px; border-radius: 9px; font-size: 14px; font-weight: 500; display: none; box-shadow: 0 4px 14px rgba(0,0,0,0.4); }}
</style>
</head>
<body>

<div class="header-box">
  <div>
    <div class="header-title">🔑 {safe_name}</div>
    <div class="header-meta">📊 Трафик: {safe_tr} (безлимит) &nbsp;•&nbsp; ⏳ До: {safe_exp}</div>
  </div>
  <button class="copy-sub-btn" onclick="copySubUrl()">📋 Скопировать ссылку подписки</button>
</div>

<div class="tabs-bar">
  <button class="tab-btn" id="tab-android" onclick="switchTab('android')">🤖 Android</button>
  <button class="tab-btn" id="tab-ios" onclick="switchTab('ios')">🍎 iOS</button>
  <button class="tab-btn" id="tab-windows" onclick="switchTab('windows')">💻 Windows (ПК)</button>
  <button class="tab-btn" id="tab-macos" onclick="switchTab('macos')">🍏 macOS / Linux</button>
</div>

<!-- ВКЛАДКА ANDROID (КАК НА СКРИНШОТЕ 2) -->
<div class="apps-grid" id="grid-android">
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-v2box">V2</div><div><div class="app-name">V2Box</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://play.google.com/store/apps/details?id=dev.hexasoftware.v2box" target="_blank">Скачать</a>
      <a class="add-btn" href="v2box://install-sub?url={enc_url}&name={quote(key_name)}">Добавить</a>
    </div>
  </div>
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-v2rayng">V</div><div><div class="app-name">V2RayNG</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://github.com/2dust/v2rayNG/releases" target="_blank">Скачать</a>
      <a class="add-btn" href="v2rayng://install-config?url={enc_url}">Добавить</a>
    </div>
  </div>
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-singbox">📦</div><div><div class="app-name">Sing-box</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://play.google.com/store/apps/details?id=io.nekohasekai.sfa" target="_blank">Скачать</a>
      <a class="add-btn" href="sing-box://import-remote-profile?url={enc_url}#{quote(key_name)}">Добавить</a>
    </div>
  </div>
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-v2raytun">V₂</div><div><div class="app-name">V2RayTun</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://play.google.com/store/apps/details?id=com.v2raytun.android" target="_blank">Скачать</a>
      <a class="add-btn" href="v2raytun://import/{sub_url}">Добавить</a>
    </div>
  </div>
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-happ">H</div><div><div class="app-name">Happ</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://play.google.com/store/apps/details?id=com.happproxy" target="_blank">Скачать</a>
      <a class="add-btn" href="happ://add/{sub_url}">Добавить</a>
    </div>
  </div>
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-incy">INCY</div><div><div class="app-name">Incy / Hiddify</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://play.google.com/store/apps/details?id=app.hiddify.com" target="_blank">Скачать</a>
      <a class="add-btn" href="hiddify://import/{sub_url}#{quote(key_name)}">Добавить</a>
    </div>
  </div>
</div>

<!-- ВКЛАДКА iOS (КАК НА СКРИНШОТЕ 1) -->
<div class="apps-grid" id="grid-ios">
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-shadow">🚀</div><div><div class="app-name">Shadowrocket</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://apps.apple.com/app/shadowrocket/id932747118" target="_blank">App Store</a>
      <a class="add-btn" href="sub://{b64_url}">Добавить</a>
    </div>
  </div>
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-v2box">V2</div><div><div class="app-name">V2Box</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://apps.apple.com/app/v2box-v2ray-client/id6446814690" target="_blank">App Store</a>
      <a class="add-btn" href="v2box://install-sub?url={enc_url}&name={quote(key_name)}">Добавить</a>
    </div>
  </div>
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-streisand">💠</div><div><div class="app-name">Streisand</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://apps.apple.com/app/streisand/id6450534064" target="_blank">App Store</a>
      <a class="add-btn" href="streisand://import/{sub_url}">Добавить</a>
    </div>
  </div>
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-v2raytun">V₂</div><div><div class="app-name">V2RayTun</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://apps.apple.com/app/v2raytun/id6476628951" target="_blank">App Store</a>
      <a class="add-btn" href="v2raytun://import/{sub_url}">Добавить</a>
    </div>
  </div>
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-happ">H</div><div><div class="app-name">Happ</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://apps.apple.com/app/happ-proxy-utility/id6504287215" target="_blank">App Store</a>
      <a class="add-btn" href="happ://add/{sub_url}">Добавить</a>
    </div>
  </div>
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-incy">INCY</div><div><div class="app-name">Incy / Karing</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://apps.apple.com/app/karing/id6472431552" target="_blank">App Store</a>
      <a class="add-btn" href="karing://install-config?url={enc_url}&name={quote(key_name)}">Добавить</a>
    </div>
  </div>
</div>

<!-- ВКЛАДКА WINDOWS (НАЙДЕННЫЕ ПК-ПРОГРАММЫ С АВТО-ИМПОРТОМ) -->
<div class="apps-grid" id="grid-windows">
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-hiddify">H</div><div><div class="app-name">Hiddify (Windows)</div><div class="app-sub">Рекомендуется для ПК</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://github.com/hiddify/hiddify-app/releases/latest" target="_blank">Скачать .exe</a>
      <a class="add-btn" href="hiddify://import/{sub_url}#{quote(key_name)}">Добавить</a>
    </div>
  </div>
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-v2raytun">V₂</div><div><div class="app-name">v2RayTun / Happ PC</div><div class="app-sub">Простой интерфейс</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://github.com/Happ-proxy/happ-desktop/releases" target="_blank">Скачать .exe</a>
      <a class="add-btn" href="happ://add/{sub_url}">Добавить</a>
    </div>
  </div>
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-clash">CV</div><div><div class="app-name">Clash Verge Rev</div><div class="app-sub">Мощный клиент с TUN</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://github.com/clash-verge-rev/clash-verge-rev/releases/latest" target="_blank">Скачать .exe</a>
      <a class="add-btn" href="clash://install-config?url={enc_url}&name={quote(key_name)}">Добавить</a>
    </div>
  </div>
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-flclash">FC</div><div><div class="app-name">FlClash</div><div class="app-sub">Material You дизайн</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://github.com/chen08209/FlClash/releases/latest" target="_blank">Скачать .exe</a>
      <a class="add-btn" href="flclash://install-config?url={enc_url}">Добавить</a>
    </div>
  </div>
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-karing">KR</div><div><div class="app-name">Karing (Windows)</div><div class="app-sub">Поддержка всех протоколов</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://github.com/KaringX/karing/releases/latest" target="_blank">Скачать .exe</a>
      <a class="add-btn" href="karing://install-config?url={enc_url}&name={quote(key_name)}">Добавить</a>
    </div>
  </div>
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-v2rayng">VN</div><div><div class="app-name">v2rayN / Throne (NekoBox)</div><div class="app-sub">Импорт через Ctrl+V</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://github.com/2dust/v2rayN/releases/latest" target="_blank">Скачать .zip</a>
      <button class="add-btn" onclick="copySubUrl()">Добавить (Буфер)</button>
    </div>
  </div>
</div>

<!-- ВКЛАДКА macOS / Linux -->
<div class="apps-grid" id="grid-macos">
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-hiddify">H</div><div><div class="app-name">Hiddify (macOS / Linux)</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://github.com/hiddify/hiddify-app/releases/latest" target="_blank">Скачать</a>
      <a class="add-btn" href="hiddify://import/{sub_url}#{quote(key_name)}">Добавить</a>
    </div>
  </div>
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-streisand">💠</div><div><div class="app-name">Streisand (Mac M1/M2/M3)</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://apps.apple.com/app/streisand/id6450534064" target="_blank">App Store</a>
      <a class="add-btn" href="streisand://import/{sub_url}">Добавить</a>
    </div>
  </div>
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-clash">CV</div><div><div class="app-name">Clash Verge Rev</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://github.com/clash-verge-rev/clash-verge-rev/releases/latest" target="_blank">Скачать</a>
      <a class="add-btn" href="clash://install-config?url={enc_url}&name={quote(key_name)}">Добавить</a>
    </div>
  </div>
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-flclash">FC</div><div><div class="app-name">FlClash (macOS / Linux)</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://github.com/chen08209/FlClash/releases/latest" target="_blank">Скачать</a>
      <a class="add-btn" href="flclash://install-config?url={enc_url}">Добавить</a>
    </div>
  </div>
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-v2box">V2</div><div><div class="app-name">V2Box (macOS)</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://apps.apple.com/app/v2box-v2ray-client/id6446814690" target="_blank">App Store</a>
      <a class="add-btn" href="v2box://install-sub?url={enc_url}&name={quote(key_name)}">Добавить</a>
    </div>
  </div>
  <div class="app-card">
    <div class="app-left"><div class="app-icon ic-karing">KR</div><div><div class="app-name">Karing (macOS)</div></div></div>
    <div class="app-actions">
      <a class="dl-link" href="https://github.com/KaringX/karing/releases/latest" target="_blank">Скачать</a>
      <a class="add-btn" href="karing://install-config?url={enc_url}&name={quote(key_name)}">Добавить</a>
    </div>
  </div>
</div>

<div class="toast" id="toast">✅ Ссылка подписки скопирована в буфер обмена!</div>

<script>
function switchTab(os) {{
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.apps-grid').forEach(g => g.classList.remove('active'));
  document.getElementById('tab-' + os).classList.add('active');
  document.getElementById('grid-' + os).classList.add('active');
}}

function copySubUrl() {{
  navigator.clipboard.writeText("{sub_url}");
  const t = document.getElementById('toast');
  t.style.display = 'block';
  setTimeout(() => {{ t.style.display = 'none'; }}, 2600);
}}

// Автоопределение ОС при открытии ссылки
(function() {{
  const ua = navigator.userAgent.toLowerCase();
  if (ua.includes("iphone") || ua.includes("ipad") || ua.includes("ipod")) {{
    switchTab('ios');
  }} else if (ua.includes("android")) {{
    switchTab('android');
  }} else if (ua.includes("macintosh") || ua.includes("mac os") || ua.includes("linux")) {{
    switchTab('macos');
  }} else {{
    switchTab('windows');
  }}
}})();
</script>
</body>
</html>"""
    return page.encode("utf-8")
