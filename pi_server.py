#!/usr/bin/env python3
"""
电费查询中转服务器 - 树莓派 2B
ESP8266 数据: GET /       (纯文本)
管理页面:     GET /admin  (HTML)
更新Cookie:   GET /save?cookie=JSESSIONID=xxx
"""

import http.server
import urllib.request
import urllib.parse
import json
import os
import time

# ===== 配置 =====
COOKIE_FILE = "cookie.txt"
ID_CODE     = "ccde62938e362242cg26885790e70b62c9dz"
API_HOST    = "ssdf.sztu.edu.cn"
API_URL     = f"http://{API_HOST}/sdms-pay-weixin/service/ele/list?idCode={ID_CODE}"
REFERER     = f"http://{API_HOST}/sdms-pay-weixin/service/weixin/electric"
PORT        = 8080

# 缓存
cache     = {"data": None, "time": 0}
CACHE_TTL = 60

# ===== Cookie 管理 =====

def load_cookie():
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE) as f:
            c = f.read().strip()
            if c:
                return c
    return ""

def save_cookie(c):
    with open(COOKIE_FILE, 'w') as f:
        f.write(c)

# ===== API 请求 =====

def fetch_from_api(cookie_str):
    try:
        req = urllib.request.Request(API_URL)
        req.add_header('Cookie', cookie_str)
        req.add_header('Referer', REFERER)
        req.add_header('Accept', 'application/json, text/javascript, */*; q=0.01')
        req.add_header('X-Requested-With', 'XMLHttpRequest')
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.getcode() == 200:
                data = json.loads(resp.read().decode('utf-8'))
                if data.get('resultObject') and len(data['resultObject']) > 0:
                    return data
    except Exception as e:
        print(f"  [!] API: {e}")
    return None

def get_data():
    global cache
    if cache["data"] and (time.time() - cache["time"]) < CACHE_TTL:
        return cache["data"]

    cookie = load_cookie()
    if cookie:
        print(f"  [*] 尝试文件cookie: {cookie[:35]}...")
        data = fetch_from_api(cookie)
        if data:
            print("  [+] 成功")
            cache["data"] = data
            cache["time"] = time.time()
            return data

    return None

# ===== 管理页面 HTML =====

def build_admin_html(data, current_cookie):
    if data:
        t = data['resultObject'][0]
        y = data['resultObject'][1] if len(data['resultObject']) > 1 else t
        status_class = "ok"
        status_text  = "&#9989; Cookie 有效，数据正常"
        data_rows = (
            '<div class="row"><span>日期</span> ' + t['time'] + '</div>\n'
            '<div class="row"><span>剩余电量</span> ' + t['leftEleQuantity'] + ' kWh</div>\n'
            '<div class="row"><span>今日用电</span> ' + t['dailyUsedEleQuantity'] + ' kWh</div>\n'
            '<div class="row"><span>昨日用电</span> ' + y['dailyUsedEleQuantity'] + ' kWh</div>'
        )
    else:
        status_class = "err"
        status_text  = "&#10060; Cookie 已过期，请更新"
        data_rows    = '<div class="row" style="color:#666;">暂无数据 &mdash; 请更新 Cookie 后刷新</div>'

    # XSS 防护：转义 cookie 值
    safe_cookie = current_cookie.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')

    return '<!DOCTYPE html>\n<html lang="zh">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>电费查询</title>\n<style>\n* { box-sizing:border-box; margin:0; padding:0; }\nbody { font-family:-apple-system,"Microsoft YaHei",sans-serif; background:#1a1a2e; color:#eee; display:flex; justify-content:center; align-items:center; min-height:100vh; }\n.card { background:#16213e; border-radius:12px; padding:24px; width:90%; max-width:420px; box-shadow:0 4px 20px rgba(0,0,0,0.5); }\nh1 { font-size:20px; margin-bottom:16px; color:#e94560; text-align:center; }\n.status { padding:12px; border-radius:8px; margin-bottom:20px; text-align:center; font-size:14px; }\n.status.ok { background:#0f3460; color:#4ecca3; }\n.status.err { background:#3a0d0d; color:#e94560; }\n.row { margin-bottom:8px; font-size:14px; }\n.row span { color:#999; }\nlabel { display:block; font-size:13px; color:#999; margin:16px 0 6px; }\ninput { width:100%; padding:10px; border:1px solid #0f3460; border-radius:6px; background:#1a1a2e; color:#eee; font-size:13px; }\n.btn { display:block; width:100%; padding:10px; margin-top:12px; border:none; border-radius:6px; background:#e94560; color:#fff; font-size:15px; cursor:pointer; }\n.btn:hover { background:#c73652; }\n.hint { font-size:12px; color:#555; margin-top:14px; text-align:center; }\n</style>\n</head>\n<body>\n<div class="card">\n<h1>⚡ 电费查询管理</h1>\n<div class="status ' + status_class + '">' + status_text + '</div>\n' + data_rows + '\n<label>JSESSIONID Cookie</label>\n<form action="/save" method="get">\n<input type="text" name="cookie" placeholder="JSESSIONID=xxxxxxxx..." value="' + safe_cookie + '">\n<button class="btn" type="submit">更 新 Cookie</button>\n</form>\n<p class="hint">微信打开电费页 → Fiddler 抓包 → 复制 JSESSIONID → 粘贴更新</p>\n</div>\n</body>\n</html>'

# ===== HTTP Handler =====

class Handler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        # ---- /save?cookie=xxx ----
        if path == '/save':
            cookie = params.get('cookie', [''])[0].strip()
            if cookie.startswith('JSESSIONID='):
                save_cookie(cookie)
                # 清缓存
                global cache
                cache["data"] = None
                cache["time"] = 0
                print(f"  [+] Cookie 已更新: {cookie[:35]}...")
                self.send_response(302)
                self.send_header('Location', '/admin?ok=1')
                self.end_headers()
            else:
                self.send_response(400)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(b"ERR: cookie must start with JSESSIONID=")
            return

        # ---- /admin (管理页面) ----
        if path == '/admin':
            data = get_data()
            html = build_admin_html(data, load_cookie())
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
            return

        # ---- / (ESP8266 数据接口) ----
        data = get_data()
        if data:
            today = data['resultObject'][0]
            yest  = data['resultObject'][1] if len(data['resultObject']) > 1 else today
            body = f"OK\n{today['time']}\n{today['leftEleQuantity']}\n{today['dailyUsedEleQuantity']}\n{yest['dailyUsedEleQuantity']}\n"
            self.send_response(200)
        else:
            body = "ERR\ncookie expired\n"
            self.send_response(502)

        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, fmt, *args):
        print(f"  [{time.strftime('%H:%M:%S')}] {args[0]}")

# ===== 启动 =====

if __name__ == '__main__':
    print("=" * 50)
    print("  深圳技术大学 电费查询中转服务器")
    print(f"  数据接口:  http://Pi_IP:{PORT}/       (ESP8266)")
    print(f"  管理页面:  http://Pi_IP:{PORT}/admin   (浏览器)")
    print("=" * 50)
    httpd = http.server.HTTPServer(('0.0.0.0', PORT), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        httpd.shutdown()
