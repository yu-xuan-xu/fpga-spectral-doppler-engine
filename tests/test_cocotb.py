"""Compile and launch cocotb integration tests through pytest."""

import os
from pathlib import Path

from cocotb_tools.runner import get_runner


def test_doppler_core_cocotb():
    root = Path(__file__).resolve().parents[1]
    rtl = root / "rtl" / "core"
    sources = [
        rtl / "sync_ram_256x16.sv",
        rtl / "frame_checker_256.sv",
        rtl / "dc_wall_filter.sv",
        rtl / "window_multiplier.sv",
        rtl / "fft_iterative_256.sv",
        rtl / "power_calculator.sv",
        rtl / "peak_bin_detector.sv",
        rtl / "velocity_mapper.sv",
        rtl / "doppler_core.sv",
    ]
    runner = get_runner("icarus")
    runner.build(
        sources=sources,
        hdl_toplevel="doppler_core",
        build_dir=root / "build" / "cocotb_core",
        includes=[rtl],
        build_args=["-g2012"],
        timescale=("1ns", "1ps"),
        always=True,
    )
    runner.test(
        hdl_toplevel="doppler_core",
        test_module="test_doppler_core",
        test_dir=root / "tb" / "cocotb",
    )


def test_packetizer_cocotb():
    root = Path(__file__).resolve().parents[1]
    board = root / "rtl" / "board"
    runner = get_runner("icarus")
    runner.build(
        sources=[board / "crc16_ccitt.sv", board / "result_packetizer.sv"],
        hdl_toplevel="result_packetizer",
        build_dir=root / "build" / "cocotb_packetizer",
        build_args=["-g2012"],
        timescale=("1ns", "1ps"),
        always=True,
    )
    runner.test(
        hdl_toplevel="result_packetizer",
        test_module="test_packetizer",
        test_dir=root / "tb" / "cocotb",
    )


def test_v1_performance_cocotb():
    root = Path(__file__).resolve().parents[1]
    rtl = root / "rtl" / "core"
    sources = [
        rtl / "sync_ram_256x16.sv",
        rtl / "frame_checker_256.sv",
        rtl / "dc_wall_filter.sv",
        rtl / "window_multiplier.sv",
        rtl / "fft_iterative_256.sv",
        rtl / "power_calculator.sv",
        rtl / "peak_bin_detector.sv",
        rtl / "velocity_mapper.sv",
        rtl / "doppler_core.sv",
    ]
    runner = get_runner("icarus")
    runner.build(
        sources=sources,
        hdl_toplevel="doppler_core",
        build_dir=root / "build" / "cocotb_v1_performance",
        includes=[rtl],
        build_args=["-g2012"],
        timescale=("1ns", "1ps"),
        always=True,
    )
    runner.test(
        hdl_toplevel="doppler_core",
        test_module="test_v1_performance",
        test_dir=root / "tb" / "cocotb",
    )


def test_stream_contract_cocotb():
    root = Path(__file__).resolve().parents[1]
    rtl = root / "rtl" / "core"
    sources = [
        rtl / "sync_ram_256x16.sv",
        rtl / "frame_checker_256.sv",
        rtl / "dc_wall_filter.sv",
        rtl / "window_multiplier.sv",
        rtl / "fft_iterative_256.sv",
        rtl / "power_calculator.sv",
        rtl / "peak_bin_detector.sv",
        rtl / "velocity_mapper.sv",
        rtl / "doppler_core.sv",
        root / "rtl" / "assertions" / "doppler_stream_sva.sv",
    ]
    runner = get_runner("icarus")
    runner.build(
        sources=sources,
        hdl_toplevel="doppler_core_contract_top",
        build_dir=root / "build" / "cocotb_stream_contract",
        includes=[rtl],
        build_args=["-g2012"],
        timescale=("1ns", "1ps"),
        always=True,
    )
    runner.test(
        hdl_toplevel="doppler_core_contract_top",
        test_module="test_stream_contract",
        test_dir=root / "tb" / "cocotb",
    )


def axi_sources(root):
    rtl = root / "rtl" / "core"
    return [
        rtl / "sync_ram_256x16.sv",
        rtl / "frame_checker_256.sv",
        rtl / "dc_wall_filter.sv",
        rtl / "window_multiplier.sv",
        rtl / "fft_iterative_256.sv",
        rtl / "power_calculator.sv",
        rtl / "peak_bin_detector.sv",
        rtl / "velocity_mapper.sv",
        rtl / "doppler_core.sv",
        root / "rtl" / "axi" / "doppler_axi_stream_wrapper.sv",
        root / "rtl" / "assertions" / "doppler_axi_stream_sva.sv",
    ]


