// numpre.h — ナンプレの画像から盤面を読み取って解く（ヘッダオンリー、依存なし）。
// python/numpre.py と同じ手順。数値の丸めも Python に合わせてある（round は偶数丸め）。
#pragma once
#include <vector>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <algorithm>
#include "numpre_templates.h"

namespace numpre {

static const int FEAT = 20;
static const int EDGE_T = 24;
static const int SMALL = 400;
static const double HOLE_MARGIN = 0.15;

inline int pyround(double v) { return (int)std::nearbyint(v); }   // Python の round（偶数丸め）

struct Image {            // RGB 8bit
    int w = 0, h = 0;
    std::vector<uint8_t> rgb;
    int at(int x, int y, int c) const { return rgb[((size_t)y * w + x) * 3 + c]; }
};

struct Grid {
    int x0 = 0, y0 = 0;
    double px = 0, py = 0, p = 0, score = 0, coarse_score = 0;
    double xs[10], ys[10];
};

struct Result {
    Grid grid;
    int board[9][9];
    double conf[9][9];
};

// ------------------------------------------------------------------ 盤の位置
struct U8Map {
    int w = 0, h = 0;
    std::vector<uint8_t> v;
    U8Map() {}
    U8Map(int w_, int h_) : w(w_), h(h_), v((size_t)w_ * h_, 0) {}
    uint8_t& at(int x, int y) { return v[(size_t)y * w + x]; }
    uint8_t at(int x, int y) const { return v[(size_t)y * w + x]; }
};

inline void edge_maps(const Image& im, U8Map& ev, U8Map& eh) {
    ev = U8Map(im.w, im.h); eh = U8Map(im.w, im.h);
    for (int y = 0; y < im.h; y++)
        for (int x = 0; x < im.w; x++) {
            if (x + 1 < im.w) {
                int m = 0;
                for (int c = 0; c < 3; c++) m = std::max(m, std::abs(im.at(x + 1, y, c) - im.at(x, y, c)));
                ev.at(x, y) = m >= EDGE_T;
            }
            if (y + 1 < im.h) {
                int m = 0;
                for (int c = 0; c < 3; c++) m = std::max(m, std::abs(im.at(x, y + 1, c) - im.at(x, y, c)));
                eh.at(x, y) = m >= EDGE_T;
            }
        }
}

inline U8Map pool_max(const U8Map& e, int k) {
    U8Map o(e.w / k, e.h / k);
    for (int y = 0; y < o.h * k; y++)
        for (int x = 0; x < o.w * k; x++)
            if (e.at(x, y)) o.at(x / k, y / k) = 1;
    return o;
}

inline U8Map dilate_x(const U8Map& e, int r) {
    U8Map o = e;
    for (int y = 0; y < e.h; y++)
        for (int x = 0; x < e.w; x++)
            if (e.at(x, y))
                for (int d = -r; d <= r; d++) {
                    int xx = x + d;
                    if (xx >= 0 && xx < e.w) o.at(xx, y) = 1;
                }
    return o;
}

inline U8Map transpose(const U8Map& e) {
    U8Map o(e.h, e.w);
    for (int y = 0; y < e.h; y++)
        for (int x = 0; x < e.w; x++) o.at(y, x) = e.at(x, y);
    return o;
}

inline U8Map dilate_y(const U8Map& e, int r) { return transpose(dilate_x(transpose(e), r)); }

struct Best { double score; double px, py; int x0, y0; };

inline std::vector<double> frange(double lo, double hi, double step) {
    std::vector<double> o;
    for (double v = lo; v <= hi + 1e-9; v += step) o.push_back(v);
    return o;
}

static const int NASPECT = 15;
inline double aspect(int i) { return 0.70 + 0.05 * i; }

inline Best search(const U8Map& ev, const U8Map& eh, int r,
                   const std::vector<std::pair<double, double>>& pairs,
                   int xr0, int xr1, int yr0, int yr1) {
    const int H = ev.h, W = ev.w;
    U8Map V = dilate_x(ev, r), Hh = dilate_y(eh, r);
    // CV[(y)*W + x] = 列 x の y 行目までの累積（y は 0..H）、CH[y*(W+1) + x]
    std::vector<int32_t> CV((size_t)(H + 1) * W, 0), CH((size_t)H * (W + 1), 0);
    for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++) CV[(size_t)(y + 1) * W + x] = CV[(size_t)y * W + x] + V.at(x, y);
    for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++) CH[(size_t)y * (W + 1) + x + 1] = CH[(size_t)y * (W + 1) + x] + Hh.at(x, y);
    Best best{-1e9, 0, 0, 0, 0};
    std::vector<int> ox(19), oy(19);
    for (auto& pp : pairs) {
        double px = pp.first, py = pp.second;
        int LX = pyround(9 * px), LY = pyround(9 * py);
        int x_lo = std::max(0, xr0), x_hi = std::min(W - 1 - LX, xr1);
        int y_lo = std::max(0, yr0), y_hi = std::min(H - 1 - LY, yr1);
        if (x_hi < x_lo || y_hi < y_lo) continue;
        for (int k = 0; k < 19; k++) { ox[k] = pyround(k * px / 2); oy[k] = pyround(k * py / 2); }
        for (int y0 = y_lo; y0 <= y_hi; y0++)
            for (int x0 = x_lo; x0 <= x_hi; x0++) {
                double on = 0, mid = 0;
                for (int k = 0; k < 19; k++) {
                    int xv = x0 + ox[k], yh = y0 + oy[k];
                    double a = (double)(CV[(size_t)(y0 + LY) * W + xv] - CV[(size_t)y0 * W + xv]) / LY;
                    double b = (double)(CH[(size_t)yh * (W + 1) + x0 + LX] - CH[(size_t)yh * (W + 1) + x0]) / LX;
                    if (k % 2 == 0) { on += a; on += b; } else { mid += a; mid += b; }
                }
                double s = on / 20.0 - 0.5 * mid / 18.0;
                if (s > best.score + 1e-12) best = {s, px, py, x0, y0};
            }
    }
    return best;
}

