#!/bin/sh
set -eu
mkdir -p build/sim
mkdir -p build/test-results
.venv/bin/ruff check python tests scripts demo tb/cocotb
.venv/bin/ruff format --check python tests scripts demo tb/cocotb
.venv/bin/pytest --junitxml=build/test-results/pytest.xml
.venv/bin/python scripts/generate_fft_assets.py
iverilog -g2012 -I rtl/core -s tb_fft_iterative -o build/sim/tb_fft.vvp \
  rtl/core/sync_ram_256x16.sv rtl/core/fft_iterative_256.sv tb/sv/tb_fft_iterative.sv
vvp build/sim/tb_fft.vvp
iverilog -g2012 -I rtl/core -s tb_doppler_core -o build/sim/tb_core.vvp \
  rtl/core/sync_ram_256x16.sv rtl/core/frame_checker_256.sv rtl/core/dc_wall_filter.sv \
  rtl/core/window_multiplier.sv \
  rtl/core/fft_iterative_256.sv rtl/core/power_calculator.sv rtl/core/peak_bin_detector.sv \
  rtl/core/velocity_mapper.sv rtl/core/doppler_core.sv tb/sv/tb_doppler_core.sv
vvp build/sim/tb_core.vvp
iverilog -g2012 -s tb_velocity_mapper -o build/sim/tb_mapper.vvp \
  rtl/core/velocity_mapper.sv tb/sv/tb_velocity_mapper.sv
vvp build/sim/tb_mapper.vvp
printf '%s\n' '{"doppler_core":true,"fft_iterative_256":true,"signed_velocity_mapper":true}' \
  > build/test-results/standalone_rtl.json
