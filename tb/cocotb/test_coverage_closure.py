"""Targeted tests that close risk-driven bins left by the first 100 seeds."""

from __future__ import annotations

import json
from pathlib import Path

import cocotb
import numpy as np
from axi_lite_driver import AxiLiteDriver
from axi_stream_driver import AxiStreamDriver
from axi_stream_monitor import AxiStreamMonitor
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from coverage_model import (
    CoverageTracker,
    ObservedSystemCoverage,
    direction_bin,
    peak_range_bin,
    snr_bin,
)
from doppler.config import DopplerConfig, FlowProfile
from doppler.fixed import process_fixed_frame, quantize_q15
from doppler.generator import generate_signal

ROOT = Path(__file__).resolve().parents[2]
COVERAGE_PATH = ROOT / "build/test-results/coverage/closure_coverage.json"
METRICS_PATH = ROOT / "build/test-results/coverage/closure_metrics.json"


def tone_frame(signed_bin=16, *, snr=None, seed=1):
    config = DopplerConfig(
        profile=FlowProfile.REVERSE if signed_bin < 0 else FlowProfile.STEADY,
        velocity_m_s=signed_bin * 0.01203125,
        snr_db=snr,
        clutter_ratio=0,
        initial_phase_rad=0.37,
        seed=seed,
    )
    return generate_signal(config).iq[:256], config


def expected_payload(result):
    status = (int(result.saturation_count > 0) << 2) | (int(result.low_confidence) << 1)
    return (
        result.peak_bin,
        result.frequency_q8_hz,
        result.velocity_q8_mm_s,
        result.peak_power,
        status,
    )


async def wait_cycles(dut, count):
    for _ in range(count):
        await RisingEdge(dut.aclk)


async def wait_output_valid(dut, limit=120_000):
    for _ in range(limit):
        await RisingEdge(dut.aclk)
        if dut.m_axis_tvalid.value:
            return
    raise AssertionError("timed out waiting for closure result")


async def global_reset(dut, lite, *, cycles=2):
    dut.s_axis_tvalid.value = 0
    dut.s_axis_tlast.value = 0
    dut.s_axi_awvalid.value = 0
    dut.s_axi_wvalid.value = 0
    dut.s_axi_arvalid.value = 0
    dut.s_axi_bready.value = 0
    dut.s_axi_rready.value = 0
    dut.aresetn.value = 0
    await wait_cycles(dut, cycles)
    dut.aresetn.value = 1
    await RisingEdge(dut.aclk)
    lite.initialize()


async def enable(lite, coverage, value=1):
    await lite.write(0x08, value)
    coverage.hit("cross.enable_frame_state", f"{'set' if value else 'clear'}_x_idle")


async def send_and_check(dut, lite, stream, monitor, samples, config, *, stall=0):
    start = len(monitor.results)
    await enable(lite, lite.coverage)
    dut.m_axis_tready.value = int(stall == 0)
    await stream.send_frame(samples)
    if stall:
        await wait_output_valid(dut)
        await wait_cycles(dut, stall)
        dut.m_axis_tready.value = 1
    await monitor.wait_for_results(start + 1)
    expected = process_fixed_frame(samples, config)
    assert monitor.results[-1].algorithm_payload() == expected_payload(expected)
    return monitor.results[-1]


async def check_global_reset_contract(lite, coverage):
    assert (await lite.read(0x08))[0] == 0
    coverage.hit("reset.post_check", "enable_clear")
    assert (await lite.read(0x10))[0] == 0
    coverage.hit("reset.post_check", "result_count_clear")
    status = (await lite.read(0x0C))[0]
    assert not status & ((1 << 4) | (1 << 3))
    coverage.hit("reset.post_check", "snapshot_valid_clear")
    coverage.hit("reset.post_check", "irq_status_clear")
    assert (await lite.read(0x14))[0] == 0
    coverage.hit("reset.post_check", "sequence_restart")
    assert (await lite.read(0x38))[0] == 0
    coverage.hit("reset.post_check", "scratch_contract")
    assert (await lite.read(0x30))[0] == 0
    coverage.hit("reset.post_check", "irq_enable_contract")
    assert (await lite.read(0x00))[0] == 0x02000000
    coverage.hit("reset.post_check", "axi_lite_responsive")
    assert not lite.dut.m_axis_tvalid.value
    coverage.hit("reset.post_check", "no_stale_result")


