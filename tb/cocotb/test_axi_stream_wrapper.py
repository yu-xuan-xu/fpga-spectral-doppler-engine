"""AXI4-Stream protocol, packing, backpressure, reset, and error tests."""

from __future__ import annotations

import json
import random
from pathlib import Path

import cocotb
import numpy as np
from axi_stream_driver import AxiStreamDriver
from axi_stream_monitor import AxiResultBeat, AxiStreamMonitor
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from doppler.config import DopplerConfig, FlowProfile
from doppler.fixed import FixedFilterState, process_fixed_frame, quantize_q15
from doppler.generator import generate_signal

RESULT_GUARD_CYCLES = 16_000
METRICS_DIRECTORY = Path(__file__).resolve().parents[2] / "build" / "test-results" / "axi_metrics"


def config_for_bin(signed_bin: int) -> DopplerConfig:
    return DopplerConfig(
        profile=FlowProfile.STEADY if signed_bin >= 0 else FlowProfile.REVERSE,
        velocity_m_s=signed_bin * 0.01203125,
        snr_db=None,
        clutter_ratio=0,
        initial_phase_rad=0.37,
    )


def tone_frame(signed_bin: int) -> tuple[np.ndarray, DopplerConfig]:
    config = config_for_bin(signed_bin)
    return generate_signal(config).iq[:256], config


def expected_payload(result, *, frame_error: bool = False):
    status = (int(result.saturation_count > 0) << 2) | (int(result.low_confidence) << 1)
    status |= int(frame_error)
    return (
        result.peak_bin,
        result.frequency_q8_hz,
        result.velocity_q8_mm_s,
        result.peak_power,
        status,
    )


def check_result(beat: AxiResultBeat, expected, sequence: int) -> None:
    assert beat.algorithm_payload() == expected
    assert beat.sequence == sequence
    assert beat.reserved == 0
    assert beat.last


