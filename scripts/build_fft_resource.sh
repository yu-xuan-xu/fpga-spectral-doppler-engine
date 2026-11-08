#!/bin/sh
set -eu
mkdir -p build/fft_resource
yosys -q -p 'synth_ice40 -dsp -top fft_resource_top -json build/fft_resource/fft.json' \
  rtl/core/sync_ram_256x16.sv rtl/core/fft_iterative_256.sv rtl/board/fft_resource_top.sv
nextpnr-ice40 --up5k --package sg48 --freq 12 --json build/fft_resource/fft.json \
  --asc build/fft_resource/fft.asc --pcf-allow-unconstrained --report build/fft_resource/report.json
icepack build/fft_resource/fft.asc build/fft_resource/fft.bin
