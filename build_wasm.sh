#!/bin/sh
# WASM をビルドして docs/numpre.js（wasm 埋め込みの 1 ファイル）を作る。
set -e
cd "$(dirname "$0")"
EMSDK=${EMSDK:-/c/prog/emsdk/emsdk}
export EM_CONFIG="$EMSDK/.emscripten"
EMCC="$EMSDK/upstream/emscripten/em++.exe"
"$EMCC" -O3 -std=c++17 -Icpp cpp/wasm_api.cpp -o docs/numpre.js \
  -sSINGLE_FILE=1 -sMODULARIZE=1 -sEXPORT_NAME=NumpreModule -sALLOW_MEMORY_GROWTH=1 \
  -sENVIRONMENT=web,worker,node \
  -sEXPORTED_FUNCTIONS=_np_recognize,_np_solve,_malloc,_free \
  -sEXPORTED_RUNTIME_METHODS=HEAPU8,HEAP32,HEAPF64
ls -la docs/numpre.js
