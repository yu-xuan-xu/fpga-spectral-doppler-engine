#!/bin/sh
set -eu
mkdir -p build/core_resource
yosys -q -p 'synth_ice40 -dsp -top doppler_resource_top -json build/core_resource/core.json' \
  rtl/core/sync_ram_256x16.sv rtl/core/frame_checker_256.sv \
  rtl/core/dc_wall_filter.sv rtl/core/window_multiplier.sv \
  rtl/core/fft_iterative_256.sv rtl/core/power_calculator.sv \
  rtl/core/peak_bin_detector.sv rtl/core/velocity_mapper.sv rtl/core/doppler_core.sv \
  rtl/board/doppler_resource_top.sv
nextpnr-ice40 --up5k --package sg48 --freq 12 --json build/core_resource/core.json \
  --asc build/core_resource/core.asc --pcf-allow-unconstrained --report build/core_resource/report.json
icepack build/core_resource/core.asc build/core_resource/core.bin
