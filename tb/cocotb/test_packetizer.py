"""Check packetizer bytes and CRC against the host implementation."""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from doppler.protocol import ResultPacket


@cocotb.test()
async def packet_matches_host_codec(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst_n.value = 0
    dut.s_valid.value = 0
    dut.m_ready.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    dut.s_case_id.value = 1
    dut.s_peak_bin.value = 16
    dut.s_frequency.value = 320000
    dut.s_velocity.value = 49280
    dut.s_peak_power.value = 81753044
    dut.s_status.value = 0
    dut.s_valid.value = 1
    await RisingEdge(dut.clk)
    dut.s_valid.value = 0
    data = bytearray()
    for cycle in range(200):
        dut.m_ready.value = int(cycle % 3 != 0)
        await RisingEdge(dut.clk)
        if dut.m_valid.value and dut.m_ready.value:
            data.append(int(dut.m_data.value))
            if len(data) == 20:
                break
    expected = ResultPacket(1, 0, 16, 320000, 49280, 81753044)
    assert bytes(data) == expected.encode()