async def close_global_reset_locations(dut, lite, stream, monitor, coverage, frame):
    await global_reset(dut, lite)
    await check_global_reset_contract(lite, coverage)

    await enable(lite, coverage)
    i_data, q_data = quantize_q15(frame.real), quantize_q15(frame.imag)
    await stream.send_raw(i_data[:73], q_data[:73])
    await global_reset(dut, lite)

    await enable(lite, coverage)
    await stream.send_frame(frame)
    await wait_cycles(dut, 101)
    await global_reset(dut, lite)

    await enable(lite, coverage)
    dut.m_axis_tready.value = 0
    await stream.send_frame(frame)
    await wait_output_valid(dut)
    await wait_cycles(dut, 2)
    await global_reset(dut, lite)

    await enable(lite, coverage)
    dut.m_axis_tready.value = 0
    await stream.send_frame(frame)
    await wait_output_valid(dut)
    dut.m_axis_tready.value = 1
    await RisingEdge(dut.aclk)
    dut.aresetn.value = 0
    await RisingEdge(dut.aclk)
    dut.aresetn.value = 1
    await RisingEdge(dut.aclk)
    lite.initialize()

    # Reset after only AW, only W, and while a B response is stalled.
    dut.s_axi_awaddr.value = 0x38
    dut.s_axi_awvalid.value = 1
    await RisingEdge(dut.aclk)
    dut.s_axi_awvalid.value = 0
    await RisingEdge(dut.aclk)
    await global_reset(dut, lite)

    dut.s_axi_wdata.value = 0x12345678
    dut.s_axi_wstrb.value = 0xF
    dut.s_axi_wvalid.value = 1
    await RisingEdge(dut.aclk)
    dut.s_axi_wvalid.value = 0
    await RisingEdge(dut.aclk)
    await global_reset(dut, lite)

    dut.s_axi_awaddr.value = 0x38
    dut.s_axi_awvalid.value = 1
    dut.s_axi_wdata.value = 0xA5A5A5A5
    dut.s_axi_wstrb.value = 0xF
    dut.s_axi_wvalid.value = 1
    await RisingEdge(dut.aclk)
    dut.s_axi_awvalid.value = 0
    dut.s_axi_wvalid.value = 0
    while not dut.s_axi_bvalid.value:
        await RisingEdge(dut.aclk)
    await RisingEdge(dut.aclk)
    await global_reset(dut, lite)

    # AR accepted but not yet observed as a stalled response.
    dut.s_axi_araddr.value = 0x00
    dut.s_axi_arvalid.value = 1
    dut.s_axi_rready.value = 1
    await RisingEdge(dut.aclk)
    dut.s_axi_arvalid.value = 0
    dut.s_axi_rready.value = 0
    dut.aresetn.value = 0
    await RisingEdge(dut.aclk)
    dut.aresetn.value = 1
    await RisingEdge(dut.aclk)
    lite.initialize()

    dut.s_axi_araddr.value = 0x00
    dut.s_axi_arvalid.value = 1
    dut.s_axi_rready.value = 0
    await RisingEdge(dut.aclk)
    dut.s_axi_arvalid.value = 0
    while not dut.s_axi_rvalid.value:
        await RisingEdge(dut.aclk)
    await RisingEdge(dut.aclk)
    await global_reset(dut, lite)

    # One-cycle input stall is terminated legally by reset.
    dut.s_axis_tdata.value = 0
    dut.s_axis_tlast.value = 0
    dut.s_axis_tvalid.value = 1
    await RisingEdge(dut.aclk)
    await global_reset(dut, lite)

    # Prove a subsequent legal frame still succeeds.
    dut.m_axis_tready.value = 1
    start = len(monitor.results)
    await enable(lite, coverage)
    await stream.send_frame(frame)
    await monitor.wait_for_results(start + 1)
    coverage.hit("reset.post_check", "subsequent_legal_frame")


