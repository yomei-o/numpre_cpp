# numpre.py — ナンプレの画像から盤面を読み取って解く（C++ 版 numpre.h と同じ手順）。
#   python numpre.py 画像.png [-o 結果.png]
# 依存: numpy（画像の読み書きだけ Pillow）。
import os, sys, struct
import numpy as np

FEAT = 20          # 数字の特徴は FEAT x FEAT
EDGE_T = 24        # 色の段差がこれ以上なら「縁」
SMALL = 400        # 粗探しの縮小後の長辺

# ---------------------------------------------------------------- 画像
def load_rgb(path):
    from PIL import Image
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.int32)

def to_gray(rgb):
    # 整数で（C++ と一致させるため）
    return (rgb[..., 0] * 77 + rgb[..., 1] * 150 + rgb[..., 2] * 29) >> 8

# ---------------------------------------------------------------- 盤の位置
def edge_maps(rgb):
    """縦の縁（左右の色差）と横の縁（上下の色差）の 0/1 マップ。"""
    H, W, _ = rgb.shape
    ev = np.zeros((H, W), np.uint8)
    eh = np.zeros((H, W), np.uint8)
    dx = np.abs(rgb[:, 1:] - rgb[:, :-1]).max(axis=2)
    dy = np.abs(rgb[1:] - rgb[:-1]).max(axis=2)
    ev[:, :-1] = dx >= EDGE_T
    eh[:-1] = dy >= EDGE_T
    return ev, eh

def pool_max(e, k):
    H, W = e.shape
    h, w = H // k, W // k
    return e[:h * k, :w * k].reshape(h, k, w, k).max(axis=(1, 3))

def dilate_x(e, r):
    out = e.copy()
    for d in range(1, r + 1):
        out[:, d:] |= e[:, :-d]
        out[:, :-d] |= e[:, d:]
    return out

def dilate_y(e, r):
    return dilate_x(e.T, r).T

ASPECTS = [0.70 + 0.05 * i for i in range(15)]   # 縦の刻み / 横の刻み（0.70〜1.40）

def lattice_scores(CV, CH, px, py, xs, ys):
    """左上 (x0,y0) の候補すべて（xs×ys）について、横刻み px・縦刻み py の 10 本×2 の線が縁に乗る割合。
    CV[y+1,x] = 列 x の縦の縁の y までの累積、CH[y,x+1] = 行 y の横の縁の累積。
    戻り値: 格子線の平均被覆 − 0.5×中間線（半マスずれ）の平均被覆。"""
    LX, LY = int(round(9 * px)), int(round(9 * py))
    X0, Y0 = np.meshgrid(xs, ys)          # 形 (len(ys), len(xs))
    on = np.zeros(X0.shape, np.float64)
    mid = np.zeros(X0.shape, np.float64)
    for k in range(19):
        ox, oy = int(round(k * px / 2)), int(round(k * py / 2))
        acc = on if k % 2 == 0 else mid
        # 縦線: x = x0+ox, y = y0..y0+LY
        acc += (CV[Y0 + LY, X0 + ox] - CV[Y0, X0 + ox]) / LY
        # 横線: y = y0+oy, x = x0..x0+LX
        acc += (CH[Y0 + oy, X0 + LX] - CH[Y0 + oy, X0]) / LX
    return on / 20.0 - 0.5 * mid / 18.0