// 10 本の縦線を 1 本ずつ合わせ直す（横線は転置した縁マップで同じ関数）
inline void refine_lines(const U8Map& ev, int x0, int y0, double px, double py, double out[10]) {
    const int H = ev.h, W = ev.w;
    int L = pyround(9 * py);
    int ya = std::max(0, y0), yb = std::min(H, y0 + L);
    for (int k = 0; k < 10; k++) {
        double xk = x0 + k * px;
        int a = std::max(0, (int)std::floor(xk - 0.2 * px));
        int b = std::min(W - 1, (int)std::ceil(xk + 0.2 * px));
        std::vector<long> cov;
        long mx = 0;
        for (int x = a; x <= b; x++) {
            long c = 0;
            for (int y = ya; y < yb; y++) c += ev.at(x, y);
            cov.push_back(c);
            mx = std::max(mx, c);
        }
        if (cov.empty() || mx * 5 < (yb - ya)) { out[k] = xk; continue; }
        int first = -1, last = -1;
        for (int i = 0; i < (int)cov.size(); i++)
            if (cov[i] * 2 >= mx) { if (first < 0) first = i; last = i; }
        out[k] = (a + first + a + last) / 2.0 + 0.5;
    }
}

inline Grid find_grid(const Image& im) {
    U8Map ev, eh;
    edge_maps(im, ev, eh);
    int k = std::max(1, (std::max(im.w, im.h) + SMALL - 1) / SMALL);
    U8Map sv = pool_max(ev, k), sh = pool_max(eh, k);
    int m = std::min(sv.w, sv.h);
    std::vector<std::pair<double, double>> pairs;
    for (double p : frange(m / 30.0, m / 9.0, 0.25))
        for (int i = 0; i < NASPECT; i++) pairs.push_back({p, p * aspect(i)});
    Best c = search(sv, sh, 1, pairs, 0, sv.w, 0, sv.h);
    double PX = c.px * k, PY = c.py * k;
    int r = std::max(1, pyround(std::min(PX, PY) * 0.05));
    double st = std::max(0.25, k / 8.0);
    pairs.clear();
    for (double a : frange(PX - k, PX + k, st))
        for (double b : frange(PY - k, PY + k, st)) pairs.push_back({a, b});
    Best f = search(ev, eh, r, pairs, c.x0 * k - 2 * k, c.x0 * k + 2 * k, c.y0 * k - 2 * k, c.y0 * k + 2 * k);
    Grid g;
    g.x0 = f.x0; g.y0 = f.y0; g.px = f.px; g.py = f.py; g.p = std::min(f.px, f.py);
    g.score = f.score; g.coarse_score = c.score;
    refine_lines(ev, f.x0, f.y0, f.px, f.py, g.xs);
    refine_lines(transpose(eh), f.y0, f.x0, f.py, f.px, g.ys);
    return g;
}

