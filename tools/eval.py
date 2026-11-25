# 合成画像＋実画像で読み取り精度を測る。
#   python tools/eval.py
import os, sys, json, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "python"))
import numpre  # noqa: E402

REAL = {  # 実画像の正解（目で確認したもの）
    "app_tiles_1519.png": ".17 5.. .42 463 ..2 ..7 529 .76 3.. 7.. 8.. 21. ..1 ... 8.. .82 ..1 ..4 ..5 61. 473 3.. 2.. 169 14. ..7 52.",
}


def parse(s):
    s = s.replace(" ", "")
    return [[0 if s[r * 9 + c] == "." else int(s[r * 9 + c]) for c in range(9)] for r in range(9)]


def main():
    cases = []
    for name, s in REAL.items():
        cases.append((os.path.join(ROOT, "testdata", name), parse(s), "real"))
    for js in sorted(glob.glob(os.path.join(ROOT, "testdata", os.environ.get("SYNTH_DIR", "synth"), "*.json"))):
        m = json.load(open(js))
        cases.append((os.path.join(os.path.dirname(js), m["file"]), m["board"], m["style"] + "/" + m["font"]))
    ok_boards = 0
    cell_err = 0
    for path, truth, tag in cases:
        b, conf, g = numpre.recognize(numpre.load_rgb(path))
        errs = [(r, c, truth[r][c], b[r][c]) for r in range(9) for c in range(9) if truth[r][c] != b[r][c]]
        cell_err += len(errs)
        ok_boards += not errs
        status = "OK " if not errs else "NG "
        print(f"{status}{os.path.basename(path):24s} {tag:28s} p={g['p']:.1f} errs={errs[:6]}")
    print(f"boards {ok_boards}/{len(cases)}  cell errors {cell_err}")


if __name__ == "__main__":
    main()