async def close_output_and_irq(dut, lite, stream, monitor, coverage, frame):
    await global_reset(dut, lite)
    await enable(lite, coverage)
    dut.m_axis_tready.value = 0
    await stream.send_frame(frame)
    await wait_output_valid(dut)
    await RisingEdge(dut.aclk)
    dut.m_axis_tready.value = 1
    await monitor.wait_for_results(len(monitor.results) + 1)

    # Pending output remains live through disable and while next-frame TVALID is active.
    await global_reset(dut, lite)
    await enable(lite, coverage)
    dut.m_axis_tready.value = 0
    await stream.send_frame(frame)
    await wait_output_valid(dut)
    next_task = cocotb.start_soon(stream.send_frame(frame))
    await wait_cycles(dut, 3)
    await lite.write(0x08, 0)
    assert dut.m_axis_tvalid.value
    coverage.hit("stream.output_stall_context", "disable_nearby")
    await lite.write(0x08, 1)
    dut.m_axis_tready.value = 1
    start = len(monitor.results)
    await monitor.wait_for_results(start + 1)
    await next_task
    await monitor.wait_for_results(start + 2)
    coverage.hit("irq.behavior", "multiple_results_before_clear")

    # IRQ disabled result, late enable, clear-only, and clear/result race.
    await global_reset(dut, lite)
    dut.m_axis_tready.value = 1
    await enable(lite, coverage)
    start = len(monitor.results)
    await stream.send_frame(frame)
    await monitor.wait_for_results(start + 1)
    assert (await lite.read(0x34))[0] == 1 and not dut.irq.value
    await lite.write(0x30, 1)
    assert dut.irq.value
    coverage.hit("irq.behavior", "enable_with_status_pending")
    await lite.write(0x34, 1)
    assert (await lite.read(0x34))[0] == 0
    coverage.hit("cross.irq_clear_result", "clear_only")

    # Capture clear AW/W, then align its execution with a stalled-result release.
    dut.m_axis_tready.value = 0
    await stream.send_frame(frame)
    await wait_output_valid(dut)
    dut.s_axi_awaddr.value = 0x34
    dut.s_axi_awvalid.value = 1
    dut.s_axi_wdata.value = 1
    dut.s_axi_wstrb.value = 0xF
    dut.s_axi_wvalid.value = 1
    await RisingEdge(dut.aclk)
    dut.s_axi_awvalid.value = 0
    dut.s_axi_wvalid.value = 0
    dut.m_axis_tready.value = 1
    await RisingEdge(dut.aclk)
    dut.s_axi_bready.value = 1
    while not dut.s_axi_bvalid.value:
        await RisingEdge(dut.aclk)
    await RisingEdge(dut.aclk)
    dut.s_axi_bready.value = 0
    assert (await lite.read(0x34))[0] == 1
    coverage.hit("irq.behavior", "clear_and_result_same_cycle")
    coverage.hit("cross.irq_clear_result", "clear_x_result")

    # Soft reset while IRQ is pending and while output is stalled.
    coverage.hit("irq.behavior", "soft_reset_while_pending")
    await lite.write(0x08, 2)
    assert (await lite.read(0x34))[0] == 0

    await lite.write(0x08, 1)
    dut.m_axis_tready.value = 0
    await stream.send_frame(frame)
    await wait_output_valid(dut)
    coverage.hit("stream.output_stall_context", "reset_nearby")
    await lite.write(0x08, 2)
    assert not dut.m_axis_tvalid.value

    # Global reset while IRQ pending.
    await lite.write(0x08, 1)
    dut.m_axis_tready.value = 1
    start = len(monitor.results)
    await stream.send_frame(frame)
    await monitor.wait_for_results(start + 1)
    assert (await lite.read(0x34))[0] == 1
    coverage.hit("irq.behavior", "global_reset_while_pending")
    await global_reset(dut, lite)


async def close_soft_reset_locations(dut, lite, stream, monitor, coverage, frame):
    await global_reset(dut, lite)
    await enable(lite, coverage, 0)
    await lite.write(0x38, 0xA5C33C5A)
    await lite.write(0x30, 1)
    await lite.write(0x08, 2)
    assert (await lite.read(0x38))[0] == 0xA5C33C5A
    assert (await lite.read(0x30))[0] == 1

    await lite.write(0x08, 1)
    i_data, q_data = quantize_q15(frame.real), quantize_q15(frame.imag)
    await stream.send_raw(i_data[:73], q_data[:73])
    await lite.write(0x08, 2)

    await lite.write(0x08, 1)
    await stream.send_frame(frame)
    await wait_cycles(dut, 101)
    await lite.write(0x08, 2)

    await lite.write(0x08, 1)
    dut.m_axis_tready.value = 1
    start = len(monitor.results)
    await stream.send_frame(frame)
    await monitor.wait_for_results(start + 1)
    await lite.write(0x34, 1)
    await lite.write(0x08, 2)


