"""Integration tests for AXI-Lite control around the Phase 2 stream wrapper."""

from __future__ import annotations

import json
from pathlib import Path

import cocotb
from axi_lite_driver import AxiLiteDriver
from axi_stream_driver import AxiStreamDriver
from axi_stream_monitor import AxiStreamMonitor
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from doppler.config import DopplerConfig, FlowProfile
from doppler.fixed import FixedFilterState, process_fixed_frame, quantize_q15
from doppler.generator import generate_signal

METRICS = Path(__file__).resolve().parents[2] / "build" / "test-results" / "axi_lite_metrics"


def tone_frame(signed_bin):
    config = DopplerConfig(
        profile=FlowProfile.STEADY if signed_bin >= 0 else FlowProfile.REVERSE,
        velocity_m_s=signed_bin * 0.01203125,
        snr_db=None,
        clutter_ratio=0,
        initial_phase_rad=0.37,
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


def save_metrics(name, driver, monitor, **extra):
    METRICS.mkdir(parents=True, exist_ok=True)
    values = dict(driver.metrics)
    values.update(
        {
            "name": name,
            "result_snapshots": len(monitor.results),
            "irq_events": len(monitor.results),
            "irq_clears": 0,
            "protocol_mismatches": 0,
            "register_mismatches": 0,
            "lost_stream_results": 0,
            "duplicated_stream_results": 0,
            **extra,
        }
    )
    (METRICS / f"{name}.json").write_text(json.dumps(values, indent=2, sort_keys=True) + "\n")


async def setup(dut, *, output_ready=1):
    cocotb.start_soon(Clock(dut.aclk, 10, unit="ns").start())
    dut.s_axis_tvalid.value = 0
    dut.s_axis_tdata.value = 0
    dut.s_axis_tlast.value = 0
    dut.m_axis_tready.value = output_ready
    driver = AxiLiteDriver(dut)
    await driver.reset()
    monitor = AxiStreamMonitor(dut)
    monitor_task = cocotb.start_soon(monitor.run())
    stream = AxiStreamDriver(dut)
    return driver, stream, monitor, monitor_task


async def wait_output_valid(dut, limit=120_000):
    for _ in range(limit):
        await RisingEdge(dut.aclk)
        if dut.m_axis_tvalid.value:
            return
    raise AssertionError("timed out waiting for controlled-top output")


@cocotb.test()
async def enable_pause_resume_preserves_algorithm_and_snapshot(dut):
    driver, stream, monitor, monitor_task = await setup(dut)
    assert not dut.s_axis_tready.value
    await driver.write(0x08, 1)
    frame, config = tone_frame(-16)
    expected = process_fixed_frame(frame, config)
    i_values = quantize_q15(frame.real)
    q_values = quantize_q15(frame.imag)

    await stream.send_raw(i_values[:73], q_values[:73])
    await driver.write(0x08, 0)
    assert not dut.s_axis_tready.value
    remainder = cocotb.start_soon(stream.send_raw(i_values[73:], q_values[73:], last_indices={182}))
    for _ in range(31):
        await RisingEdge(dut.aclk)
    assert not remainder.done()
    await driver.write(0x08, 1)
    await remainder
    await monitor.wait_for_results(1)
    beat = monitor.results[0]
    assert beat.algorithm_payload() == expected_payload(expected)
    assert beat.sequence == 0 and beat.last and beat.reserved == 0
    assert len(monitor.inputs) == 256
    assert (await driver.read(0x10))[0] == 1
    assert (await driver.read(0x14))[0] == beat.sequence
    assert (await driver.read(0x18))[0] == (beat.peak_bin & 0xFFFFFFFF)
    assert (await driver.read(0x1C))[0] == (beat.frequency_q8_hz & 0xFFFFFFFF)
    assert (await driver.read(0x20))[0] == (beat.velocity_q8_mm_s & 0xFFFFFFFF)
    assert (await driver.read(0x24))[0] == (beat.peak_power & 0xFFFFFFFF)
    assert (await driver.read(0x28))[0] == (beat.peak_power >> 32)
    assert (await driver.read(0x2C))[0] == beat.status
    assert ((await driver.read(0x0C))[0] >> 4) & 1
    assert (await driver.read(0x34))[0] == 1
    save_metrics("enable_pause_resume_preserves_algorithm_and_snapshot", driver, monitor)
    monitor_task.cancel()


@cocotb.test()
async def soft_reset_while_processing_aborts_and_recovers(dut):
    driver, stream, monitor, monitor_task = await setup(dut)
    await driver.write(0x08, 1)
    aborted_frame, _ = tone_frame(64)
    await stream.send_frame(aborted_frame)
    driver.metrics["soft_resets"] += 1
    await driver.write(0x08, 0x2, response_stall=9)
    assert (await driver.read(0x08))[0] == 0
    for _ in range(20_000):
        await RisingEdge(dut.aclk)
    assert len(monitor.results) == 0
    assert (await driver.read(0x10))[0] == 0
    assert (await driver.read(0x34))[0] == 0

    await driver.write(0x08, 1)
    recovery_frame, config = tone_frame(3)
    expected = process_fixed_frame(recovery_frame, config, FixedFilterState())
    await stream.send_frame(recovery_frame)
    await monitor.wait_for_results(1)
    assert monitor.results[0].algorithm_payload() == expected_payload(expected)
    assert monitor.results[0].sequence == 0
    assert (await driver.read(0x10))[0] == 1
    save_metrics("soft_reset_while_processing_aborts_and_recovers", driver, monitor)
    monitor_task.cancel()


@cocotb.test()
async def soft_reset_discards_stalled_result_and_irq_recovers(dut):
    driver, stream, monitor, monitor_task = await setup(dut, output_ready=0)
    await driver.write(0x30, 1)
    await driver.write(0x08, 1)
    frame, _ = tone_frame(16)
    await stream.send_frame(frame)
    await wait_output_valid(dut)
    held = int(dut.m_axis_tdata.value)
    for _ in range(25):
        await RisingEdge(dut.aclk)
        assert dut.m_axis_tvalid.value and int(dut.m_axis_tdata.value) == held
    assert (await driver.read(0x10))[0] == 0
    assert (await driver.read(0x14))[0] == 0
    assert not ((await driver.read(0x0C))[0] & (1 << 4))
    driver.metrics["soft_resets"] += 1
    await driver.write(0x08, 0x2, response_stall=11)
    await RisingEdge(dut.aclk)
    assert not dut.m_axis_tvalid.value
    assert (await driver.read(0x10))[0] == 0
    assert (await driver.read(0x34))[0] == 0
    assert not dut.irq.value

    dut.m_axis_tready.value = 1
    await driver.write(0x08, 1)
    recovery_frame, config = tone_frame(-3)
    expected = process_fixed_frame(recovery_frame, config)
    await stream.send_frame(recovery_frame)
    await monitor.wait_for_results(1)
    assert monitor.results[0].algorithm_payload() == expected_payload(expected)
    assert monitor.results[0].sequence == 0
    await RisingEdge(dut.aclk)
    assert dut.irq.value
    await driver.write(0x34, 1)
    assert not dut.irq.value
    save_metrics(
        "soft_reset_discards_stalled_result_and_irq_recovers",
        driver,
        monitor,
        irq_clears=1,
    )
    monitor_task.cancel()


@cocotb.test()
async def disable_does_not_gate_pending_output(dut):
    driver, stream, monitor, monitor_task = await setup(dut, output_ready=0)
    await driver.write(0x08, 1)
    frame, config = tone_frame(64)
    expected = process_fixed_frame(frame, config)
    await stream.send_frame(frame)
    await wait_output_valid(dut)
    held = int(dut.m_axis_tdata.value)
    await driver.write(0x08, 0)
    assert not dut.s_axis_tready.value
    for _ in range(19):
        await RisingEdge(dut.aclk)
        assert dut.m_axis_tvalid.value and int(dut.m_axis_tdata.value) == held
    dut.m_axis_tready.value = 1
    await monitor.wait_for_results(1)
    assert monitor.results[0].algorithm_payload() == expected_payload(expected)
    assert (await driver.read(0x10))[0] == 1
    save_metrics("disable_does_not_gate_pending_output", driver, monitor)
    monitor_task.cancel()
