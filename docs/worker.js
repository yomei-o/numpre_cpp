// WASM を裏のスレッドで動かす。メッセージ: {type:'recognize', rgba, w, h} / {type:'solve', board}
importScripts('numpre.js');
let M = null;
const ready = NumpreModule().then(m => { M = m; });

function solve(board) {
  const pb = M._malloc(81 * 4), ps = M._malloc(81 * 4);
  M.HEAP32.set(Int32Array.from(board), pb / 4);
  const n = M._np_solve(pb, ps);
  const sol = Array.from(M.HEAP32.subarray(ps / 4, ps / 4 + 81));
  M._free(pb); M._free(ps);
  return { n, sol };
}

onmessage = async (e) => {
  await ready;
  const d = e.data;
  if (d.type === 'recognize') {
    const t0 = performance.now();
    const p = M._malloc(d.rgba.length), pb = M._malloc(81 * 4), pg = M._malloc(21 * 8), pc = M._malloc(81 * 8);
    M.HEAPU8.set(d.rgba, p);
    M._np_recognize(p, d.w, d.h, pb, pg, pc);
    const board = Array.from(M.HEAP32.subarray(pb / 4, pb / 4 + 81));
    const geom = Array.from(M.HEAPF64.subarray(pg / 8, pg / 8 + 21));
    const conf = Array.from(M.HEAPF64.subarray(pc / 8, pc / 8 + 81));
    [p, pb, pg, pc].forEach(q => M._free(q));
    const ms = performance.now() - t0;
    postMessage({ type: 'recognized', board, xs: geom.slice(0, 10), ys: geom.slice(10, 20), conf, ms, ...solve(board) });
  } else if (d.type === 'solve') {
    postMessage({ type: 'solved', board: d.board, ...solve(d.board) });
  }
};