def run_axi_cocotb(*, test_module, top, build_name, parameters=None):
    root = Path(__file__).resolve().parents[1]
    runner = get_runner("icarus")
    runner.build(
        sources=axi_sources(root),
        hdl_toplevel=top,
        build_dir=root / "build" / build_name,
        includes=[root / "rtl" / "core"],
        build_args=["-g2012"],
        parameters=parameters or {},
        timescale=("1ns", "1ps"),
        always=True,
    )
    runner.test(
        hdl_toplevel=top,
        test_module=test_module,
        test_dir=root / "tb" / "cocotb",
        parameters=parameters or {},
    )


def test_axi_stream_cocotb():
    run_axi_cocotb(
        test_module="test_axi_stream_wrapper",
        top="doppler_axi_contract_top",
        build_name="cocotb_axi_stream",
    )


def test_axi_sequence_wrap_cocotb():
    run_axi_cocotb(
        test_module="test_axi_sequence_wrap",
        top="doppler_axi_contract_top",
        build_name="cocotb_axi_sequence_wrap",
        parameters={"RESULT_SEQUENCE_RESET_VALUE": 0xFFFF_FFFE},
    )


def test_axi_legacy_equivalence_cocotb():
    run_axi_cocotb(
        test_module="test_axi_legacy_equivalence",
        top="doppler_axi_equivalence_top",
        build_name="cocotb_axi_legacy_equivalence",
    )


def test_axi_lite_regs_cocotb():
    root = Path(__file__).resolve().parents[1]
    runner = get_runner("icarus")
    runner.build(
        sources=[
            root / "rtl" / "axi" / "doppler_axi_lite_regs.sv",
            root / "rtl" / "assertions" / "doppler_axi_lite_sva.sv",
        ],
        hdl_toplevel="doppler_axi_lite_contract_top",
        build_dir=root / "build" / "cocotb_axi_lite_regs",
        build_args=["-g2012"],
        timescale=("1ns", "1ps"),
        always=True,
    )
    runner.test(
        hdl_toplevel="doppler_axi_lite_contract_top",
        test_module="test_axi_lite_regs",
        test_dir=root / "tb" / "cocotb",
    )


def test_axi_controlled_top_cocotb():
    root = Path(__file__).resolve().parents[1]
    sources = axi_sources(root)[:-1] + [
        root / "rtl" / "axi" / "doppler_axi_lite_regs.sv",
        root / "rtl" / "axi" / "doppler_axi_controlled_top.sv",
    ]
    runner = get_runner("icarus")
    runner.build(
        sources=sources,
        hdl_toplevel="doppler_axi_controlled_top",
        build_dir=root / "build" / "cocotb_axi_controlled_top",
        includes=[root / "rtl" / "core"],
        build_args=["-g2012"],
        timescale=("1ns", "1ps"),
        always=True,
    )
    runner.test(
        hdl_toplevel="doppler_axi_controlled_top",
        test_module="test_axi_controlled_top",
        test_dir=root / "tb" / "cocotb",
    )


def test_random_system_regression_cocotb():
    root = Path(__file__).resolve().parents[1]
    sources = axi_sources(root)[:-1] + [
        root / "rtl" / "axi" / "doppler_axi_lite_regs.sv",
        root / "rtl" / "axi" / "doppler_axi_controlled_top.sv",
    ]
    runner = get_runner("icarus")
    runner.build(
        sources=sources,
        hdl_toplevel="doppler_axi_controlled_top",
        build_dir=root / "build" / "cocotb_random_system",
        includes=[root / "rtl" / "core"],
        build_args=["-g2012"],
        timescale=("1ns", "1ps"),
        always=True,
    )
    runner.test(
        hdl_toplevel="doppler_axi_controlled_top",
        test_module="test_random_system_regression",
        test_dir=root / "tb" / "cocotb",
        waves=os.environ.get("DOPPLER_WAVES") == "1",
    )


def test_coverage_closure_cocotb():
    root = Path(__file__).resolve().parents[1]
    sources = axi_sources(root)[:-1] + [
        root / "rtl" / "axi" / "doppler_axi_lite_regs.sv",
        root / "rtl" / "axi" / "doppler_axi_controlled_top.sv",
    ]
    runner = get_runner("icarus")
    runner.build(
        sources=sources,
        hdl_toplevel="doppler_axi_controlled_top",
        build_dir=root / "build" / "cocotb_coverage_closure",
        includes=[root / "rtl" / "core"],
        build_args=["-g2012"],
        timescale=("1ns", "1ps"),
        always=True,
    )
    runner.test(
        hdl_toplevel="doppler_axi_controlled_top",
        test_module="test_coverage_closure",
        test_dir=root / "tb" / "cocotb",
    )
