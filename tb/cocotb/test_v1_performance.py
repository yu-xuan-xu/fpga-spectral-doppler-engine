"""Deterministic cycle measurements for the frozen v1 streaming core."""

from __future__ import annotations

import json
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from doppler.config import DopplerConfig, FlowProfile
from doppler.fixed import quantize_q15
from doppler.generator import generate_signal

TARGET_CLOCK_HZ = 12_000_000.0
BOARD_TOP_ESTIMATED_FMAX_HZ = 15_887_641.906738281


class TransferMonitor:
    def __init__(self, dut):
        self.dut = dut
        self.cycle = 0
        self.input_transfers: list[dict] = []
        self.result_valid_cycles: list[int] = []
        self.result_transfers: list[dict] = []
        self._result_pending = False

    async def run(self) -> None:
        while True:
            await RisingEdge(self.dut.clk)
            self.cycle += 1
            if self.dut.s_valid.value and self.dut.s_ready.value:
                self.input_transfers.append(
                    {"cycle": self.cycle, "last": int(self.dut.s_last.value)}
                )
            if self.dut.m_valid.value and not self._result_pending:
                self.result_valid_cycles.append(self.cycle)
                self._result_pending = True
            if self.dut.m_valid.value and self.dut.m_ready.value:
                self.result_transfers.append(
                    {
                        "cycle": self.cycle,
                        "peak_bin": int(self.dut.m_peak_bin.value.to_signed()),
                        "status": int(self.dut.m_status.value),
                    }
                )
                self._result_pending = False


async def reset(dut, *, output_ready: int) -> None:
    dut.rst_n.value = 0
    dut.s_valid.value = 0
    dut.s_last.value = 0
    dut.m_ready.value = output_ready
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


def tone_frame(signed_bin: int = 16):
    config = DopplerConfig(
        profile=FlowProfile.STEADY if signed_bin > 0 else FlowProfile.REVERSE,
        velocity_m_s=signed_bin * 0.01203125,
        snr_db=None,
        clutter_ratio=0,
    )
    return generate_signal(config).iq[:256]


async def send_frames(dut, frames) -> None:
    packed = []
    for frame in frames:
        i_data = quantize_q15(frame.real)
        q_data = quantize_q15(frame.imag)
        packed.extend(zip(i_data, q_data, strict=True))
    for index, (i_value, q_value) in enumerate(packed):
        dut.s_valid.value = 1
        dut.s_i.value = int(i_value) & 0xFFFF
        dut.s_q.value = int(q_value) & 0xFFFF
        dut.s_last.value = int(index % 256 == 255)
        while True:
            await RisingEdge(dut.clk)
            if dut.s_ready.value:
                break
    dut.s_valid.value = 0
    dut.s_last.value = 0


async def wait_for_results(monitor: TransferMonitor, count: int, limit: int = 100_000) -> None:
    for _ in range(limit):
        if len(monitor.result_transfers) >= count:
            return
        await RisingEdge(monitor.dut.clk)
    raise AssertionError(f"timed out waiting for {count} result transfers")


async def run_no_stall(dut, frame_count: int) -> dict:
    await reset(dut, output_ready=1)
    monitor = TransferMonitor(dut)
    task = cocotb.start_soon(monitor.run())
    frames = [tone_frame(16 if index % 2 == 0 else -16) for index in range(frame_count)]
    await send_frames(dut, frames)
    await wait_for_results(monitor, frame_count)
    task.cancel()

    first_samples = [monitor.input_transfers[index * 256]["cycle"] for index in range(frame_count)]
    frame_ends = [
        monitor.input_transfers[index * 256 + 255]["cycle"] for index in range(frame_count)
    ]
    result_valid = monitor.result_valid_cycles[:frame_count]
    result_accept = [item["cycle"] for item in monitor.result_transfers[:frame_count]]
    return {
        "frame_count": frame_count,
        "first_sample_cycles": first_samples,
        "end_of_frame_cycles": frame_ends,
        "result_valid_cycles": result_valid,
        "result_handshake_cycles": result_accept,
        "first_sample_latency_cycles": [
            result_valid[i] - first_samples[i] for i in range(frame_count)
        ],
        "end_of_frame_latency_cycles": [
            result_valid[i] - frame_ends[i] for i in range(frame_count)
        ],
        "result_handshake_latency_cycles": [
            result_accept[i] - frame_ends[i] for i in range(frame_count)
        ],
        "cycles_per_frame_first_sample_to_result_handshake": [
            result_accept[i] - first_samples[i] for i in range(frame_count)
        ],
        "result_to_result_intervals_cycles": [
            result_accept[i] - result_accept[i - 1] for i in range(1, frame_count)
        ],
        "peak_bins": [item["peak_bin"] for item in monitor.result_transfers[:frame_count]],
        "status": [item["status"] for item in monitor.result_transfers[:frame_count]],
    }


