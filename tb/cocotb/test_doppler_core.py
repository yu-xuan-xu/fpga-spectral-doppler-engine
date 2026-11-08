"""Randomized streaming and ordered-oracle checks for doppler_core."""

from __future__ import annotations

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from doppler.config import DopplerConfig, FlowProfile
from doppler.fixed import FixedFilterState, process_fixed_frame, quantize_q15
from doppler.generator import generate_signal


async def reset(dut) -> None:
    dut.rst_n.value = 0
    dut.s_valid.value = 0
    dut.s_last.value = 0
    dut.m_ready.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


async def send_samples(dut, samples, *, final_last=True, gaps=False) -> None:
    i_data = quantize_q15(samples.real)
    q_data = quantize_q15(samples.imag)
    rng = random.Random(701)
    for index, (i_value, q_value) in enumerate(zip(i_data, q_data, strict=True)):
        if gaps:
            for _ in range(rng.randrange(3)):
                dut.s_valid.value = 0
                await RisingEdge(dut.clk)
        dut.s_valid.value = 1
        dut.s_i.value = int(i_value) & 0xFFFF
        dut.s_q.value = int(q_value) & 0xFFFF
        dut.s_last.value = int(final_last and index == len(samples) - 1)
        while True:
            await RisingEdge(dut.clk)
            if dut.s_ready.value:
                break
    dut.s_valid.value = 0
    dut.s_last.value = 0


async def receive_result(dut, *, stalls=False, limit=120_000):
    rng = random.Random(911)
    stalled_payload = None
    for cycle in range(limit):
        dut.m_ready.value = int(not stalls or rng.randrange(4) != 0)
        await RisingEdge(dut.clk)
        if dut.m_valid.value and not dut.m_ready.value:
            payload = (
                int(dut.m_peak_bin.value.to_signed()),
                int(dut.m_frequency_q8_hz.value.to_signed()),
                int(dut.m_velocity_q8_mm_s.value.to_signed()),
                int(dut.m_peak_power.value),
                int(dut.m_status.value),
            )
            if stalled_payload is not None:
                assert payload == stalled_payload, "result changed while stalled"
            stalled_payload = payload
        elif dut.m_valid.value and dut.m_ready.value:
            return (
                int(dut.m_peak_bin.value.to_signed()),
                int(dut.m_frequency_q8_hz.value.to_signed()),
                int(dut.m_velocity_q8_mm_s.value.to_signed()),
                int(dut.m_peak_power.value),
                int(dut.m_status.value),
                cycle,
            )
        else:
            stalled_payload = None
    raise AssertionError("result latency exceeded 120,000 cycles")


async def receive_result_with_latency(dut, *, stalls=False, limit=120_000):
    """Count latency from the first cycle after input last acceptance."""
    return await receive_result(dut, stalls=stalls, limit=limit)


def expected_tuple(result, frame_error=0):
    status = (int(result.saturation_count > 0) << 2) | (int(result.low_confidence) << 1)
    status |= frame_error
    return (
        result.peak_bin,
        result.frequency_q8_hz,
        result.velocity_q8_mm_s,
        result.peak_power,
        status,
    )


@cocotb.test()
async def randomized_stream_matches_oracle(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await reset(dut)
    config = DopplerConfig(
        profile=FlowProfile.STEADY,
        velocity_m_s=16 * 0.01203125,
        snr_db=None,
        clutter_ratio=0.5,
        seed=41,
    )
    frame = generate_signal(config).iq[:256]
    expected = process_fixed_frame(frame, config, FixedFilterState())

    # Early-last frame is discarded before reaching the stateful DSP chain.
    await send_samples(dut, frame[:19], final_last=True, gaps=True)
    await send_samples(dut, frame, gaps=True)
    received = await receive_result(dut, stalls=True)
    assert received[:5] == expected_tuple(expected, frame_error=1)
    assert received[5] < 120_000

    dut._log.info("measured processing latency with randomized stalls: %d cycles", received[5])

    # The sticky frame error clears only after the reported result handshake.
    second_expected = process_fixed_frame(frame, config, expected.state)
    await send_samples(dut, frame, gaps=True)
    received = await receive_result(dut, stalls=True)
    assert received[:5] == expected_tuple(second_expected)

    # Missing sample-255 last enters discard mode; the next last resynchronizes.
    await send_samples(dut, frame, final_last=False)
    await send_samples(dut, frame[:7], final_last=True)
    await send_samples(dut, frame, gaps=True)
    third_expected = process_fixed_frame(frame, config, second_expected.state)
    received = await receive_result(dut, stalls=True)
    assert received[:5] == expected_tuple(third_expected, frame_error=1)


@cocotb.test()
async def reset_aborts_partial_frame(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await reset(dut)
    config = DopplerConfig(
        velocity_m_s=-16 * 0.01203125,
        profile=FlowProfile.REVERSE,
        snr_db=None,
        clutter_ratio=0,
    )
    frame = generate_signal(config).iq[:256]
    await send_samples(dut, frame[:73], final_last=False)
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    await send_samples(dut, frame)
    received = await receive_result(dut, stalls=True)
    expected = process_fixed_frame(frame, config)
    assert received[:5] == expected_tuple(expected)


@cocotb.test()
async def all_directed_signed_bins_match_oracle(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    for signed_bin in [2, 3, 16, 64, 127, -2, -3, -16, -64, -127]:
        await reset(dut)
        config = DopplerConfig(
            velocity_m_s=signed_bin * 0.01203125,
            profile=FlowProfile.STEADY if signed_bin > 0 else FlowProfile.REVERSE,
            snr_db=None,
            clutter_ratio=0,
            initial_phase_rad=0.37,
        )
        frame = generate_signal(config).iq[:256]
        expected = process_fixed_frame(frame, config)
        await send_samples(dut, frame, gaps=True)
        received = await receive_result(dut, stalls=True)
        assert received[:5] == expected_tuple(expected), f"failed signed bin {signed_bin}"
        dut._log.info(
            "rtl bin %+d  %+.2f hz  %+.2f mm/s   python bin %+d  %+.2f hz  %+.2f mm/s",
            received[0],
            received[1] / 256,
            received[2] / 256,
            expected.peak_bin,
            expected.frequency_q8_hz / 256,
            expected.velocity_q8_mm_s / 256,
        )
