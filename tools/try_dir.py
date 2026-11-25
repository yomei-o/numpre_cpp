# フォルダ内の画像を全部読み取り、盤・解の数を出し、読んだ数字を重ねた確認画像を作る。
#   python tools/try_dir.py 画像フォルダ 出力フォルダ
import os, sys, glob
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "python"))
import numpre  # noqa: E402


def main(src, dst):
    os.makedirs(dst, exist_ok=True)
    for path in sorted(glob.glob(os.path.join(src, "*.png")) + glob.glob(os.path.join(src, "*.jpg"))):
        rgb = numpre.load_rgb(path)
        board, conf, g = numpre.recognize(rgb)
        n, sol = numpre.solve(board)
        name = os.path.basename(path)
        given = sum(1 for r in board for v in r if v)
        lowc = min([c for r in conf for c in r if c > 0] or [0])
        print(f"== {name}  size={rgb.shape[1]}x{rgb.shape[0]}  grid x0={g['x0']} y0={g['y0']} p={g['p']:.1f} "
              f"score={g['score']:.2f}  digits={given}  min_conf={lowc:.2f}  solutions={'2+' if n >= 2 else n}")
        print(numpre.board_str(board))
        # 確認画像: 格子（緑）と読んだ数字（赤、マスの左上）
        im = Image.open(path).convert("RGB")
        d = ImageDraw.Draw(im)
        xs, ys, p = g["xs"], g["ys"], g["p"]
        for k in range(10):
            d.line([(xs[k], ys[0]), (xs[k], ys[9])], fill=(0, 200, 0), width=2)
            d.line([(xs[0], ys[k]), (xs[9], ys[k])], fill=(0, 200, 0), width=2)
        font = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", max(10, int(p * 0.3)))
        for r in range(9):
            for c in range(9):
                if board[r][c]:
                    d.text((xs[c] + 3, ys[r] + 1), str(board[r][c]), fill=(230, 0, 0), font=font)
        pad = int(p * 0.5)
        im.crop((max(0, int(xs[0]) - pad), max(0, int(ys[0]) - pad),
                 min(im.width, int(xs[9]) + pad), min(im.height, int(ys[9]) + pad))).save(
            os.path.join(dst, os.path.splitext(name)[0] + "_ov.png"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