async def run_fixed_output_stall(dut, stall_cycles: int) -> dict:
    await reset(dut, output_ready=0)
    monitor = TransferMonitor(dut)
    task = cocotb.start_soon(monitor.run())
    await send_frames(dut, [tone_frame()])
    while not monitor.result_valid_cycles:
        await RisingEdge(dut.clk)
    valid_cycle = monitor.result_valid_cycles[0]
    stalled_payload = (
        int(dut.m_peak_bin.value.to_signed()),
        int(dut.m_frequency_q8_hz.value.to_signed()),
        int(dut.m_velocity_q8_mm_s.value.to_signed()),
        int(dut.m_peak_power.value),
        int(dut.m_status.value),
    )
    while monitor.cycle < valid_cycle + stall_cycles - 2:
        await RisingEdge(dut.clk)
        payload = (
            int(dut.m_peak_bin.value.to_signed()),
            int(dut.m_frequency_q8_hz.value.to_signed()),
            int(dut.m_velocity_q8_mm_s.value.to_signed()),
            int(dut.m_peak_power.value),
            int(dut.m_status.value),
        )
        assert payload == stalled_payload
    dut.m_ready.value = 1
    await wait_for_results(monitor, 1)
    handshake_cycle = monitor.result_transfers[0]["cycle"]
    task.cancel()
    return {
        "requested_stall_cycles": stall_cycles,
        "result_valid_cycle": valid_cycle,
        "result_handshake_cycle": handshake_cycle,
        "observed_valid_to_handshake_cycles": handshake_cycle - valid_cycle,
        "payload_stable": True,
    }


async def run_malformed_then_legal(dut) -> dict:
    await reset(dut, output_ready=1)
    monitor = TransferMonitor(dut)
    task = cocotb.start_soon(monitor.run())
    malformed = tone_frame()[:19]
    await send_frames(dut, [malformed])
    # send_frames only asserts last at position 255, so explicitly terminate this early frame
    dut.s_valid.value = 1
    dut.s_i.value = 0
    dut.s_q.value = 0
    dut.s_last.value = 1
    while True:
        await RisingEdge(dut.clk)
        if dut.s_ready.value:
            break
    dut.s_valid.value = 0
    dut.s_last.value = 0
    await Timer(1, unit="ns")
    legal_start_index = len(monitor.input_transfers)
    assert legal_start_index == 20
    await send_frames(dut, [tone_frame()])
    await wait_for_results(monitor, 1)
    task.cancel()
    legal_first = monitor.input_transfers[legal_start_index]["cycle"]
    legal_end = monitor.input_transfers[legal_start_index + 255]["cycle"]
    return {
        "malformed_accepted_samples": legal_start_index,
        "legal_first_sample_cycle": legal_first,
        "legal_end_of_frame_cycle": legal_end,
        "result_handshake_cycle": monitor.result_transfers[0]["cycle"],
        "result_status": monitor.result_transfers[0]["status"],
        "recovered": bool(monitor.result_transfers[0]["status"] & 1),
    }


def throughput(interval_cycles: int, clock_hz: float) -> dict:
    frames_per_second = clock_hz / interval_cycles
    return {
        "clock_hz": clock_hz,
        "frames_per_second": frames_per_second,
        "samples_per_second": frames_per_second * 256,
    }


@cocotb.test()
async def characterize_v1_core(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    single = await run_no_stall(dut, 1)
    continuous = await run_no_stall(dut, 3)
    fixed_stall = await run_fixed_output_stall(dut, 17)
    reset_first_frame = await run_no_stall(dut, 1)
    malformed_recovery = await run_malformed_then_legal(dut)

    intervals = continuous["result_to_result_intervals_cycles"]
    assert intervals and len(set(intervals)) == 1
    interval = intervals[0]
    assert single["peak_bins"] == [16]
    assert continuous["peak_bins"] == [16, -16, 16]
    assert all(status == 0 for status in single["status"] + continuous["status"])
    assert malformed_recovery["recovered"]

    report = {
        "schema_version": 1,
        "evidence": "rtl_simulation_measured_cycles_and_derived_rates",
        "cycle_definition": "difference between sampled rising-edge transfer indices",
        "single_frame_no_stall": single,
        "three_continuous_frames_no_stall": continuous,
        "fixed_output_stall": fixed_stall,
        "reset_then_first_frame": reset_first_frame,
        "malformed_then_legal_frame": malformed_recovery,
        "sustained_result_interval_cycles": interval,
        "derived_throughput": {
            "at_12_mhz_target": throughput(interval, TARGET_CLOCK_HZ),
            "at_15_89_mhz_board_top_estimated_fmax": throughput(
                interval, BOARD_TOP_ESTIMATED_FMAX_HZ
            ),
        },
    }
    destination = Path(__file__).resolve().parents[2] / "results" / "ice40" / "performance.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    dut._log.info("v1 performance report: %s", destination)
