"""AXI4-Lite ordering, response, register, snapshot, and IRQ tests."""

from __future__ import annotations

import json
import random
from pathlib import Path

import cocotb
from axi_lite_driver import AxiLiteDriver
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

METRICS = Path(__file__).resolve().parents[2] / "build" / "test-results" / "axi_lite_metrics"


def save_metrics(name, driver, **extra):
    METRICS.mkdir(parents=True, exist_ok=True)
    values = dict(driver.metrics)
    values.update(
        {
            "name": name,
            "result_snapshots": 0,
            "irq_events": 0,
            "irq_clears": 0,
            "protocol_mismatches": 0,
            "register_mismatches": 0,
            "lost_stream_results": 0,
            "duplicated_stream_results": 0,
            **extra,
        }
    )
    (METRICS / f"{name}.json").write_text(json.dumps(values, indent=2, sort_keys=True) + "\n")


async def setup(dut):
    cocotb.start_soon(Clock(dut.s_axi_aclk, 10, unit="ns").start())
    dut.stream_input_ready.value = 0
    dut.stream_output_valid.value = 0
    dut.result_data.value = 0
    dut.result_valid.value = 0
    dut.result_ready.value = 0
    driver = AxiLiteDriver(dut)
    await driver.reset()
    return driver


def packed_result(sequence, peak, frequency, velocity, power, status):
    return (
        (sequence & 0xFFFF_FFFF)
        | ((peak & 0x1FF) << 32)
        | ((frequency & 0xFF_FFFF) << 41)
        | ((velocity & 0xF_FFFF) << 65)
        | ((power & ((1 << 37) - 1)) << 85)
        | ((status & 0xF) << 122)
    )


async def pulse_result(dut, data):
    dut.result_data.value = data
    dut.result_valid.value = 1
    dut.result_ready.value = 1
    await RisingEdge(dut.s_axi_aclk)
    dut.result_valid.value = 0
    dut.result_ready.value = 0


@cocotb.test()
async def register_reset_values_and_capabilities(dut):
    driver = await setup(dut)
    expected = {
        0x00: 0x02000000,
        0x04: 0x03104100,
        0x08: 0,
        0x0C: 0,
        0x10: 0,
        0x14: 0,
        0x18: 0,
        0x1C: 0,
        0x20: 0,
        0x24: 0,
        0x28: 0,
        0x2C: 0,
        0x30: 0,
        0x34: 0,
        0x38: 0,
    }
    for address, value in expected.items():
        assert (await driver.read(address))[0] == value
    assert int(dut.assertion_checked_cycles.value) > 0
    save_metrics("register_reset_values_and_capabilities", driver)


@cocotb.test()
async def aw_w_ordering_and_partial_writes(dut):
    driver = await setup(dut)
    await driver.write(0x38, 0x11223344, aw_delay=0, w_delay=5)
    await driver.write(0x38, 0xAABBCCDD, strobes=0x5, aw_delay=6, w_delay=0)
    assert (await driver.read(0x38))[0] == 0x11BB33DD
    await driver.write(0x38, 0x55667788, strobes=0xA)
    assert (await driver.read(0x38))[0] == 0x55BB77DD
    await driver.write(0x08, 1, strobes=0x2)
    assert (await driver.read(0x08))[0] == 0
    await driver.write(0x08, 1, strobes=0x1)
    assert (await driver.read(0x08))[0] == 1
    await driver.write(0x30, 1, strobes=0x1)
    assert (await driver.read(0x30))[0] == 1
    expected = 0x55BB77DD
    rng = random.Random(3103)
    for strobes in range(16):
        value = (0x10203040 + strobes * 0x01010101) & 0xFFFFFFFF
        await driver.write(
            0x38,
            value,
            strobes=strobes,
            aw_delay=rng.randrange(7),
            w_delay=rng.randrange(7),
        )
        for byte_index in range(4):
            if strobes & (1 << byte_index):
                mask = 0xFF << (8 * byte_index)
                expected = (expected & ~mask) | (value & mask)
        assert (await driver.read(0x38))[0] == expected
    save_metrics("aw_w_ordering_and_partial_writes", driver)


