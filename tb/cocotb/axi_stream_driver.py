"""AXI4-Stream source driver for complex Q1.15 Doppler samples."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np
from cocotb.triggers import RisingEdge
from doppler.fixed import quantize_q15

GapFunction = Callable[[int], int]


class AxiStreamDriver:
    def __init__(self, dut):
        self.dut = dut

    async def reset(self, *, output_ready: int = 0, cycles: int = 3) -> None:
        self.dut.aresetn.value = 0
        self.dut.s_axis_tvalid.value = 0
        self.dut.s_axis_tdata.value = 0
        self.dut.s_axis_tlast.value = 0
        self.dut.m_axis_tready.value = output_ready
        for _ in range(cycles):
            await RisingEdge(self.dut.aclk)
        self.dut.aresetn.value = 1
        await RisingEdge(self.dut.aclk)

    async def idle(self, cycles: int) -> None:
        self.dut.s_axis_tvalid.value = 0
        self.dut.s_axis_tlast.value = 0
        for _ in range(cycles):
            await RisingEdge(self.dut.aclk)

    async def send_raw(
        self,
        i_values: Sequence[int],
        q_values: Sequence[int],
        *,
        last_indices: set[int] | None = None,
        gaps: GapFunction | None = None,
    ) -> None:
        if len(i_values) != len(q_values):
            raise ValueError("I and Q streams must have equal length")
        last_indices = last_indices or set()
        for index, (i_value, q_value) in enumerate(zip(i_values, q_values, strict=True)):
            await self.idle(gaps(index) if gaps is not None else 0)
            packed = ((int(i_value) & 0xFFFF) << 16) | (int(q_value) & 0xFFFF)
            self.dut.s_axis_tvalid.value = 1
            self.dut.s_axis_tdata.value = packed
            self.dut.s_axis_tlast.value = int(index in last_indices)
            while True:
                await RisingEdge(self.dut.aclk)
                if self.dut.s_axis_tready.value:
                    break
        self.dut.s_axis_tvalid.value = 0
        self.dut.s_axis_tlast.value = 0

    async def send_frame(
        self,
        samples: np.ndarray,
        *,
        assert_last: bool = True,
        gaps: GapFunction | None = None,
    ) -> None:
        i_values = quantize_q15(samples.real)
        q_values = quantize_q15(samples.imag)
        last_indices = {len(samples) - 1} if assert_last and len(samples) else set()
        await self.send_raw(i_values, q_values, last_indices=last_indices, gaps=gaps)
