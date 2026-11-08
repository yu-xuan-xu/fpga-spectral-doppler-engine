"""Seeded randomized system regression for the complete controlled accelerator."""

from __future__ import annotations

import json
import os
from pathlib import Path

import cocotb
from axi_lite_driver import AxiLiteDriver
from axi_stream_driver import AxiStreamDriver
from axi_stream_monitor import AxiStreamMonitor
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from coverage_model import (
    CoverageTracker,
    ObservedSystemCoverage,
    amplitude_bin,
    clutter_bin,
    direction_bin,
    peak_range_bin,
    snr_bin,
)
from doppler.config import DopplerConfig, FlowProfile
from doppler.fixed import process_fixed_frame, quantize_q15
from doppler.generator import generate_signal
from random_scenarios import gap_cycles, scenario_for_seed

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "build/test-results/coverage/random_regression.json"
DEFAULT_COVERAGE = ROOT / "build/test-results/coverage/random_coverage.json"


def expected_payload(result, *, frame_error=False):
    status = (int(result.saturation_count > 0) << 2) | (int(result.low_confidence) << 1)
    status |= int(frame_error)
    return (
        result.peak_bin,
        result.frequency_q8_hz,
        result.velocity_q8_mm_s,
        result.peak_power,
        status,
    )


def scenario_config(scenario):
    return DopplerConfig(
        profile=FlowProfile.REVERSE if scenario.peak_bin < 0 else FlowProfile.STEADY,
        velocity_m_s=scenario.peak_bin * 0.01203125,
        signal_amplitude=scenario.amplitude,
        snr_db=scenario.snr_db,
        clutter_ratio=scenario.clutter_ratio,
        initial_phase_rad=0.37,
        seed=scenario.seed,
    )


async def wait_output_valid(dut, limit=120_000):
    for _ in range(limit):
        await RisingEdge(dut.aclk)
        if dut.m_axis_tvalid.value:
            return
    raise AssertionError("timed out waiting for randomized result")


async def wait_cycles(dut, cycles):
    for _ in range(cycles):
        await RisingEdge(dut.aclk)