@cocotb.test()
async def read_and_write_response_backpressure(dut):
    driver = await setup(dut)
    write_task = cocotb.start_soon(driver.write(0x38, 0xC0DEC0DE, response_stall=17))
    while not dut.s_axi_bvalid.value:
        await RisingEdge(dut.s_axi_aclk)
    held_resp = int(dut.s_axi_bresp.value)
    for _ in range(8):
        await RisingEdge(dut.s_axi_aclk)
        assert dut.s_axi_bvalid.value and int(dut.s_axi_bresp.value) == held_resp
        assert not dut.s_axi_awready.value and not dut.s_axi_wready.value
    await write_task
    read_task = cocotb.start_soon(driver.read(0x38, response_stall=19))
    while not dut.s_axi_rvalid.value:
        await RisingEdge(dut.s_axi_aclk)
    held = (int(dut.s_axi_rdata.value), int(dut.s_axi_rresp.value))
    for _ in range(8):
        await RisingEdge(dut.s_axi_aclk)
        assert dut.s_axi_rvalid.value
        assert (int(dut.s_axi_rdata.value), int(dut.s_axi_rresp.value)) == held
        assert not dut.s_axi_arready.value
    assert (await read_task)[0] == 0xC0DEC0DE
    save_metrics("read_and_write_response_backpressure", driver)


@cocotb.test()
async def invalid_and_simultaneous_accesses(dut):
    driver = await setup(dut)
    await driver.write(0x38, 0x12345678)
    read_task = cocotb.start_soon(driver.read(0x00))
    write_task = cocotb.start_soon(driver.write(0x38, 0x89ABCDEF))
    assert (await read_task)[0] == 0x02000000
    await write_task
    for address, is_write in ((0x39, False), (0x3C, False), (0x01, True), (0x00, True)):
        driver.metrics["invalid_accesses"] += 1
        if is_write:
            await driver.write(address, 0xFFFFFFFF, expected_resp=2)
        else:
            assert (await driver.read(address, expected_resp=2))[0] == 0
    assert (await driver.read(0x38))[0] == 0x89ABCDEF
    save_metrics("invalid_and_simultaneous_accesses", driver)


@cocotb.test()
async def global_reset_aborts_pending_transactions(dut):
    driver = await setup(dut)
    dut.s_axi_awaddr.value = 0x38
    dut.s_axi_awvalid.value = 1
    await RisingEdge(dut.s_axi_aclk)
    dut.s_axi_awvalid.value = 0
    await RisingEdge(dut.s_axi_aclk)
    assert not dut.s_axi_awready.value
    driver.resetn.value = 0
    await RisingEdge(dut.s_axi_aclk)
    driver.resetn.value = 1
    await RisingEdge(dut.s_axi_aclk)
    driver.metrics["global_resets"] += 1
    assert not dut.s_axi_bvalid.value

    dut.s_axi_wdata.value = 0x55
    dut.s_axi_wstrb.value = 0xF
    dut.s_axi_wvalid.value = 1
    await RisingEdge(dut.s_axi_aclk)
    dut.s_axi_wvalid.value = 0
    await RisingEdge(dut.s_axi_aclk)
    driver.resetn.value = 0
    await RisingEdge(dut.s_axi_aclk)
    driver.resetn.value = 1
    await RisingEdge(dut.s_axi_aclk)
    driver.metrics["global_resets"] += 1
    assert not dut.s_axi_bvalid.value

    dut.s_axi_awaddr.value = 0x38
    dut.s_axi_awvalid.value = 1
    dut.s_axi_wdata.value = 0xCAFEF00D
    dut.s_axi_wstrb.value = 0xF
    dut.s_axi_wvalid.value = 1
    await RisingEdge(dut.s_axi_aclk)
    dut.s_axi_awvalid.value = 0
    dut.s_axi_wvalid.value = 0
    while not dut.s_axi_bvalid.value:
        await RisingEdge(dut.s_axi_aclk)
    driver.resetn.value = 0
    await RisingEdge(dut.s_axi_aclk)
    driver.resetn.value = 1
    await RisingEdge(dut.s_axi_aclk)
    driver.metrics["global_resets"] += 1
    assert not dut.s_axi_bvalid.value

    await driver.write(0x38, 0xA5A5A5A5, response_stall=2)
    read_task = cocotb.start_soon(driver.read(0x38, response_stall=20))
    while not dut.s_axi_rvalid.value:
        await RisingEdge(dut.s_axi_aclk)
    driver.resetn.value = 0
    await RisingEdge(dut.s_axi_aclk)
    driver.resetn.value = 1
    await RisingEdge(dut.s_axi_aclk)
    driver.metrics["global_resets"] += 1
    read_task.cancel()
    assert not dut.s_axi_rvalid.value
    assert (await driver.read(0x38))[0] == 0
    save_metrics("global_reset_aborts_pending_transactions", driver)