// ------------------------------------------------------------------ 数字
struct FMap {      // double の 2 次元
    int w = 0, h = 0;
    std::vector<double> v;
    FMap() {}
    FMap(int w_, int h_) : w(w_), h(h_), v((size_t)w_ * h_, 0.0) {}
    double& at(int x, int y) { return v[(size_t)y * w + x]; }
    double at(int x, int y) const { return v[(size_t)y * w + x]; }
};

inline FMap resize_box(const FMap& img, int oh, int ow) {
    int ih = img.h, iw = img.w;
    FMap out(ow, oh);
    for (int oy = 0; oy < oh; oy++)
        for (int ox = 0; ox < ow; ox++) {
            double acc = 0.0;
            for (int sy = 0; sy < 4; sy++) {
                double fy = (oy + (sy + 0.5) / 4) * ih / oh - 0.5;
                fy = std::min(std::max(fy, 0.0), ih - 1.0);
                int y0 = (int)fy, y1 = std::min(y0 + 1, ih - 1);
                double ty = fy - y0;
                for (int sx = 0; sx < 4; sx++) {
                    double fx = (ox + (sx + 0.5) / 4) * iw / ow - 0.5;
                    fx = std::min(std::max(fx, 0.0), iw - 1.0);
                    int x0 = (int)fx, x1 = std::min(x0 + 1, iw - 1);
                    double tx = fx - x0;
                    double a = img.at(x0, y0) * (1 - tx) + img.at(x1, y0) * tx;
                    double b = img.at(x0, y1) * (1 - tx) + img.at(x1, y1) * tx;
                    acc += a * (1 - ty) + b * ty;
                }
            }
            out.at(ox, oy) = acc / 16.0;
        }
    return out;
}

inline FMap digit_feature(const FMap& mask) {
    int x0 = mask.w, x1 = -1, y0 = mask.h, y1 = -1;
    for (int y = 0; y < mask.h; y++)
        for (int x = 0; x < mask.w; x++)
            if (mask.at(x, y) > 0.5) { x0 = std::min(x0, x); x1 = std::max(x1, x); y0 = std::min(y0, y); y1 = std::max(y1, y); }
    FMap out(FEAT, FEAT);
    if (x1 < 0) return out;
    int h = y1 - y0 + 1, w = x1 - x0 + 1;
    FMap crop(w, h);
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) crop.at(x, y) = mask.at(x0 + x, y0 + y);
    int oh, ow;
    if (h >= w) { oh = FEAT; ow = std::max(1, pyround((double)w * FEAT / h)); }
    else { ow = FEAT; oh = std::max(1, pyround((double)h * FEAT / w)); }
    FMap s = resize_box(crop, oh, ow);
    int oy = (FEAT - oh) / 2, ox = (FEAT - ow) / 2;
    for (int y = 0; y < oh; y++)
        for (int x = 0; x < ow; x++) out.at(ox + x, oy + y) = s.at(x, y);
    return out;
}

inline int otsu(const std::vector<int>& g) {
    double hist[256] = {0};
    for (int v : g) hist[v] += 1;
    double n = (double)g.size(), tot = 0;
    for (int t = 0; t < 256; t++) tot += hist[t] * t;
    double best = -1.0, w0 = 0, s0 = 0;
    int bt = 0;
    for (int t = 0; t < 256; t++) {
        w0 += hist[t]; s0 += t * hist[t];
        double w1 = n - w0;
        if (w0 == 0 || w1 == 0) continue;
        double m0 = s0 / w0, m1 = (tot - s0) / w1;
        double v = w0 * w1 * (m0 - m1) * (m0 - m1);
        if (v > best) { best = v; bt = t; }
    }
    return bt;
}

// 連結成分（4 近傍、eight なら 8 近傍）。走査は行優先、塗りは後入れ先出し。ラベル 1..n
inline int components(const std::vector<uint8_t>& bin, int W, int H, std::vector<int>& lab, bool eight = false) {
    lab.assign((size_t)W * H, 0);
    int n = 0;
    std::vector<int> st;
    static const int d4[4][2] = {{0, -1}, {0, 1}, {-1, 0}, {1, 0}};
    static const int d8[8][2] = {{0, -1}, {0, 1}, {-1, 0}, {1, 0}, {-1, -1}, {1, -1}, {-1, 1}, {1, 1}};
    for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++) {
            if (!bin[(size_t)y * W + x] || lab[(size_t)y * W + x]) continue;
            n++;
            lab[(size_t)y * W + x] = n;
            st.push_back(y * W + x);
            while (!st.empty()) {
                int cur = st.back(); st.pop_back();
                int cy = cur / W, cx = cur % W;
                int nd = eight ? 8 : 4;
                for (int i = 0; i < nd; i++) {
                    int nx = cx + (eight ? d8[i][0] : d4[i][0]);
                    int ny = cy + (eight ? d8[i][1] : d4[i][1]);
                    if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
                    size_t j = (size_t)ny * W + nx;
                    if (bin[j] && !lab[j]) { lab[j] = n; st.push_back(ny * W + nx); }
                }
            }
        }
    return n;
}

