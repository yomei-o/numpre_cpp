# 数字 1-9 の型（テンプレート）を Windows のフォントで描いて作る。
# 出力: templates.bin（Python が読む）と cpp/numpre_templates.h（C++ が埋め込む）。
# 型の正規化は numpre.py の digit_feature() と同じ処理を通すので、ずれない。
import os, sys, struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "python"))
import numpre  # noqa: E402

FONT_DIR = r"C:\Windows\Fonts"
# 照合用に使うフォント（テストでは別のフォントで描いた盤も使う）
FONTS = [
    "arial.ttf", "arialbd.ttf", "segoeui.ttf", "segoeuib.ttf", "calibri.ttf",
    "calibrib.ttf", "tahoma.ttf", "verdana.ttf", "times.ttf", "georgia.ttf",
    "consola.ttf", "cour.ttf", "bahnschrift.ttf", "meiryo.ttc", "YuGothM.ttc",
    "YuGothB.ttc", "msgothic.ttc", "BIZ-UDGothicR.ttc", "BIZ-UDGothicB.ttc",
    "UDDigiKyokashoN-R.ttc", "trebuc.ttf", "impact.ttf",
]


def render_digit(font_path, d, size=96):
    font = ImageFont.truetype(font_path, size)
    im = Image.new("L", (size * 2, size * 2), 0)
    ImageDraw.Draw(im).text((size // 2, size // 4), str(d), fill=255, font=font)
    return np.asarray(im, dtype=np.float32)


def main():
    feats, labels, names = [], [], []
    for f in FONTS:
        p = os.path.join(FONT_DIR, f)
        if not os.path.exists(p):
            print("skip", f)
            continue
        for d in range(1, 10):
            g = render_digit(p, d)
            mask = g / 255.0
            feat = numpre.digit_feature(mask)
            feats.append(np.round(feat * 255).astype(np.uint8))
            labels.append(d)
        names.append(f)
    feats = np.stack(feats)
    n, S = feats.shape[0], numpre.FEAT
    with open(os.path.join(ROOT, "python", "templates.bin"), "wb") as fp:
        fp.write(struct.pack("<II", n, S))
        fp.write(bytes(labels))
        fp.write(feats.tobytes())
    with open(os.path.join(ROOT, "cpp", "numpre_templates.h"), "w", newline="\n") as fp:
        fp.write("// gen_templates.py が生成。手で直さない。\n#pragma once\n")
        fp.write(f"// fonts: {' '.join(names)}\n")
        fp.write(f"static const int NUMPRE_TMPL_N = {n};\nstatic const int NUMPRE_TMPL_S = {S};\n")
        fp.write("static const unsigned char NUMPRE_TMPL_LABEL[] = {" + ",".join(map(str, labels)) + "};\n")
        fp.write("static const unsigned char NUMPRE_TMPL_DATA[] = {\n")
        flat = feats.reshape(-1)
        for i in range(0, len(flat), 32):
            fp.write(",".join(map(str, flat[i:i + 32])) + ",\n")
        fp.write("};\n")
    print(f"{n} templates from {len(names)} fonts, {S}x{S}")


if __name__ == "__main__":
    main()