def search(ev, eh, r, pairs, xr, yr):
    """縁マップ上で格子を総当たり。pairs は (px, py) の候補、xr, yr は x0, y0 の範囲 (lo, hi) 含む。"""
    H, W = ev.shape
    V = dilate_x(ev, r).astype(np.int32)
    Hh = dilate_y(eh, r).astype(np.int32)
    CV = np.zeros((H + 1, W), np.int32); CV[1:] = np.cumsum(V, axis=0)
    CH = np.zeros((H, W + 1), np.int32); CH[:, 1:] = np.cumsum(Hh, axis=1)
    best = (-1e9, 0.0, 0.0, 0, 0)
    for px, py in pairs:
        LX, LY = int(round(9 * px)), int(round(9 * py))
        x_lo, x_hi = max(0, xr[0]), min(W - 1 - LX, xr[1])
        y_lo, y_hi = max(0, yr[0]), min(H - 1 - LY, yr[1])
        if x_hi < x_lo or y_hi < y_lo:
            continue
        xs = np.arange(x_lo, x_hi + 1)
        ys = np.arange(y_lo, y_hi + 1)
        s = lattice_scores(CV, CH, px, py, xs, ys)
        i = int(np.argmax(s))       # 行優先で最初の最大（C++ も同じ順）
        iy, ix = divmod(i, s.shape[1])
        if s[iy, ix] > best[0] + 1e-12:
            best = (float(s[iy, ix]), px, py, int(xs[ix]), int(ys[iy]))
    return best

def frange(lo, hi, step):
    out, v = [], lo
    while v <= hi + 1e-9:
        out.append(v); v += step
    return out

def find_grid(rgb):
    """盤の左上 (x0, y0) と 1 マスの横・縦の大きさ px, py（画素）、10 本ずつの線の位置 xs, ys を返す。"""
    H, W, _ = rgb.shape
    ev, eh = edge_maps(rgb)
    k = max(1, -(-max(H, W) // SMALL))
    sv, sh = pool_max(ev, k), pool_max(eh, k)
    h, w = sv.shape
    m = min(h, w)
    pairs = [(p, p * a) for p in frange(m / 30.0, m / 9.0, 0.25) for a in ASPECTS]
    score, px, py, x0, y0 = search(sv, sh, 1, pairs, (0, w), (0, h))
    # 原寸で詰める
    PX, PY = px * k, py * k
    r = max(1, int(round(min(PX, PY) * 0.05)))
    st = max(0.25, k / 8.0)
    pairs = [(a, b) for a in frange(PX - k, PX + k, st) for b in frange(PY - k, PY + k, st)]
    score2, PX2, PY2, X0, Y0 = search(ev, eh, r, pairs,
                                      (x0 * k - 2 * k, x0 * k + 2 * k), (y0 * k - 2 * k, y0 * k + 2 * k))
    xs = refine_lines(ev, X0, Y0, PX2, PY2)
    ys = refine_lines(eh.T, Y0, X0, PY2, PX2)
    return {"x0": X0, "y0": Y0, "px": PX2, "py": PY2, "p": min(PX2, PY2),
            "score": score2, "coarse_score": score, "xs": xs, "ys": ys}

def refine_lines(ev, x0, y0, px, py):
    """10 本の縦線を 1 本ずつ合わせ直す（横線は転置して同じ関数）。
    線の近く ±0.2px の各列で縦の縁の被覆を数え、最大の半分以上ある列の最初と最後の真ん中に置く。
    タイル型なら隙間の両側の縁の真ん中、線なら線の太さの真ん中になる。"""
    H, W = ev.shape
    L = int(round(9 * py))
    ya, yb = max(0, y0), min(H, y0 + L)
    out = []
    for k in range(10):
        xk = x0 + k * px
        a = max(0, int(np.floor(xk - 0.2 * px)))
        b = min(W - 1, int(np.ceil(xk + 0.2 * px)))
        cov = ev[ya:yb, a:b + 1].sum(axis=0).astype(np.int64)
        mx = int(cov.max()) if cov.size else 0
        if mx * 5 < (yb - ya):           # 被覆 20% 未満なら動かさない
            out.append(float(xk))
            continue
        idx = np.nonzero(cov * 2 >= mx)[0]
        out.append((a + idx[0] + a + idx[-1]) / 2.0 + 0.5)
    return out

# ---------------------------------------------------------------- 数字
def resize_box(img, oh, ow):
    """ (ih, iw) → (oh, ow) を 4x4 点の双線形サンプル平均で縮小／拡大。C++ と同じ式。"""
    ih, iw = img.shape
    out = np.zeros((oh, ow), np.float64)
    for oy in range(oh):
        for ox in range(ow):
            acc = 0.0
            for sy in range(4):
                fy = (oy + (sy + 0.5) / 4) * ih / oh - 0.5
                fy = min(max(fy, 0.0), ih - 1.0)
                y0 = int(fy); y1 = min(y0 + 1, ih - 1); ty = fy - y0
                for sx in range(4):
                    fx = (ox + (sx + 0.5) / 4) * iw / ow - 0.5
                    fx = min(max(fx, 0.0), iw - 1.0)
                    x0 = int(fx); x1 = min(x0 + 1, iw - 1); tx = fx - x0
                    a = img[y0, x0] * (1 - tx) + img[y0, x1] * tx
                    b = img[y1, x0] * (1 - tx) + img[y1, x1] * tx
                    acc += a * (1 - ty) + b * ty
            out[oy, ox] = acc / 16.0
    return out

def digit_feature(mask):
    """前景 0..1 のマスク → 外接矩形で切り、縦横比を保って FEAT×FEAT の中央に置く。"""
    ys, xs = np.nonzero(mask > 0.5)
    if len(ys) == 0:
        return np.zeros((FEAT, FEAT))
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    crop = mask[y0:y1, x0:x1].astype(np.float64)
    h, w = crop.shape
    if h >= w:
        oh, ow = FEAT, max(1, int(round(w * FEAT / h)))
    else:
        ow, oh = FEAT, max(1, int(round(h * FEAT / w)))
    small = resize_box(crop, oh, ow)
    out = np.zeros((FEAT, FEAT))
    oy, ox = (FEAT - oh) // 2, (FEAT - ow) // 2
    out[oy:oy + oh, ox:ox + ow] = small
    return out

def otsu(g):
    hist = np.bincount(g.reshape(-1), minlength=256).astype(np.float64)
    n = hist.sum()
    tot = (hist * np.arange(256)).sum()
    best, bt = -1.0, 0
    w0 = s0 = 0.0
    for t in range(256):
        w0 += hist[t]; s0 += t * hist[t]
        w1 = n - w0
        if w0 == 0 or w1 == 0:
            continue
        m0, m1 = s0 / w0, (tot - s0) / w1
        v = w0 * w1 * (m0 - m1) ** 2
        if v > best:
            best, bt = v, t
    return bt   # g <= bt が暗い側

def NB4(y, x):
    return ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1))

