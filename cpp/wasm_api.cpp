// WASM の入口。JS は canvas から取った RGBA を渡すだけ。
#include <cstdint>
#include "numpre.h"

extern "C" {

// rgba: w*h*4。out_board: 81 個（0=空き）、out_geom: xs[10], ys[10], score の 21 個、out_conf: 81 個
int np_recognize(const uint8_t* rgba, int w, int h, int* out_board, double* out_geom, double* out_conf) {
    numpre::Image im;
    im.w = w; im.h = h; im.rgb.resize((size_t)w * h * 3);
    for (size_t i = 0, n = (size_t)w * h; i < n; i++) {
        im.rgb[i * 3] = rgba[i * 4]; im.rgb[i * 3 + 1] = rgba[i * 4 + 1]; im.rgb[i * 3 + 2] = rgba[i * 4 + 2];
    }
    numpre::Result R = numpre::recognize(im);
    int digits = 0;
    for (int r = 0; r < 9; r++)
        for (int c = 0; c < 9; c++) {
            out_board[r * 9 + c] = R.board[r][c];
            out_conf[r * 9 + c] = R.conf[r][c];
            digits += R.board[r][c] != 0;
        }
    for (int k = 0; k < 10; k++) { out_geom[k] = R.grid.xs[k]; out_geom[10 + k] = R.grid.ys[k]; }
    out_geom[20] = R.grid.score;
    return digits;
}

// 解の数（0 / 1 / 2=2 以上）。out に最初の解。
int np_solve(const int* in, int* out) {
    int b[9][9], s[9][9] = {{0}};
    for (int i = 0; i < 81; i++) b[i / 9][i % 9] = in[i];
    int n = numpre::solve(b, s, 2);
    for (int i = 0; i < 81; i++) out[i] = s[i / 9][i % 9];
    return n;
}

}
