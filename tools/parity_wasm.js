// Python の結果（build/rgba/py.json）と WASM の結果を比べる。  node tools/parity_wasm.js
const fs = require('fs'), path = require('path');
const NumpreModule = require('../docs/numpre.js');
NumpreModule().then(M => {
  const dir = path.join(__dirname, '..', 'build', 'rgba');
  const cases = JSON.parse(fs.readFileSync(path.join(dir, 'py.json')));
  let ok = 0;
  for (const c of cases) {
    const raw = fs.readFileSync(path.join(dir, c.name + '.raw'));
    const p = M._malloc(raw.length), pb = M._malloc(81 * 4), pg = M._malloc(21 * 8), pc = M._malloc(81 * 8);
    M.HEAPU8.set(raw, p);
    const t0 = Date.now();
    M._np_recognize(p, c.w, c.h, pb, pg, pc);
    const ms = Date.now() - t0;
    const board = Array.from(M.HEAP32.subarray(pb / 4, pb / 4 + 81));
    const geom = Array.from(M.HEAPF64.subarray(pg / 8, pg / 8 + 21));
    const same = board.join() === c.board.flat().join();
    const dg = Math.max(...c.xs.map((v, i) => Math.abs(v - geom[i])), ...c.ys.map((v, i) => Math.abs(v - geom[10 + i])));
    const ps = M._malloc(81 * 4);
    M.HEAP32.set(Int32Array.from(board), pb / 4);
    const nsol = M._np_solve(pb, ps);
    console.log(`${same && dg < 1e-6 ? 'OK ' : 'NG '} ${c.name.padEnd(28)} ${ms} ms  board ${same ? 'same' : 'DIFF'}  grid diff ${dg.toFixed(3)}  solutions ${nsol}`);
    ok += same && dg < 1e-6;
    [p, pb, pg, pc, ps].forEach(q => M._free(q));
  }
  console.log(`parity ${ok}/${cases.length}`);
});
