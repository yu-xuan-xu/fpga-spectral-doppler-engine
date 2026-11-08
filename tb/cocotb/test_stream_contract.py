"""Public-interface contract tests for the canonical Doppler core."""

from __future__ import annotations

import cocotb
import numpy as np
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from doppler.config import DopplerConfig, FlowProfile
from doppler.fixed import FixedFilterState, process_fixed_frame, quantize_q15
from doppler.generator import generate_signal
from stream_driver import StreamDriver
from stream_monitor import StreamMonitor

RESULT_GUARD_CYCLES = 16_000


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


async def environment(dut, *, output_ready: int = 1):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    driver = StreamDriver(dut)
    monitor = StreamMonitor(dut)
    task = cocotb.start_soon(monitor.run())
    await driver.reset(output_ready=output_ready)
    return driver, monitor, task


async def wait_high(dut, signal, *, limit: int = 120_000) -> None:
    for _ in range(limit):
        await RisingEdge(dut.clk)
        if signal.value:
            return
    raise AssertionError("timed out waiting for signal")


@cocotb.test()
async def legal_single_and_three_back_to_back_are_ordered(dut):
    driver, monitor, task = await environment(dut)
    state = FixedFilterState()
    expected = []

    first_frame, first_config = tone_frame(16)
    first_result = process_fixed_frame(first_frame, first_config, state)
    state = first_result.state
    expected.append(expected_payload(first_result))
    await driver.send_frame(first_frame)
    await monitor.wait_for_results(1)

    for signed_bin in (2, -16, 64):
        frame, config = tone_frame(signed_bin)
        result = process_fixed_frame(frame, config, state)
        state = result.state
        expected.append(expected_payload(result))
        await driver.send_frame(frame)
    await monitor.wait_for_results(4)

    assert [item.payload() for item in monitor.results] == expected
    assert len(monitor.inputs) == 4 * 256
    assert sum(item.last for item in monitor.inputs) == 4
    await driver.idle(50)
    assert len(monitor.results) == 4
    assert int(dut.assertion_checked_cycles.value) > 0
    task.cancel()


@cocotb.test()
async def long_input_gaps_and_output_stall_hold_payload(dut):
    driver, monitor, task = await environment(dut, output_ready=0)
    frame, config = tone_frame(16)
    expected = process_fixed_frame(frame, config)

    await driver.send_frame(frame, gaps=lambda index: 9 if index % 31 == 0 else 0)
    await wait_high(dut, dut.m_valid)
    payload = monitor.current_payload()
    for _ in range(41):
        await RisingEdge(dut.clk)
        assert dut.m_valid.value
        assert monitor.current_payload() == payload
    dut.m_ready.value = 1
    await monitor.wait_for_results(1)

    assert monitor.results[0].payload() == expected_payload(expected)
    assert monitor.stalled_result_cycles >= 41
    assert len(monitor.results) == 1
    task.cancel()


@cocotb.test()
async def reset_aborts_collecting_processing_and_stalled_result(dut):
    driver, monitor, task = await environment(dut, output_ready=1)
    frame, config = tone_frame(-16)
    i_values = quantize_q15(frame.real)
    q_values = quantize_q15(frame.imag)

    # Reset while collecting a partial frame.
    await driver.send_raw(i_values[:73], q_values[:73])
    await driver.reset(output_ready=1)
    await driver.send_frame(frame)
    await monitor.wait_for_results(1)
    assert monitor.results[-1].payload() == expected_payload(process_fixed_frame(frame, config))

    # Reset after a legal frame has entered processing but before any result.
    await driver.reset(output_ready=1)
    result_count = len(monitor.results)
    await driver.send_frame(frame)
    await driver.idle(200)
    assert len(monitor.results) == result_count
    await driver.reset(output_ready=1)
    await driver.idle(RESULT_GUARD_CYCLES)
    assert len(monitor.results) == result_count
    await driver.send_frame(frame)
    await monitor.wait_for_results(result_count + 1)
    assert monitor.results[-1].payload() == expected_payload(process_fixed_frame(frame, config))

    # Reset while result_valid is stalled; the aborted result is never accepted.
    await driver.reset(output_ready=0)
    result_count = len(monitor.results)
    await driver.send_frame(frame)
    await wait_high(dut, dut.m_valid)
    await RisingEdge(dut.clk)
    assert dut.m_valid.value
    await driver.reset(output_ready=1)
    assert not dut.m_valid.value
    await driver.idle(200)
    assert len(monitor.results) == result_count
    await driver.send_frame(frame)
    await monitor.wait_for_results(result_count + 1)
    assert monitor.results[-1].payload() == expected_payload(process_fixed_frame(frame, config))
    task.cancel()


