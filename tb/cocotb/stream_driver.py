"""Reusable source driver for the Doppler valid/ready input stream."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np
from cocotb.triggers import RisingEdge
from doppler.fixed import quantize_q15

GapFunction = Callable[[int], int]


class StreamDriver:
    def __init__(self, dut):
        self.dut = dut

    async def reset(self, *, output_ready: int = 0, cycles: int = 3) -> None:
        self.dut.rst_n.value = 0
        self.dut.s_valid.value = 0
        self.dut.s_i.value = 0
        self.dut.s_q.value = 0
        self.dut.s_last.value = 0
        self.dut.m_ready.value = output_ready
        for _ in range(cycles):
            await RisingEdge(self.dut.clk)
        self.dut.rst_n.value = 1
        await RisingEdge(self.dut.clk)

    async def idle(self, cycles: int) -> None:
        self.dut.s_valid.value = 0
        self.dut.s_last.value = 0
        for _ in range(cycles):
            await RisingEdge(self.dut.clk)

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
            gap_cycles = gaps(index) if gaps is not None else 0
            await self.idle(gap_cycles)
            self.dut.s_valid.value = 1
            self.dut.s_i.value = int(i_value) & 0xFFFF
            self.dut.s_q.value = int(q_value) & 0xFFFF
            self.dut.s_last.value = int(index in last_indices)
            while True:
                await RisingEdge(self.dut.clk)
                if self.dut.s_ready.value:
                    break
        self.dut.s_valid.value = 0
        self.dut.s_last.value = 0

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
