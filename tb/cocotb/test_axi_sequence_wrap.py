"""Verify natural 32-bit result-sequence wrap using an elaboration parameter."""

from __future__ import annotations

import cocotb
from doppler.fixed import FixedFilterState, process_fixed_frame
from test_axi_stream_wrapper import (
    check_result,
    environment,
    expected_payload,
    tone_frame,
    write_metrics,
)


@cocotb.test()
async def result_sequence_wraps_naturally(dut):
    driver, monitor, task = await environment(dut)
    state = FixedFilterState()
    expected_sequences = [0xFFFF_FFFE, 0xFFFF_FFFF, 0]
    expected_payloads = []
    for signed_bin in (2, 3, 16):
        frame, config = tone_frame(signed_bin)
        result = process_fixed_frame(frame, config, state)
        state = result.state
        expected_payloads.append(expected_payload(result))
        await driver.send_frame(frame)
    await monitor.wait_for_results(3)
    for beat, payload, sequence in zip(
        monitor.results, expected_payloads, expected_sequences, strict=True
    ):
        check_result(beat, payload, sequence)
    write_metrics(
        "result_sequence_wraps_naturally",
        monitor,
        expected_outputs=3,
        packing_checks=3,
        sequence_checks=3,
    )
    task.cancel()
