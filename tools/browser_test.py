# docs/ をローカルで配信し、playwright でサンプルを順に押して結果を取る＋画面のスクショ。
# usage: python tools/browser_test.py docs out_prefix
import sys, threading, http.server, functools
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
root, pre = sys.argv[1], sys.argv[2]
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8766), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 420, "height": 900})
    pg.on("console", lambda m: print("console:", m.text))
    pg.goto("http://127.0.0.1:8766/index.html")
    pg.screenshot(path=pre + "_top.png")
    n = pg.locator("button.sample").count()
    for i in range(n):
        pg.evaluate("document.getElementById('status').textContent=''")
        pg.locator("button.sample").nth(i).click()
        pg.wait_for_function("/解けました|答えが|答えがありません|読み込めません/.test(document.getElementById('status').textContent)", timeout=120000)
        print(pg.locator("button.sample").nth(i).get_attribute("data-src"), pg.text_content("#status"))
        pg.screenshot(path="%s_%d.png" % (pre, i), full_page=True)
    b.close()
srv.shutdown()