struct GrayImg {
    int w = 0, h = 0;
    std::vector<int> v;
    int at(int x, int y) const { return v[(size_t)y * w + x]; }
};

inline GrayImg to_gray(const Image& im) {
    GrayImg g; g.w = im.w; g.h = im.h; g.v.resize((size_t)im.w * im.h);
    for (size_t i = 0; i < g.v.size(); i++)
        g.v[i] = (im.rgb[i * 3] * 77 + im.rgb[i * 3 + 1] * 150 + im.rgb[i * 3 + 2] * 29) >> 8;
    return g;
}

// マス中央付近の数字の前景マスク。数字が無ければ false。
inline bool cell_mask(const GrayImg& gray, double cx, double cy, double p, double min_h, FMap& out, int& kh) {
    int half = pyround(p * 0.40);
    int x0 = pyround(cx) - half, y0 = pyround(cy) - half;
    int xa = std::max(0, x0), ya = std::max(0, y0);
    int xb = std::min(gray.w, x0 + 2 * half), yb = std::min(gray.h, y0 + 2 * half);
    int W = xb - xa, H = yb - ya;
    if (W <= 0 || H <= 0) return false;
    std::vector<int> g((size_t)W * H);
    for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++) g[(size_t)y * W + x] = gray.at(xa + x, ya + y);
    int t = otsu(g);
    long nlo = 0; double slo = 0, shi = 0;
    for (int v : g) { if (v <= t) { nlo++; slo += v; } else shi += v; }
    long nhi = (long)g.size() - nlo;
    if (nlo == 0 || nhi == 0) return false;
    double mlo = slo / nlo, mhi = shi / nhi;
    if (mhi - mlo < 60) return false;
    bool fg_is_hi = nhi < nlo;
    double bgm = fg_is_hi ? mlo : mhi, fgm = fg_is_hi ? mhi : mlo;
    std::vector<uint8_t> fg(g.size());
    for (size_t i = 0; i < g.size(); i++) fg[i] = fg_is_hi ? (g[i] > t) : (g[i] <= t);
    std::vector<int> lab;
    int n = components(fg, W, H, lab);
    std::vector<int> bx0(n + 1, W), bx1(n + 1, -1), by0(n + 1, H), by1(n + 1, -1);
    std::vector<double> sx(n + 1, 0), sy(n + 1, 0), cnt(n + 1, 0);
    for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++) {
            int l = lab[(size_t)y * W + x];
            if (!l) continue;
            bx0[l] = std::min(bx0[l], x); bx1[l] = std::max(bx1[l], x);
            by0[l] = std::min(by0[l], y); by1[l] = std::max(by1[l], y);
            sx[l] += x; sy[l] += y; cnt[l] += 1;
        }
    std::vector<uint8_t> keep(n + 1, 0);
    bool any = false;
    kh = 0;
    for (int i = 1; i <= n; i++) {
        int h = by1[i] - by0[i] + 1, w = bx1[i] - bx0[i] + 1;
        if (h < min_h) continue;
        if (h > 0.95 * H || w > 0.95 * W) continue;
        double my = sy[i] / cnt[i], mx = sx[i] / cnt[i];
        if (std::fabs(my - H / 2.0) > 0.25 * H || std::fabs(mx - W / 2.0) > 0.25 * W) continue;
        keep[i] = 1; any = true;
        kh = std::max(kh, h);
    }
    if (!any) return false;
    out = FMap(W, H);
    for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++) {
            bool k2 = false;
            const int dd[5][2] = {{0, 0}, {0, -1}, {0, 1}, {-1, 0}, {1, 0}};
            for (auto& d : dd) {
                int xx = x + d[0], yy = y + d[1];
                if (xx >= 0 && yy >= 0 && xx < W && yy < H && keep[lab[(size_t)yy * W + xx]] && lab[(size_t)yy * W + xx]) { k2 = true; break; }
            }
            if (!k2) continue;
            double s = (g[(size_t)y * W + x] - bgm) / (fgm - bgm);
            out.at(x, y) = std::min(1.0, std::max(0.0, s));
        }
    return true;
}