def NB8(y, x):
    return ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1),
            (y - 1, x - 1), (y - 1, x + 1), (y + 1, x - 1), (y + 1, x + 1))

def components(binm, eight=False):
    """4 近傍（eight=True なら 8 近傍）の連結成分。ラベル配列と個数。走査順は行優先（C++ と同じ）。"""
    H, W = binm.shape
    lab = np.zeros((H, W), np.int32)
    n = 0
    for y in range(H):
        for x in range(W):
            if binm[y, x] and lab[y, x] == 0:
                n += 1
                st = [(y, x)]
                lab[y, x] = n
                while st:
                    cy, cx = st.pop()
                    for ny, nx in (NB8 if eight else NB4)(cy, cx):
                        if 0 <= ny < H and 0 <= nx < W and binm[ny, nx] and lab[ny, nx] == 0:
                            lab[ny, nx] = n
                            st.append((ny, nx))
    return lab, n

def cell_mask(gray, cx, cy, p, min_h):
    """マス中央付近を切り出し、(数字の前景マスク 0..1, 高さ) を返す。数字が無ければ None。
    高さ min_h 未満の成分（メモ書き・ごみ）は捨てる。"""
    half = int(round(p * 0.40))
    x0, y0 = int(round(cx)) - half, int(round(cy)) - half
    g = gray[max(0, y0):y0 + 2 * half, max(0, x0):x0 + 2 * half]
    if g.size == 0:
        return None
    t = otsu(g)
    lo = g <= t
    nlo = int(lo.sum()); nhi = g.size - nlo
    if nlo == 0 or nhi == 0:
        return None
    mlo, mhi = g[lo].mean(), g[~lo].mean()
    if mhi - mlo < 60:
        return None                      # 濃淡差が小さい＝空き
    fg_is_hi = nhi < nlo                 # 少ない側が数字
    fg = (~lo) if fg_is_hi else lo
    bgm, fgm = (mlo, mhi) if fg_is_hi else (mhi, mlo)
    soft = np.clip((g - bgm) / (fgm - bgm), 0.0, 1.0)
    lab, n = components(fg)
    H, W = g.shape
    keep = np.zeros_like(fg)
    kh = 0
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        h = ys.max() - ys.min() + 1
        w = xs.max() - xs.min() + 1
        if h < min_h:                    # 小さい（メモ書き・ごみ）
            continue
        if h > 0.95 * H or w > 0.95 * W:  # 枠線
            continue
        my, mx = ys.mean(), xs.mean()
        if abs(my - H / 2) > 0.25 * H or abs(mx - W / 2) > 0.25 * W:
            continue
        keep |= lab == i
        kh = max(kh, h)
    if not keep.any():
        return None
    # 輪郭のなじみ（0.5 未満の画素）を拾うため 1 画素広げる
    k2 = keep.copy()
    k2[1:] |= keep[:-1]; k2[:-1] |= keep[1:]
    k2[:, 1:] |= keep[:, :-1]; k2[:, :-1] |= keep[:, 1:]
    return soft * k2, kh

