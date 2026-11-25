# numpre_cpp

ナンプレ（数独）が解けないとき、その画面のスクリーンショットを渡すと盤面を読み取って解くアプリ。
C++ のヘッダオンリー本体を WASM にしてスマホのブラウザで動かす予定。Python 版も同じ手順で持つ。

## 今できること（Python 版）

```
python python/numpre.py testdata/app_tiles_1519.png
```

1. **盤の位置**：色の段差（縁）の 0/1 マップを作り、刻み p の 10×10 本の格子線が縁に乗る割合を総当たり
   （縮小画像で粗く → 原寸で詰める → 10 本の線を 1 本ずつ合わせ直す）。
2. **数字**：マス中央を切り出し大津の二値化、少ない側を字とする。盤全体の字の高さの中央値の 55% 未満は
   メモ書きとして捨てる。外接矩形を 20×20 に正規化し、Windows の 22 フォントで描いた型と照合
   （ぼかしてから相関）。一致度が僅差なら字の穴の数（6・9 は 1、8 は 2）で選び直す。MNIST などの学習は使っていない。
3. **解く**：ビットマスク＋候補の最も少ないマスから試すバックトラック。解の数（0 / 1 / 2 以上）も返す。

## 評価

`tools/gen_synth.py` で合成スクショ（新聞風・メモ書き入り・ダーク・タイル・行列ハイライト、型に入れていないフォント、
下に数字パッド、1/4 は JPEG）を正解つきで作り、`tools/eval.py` で測る。

| セット | 全マス正解の盤 | 誤りマス |
|---|---|---|
| 実画像 1 枚＋調整に使った 100 枚 (`synth`, seed 1519) | 101/101 | 0 |
| 見ていない 100 枚 (`holdout`, seed 2026) | 97/101 | 22 |

盤の位置は 201 枚すべて正解から 1 画素以内。holdout の誤りは全部数字の分類（細い字の 6→5・2→7、
Constantia のオールドスタイルの 2 の見落とし）。

```
python tools/gen_templates.py                               # 型を作り直す（python/templates.bin と cpp/numpre_templates.h）
python tools/gen_synth.py 100                               # testdata/synth
SYNTH_DIR=holdout SYNTH_SEED=2026 python tools/gen_synth.py 100
SYNTH_DIR=holdout python tools/eval.py
```