@cocotb.test()
async def result_snapshot_irq_and_soft_reset(dut):
    driver = await setup(dut)
    first = packed_result(7, -16, -123456, -23456, 0x1ABCDEF01, 0xD)
    await pulse_result(dut, first)
    expected = {
        0x10: 1,
        0x14: 7,
        0x18: (-16) & 0xFFFFFFFF,
        0x1C: (-123456) & 0xFFFFFFFF,
        0x20: (-23456) & 0xFFFFFFFF,
        0x24: 0xABCDEF01,
        0x28: 1,
        0x2C: 0xD,
        0x34: 1,
    }
    for address, value in expected.items():
        assert (await driver.read(address))[0] == value
    assert not dut.irq.value
    await driver.write(0x30, 1)
    assert dut.irq.value
    await driver.write(0x34, 0)
    assert dut.irq.value
    await driver.write(0x34, 1)
    assert not dut.irq.value

    # A new result on the exact RW1C execution edge wins over the clear.
    dut.s_axi_awaddr.value = 0x34
    dut.s_axi_awvalid.value = 1
    dut.s_axi_wdata.value = 1
    dut.s_axi_wstrb.value = 0xF
    dut.s_axi_wvalid.value = 1
    await RisingEdge(dut.s_axi_aclk)
    dut.s_axi_awvalid.value = 0
    dut.s_axi_wvalid.value = 0
    dut.result_data.value = packed_result(8, 3, 456, 789, 2, 1)
    dut.result_valid.value = 1
    dut.result_ready.value = 1
    await RisingEdge(dut.s_axi_aclk)
    dut.result_valid.value = 0
    dut.result_ready.value = 0
    dut.s_axi_bready.value = 1
    while not dut.s_axi_bvalid.value:
        await RisingEdge(dut.s_axi_aclk)
    await RisingEdge(dut.s_axi_aclk)
    dut.s_axi_bready.value = 0
    driver.metrics["axi_lite_writes"] += 1
    driver.metrics["simultaneous_aw_w_cases"] += 1
    assert (await driver.read(0x34))[0] == 1
    assert (await driver.read(0x10))[0] == 2

    driver.metrics["soft_resets"] += 1
    await driver.write(0x08, 0x3, response_stall=7)
    assert (await driver.read(0x08))[0] == 0
    for address in (0x10, 0x14, 0x18, 0x1C, 0x20, 0x24, 0x28, 0x2C, 0x34):
        assert (await driver.read(address))[0] == 0
    assert (await driver.read(0x30))[0] == 1
    save_metrics(
        "result_snapshot_irq_and_soft_reset",
        driver,
        result_snapshots=2,
        irq_events=2,
        irq_clears=2,
    )
