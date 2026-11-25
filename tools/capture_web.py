# web のナンプレサイトを撮る（実験用。画像は testdata/web/ に置き、リポには入れない）。
#   python tools/capture_web.py [名前...]
import os, sys, asyncio
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "testdata", "web")

SITES = {
    "websudoku": "https://view.websudoku.com/?level=1",
    "websudoku_evil": "https://view.websudoku.com/?level=4",
    "sudokuweb": "https://www.sudokuweb.org/",
    "sudoku_game": "https://sudoku.game/",
    "sudokuonline_io": "https://www.sudokuonline.io/",
    "puzzle_sudoku": "https://www.puzzle-sudoku.com/",
    "livesudoku": "https://www.livesudoku.com/",
    "sudokukingdom": "https://www.sudokukingdom.com/",
    "s247sudoku": "https://www.247sudoku.com/",
    "free_sudoku": "https://www.free-sudoku.com/",
    "sudoku_coach": "https://sudoku.coach/en/play",
    "nyt_easy": "https://www.nytimes.com/puzzles/sudoku/easy",
    "sudoku_online_org": "https://www.sudoku-online.org/",
    "sudoku_kids": "https://www.sudoku.name/",
    "numpre_jp": "https://numpre.net/",
    "sudoku_cool": "https://www.sudokuoftheday.com/",
}

MODES = {
    "phone": dict(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True,
                  has_touch=True,
                  user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
                             "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"),
    "pc": dict(viewport={"width": 1366, "height": 900}, device_scale_factor=1),
}


ACCEPT_RE = (r"^\s*(accept( all)?( cookies)?|agree( and close)?|i agree|ok(ay)?|got it|allow( all)?|"
             r"consent|continue|close|dismiss|no thanks|同意(する)?|すべて(に)?同意|閉じる|×|✕|x)\s*$")

TIP_RE = r"(select a cell|tap a (cell|number)|click a cell|マスを(選|タップ)|タップして)"

# 盤（セルが 20 個以上ある要素か大きい canvas）を含まない、画面に貼り付いた要素を隠す。
# 同意バナー・広告の帯・案内の吹き出し・全面のモーダルをまとめて消す。
HIDE_JS = r"""
() => {
  const hasBoard = el => el.querySelectorAll('td, [class*="cell" i], [class*="square" i]').length >= 20 ||
      [...el.querySelectorAll('canvas')].some(c => c.getBoundingClientRect().width > 200);
  let n = 0;
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el);
    if (cs.position !== 'fixed' && cs.position !== 'sticky') continue;
    if (el.getBoundingClientRect().height === 0 || hasBoard(el)) continue;
    el.style.setProperty('display', 'none', 'important'); n++;
  }
  // 広告の iframe も（盤の上に被ることがある）
  for (const f of document.querySelectorAll('iframe')) {
    if (!hasBoard(f.parentElement || document.body)) { f.style.setProperty('visibility', 'hidden', 'important'); n++; }
  }
  document.documentElement.style.overflow = 'auto'; document.body.style.overflow = 'auto';
  return n;
}
"""


async def clean(page):
    """同意ボタンを押し、残った貼り付き要素を隠す。押した／隠した数を返す。"""
    import re
    clicked = 0
    for _ in range(2):
        for fr in page.frames:
            try:
                btns = fr.get_by_role("button", name=re.compile(ACCEPT_RE, re.I))
                for i in range(await btns.count()):
                    b = btns.nth(i)
                    if await b.is_visible():
                        await b.click(timeout=2000)
                        clicked += 1
            except Exception:
                pass
        await page.wait_for_timeout(800)
    # 盤に重なる案内の吹き出しは、それ自体をクリックすると閉じる（sudoku.com など）
    for fr in page.frames:
        try:
            tips = fr.get_by_text(re.compile(TIP_RE, re.I))
            for i in range(await tips.count()):
                t = tips.nth(i)
                if await t.is_visible():
                    await t.click(timeout=2000)
                    clicked += 1
                    await page.wait_for_timeout(800)
                    if await t.is_visible():        # 閉じなければ隠す
                        await t.evaluate("e => e.style.setProperty('display','none','important')")
        except Exception:
            pass
    await page.keyboard.press("Escape")
    hidden = await page.evaluate(HIDE_JS)
    await page.wait_for_timeout(500)
    return clicked, hidden


async def shot(browser, name, url, mode):
    ctx = await browser.new_context(**MODES[mode], locale="ja-JP")
    page = await ctx.new_page()
    path = os.path.join(OUT, f"{name}_{mode}.png")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(5000)
        clicked, hidden = await clean(page)
        await page.screenshot(path=path)
        print("ok  ", name, mode, f"clicked={clicked} hidden={hidden}")
    except Exception as e:
        print("FAIL", name, mode, str(e).splitlines()[0][:100])
    await ctx.close()


async def main(names):
    os.makedirs(OUT, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for n in names:
            for m in MODES:
                await shot(browser, n, SITES[n], m)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or list(SITES)))
