#!/bin/sh
set -eu
mkdir -p build/board_top
yosys -q -p 'synth_ice40 -dsp -top board_top -json build/board_top/board.json' \
  rtl/core/sync_ram_256x16.sv rtl/core/frame_checker_256.sv rtl/core/dc_wall_filter.sv \
  rtl/core/window_multiplier.sv rtl/core/fft_iterative_256.sv rtl/core/power_calculator.sv \
  rtl/core/peak_bin_detector.sv rtl/core/velocity_mapper.sv rtl/core/doppler_core.sv \
  rtl/board/bram_sample_source.sv rtl/board/crc16_ccitt.sv rtl/board/result_packetizer.sv \
  rtl/board/uart_tx.sv rtl/board/board_top.sv
nextpnr-ice40 --up5k --package sg48 --freq 12 --json build/board_top/board.json \
  --asc build/board_top/board.asc --pcf-allow-unconstrained --report build/board_top/report.json
icepack build/board_top/board.asc build/board_top/board.bin
