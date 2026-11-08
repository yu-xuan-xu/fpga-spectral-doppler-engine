"""Reusable transfer monitor and ordered result collector."""

from __future__ import annotations

from dataclasses import dataclass

from cocotb.triggers import RisingEdge


@dataclass(frozen=True)
class InputTransfer:
    cycle: int
    i: int
    q: int
    last: bool


@dataclass(frozen=True)
class ResultTransfer:
    cycle: int
    peak_bin: int
    frequency_q8_hz: int
    velocity_q8_mm_s: int
    peak_power: int
    status: int

    def payload(self) -> tuple[int, int, int, int, int]:
        return (
            self.peak_bin,
            self.frequency_q8_hz,
            self.velocity_q8_mm_s,
            self.peak_power,
            self.status,
        )


class StreamMonitor:
    def __init__(self, dut):
        self.dut = dut
        self.cycle = 0
        self.inputs: list[InputTransfer] = []
        self.results: list[ResultTransfer] = []
        self.stalled_result_cycles = 0
        self._stalled_payload: tuple[int, int, int, int, int] | None = None

    def current_payload(self) -> tuple[int, int, int, int, int]:
        return (
            int(self.dut.m_peak_bin.value.to_signed()),
            int(self.dut.m_frequency_q8_hz.value.to_signed()),
            int(self.dut.m_velocity_q8_mm_s.value.to_signed()),
            int(self.dut.m_peak_power.value),
            int(self.dut.m_status.value),
        )

    async def run(self) -> None:
        while True:
            await RisingEdge(self.dut.clk)
            self.cycle += 1
            if not self.dut.rst_n.value:
                self._stalled_payload = None
                continue
            if self.dut.s_valid.value and self.dut.s_ready.value:
                self.inputs.append(
                    InputTransfer(
                        self.cycle,
                        int(self.dut.s_i.value.to_signed()),
                        int(self.dut.s_q.value.to_signed()),
                        bool(self.dut.s_last.value),
                    )
                )
            if self.dut.m_valid.value and not self.dut.m_ready.value:
                payload = self.current_payload()
                if self._stalled_payload is not None:
                    assert payload == self._stalled_payload, "result payload changed while stalled"
                self._stalled_payload = payload
                self.stalled_result_cycles += 1
            elif self.dut.m_valid.value and self.dut.m_ready.value:
                payload = self.current_payload()
                if self._stalled_payload is not None:
                    assert payload == self._stalled_payload
                self.results.append(ResultTransfer(self.cycle, *payload))
                self._stalled_payload = None
            else:
                self._stalled_payload = None

    async def wait_for_results(self, count: int, *, timeout_cycles: int = 120_000) -> None:
        for _ in range(timeout_cycles):
            if len(self.results) >= count:
                return
            await RisingEdge(self.dut.clk)
        raise AssertionError(f"timed out waiting for {count} result transfers")