_TMPL = None
def templates():
    global _TMPL
    if _TMPL is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates.bin")
        with open(path, "rb") as fp:
            n, S = struct.unpack("<II", fp.read(8))
            labels = np.frombuffer(fp.read(n), np.uint8).astype(int)
            data = np.frombuffer(fp.read(n * S * S), np.uint8).reshape(n, S, S) / 255.0
        data = np.stack([blur(t) for t in data]).reshape(n, S * S)
        data = data - data.mean(axis=1, keepdims=True)
        data /= np.linalg.norm(data, axis=1, keepdims=True)
        _TMPL = (labels, data)
    return _TMPL

def blur(f):
    """[1 2 1]/4 を縦横に 2 回（端は複製）。照合のずれ・太さの差を吸収する。"""
    for _ in range(2):
        a = np.pad(f, 1, mode="edge")
        f = (a[:-2, 1:-1] + 2 * a[1:-1, 1:-1] + a[2:, 1:-1]) / 4
        a = np.pad(f, 1, mode="edge")
        f = (a[1:-1, :-2] + 2 * a[1:-1, 1:-1] + a[1:-1, 2:]) / 4
    return f

def holes(binm):
    """前景の穴（外とつながらない背景の 4 近傍連結成分。前景は斜めでもつながる扱い）の数。
    外接矩形の面積の 1.5% 未満の穴（にじみ・JPEG の粒）は数えない。"""
    ys, xs = np.nonzero(binm)
    if len(ys) == 0:
        return 0
    b = binm[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    pad = np.zeros((b.shape[0] + 2, b.shape[1] + 2), bool)
    pad[1:-1, 1:-1] = b
    lab, n = components(~pad)
    cnt = np.bincount(lab.reshape(-1), minlength=n + 1)
    amin = max(2.0, 0.015 * b.size)
    return int(sum(1 for i in range(2, n + 1) if cnt[i] >= amin))   # ラベル 1 は外側

# 数字ごとにあり得る穴の数
HOLES_OK = {1: (0,), 2: (0,), 3: (0,), 4: (0, 1), 5: (0,), 6: (1,), 7: (0,), 8: (2,), 9: (1,)}
HOLE_MARGIN = 0.15   # 穴の数で選び直すのは、一致度の差がこれ以内のときだけ

def classify(feat, nholes=None):
    labels, data = templates()
    f = blur(np.round(feat * 255) / 255.0)     # 型と同じ 8bit に丸めてからぼかす
    f = f.reshape(-1) - f.mean()
    nf = np.linalg.norm(f)
    if nf == 0:
        return 0, 0.0
    s = data @ (f / nf)
    i = int(np.argmax(s))
    if nholes is not None and nholes not in HOLES_OK[int(labels[i])]:
        j, sj = -1, -2.0
        for t in range(len(labels)):
            if nholes in HOLES_OK[int(labels[t])] and s[t] > sj:
                j, sj = t, s[t]
        if j >= 0 and sj >= s[i] - HOLE_MARGIN:
            i = j
    return int(labels[i]), float(s[i])

def recognize(rgb):
    g = find_grid(rgb)
    gray = to_gray(rgb)
    xs, ys, p = g["xs"], g["ys"], g["p"]
    board = [[0] * 9 for _ in range(9)]
    conf = [[0.0] * 9 for _ in range(9)]
    # 1 回目: 小さめまで拾い、盤の数字の高さの基準（中央値）を決める
    cells = {}
    for r in range(9):
        for c in range(9):
            m = cell_mask(gray, (xs[c] + xs[c + 1]) / 2, (ys[r] + ys[r + 1]) / 2, p, 0.15 * p)
            if m is not None:
                cells[(r, c)] = m
    hs = sorted(h for _, h in cells.values() if h >= 0.3 * p)
    href = hs[(len(hs) - 1) // 2] if hs else 0.5 * p
    # 2 回目: 基準の 55% 未満はメモ書きとして捨てる（オールドスタイル数字の 1, 2 は残る）
    for (r, c), (m, h) in sorted(cells.items()):
        if h < 0.55 * href:
            m = cell_mask(gray, (xs[c] + xs[c + 1]) / 2, (ys[r] + ys[r + 1]) / 2, p, 0.55 * href)
            if m is None:
                continue
            m = m[0]
        d, s = classify(digit_feature(m), holes(m > 0.5))
        board[r][c], conf[r][c] = d, s
    return board, conf, g

# ---------------------------------------------------------------- 解く
def solve(board, limit=2):
    """解の数（limit で打ち切り）と最初の解。制約の矛盾がある盤は 0。"""
    rows = [0] * 9; cols = [0] * 9; boxes = [0] * 9
    g = [row[:] for row in board]
    for r in range(9):
        for c in range(9):
            d = g[r][c]
            if d:
                b = 1 << d; bx = (r // 3) * 3 + c // 3
                if rows[r] & b or cols[c] & b or boxes[bx] & b:
                    return 0, None
                rows[r] |= b; cols[c] |= b; boxes[bx] |= b
    found = [0, None]

    def rec():
        best, bm, bc = None, 0, 10
        for r in range(9):
            for c in range(9):
                if g[r][c] == 0:
                    m = ~(rows[r] | cols[c] | boxes[(r // 3) * 3 + c // 3]) & 0x3FE
                    cnt = bin(m).count("1")
                    if cnt < bc:
                        best, bm, bc = (r, c), m, cnt
                        if cnt <= 1:
                            break
            if bc <= 1:
                break
        if best is None:
            found[0] += 1
            if found[1] is None:
                found[1] = [row[:] for row in g]
            return found[0] >= limit
        r, c = best; bx = (r // 3) * 3 + c // 3
        for d in range(1, 10):
            b = 1 << d
            if bm & b:
                g[r][c] = d; rows[r] |= b; cols[c] |= b; boxes[bx] |= b
                stop = rec()
                g[r][c] = 0; rows[r] &= ~b; cols[c] &= ~b; boxes[bx] &= ~b
                if stop:
                    return True
        return False

    rec()
    return found[0], found[1]

def board_str(b):
    lines = []
    for r in range(9):
        s = ""
        for c in range(9):
            s += (str(b[r][c]) if b[r][c] else ".") + (" | " if c in (2, 5) else " ")
        lines.append(s.rstrip())
        if r in (2, 5):
            lines.append("------+-------+------")
    return "\n".join(lines)

def main(argv):
    if len(argv) < 2:
        print(__doc__ or "usage: numpre.py image [-o out.png]")
        return 2
    rgb = load_rgb(argv[1])
    board, conf, g = recognize(rgb)
    print(f"grid x0={g['x0']} y0={g['y0']} p={g['p']:.2f} score={g['score']:.3f}")
    print(board_str(board))
    n, sol = solve(board)
    print("solutions:", "2+" if n >= 2 else n)
    if sol:
        print(board_str(sol))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