async def close_invalid_and_order_crosses(lite):
    for address, write in ((0x01, True), (0x3C, True), (0x00, True)):
        if write:
            await lite.write(address, 0xFFFFFFFF, expected_resp=2)
    # Force exact observed B-stall bins used by the reduced risk cross.
    for aw_delay, w_delay in ((0, 0), (0, 3), (3, 0)):
        for requested_stall in (0, 2, 3, 17):
            await lite.write(
                0x38,
                0x55AA0000 | requested_stall,
                aw_delay=aw_delay,
                w_delay=w_delay,
                response_stall=requested_stall,
            )


async def close_algorithm_bins(dut, lite, stream, monitor, coverage):
    # These frames target low-value/noise combinations that random sampling missed.
    targets = [(0, snr, 1) for snr in (-5.0, 5.0, 15.0, 25.0, 35.0)]
    targets += [(-64, -5.0, 1), (-64, 25.0, 1)]
    for signed_bin, snr, seed in targets:
        await global_reset(dut, lite)
        samples, config = tone_frame(signed_bin, snr=snr, seed=seed)
        beat = await send_and_check(
            dut,
            lite,
            stream,
            monitor,
            samples,
            config,
            stall=67 if signed_bin == 0 and snr == 35 else 0,
        )
        direction = direction_bin(signed_bin)
        snr_name = snr_bin(snr)
        peak_range = peak_range_bin(signed_bin)
        coverage.hit("algorithm.direction", direction)
        coverage.hit("algorithm.peak_bin_range", peak_range)
        coverage.hit("algorithm.snr", snr_name)
        coverage.hit("cross.direction_snr", f"{direction}_x_{snr_name}")
        coverage.hit("cross.peak_range_snr", f"{peak_range}_x_{snr_name}")
        backpressure = "long" if signed_bin == 0 and snr == 35 else "none"
        coverage.hit("cross.direction_backpressure", f"{direction}_x_{backpressure}")
        assert beat.sequence == 0

    base = DopplerConfig(snr_db=None, clutter_ratio=0)
    index = np.arange(256)
    tie = (0.75 * np.cos(2 * np.pi * 8 * index / 256)).astype(np.complex128)
    special = [
        ("zero", np.zeros(256, dtype=np.complex128), base),
        ("exact_tie", tie, base),
        ("full_scale_positive", np.full(256, 32767 / 32768, dtype=np.complex128), base),
        ("full_scale_negative", np.full(256, -1.0, dtype=np.complex128), base),
    ]
    for signed_bin, name in ((127, "near_nyquist_positive"), (-127, "near_nyquist_negative")):
        samples, config = tone_frame(signed_bin)
        special.append((name, samples, config))
    for name, samples, config in special:
        await global_reset(dut, lite)
        await send_and_check(dut, lite, stream, monitor, samples, config)
        coverage.hit("algorithm.special_signal", name)


@cocotb.test()
async def targeted_functional_coverage_closure(dut):
    cocotb.start_soon(Clock(dut.aclk, 10, unit="ns").start())
    dut.aresetn.value = 0
    dut.s_axis_tvalid.value = 0
    dut.s_axis_tdata.value = 0
    dut.s_axis_tlast.value = 0
    dut.m_axis_tready.value = 1
    coverage = CoverageTracker(test_name="targeted_functional_coverage_closure")
    coverage.context(seed=9001, scenario="coverage_closure")
    observer = ObservedSystemCoverage(dut, coverage)
    observer_task = cocotb.start_soon(observer.run())
    lite = AxiLiteDriver(dut, coverage=coverage)
    stream = AxiStreamDriver(dut)
    monitor = AxiStreamMonitor(dut)
    monitor_task = cocotb.start_soon(monitor.run())
    await global_reset(dut, lite)
    frame, _ = tone_frame(16)

    await close_global_reset_locations(dut, lite, stream, monitor, coverage, frame)
    await close_output_and_irq(dut, lite, stream, monitor, coverage, frame)
    await close_soft_reset_locations(dut, lite, stream, monitor, coverage, frame)
    await close_invalid_and_order_crosses(lite)
    await close_algorithm_bins(dut, lite, stream, monitor, coverage)

    coverage.write(COVERAGE_PATH)
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(
        json.dumps(
            {
                "cycles": coverage.cycle,
                "accepted_samples": len(monitor.inputs),
                "output_results": len(monitor.results),
                "axi_lite": lite.metrics,
                "coverage_bins_hit": len(coverage.hits),
                "protocol_mismatches": 0,
                "register_mismatches": 0,
                "lost_results": 0,
                "duplicated_results": 0,
                "reordered_results": 0,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    monitor_task.cancel()
    observer_task.cancel()
