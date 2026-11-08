"""AXI4-Stream handshake monitor and packed-result decoder."""

from __future__ import annotations

from dataclasses import dataclass

from cocotb.triggers import RisingEdge


def signed(value: int, width: int) -> int:
    return value - (1 << width) if value & (1 << (width - 1)) else value


@dataclass(frozen=True)
class AxiInputBeat:
    cycle: int
    data: int
    i: int
    q: int
    last: bool


@dataclass(frozen=True)
class AxiResultBeat:
    cycle: int
    data: int
    sequence: int
    peak_bin: int
    frequency_q8_hz: int
    velocity_q8_mm_s: int
    peak_power: int
    status: int
    reserved: int
    last: bool

    def algorithm_payload(self) -> tuple[int, int, int, int, int]:
        return (
            self.peak_bin,
            self.frequency_q8_hz,
            self.velocity_q8_mm_s,
            self.peak_power,
            self.status,
        )


def decode_result(cycle: int, data: int, last: bool) -> AxiResultBeat:
    return AxiResultBeat(
        cycle=cycle,
        data=data,
        sequence=data & 0xFFFF_FFFF,
        peak_bin=signed((data >> 32) & 0x1FF, 9),
        frequency_q8_hz=signed((data >> 41) & 0xFF_FFFF, 24),
        velocity_q8_mm_s=signed((data >> 65) & 0xF_FFFF, 20),
        peak_power=(data >> 85) & ((1 << 37) - 1),
        status=(data >> 122) & 0xF,
        reserved=(data >> 126) & 0x3,
        last=last,
    )


class AxiStreamMonitor:
    def __init__(self, dut):
        self.dut = dut
        self.cycle = 0
        self.inputs: list[AxiInputBeat] = []
        self.results: list[AxiResultBeat] = []
        self.input_stall_cycles = 0
        self.output_stall_cycles = 0
        self.reset_injections = 0
        self._prior_reset = False
        self._stalled_input: tuple[int, bool] | None = None
        self._stalled_output: tuple[int, bool] | None = None

    async def run(self) -> None:
        while True:
            await RisingEdge(self.dut.aclk)
            self.cycle += 1
            in_reset = not bool(self.dut.aresetn.value)
            if in_reset:
                if not self._prior_reset and self.cycle > 1:
                    self.reset_injections += 1
                self._prior_reset = True
                self._stalled_input = None
                self._stalled_output = None
                continue
            self._prior_reset = False

            input_payload = (
                int(self.dut.s_axis_tdata.value),
                bool(self.dut.s_axis_tlast.value),
            )
            if self.dut.s_axis_tvalid.value and not self.dut.s_axis_tready.value:
                if self._stalled_input is not None:
                    assert input_payload == self._stalled_input
                self._stalled_input = input_payload
                self.input_stall_cycles += 1
            elif self.dut.s_axis_tvalid.value and self.dut.s_axis_tready.value:
                if self._stalled_input is not None:
                    assert input_payload == self._stalled_input
                data, last = input_payload
                self.inputs.append(
                    AxiInputBeat(
                        self.cycle,
                        data,
                        signed((data >> 16) & 0xFFFF, 16),
                        signed(data & 0xFFFF, 16),
                        last,
                    )
                )
                self._stalled_input = None
            else:
                self._stalled_input = None

            output_payload = (
                int(self.dut.m_axis_tdata.value),
                bool(self.dut.m_axis_tlast.value),
            )
            if self.dut.m_axis_tvalid.value and not self.dut.m_axis_tready.value:
                if self._stalled_output is not None:
                    assert output_payload == self._stalled_output
                self._stalled_output = output_payload
                self.output_stall_cycles += 1
            elif self.dut.m_axis_tvalid.value and self.dut.m_axis_tready.value:
                if self._stalled_output is not None:
                    assert output_payload == self._stalled_output
                data, last = output_payload
                self.results.append(decode_result(self.cycle, data, last))
                self._stalled_output = None
            else:
                self._stalled_output = None

    async def wait_for_results(self, count: int, *, timeout_cycles: int = 120_000) -> None:
        for _ in range(timeout_cycles):
            if len(self.results) >= count:
                return
            await RisingEdge(self.dut.aclk)
        raise AssertionError(f"timed out waiting for {count} AXI result beats")