@cocotb.test()
async def malformed_frames_do_not_emit_and_next_result_reports_error(dut):
    driver, monitor, task = await environment(dut, output_ready=1)
    frame, config = tone_frame(16)
    i_values = quantize_q15(frame.real)
    q_values = quantize_q15(frame.imag)
    expected = process_fixed_frame(frame, config)

    # Early last: the 19-sample malformed frame is discarded immediately.
    await driver.send_raw(i_values[:19], q_values[:19], last_indices={18})
    await driver.idle(RESULT_GUARD_CYCLES)
    assert not monitor.results
    await driver.send_frame(frame)
    await monitor.wait_for_results(1)
    assert monitor.results[-1].payload() == expected_payload(expected, frame_error=True)

    # Missing last at accepted sample 256 enters DISCARD. Extra samples are
    # oversized/discarded until a later last re-establishes the boundary.
    await driver.reset(output_ready=1)
    result_count = len(monitor.results)
    await driver.send_frame(frame, assert_last=False)
    await driver.send_raw(i_values[:13], q_values[:13], last_indices={12})
    await driver.idle(RESULT_GUARD_CYCLES)
    assert len(monitor.results) == result_count
    await driver.send_frame(frame)
    await monitor.wait_for_results(result_count + 1)
    assert monitor.results[-1].payload() == expected_payload(expected, frame_error=True)
    task.cancel()


@cocotb.test()
async def numerical_edge_frames_match_the_bit_accurate_oracle(dut):
    driver, monitor, task = await environment(dut, output_ready=1)
    base_config = DopplerConfig(snr_db=None, clutter_ratio=0)
    index = np.arange(256)
    raw_rounding = np.resize(np.array([1, -1, 3, -3, 16384, -16384, 32767, -32768]), 256)
    tie = (0.75 * np.cos(2 * np.pi * 8 * index / 256)).astype(np.complex128)
    tie_expected = process_fixed_frame(tie, base_config)
    assert tie_expected.peak_power == tie_expected.second_power
    assert tie_expected.peak_bin == -8

    cases = [
        ("zero", np.zeros(256, dtype=np.complex128), base_config),
        (
            "full_scale",
            np.where(index % 2, 32767 / 32768, -1.0).astype(np.complex128),
            base_config,
        ),
        ("rounding_boundaries", (raw_rounding / 32768).astype(np.complex128), base_config),
        ("exact_tie", tie, base_config),
    ]
    for signed_bin in (127, -127):
        samples, config = tone_frame(signed_bin)
        cases.append((f"near_nyquist_{signed_bin}", samples, config))

    for name, samples, config in cases:
        await driver.reset(output_ready=1)
        result_count = len(monitor.results)
        expected = process_fixed_frame(samples, config)
        await driver.send_frame(samples)
        await monitor.wait_for_results(result_count + 1)
        assert monitor.results[-1].payload() == expected_payload(expected), name
    task.cancel()


@cocotb.test()
async def ten_directed_signed_bins_match_every_result_field(dut):
    driver, monitor, task = await environment(dut, output_ready=1)
    signed_bins = [2, 3, 16, 64, 127, -2, -3, -16, -64, -127]
    for signed_bin in signed_bins:
        await driver.reset(output_ready=1)
        result_count = len(monitor.results)
        frame, config = tone_frame(signed_bin)
        expected = process_fixed_frame(frame, config)
        await driver.send_frame(frame, gaps=lambda index: 3 if index % 47 == 0 else 0)
        await monitor.wait_for_results(result_count + 1)
        assert monitor.results[-1].payload() == expected_payload(expected), signed_bin
    assert len(monitor.results) == len(signed_bins)
    await driver.idle(50)
    assert len(monitor.results) == len(signed_bins)
    task.cancel()