inline int holes(const FMap& m) {
    int x0 = m.w, x1 = -1, y0 = m.h, y1 = -1;
    for (int y = 0; y < m.h; y++)
        for (int x = 0; x < m.w; x++)
            if (m.at(x, y) > 0.5) { x0 = std::min(x0, x); x1 = std::max(x1, x); y0 = std::min(y0, y); y1 = std::max(y1, y); }
    if (x1 < 0) return 0;
    int bw = x1 - x0 + 1, bh = y1 - y0 + 1;
    int W = bw + 2, H = bh + 2;
    std::vector<uint8_t> bg((size_t)W * H, 1);
    for (int y = 0; y < bh; y++)
        for (int x = 0; x < bw; x++) bg[(size_t)(y + 1) * W + x + 1] = !(m.at(x0 + x, y0 + y) > 0.5);
    std::vector<int> lab;
    int n = components(bg, W, H, lab);
    std::vector<long> cnt(n + 1, 0);
    for (int l : lab) cnt[l]++;
    double amin = std::max(2.0, 0.015 * bw * bh);
    int c = 0;
    for (int i = 2; i <= n; i++) if (cnt[i] >= amin) c++;
    return c;
}

inline FMap blur(FMap f) {
    for (int it = 0; it < 2; it++) {
        FMap a = f;
        for (int y = 0; y < f.h; y++)
            for (int x = 0; x < f.w; x++) {
                int ym = std::max(0, y - 1), yp = std::min(f.h - 1, y + 1);
                a.at(x, y) = (f.at(x, ym) + 2 * f.at(x, y) + f.at(x, yp)) / 4;
            }
        for (int y = 0; y < f.h; y++)
            for (int x = 0; x < f.w; x++) {
                int xm = std::max(0, x - 1), xp = std::min(f.w - 1, x + 1);
                f.at(x, y) = (a.at(xm, y) + 2 * a.at(x, y) + a.at(xp, y)) / 4;
            }
    }
    return f;
}

struct Templates {
    std::vector<int> labels;
    std::vector<std::vector<double>> data;   // ぼかし・平均引き・正規化済み
    Templates() {
        const int S = NUMPRE_TMPL_S, n = NUMPRE_TMPL_N;
        for (int i = 0; i < n; i++) {
            FMap t(S, S);
            for (int j = 0; j < S * S; j++) t.v[j] = NUMPRE_TMPL_DATA[(size_t)i * S * S + j] / 255.0;
            t = blur(t);
            double mean = 0; for (double v : t.v) mean += v; mean /= t.v.size();
            double nrm = 0; for (double& v : t.v) { v -= mean; nrm += v * v; }
            nrm = std::sqrt(nrm);
            for (double& v : t.v) v /= nrm;
            labels.push_back(NUMPRE_TMPL_LABEL[i]);
            data.push_back(t.v);
        }
    }
};

inline const Templates& templates() { static Templates t; return t; }

inline bool holes_ok(int d, int h) {
    switch (d) {
        case 4: return h == 0 || h == 1;
        case 6: case 9: return h == 1;
        case 8: return h == 2;
        default: return h == 0;
    }
}

inline int classify(const FMap& feat, int nholes, double& score) {
    const Templates& T = templates();
    FMap f = feat;
    for (double& v : f.v) v = std::nearbyint(v * 255) / 255.0;
    f = blur(f);
    double mean = 0; for (double v : f.v) mean += v; mean /= f.v.size();
    double nf = 0; for (double& v : f.v) { v -= mean; nf += v * v; }
    nf = std::sqrt(nf);
    score = 0;
    if (nf == 0) return 0;
    std::vector<double> s(T.data.size());
    int bi = 0;
    for (size_t t = 0; t < T.data.size(); t++) {
        double acc = 0;
        for (size_t j = 0; j < f.v.size(); j++) acc += T.data[t][j] * (f.v[j] / nf);
        s[t] = acc;
        if (s[t] > s[bi]) bi = (int)t;
    }
    if (nholes >= 0 && !holes_ok(T.labels[bi], nholes)) {
        int j = -1; double sj = -2.0;
        for (size_t t = 0; t < T.data.size(); t++)
            if (holes_ok(T.labels[t], nholes) && s[t] > sj) { j = (int)t; sj = s[t]; }
        if (j >= 0 && sj >= s[bi] - HOLE_MARGIN) bi = j;
    }
    score = s[bi];
    return T.labels[bi];
}

