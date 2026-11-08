#!/bin/sh
set -eu
mkdir -p build/smoke
yosys -q -p 'synth_ice40 -top toolchain_smoke -json build/smoke/smoke.json' \
  rtl/board/toolchain_smoke.sv
nextpnr-ice40 --up5k --package sg48 --freq 12 --json build/smoke/smoke.json \
  --asc build/smoke/smoke.asc --pcf-allow-unconstrained --report build/smoke/report.json
icepack build/smoke/smoke.asc build/smoke/smoke.bin
test -s build/smoke/smoke.bin