def write_metrics(
    name: str,
    monitor: AxiStreamMonitor,
    *,
    expected_outputs: int,
    malformed_frames: int = 0,
    random_seeds: list[int] | None = None,
    packing_checks: int = 0,
    sequence_checks: int = 0,
    legacy_checks: int = 0,
) -> None:
    METRICS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    payload = {
        "name": name,
        "expected_output_beats": expected_outputs,
        "frames_transferred": expected_outputs,
        "axi_input_beats": len(monitor.inputs),
        "axi_output_beats": len(monitor.results),
        "input_stall_cycles": monitor.input_stall_cycles,
        "output_stall_cycles": monitor.output_stall_cycles,
        "reset_injections": monitor.reset_injections,
        "malformed_frames": malformed_frames,
        "random_seeds": random_seeds or [],
        "packing_checks": packing_checks,
        "sequence_checks": sequence_checks,
        "legacy_checks": legacy_checks,
    }
    METRICS_DIRECTORY.joinpath(f"{name}.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


async def environment(dut, *, output_ready: int = 1):
    cocotb.start_soon(Clock(dut.aclk, 10, unit="ns").start())
    driver = AxiStreamDriver(dut)
    monitor = AxiStreamMonitor(dut)
    task = cocotb.start_soon(monitor.run())
    await driver.reset(output_ready=output_ready)
    return driver, monitor, task


async def wait_output_valid(dut, *, limit: int = 120_000) -> None:
    for _ in range(limit):
        await RisingEdge(dut.aclk)
        if dut.m_axis_tvalid.value:
            return
    raise AssertionError("timed out waiting for AXI output valid")


@cocotb.test()
async def single_frame_packing_and_iq_unpack(dut):
    driver, monitor, task = await environment(dut)
    frame, config = tone_frame(-16)
    expected = process_fixed_frame(frame, config)
    expected_i = quantize_q15(frame.real)
    expected_q = quantize_q15(frame.imag)

    await driver.send_frame(frame)
    await monitor.wait_for_results(1)
    check_result(monitor.results[0], expected_payload(expected), 0)
    assert [beat.i for beat in monitor.inputs] == expected_i.tolist()
    assert [beat.q for beat in monitor.inputs] == expected_q.tolist()
    assert sum(beat.last for beat in monitor.inputs) == 1
    assert int(dut.assertion_checked_cycles.value) > 0
    write_metrics(
        "single_frame_packing_and_iq_unpack",
        monitor,
        expected_outputs=1,
        packing_checks=1,
        sequence_checks=1,
    )
    task.cancel()


@cocotb.test()
async def three_back_to_back_frames_are_ordered(dut):
    driver, monitor, task = await environment(dut)
    state = FixedFilterState()
    expected = []
    for signed_bin in (16, -16, 64):
        frame, config = tone_frame(signed_bin)
        result = process_fixed_frame(frame, config, state)
        state = result.state
        expected.append(expected_payload(result))
        await driver.send_frame(frame)
    await monitor.wait_for_results(3)
    for sequence, (beat, payload) in enumerate(zip(monitor.results, expected, strict=True)):
        check_result(beat, payload, sequence)
    await driver.idle(50)
    assert len(monitor.results) == 3
    write_metrics(
        "three_back_to_back_frames_are_ordered",
        monitor,
        expected_outputs=3,
        packing_checks=3,
        sequence_checks=3,
    )
    task.cancel()


@cocotb.test()
async def randomized_input_gaps_preserve_all_frames(dut):
    driver, monitor, task = await environment(dut)
    rng = random.Random(2201)
    state = FixedFilterState()
    expected = []
    for signed_bin in (2, 16, -64):
        frame, config = tone_frame(signed_bin)
        result = process_fixed_frame(frame, config, state)
        state = result.state
        expected.append(expected_payload(result))
        gaps = [rng.randrange(5) for _ in range(256)]
        await driver.send_frame(frame, gaps=lambda index, values=gaps: values[index])
    await monitor.wait_for_results(3)
    for sequence, (beat, payload) in enumerate(zip(monitor.results, expected, strict=True)):
        check_result(beat, payload, sequence)
    write_metrics(
        "randomized_input_gaps_preserve_all_frames",
        monitor,
        expected_outputs=3,
        random_seeds=[2201],
        packing_checks=3,
        sequence_checks=3,
    )
    task.cancel()


@cocotb.test()
async def randomized_output_backpressure_is_lossless(dut):
    driver, monitor, task = await environment(dut, output_ready=0)
    rng = random.Random(3301)
    state = FixedFilterState()
    expected = []

    async def ready_driver():
        prior_ready = False
        while len(monitor.results) < 3:
            ready = False if prior_ready else bool(rng.randrange(3))
            dut.m_axis_tready.value = int(ready)
            prior_ready = ready
            await RisingEdge(dut.aclk)
        dut.m_axis_tready.value = 1

    ready_task = cocotb.start_soon(ready_driver())
    for signed_bin in (3, -3, 127):
        frame, config = tone_frame(signed_bin)
        result = process_fixed_frame(frame, config, state)
        state = result.state
        expected.append(expected_payload(result))
        await driver.send_frame(frame)
    await monitor.wait_for_results(3)
    await ready_task
    for sequence, (beat, payload) in enumerate(zip(monitor.results, expected, strict=True)):
        check_result(beat, payload, sequence)
    assert monitor.output_stall_cycles > 0
    write_metrics(
        "randomized_output_backpressure_is_lossless",
        monitor,
        expected_outputs=3,
        random_seeds=[3301],
        packing_checks=3,
        sequence_checks=3,
    )
    task.cancel()


@cocotb.test()
async def long_output_stall_holds_complete_result(dut):
    driver, monitor, task = await environment(dut, output_ready=0)
    first_frame, first_config = tone_frame(16)
    first_expected = process_fixed_frame(first_frame, first_config)
    await driver.send_frame(first_frame)
    await wait_output_valid(dut)
    held_data = int(dut.m_axis_tdata.value)
    held_last = bool(dut.m_axis_tlast.value)
    for _ in range(83):
        await RisingEdge(dut.aclk)
        assert dut.m_axis_tvalid.value
        assert int(dut.m_axis_tdata.value) == held_data
        assert bool(dut.m_axis_tlast.value) == held_last
        assert (held_data & 0xFFFF_FFFF) == 0
    dut.m_axis_tready.value = 1
    await monitor.wait_for_results(1)
    check_result(monitor.results[0], expected_payload(first_expected), 0)

    second_frame, second_config = tone_frame(-16)
    second_expected = process_fixed_frame(second_frame, second_config, first_expected.state)
    await driver.send_frame(second_frame)
    await monitor.wait_for_results(2)
    check_result(monitor.results[1], expected_payload(second_expected), 1)
    assert monitor.output_stall_cycles >= 83
    write_metrics(
        "long_output_stall_holds_complete_result",
        monitor,
        expected_outputs=2,
        packing_checks=2,
        sequence_checks=2,
    )
    task.cancel()


@cocotb.test()
async def reset_scenarios_abort_work_and_restart_sequence(dut):
    driver, monitor, task = await environment(dut)
    frame, config = tone_frame(-16)
    i_values = quantize_q15(frame.real)
    q_values = quantize_q15(frame.imag)
    expected = expected_payload(process_fixed_frame(frame, config))

    # Collecting.
    await driver.send_raw(i_values[:73], q_values[:73])
    await driver.reset(output_ready=1)
    await driver.send_frame(frame)
    await monitor.wait_for_results(1)
    check_result(monitor.results[-1], expected, 0)

    # Processing.
    await driver.send_frame(frame)
    await driver.idle(200)
    await driver.reset(output_ready=1)
    result_count = len(monitor.results)
    await driver.idle(RESULT_GUARD_CYCLES)
    assert len(monitor.results) == result_count
    await driver.send_frame(frame)
    await monitor.wait_for_results(result_count + 1)
    check_result(monitor.results[-1], expected, 0)

    # Output stalled.
    dut.m_axis_tready.value = 0
    await driver.send_frame(frame)
    await wait_output_valid(dut)
    await RisingEdge(dut.aclk)
    await driver.reset(output_ready=1)
    result_count = len(monitor.results)
    await driver.idle(200)
    assert len(monitor.results) == result_count
    await driver.send_frame(frame)
    await monitor.wait_for_results(result_count + 1)
    check_result(monitor.results[-1], expected, 0)

    # Between frames.
    await driver.reset(output_ready=1)
    result_count = len(monitor.results)
    await driver.send_frame(frame)
    await monitor.wait_for_results(result_count + 1)
    check_result(monitor.results[-1], expected, 0)

    write_metrics(
        "reset_scenarios_abort_work_and_restart_sequence",
        monitor,
        expected_outputs=4,
        packing_checks=4,
        sequence_checks=4,
    )
    task.cancel()


@cocotb.test()
async def malformed_frames_preserve_core_error_semantics(dut):
    driver, monitor, task = await environment(dut)
    frame, config = tone_frame(16)
    i_values = quantize_q15(frame.real)
    q_values = quantize_q15(frame.imag)
    expected = process_fixed_frame(frame, config)

    await driver.send_raw(i_values[:19], q_values[:19], last_indices={18})
    await driver.idle(RESULT_GUARD_CYCLES)
    assert not monitor.results
    await driver.send_frame(frame)
    await monitor.wait_for_results(1)
    check_result(monitor.results[-1], expected_payload(expected, frame_error=True), 0)

    await driver.reset(output_ready=1)
    result_count = len(monitor.results)
    await driver.send_frame(frame, assert_last=False)
    await driver.send_raw(i_values[:13], q_values[:13], last_indices={12})
    await driver.idle(RESULT_GUARD_CYCLES)
    assert len(monitor.results) == result_count
    await driver.send_frame(frame)
    await monitor.wait_for_results(result_count + 1)
    check_result(monitor.results[-1], expected_payload(expected, frame_error=True), 0)

    write_metrics(
        "malformed_frames_preserve_core_error_semantics",
        monitor,
        expected_outputs=2,
        malformed_frames=2,
        packing_checks=2,
        sequence_checks=2,
    )
    task.cancel()


@cocotb.test()
async def numeric_edges_and_ten_directed_bins_match(dut):
    driver, monitor, task = await environment(dut)
    base_config = DopplerConfig(snr_db=None, clutter_ratio=0)
    index = np.arange(256)
    raw_rounding = np.resize(np.array([1, -1, 3, -3, 16384, -16384, 32767, -32768]), 256)
    tie = (0.75 * np.cos(2 * np.pi * 8 * index / 256)).astype(np.complex128)
    tie_expected = process_fixed_frame(tie, base_config)
    assert tie_expected.peak_power == tie_expected.second_power
    assert tie_expected.peak_bin == -8

    cases = [
        ("zero", np.zeros(256, dtype=np.complex128), base_config),
        ("full_positive", np.full(256, 32767 / 32768, dtype=np.complex128), base_config),
        ("full_negative", np.full(256, -1.0, dtype=np.complex128), base_config),
        ("rounding", (raw_rounding / 32768).astype(np.complex128), base_config),
        ("tie", tie, base_config),
    ]
    for signed_bin in [2, 3, 16, 64, 127, -2, -3, -16, -64, -127]:
        samples, config = tone_frame(signed_bin)
        cases.append((f"signed_bin_{signed_bin}", samples, config))

    for name, samples, config in cases:
        await driver.reset(output_ready=1)
        result_count = len(monitor.results)
        expected = process_fixed_frame(samples, config)
        await driver.send_frame(samples)
        await monitor.wait_for_results(result_count + 1)
        check_result(monitor.results[-1], expected_payload(expected), 0)
        assert monitor.results[-1].algorithm_payload() == expected_payload(expected), name

    write_metrics(
        "numeric_edges_and_ten_directed_bins_match",
        monitor,
        expected_outputs=len(cases),
        packing_checks=len(cases),
        sequence_checks=len(cases),
    )
    task.cancel()