async def run_seed(dut, lite, stream, monitor, coverage, scenario):
    seed_start_cycle = coverage.cycle
    input_start = len(monitor.inputs)
    output_start = len(monitor.results)
    input_stalls_start = monitor.input_stall_cycles
    output_stalls_start = monitor.output_stall_cycles
    reads_start = lite.metrics["axi_lite_reads"]
    writes_start = lite.metrics["axi_lite_writes"]
    coverage.context(seed=scenario.seed, scenario=f"random_seed_{scenario.seed}")

    dut.s_axis_tvalid.value = 0
    dut.s_axis_tlast.value = 0
    dut.m_axis_tready.value = 1
    await lite.reset()
    await lite.write(
        0x38,
        (scenario.seed * 0x01010101) & 0xFFFFFFFF,
        strobes=scenario.seed & 0xF,
        aw_delay=scenario.aw_delay,
        w_delay=scenario.w_delay,
        response_stall=scenario.b_stall_cycles,
    )
    await lite.read(0x00 if scenario.seed & 1 else 0x38, response_stall=scenario.r_stall_cycles)
    await lite.write(0x30, int(scenario.irq_enable))
    await lite.write(0x08, 1)

    config = scenario_config(scenario)
    frame = generate_signal(config).iq[:256]
    expected = process_fixed_frame(frame, config)
    i_values = quantize_q15(frame.real)
    q_values = quantize_q15(frame.imag)
    malformed = 0
    resets = 1

    if scenario.frame_type == "early_tlast":
        await stream.send_raw(i_values[:19], q_values[:19], last_indices={18})
        malformed = 1
    elif scenario.frame_type == "missing_tlast":
        await stream.send_frame(frame, assert_last=False)
        await stream.send_raw(i_values[:13], q_values[:13], last_indices={12})
        malformed = 1

    if scenario.action == "soft_reset_collecting":
        await stream.send_raw(i_values[:73], q_values[:73])
        await lite.write(0x08, 2, response_stall=scenario.b_stall_cycles)
        resets += 1
        malformed = 0
        await lite.write(0x08, 1)
    elif scenario.action == "soft_reset_processing":
        await stream.send_frame(frame)
        await wait_cycles(dut, 101)
        await lite.write(0x08, 2, response_stall=scenario.b_stall_cycles)
        resets += 1
        malformed = 0
        await lite.write(0x08, 1)

    if scenario.action == "enable_pause":
        await stream.send_raw(i_values[:73], q_values[:73])
        await lite.write(0x08, 0)
        coverage.hit("cross.enable_frame_state", "clear_x_collecting")
        remainder = cocotb.start_soon(
            stream.send_raw(
                i_values[73:],
                q_values[73:],
                last_indices={182},
                gaps=lambda index: gap_cycles(scenario.input_gap_pattern, index),
            )
        )
        await wait_cycles(dut, max(1, scenario.output_stall_cycles))
        await lite.write(0x08, 1)
        coverage.hit("cross.enable_frame_state", "set_x_collecting")
        await remainder
    else:
        await stream.send_frame(
            frame, gaps=lambda index: gap_cycles(scenario.input_gap_pattern, index)
        )

    if scenario.output_stall_cycles:
        dut.m_axis_tready.value = 0
        await wait_output_valid(dut)
        await wait_cycles(dut, scenario.output_stall_cycles)
        dut.m_axis_tready.value = 1
    else:
        dut.m_axis_tready.value = 1

    await monitor.wait_for_results(output_start + 1)
    beat = monitor.results[-1]
    assert beat.algorithm_payload() == expected_payload(expected, frame_error=bool(malformed))
    assert beat.sequence == 0
    assert beat.last and beat.reserved == 0

    count = (await lite.read(0x10))[0]
    sequence = (await lite.read(0x14))[0]
    status = (await lite.read(0x2C))[0]
    irq_status = (await lite.read(0x34))[0]
    assert count == 1 and sequence == 0 and status == beat.status and irq_status == 1
    assert bool(dut.irq.value) == scenario.irq_enable

    direction = direction_bin(scenario.peak_bin)
    snr = snr_bin(scenario.snr_db)
    clutter = clutter_bin(scenario.clutter_ratio)
    amplitude = amplitude_bin(scenario.amplitude)
    # Input-condition coverage is credited only after a real result transfer.
    # Accuracy remains a separate scoreboard check above, particularly at low SNR.
    peak_range = peak_range_bin(scenario.peak_bin)
    saturated = "saturated" if beat.status & 4 else "not_saturated"
    coverage.hit("algorithm.direction", direction)
    coverage.hit("algorithm.peak_bin_range", peak_range)
    coverage.hit("algorithm.snr", snr)
    coverage.hit("algorithm.clutter", clutter)
    coverage.hit("algorithm.amplitude", amplitude)
    coverage.hit("cross.direction_snr", f"{direction}_x_{snr}")
    coverage.hit("cross.peak_range_snr", f"{peak_range}_x_{snr}")
    coverage.hit("cross.direction_clutter", f"{direction}_x_{clutter}")
    coverage.hit("cross.amplitude_saturation", f"{amplitude}_x_{saturated}")
    stall_delta = monitor.output_stall_cycles - output_stalls_start
    backpressure = "none" if stall_delta == 0 else "short" if stall_delta < 16 else "long"
    coverage.hit("cross.direction_backpressure", f"{direction}_x_{backpressure}")
    irq_state = "enabled" if scenario.irq_enable else "disabled"
    coverage.hit("irq.behavior", f"result_while_{irq_state}")
    coverage.hit("cross.irq_enable_result", irq_state)

    if scenario.seed % 3 == 0:
        await lite.write(0x34, 0)
        coverage.hit("irq.behavior", "write_zero")
        assert (await lite.read(0x34))[0] == 1
    await lite.write(0x34, 1)
    coverage.hit("irq.behavior", "software_clear")
    assert (await lite.read(0x34))[0] == 0

    return {
        "seed": scenario.seed,
        "scenario": scenario.as_json(),
        "cycles": coverage.cycle - seed_start_cycle,
        "input_frames": 1 + malformed + int(scenario.action == "soft_reset_processing"),
        "legal_frames": 1 + int(scenario.action == "soft_reset_processing"),
        "malformed_frames": malformed,
        "accepted_samples": len(monitor.inputs) - input_start,
        "output_results": len(monitor.results) - output_start,
        "resets": resets,
        "axi_lite_reads": lite.metrics["axi_lite_reads"] - reads_start,
        "axi_lite_writes": lite.metrics["axi_lite_writes"] - writes_start,
        "register_operations": (
            lite.metrics["axi_lite_reads"]
            - reads_start
            + lite.metrics["axi_lite_writes"]
            - writes_start
        ),
        "input_stall_cycles": monitor.input_stall_cycles - input_stalls_start,
        "output_stall_cycles": stall_delta,
        "coverage_bins_hit": len(coverage.hits),
        "pass": True,
    }


