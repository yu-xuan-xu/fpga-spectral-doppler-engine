"""Side-by-side AXI wrapper and direct canonical-core equivalence check."""

from __future__ import annotations

import cocotb
from axi_stream_driver import AxiStreamDriver
from axi_stream_monitor import AxiStreamMonitor
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from test_axi_stream_wrapper import tone_frame, write_metrics


@cocotb.test()
async def packed_result_matches_direct_canonical_core(dut):
    cocotb.start_soon(Clock(dut.aclk, 10, unit="ns").start())
    driver = AxiStreamDriver(dut)
    monitor = AxiStreamMonitor(dut)
    monitor_task = cocotb.start_soon(monitor.run())
    await driver.reset(output_ready=1)
    frame, _ = tone_frame(-64)
    await driver.send_frame(frame)

    direct_payload = None
    for _ in range(120_000):
        await RisingEdge(dut.aclk)
        if dut.direct_m_valid.value and dut.m_axis_tready.value:
            direct_payload = (
                int(dut.direct_peak_bin.value.to_signed()),
                int(dut.direct_frequency_q8_hz.value.to_signed()),
                int(dut.direct_velocity_q8_mm_s.value.to_signed()),
                int(dut.direct_peak_power.value),
                int(dut.direct_status.value),
            )
            break
    assert direct_payload is not None
    await monitor.wait_for_results(1)
    assert monitor.results[0].algorithm_payload() == direct_payload
    assert monitor.results[0].sequence == 0
    assert monitor.results[0].reserved == 0
    assert monitor.results[0].last
    write_metrics(
        "packed_result_matches_direct_canonical_core",
        monitor,
        expected_outputs=1,
        packing_checks=1,
        sequence_checks=1,
        legacy_checks=1,
    )
    monitor_task.cancel()
