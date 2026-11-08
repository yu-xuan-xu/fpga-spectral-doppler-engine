#!/bin/sh
set -eu
mkdir -p build/axi_controlled_top
yosys -q -p 'read_verilog -sv -Irtl/core rtl/core/sync_ram_256x16.sv rtl/core/frame_checker_256.sv rtl/core/dc_wall_filter.sv rtl/core/window_multiplier.sv rtl/core/fft_iterative_256.sv rtl/core/power_calculator.sv rtl/core/peak_bin_detector.sv rtl/core/velocity_mapper.sv rtl/core/doppler_core.sv rtl/axi/doppler_axi_stream_wrapper.sv rtl/axi/doppler_axi_lite_regs.sv rtl/axi/doppler_axi_controlled_top.sv; hierarchy -check -top doppler_axi_controlled_top; proc; check; tee -o build/axi_controlled_top/stats.json stat -json; write_json build/axi_controlled_top/elaborated.json'