@cocotb.test()
async def seeded_random_system_regression(dut):
    cocotb.start_soon(Clock(dut.aclk, 10, unit="ns").start())
    dut.s_axis_tvalid.value = 0
    dut.s_axis_tdata.value = 0
    dut.s_axis_tlast.value = 0
    dut.m_axis_tready.value = 1
    coverage = CoverageTracker(test_name="seeded_random_system_regression")
    observer = ObservedSystemCoverage(dut, coverage)
    observer_task = cocotb.start_soon(observer.run())
    lite = AxiLiteDriver(dut, coverage=coverage)
    stream = AxiStreamDriver(dut)
    monitor = AxiStreamMonitor(dut)
    monitor_task = cocotb.start_soon(monitor.run())

    seed_text = os.environ.get("DOPPLER_RANDOM_SEEDS", "4100,4101,4102")
    seeds = [int(value) for value in seed_text.split(",") if value]
    output_path = Path(os.environ.get("DOPPLER_RANDOM_OUTPUT", DEFAULT_OUTPUT))
    coverage_path = Path(os.environ.get("DOPPLER_RANDOM_COVERAGE", DEFAULT_COVERAGE))
    records = []
    for seed in seeds:
        scenario = scenario_for_seed(seed)
        try:
            records.append(await run_seed(dut, lite, stream, monitor, coverage, scenario))
        except Exception as error:
            failed_config = scenario_config(scenario)
            failed_frame = generate_signal(failed_config).iq[:256]
            failed_expected = process_fixed_frame(failed_frame, failed_config)
            failure = {
                "seed": seed,
                "scenario": scenario.as_json(),
                "first_mismatch_cycle": coverage.cycle,
                "error": repr(error),
                "accepted_input_trace": [item.__dict__ for item in monitor.inputs[-300:]],
                "actual_output_trace": [item.__dict__ for item in monitor.results[-10:]],
                "input_vectors": {
                    "i_q15": quantize_q15(failed_frame.real).tolist(),
                    "q_q15": quantize_q15(failed_frame.imag).tolist(),
                },
                "expected_event_trace": {
                    "algorithm_payload": expected_payload(failed_expected),
                    "expected_result_count": 1,
                    "expected_sequence": 0,
                },
            }
            failure_path = ROOT / f"build/test-results/coverage/failure_seed_{seed}.json"
            failure_path.parent.mkdir(parents=True, exist_ok=True)
            failure_path.write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n")
            raise

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "requested_seeds": seeds,
                "passed_seeds": sum(record["pass"] for record in records),
                "failed_seeds": [],
                "records": records,
                "totals": {
                    key: sum(record[key] for record in records)
                    for key in (
                        "cycles",
                        "input_frames",
                        "legal_frames",
                        "malformed_frames",
                        "accepted_samples",
                        "output_results",
                        "resets",
                        "axi_lite_reads",
                        "axi_lite_writes",
                        "register_operations",
                        "input_stall_cycles",
                        "output_stall_cycles",
                    )
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    coverage.write(coverage_path)
    monitor_task.cancel()
    observer_task.cancel()
