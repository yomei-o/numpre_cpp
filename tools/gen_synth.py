# 評価用の合成スクリーンショットを作る（正解つき）。
#   python tools/gen_synth.py [枚数]  → testdata/synth/NNN.png と NNN.json
# 数字は型（gen_templates.py）に入れていないフォントで描く。
import os, sys, json, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "testdata", os.environ.get("SYNTH_DIR", "synth"))
FD = r"C:\Windows\Fonts"
HELD_OUT = ["Candara.ttf", "Candarab.ttf", "corbel.ttf", "corbelb.ttf", "constan.ttf",
            "cambria.ttc", "ebrima.ttf", "gadugi.ttf", "lucon.ttf", "pala.ttf",
            "sylfaen.ttf", "framd.ttf", "NotoSansJP-VF.ttf", "yumin.ttf", "micross.ttf",
            "segoeuil.ttf", "seguisb.ttf", "comic.ttf", "YuGothL.ttc", "calibril.ttf"]
STYLES = ["paper", "paper_memo", "dark", "tiles", "highlight"]


def solved_grid(rng):
    base = [[(3 * (r % 3) + r // 3 + c) % 9 + 1 for c in range(9)] for r in range(9)]
    perm = list(range(1, 10)); rng.shuffle(perm)
    g = [[perm[v - 1] for v in row] for row in base]
    bands = [0, 1, 2]; rng.shuffle(bands)
    rows = [b * 3 + i for b in bands for i in rng.sample(range(3), 3)]
    stacks = [0, 1, 2]; rng.shuffle(stacks)
    cols = [s * 3 + i for s in stacks for i in rng.sample(range(3), 3)]
    return [[g[r][c] for c in cols] for r in rows]


def text_center(d, cx, cy, s, font, fill):
    l, t, r, b = d.textbbox((0, 0), s, font=font)
    d.text((cx - (l + r) / 2, cy - (t + b) / 2), s, font=font, fill=fill)


def make(i, rng):
    style = STYLES[i % len(STYLES)]
    fontname = HELD_OUT[i % len(HELD_OUT)]
    W = rng.choice([540, 720, 1080])
    H = int(W * rng.uniform(1.9, 2.2))
    sol = solved_grid(rng)
    board = [[v if rng.random() < rng.uniform(0.3, 0.5) else 0 for v in row] for row in sol]
    user = [[0] * 9 for _ in range(9)]       # 解いている途中で入れた数字（盤の一部として読む）
    for r in range(9):
        for c in range(9):
            if board[r][c] == 0 and rng.random() < 0.15:
                user[r][c] = sol[r][c]
    dark = style == "dark"
    bg = (24, 24, 28) if dark else rng.choice([(255, 255, 255), (245, 243, 235), (190, 190, 162)])
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    margin = int(W * rng.uniform(0.01, 0.04))
    gw = W - 2 * margin
    p = gw / 9
    gx, gy = margin, int(H * rng.uniform(0.18, 0.3))
    ui = ImageFont.truetype(os.path.join(FD, "meiryo.ttc"), int(W * 0.05))
    fg = (230, 230, 230) if dark else (40, 40, 40)
    d.text((W * 0.3, gy - W * 0.12), "上級 パズル 1519", font=ui, fill=fg)
    d.rectangle([W * 0.1, H * 0.03, W * 0.9, H * 0.08], fill=(200, 220, 240))
    font = ImageFont.truetype(os.path.join(FD, fontname), int(p * rng.uniform(0.6, 0.8)))
    small = ImageFont.truetype(os.path.join(FD, fontname), int(p * 0.24))
    tile_cols = [(170, 35, 40), (235, 110, 40), (40, 170, 200), (40, 170, 140), (30, 110, 40),
                 (230, 30, 100), (60, 80, 190), (240, 90, 230), (120, 30, 150)]
    if style == "tiles":
        gap = max(2, int(p * 0.06))
        for r in range(9):
            for c in range(9):
                x0 = gx + c * p + gap + (gap if c % 3 == 0 else 0) * 0.5
                y0 = gy + r * p + gap + (gap if r % 3 == 0 else 0) * 0.5
                v = board[r][c] or user[r][c]
                col = tile_cols[v - 1] if v else (215, 213, 195)
                d.rounded_rectangle([x0, y0, gx + (c + 1) * p - gap, gy + (r + 1) * p - gap],
                                    radius=int(p * 0.12), fill=col)
                if v:
                    text_center(d, gx + (c + .5) * p, gy + (r + .5) * p, str(v), font, (255, 255, 255))
        for k in (3, 6):
            d.line([gx + k * p, gy, gx + k * p, gy + 9 * p], fill=(120, 120, 120), width=2)
            d.line([gx, gy + k * p, gx + 9 * p, gy + k * p], fill=(120, 120, 120), width=2)
    else:
        cellbg = (34, 34, 40) if dark else (255, 255, 255)
        d.rectangle([gx, gy, gx + 9 * p, gy + 9 * p], fill=cellbg)
        if style == "highlight":
            sr, sc = rng.randrange(9), rng.randrange(9)
            for k in range(9):
                for (r, c) in ((sr, k), (k, sc)):
                    d.rectangle([gx + c * p, gy + r * p, gx + (c + 1) * p, gy + (r + 1) * p], fill=(220, 232, 248))
            d.rectangle([gx + sc * p, gy + sr * p, gx + (sc + 1) * p, gy + (sr + 1) * p], fill=(187, 222, 251))
        thin = (90, 90, 100) if dark else (180, 180, 180)
        thick = (200, 200, 200) if dark else (20, 20, 20)
        for k in range(10):
            w = max(2, int(p * 0.05)) if k % 3 == 0 else 1
            col = thick if k % 3 == 0 else thin
            d.line([gx + k * p, gy, gx + k * p, gy + 9 * p], fill=col, width=w)
            d.line([gx, gy + k * p, gx + 9 * p, gy + k * p], fill=col, width=w)
        given = (235, 235, 235) if dark else (20, 20, 20)
        entered = (110, 170, 255) if dark else (40, 90, 200)
        for r in range(9):
            for c in range(9):
                cx, cy = gx + (c + .5) * p, gy + (r + .5) * p
                if board[r][c]:
                    text_center(d, cx, cy, str(board[r][c]), font, given)
                elif user[r][c]:
                    text_center(d, cx, cy, str(user[r][c]), font, entered)
                elif style == "paper_memo" and rng.random() < 0.5:
                    for m in rng.sample(range(1, 10), rng.randint(2, 4)):
                        text_center(d, gx + (c + (((m - 1) % 3) + .5) / 3) * p,
                                    gy + (r + (((m - 1) // 3) + .5) / 3) * p, str(m), small, (120, 120, 120))
    # 下の数字パッド（紛らわしい部品）
    py = gy + 9 * p + W * 0.08
    bfont = ImageFont.truetype(os.path.join(FD, "arial.ttf"), int(W * 0.06))
    for k in range(9):
        bx = W * (0.06 + 0.1 * k)
        d.rounded_rectangle([bx, py, bx + W * 0.085, py + W * 0.11], radius=8, fill=tile_cols[k])
        text_center(d, bx + W * 0.042, py + W * 0.055, str(k + 1), bfont, (255, 255, 255))
    truth = [[board[r][c] or user[r][c] for c in range(9)] for r in range(9)]
    return im, {"style": style, "font": fontname, "board": truth, "grid": [gx, gy, p]}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    os.makedirs(OUT, exist_ok=True)
    rng = random.Random(int(os.environ.get("SYNTH_SEED", "1519")))
    for i in range(n):
        im, meta = make(i, rng)
        base = os.path.join(OUT, f"{i:03d}")
        if i % 4 == 3:
            im.save(base + ".jpg", quality=70)
            meta["file"] = f"{i:03d}.jpg"
        else:
            im.save(base + ".png")
            meta["file"] = f"{i:03d}.png"
        with open(base + ".json", "w") as fp:
            json.dump(meta, fp)
    print(n, "images ->", OUT)


if __name__ == "__main__":
    main()