inline Result recognize(const Image& im) {
    Result R;
    R.grid = find_grid(im);
    GrayImg gray = to_gray(im);
    const Grid& g = R.grid;
    double p = g.p;
    for (int r = 0; r < 9; r++) for (int c = 0; c < 9; c++) { R.board[r][c] = 0; R.conf[r][c] = 0; }
    FMap masks[9][9]; int hs[9][9]; bool has[9][9];
    std::vector<int> big;
    for (int r = 0; r < 9; r++)
        for (int c = 0; c < 9; c++) {
            double cx = (g.xs[c] + g.xs[c + 1]) / 2, cy = (g.ys[r] + g.ys[r + 1]) / 2;
            has[r][c] = cell_mask(gray, cx, cy, p, 0.15 * p, masks[r][c], hs[r][c]);
            if (has[r][c] && hs[r][c] >= 0.3 * p) big.push_back(hs[r][c]);
        }
    std::sort(big.begin(), big.end());
    double href = big.empty() ? 0.5 * p : big[(big.size() - 1) / 2];
    for (int r = 0; r < 9; r++)
        for (int c = 0; c < 9; c++) {
            if (!has[r][c]) continue;
            FMap m = masks[r][c];
            if (hs[r][c] < 0.55 * href) {
                double cx = (g.xs[c] + g.xs[c + 1]) / 2, cy = (g.ys[r] + g.ys[r + 1]) / 2;
                int h2;
                if (!cell_mask(gray, cx, cy, p, 0.55 * href, m, h2)) continue;
            }
            double sc;
            FMap bin = m;   // holes は m>0.5 の 2 値
            R.board[r][c] = classify(digit_feature(m), holes(bin), sc);
            R.conf[r][c] = sc;
        }
    return R;
}

// ------------------------------------------------------------------ 解く
struct Solver {
    int g[9][9];
    int rows[9] = {0}, cols[9] = {0}, boxes[9] = {0};
    int found = 0, limit = 2;
    int first[9][9];
    static int popc(int m) { int c = 0; while (m) { m &= m - 1; c++; } return c; }
    bool rec() {
        int br = -1, bc = -1, bm = 0, bcnt = 10;
        for (int r = 0; r < 9 && bcnt > 1; r++)
            for (int c = 0; c < 9; c++)
                if (g[r][c] == 0) {
                    int m = ~(rows[r] | cols[c] | boxes[(r / 3) * 3 + c / 3]) & 0x3FE;
                    int cnt = popc(m);
                    if (cnt < bcnt) { br = r; bc = c; bm = m; bcnt = cnt; if (cnt <= 1) break; }
                }
        if (br < 0) {
            if (found == 0) for (int r = 0; r < 9; r++) for (int c = 0; c < 9; c++) first[r][c] = g[r][c];
            found++;
            return found >= limit;
        }
        int bx = (br / 3) * 3 + bc / 3;
        for (int d = 1; d <= 9; d++) {
            int b = 1 << d;
            if (!(bm & b)) continue;
            g[br][bc] = d; rows[br] |= b; cols[bc] |= b; boxes[bx] |= b;
            bool stop = rec();
            g[br][bc] = 0; rows[br] &= ~b; cols[bc] &= ~b; boxes[bx] &= ~b;
            if (stop) return true;
        }
        return false;
    }
};

// 解の数（limit で打ち切り）。sol に最初の解。矛盾する盤は 0。
inline int solve(const int board[9][9], int sol[9][9], int limit = 2) {
    Solver S; S.limit = limit;
    for (int r = 0; r < 9; r++)
        for (int c = 0; c < 9; c++) {
            int d = board[r][c];
            S.g[r][c] = d;
            if (!d) continue;
            int b = 1 << d, bx = (r / 3) * 3 + c / 3;
            if ((S.rows[r] & b) || (S.cols[c] & b) || (S.boxes[bx] & b)) return 0;
            S.rows[r] |= b; S.cols[c] |= b; S.boxes[bx] |= b;
        }
    S.rec();
    if (S.found) for (int r = 0; r < 9; r++) for (int c = 0; c < 9; c++) sol[r][c] = S.first[r][c];
    return S.found;
}

}  // namespace numpre
