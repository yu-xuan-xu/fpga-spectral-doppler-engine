"""Small AXI4-Lite master used by the Phase 3 protocol tests."""

from __future__ import annotations

import cocotb
from cocotb.triggers import RisingEdge
from cocotb.utils import get_sim_time
from coverage_model import RESPONSE_EDGES, address_type, length_bin


class AxiLiteDriver:
    def __init__(self, dut, *, coverage=None):
        self.dut = dut
        self.coverage = coverage
        self.clock = dut.s_axi_aclk if hasattr(dut, "s_axi_aclk") else dut.aclk
        self.resetn = dut.s_axi_aresetn if hasattr(dut, "s_axi_aresetn") else dut.aresetn
        self.metrics = {
            "axi_lite_reads": 0,
            "axi_lite_writes": 0,
            "aw_before_w_cases": 0,
            "w_before_aw_cases": 0,
            "simultaneous_aw_w_cases": 0,
            "partial_writes": 0,
            "invalid_accesses": 0,
            "read_stall_cycles": 0,
            "write_response_stall_cycles": 0,
            "global_resets": 0,
            "soft_resets": 0,
            "slverr_responses": 0,
        }

    def initialize(self) -> None:
        dut = self.dut
        dut.s_axi_awaddr.value = 0
        dut.s_axi_awvalid.value = 0
        dut.s_axi_wdata.value = 0
        dut.s_axi_wstrb.value = 0
        dut.s_axi_wvalid.value = 0
        dut.s_axi_bready.value = 0
        dut.s_axi_araddr.value = 0
        dut.s_axi_arvalid.value = 0
        dut.s_axi_rready.value = 0

    async def reset(self, cycles: int = 3) -> None:
        self.initialize()
        self.resetn.value = 0
        for _ in range(cycles):
            await RisingEdge(self.clock)
        self.resetn.value = 1
        await RisingEdge(self.clock)
        self.metrics["global_resets"] += 1

    async def _send_aw(self, address: int, delay: int) -> int:
        for _ in range(delay):
            await RisingEdge(self.clock)
        self.dut.s_axi_awaddr.value = address
        self.dut.s_axi_awvalid.value = 1
        while True:
            await RisingEdge(self.clock)
            if self.dut.s_axi_awready.value:
                break
        self.dut.s_axi_awvalid.value = 0
        return int(get_sim_time(unit="ns"))

    async def _send_w(self, data: int, strobes: int, delay: int) -> int:
        for _ in range(delay):
            await RisingEdge(self.clock)
        self.dut.s_axi_wdata.value = data
        self.dut.s_axi_wstrb.value = strobes
        self.dut.s_axi_wvalid.value = 1
        while True:
            await RisingEdge(self.clock)
            if self.dut.s_axi_wready.value:
                break
        self.dut.s_axi_wvalid.value = 0
        return int(get_sim_time(unit="ns"))

    async def write(
        self,
        address: int,
        data: int,
        *,
        strobes: int = 0xF,
        aw_delay: int = 0,
        w_delay: int = 0,
        response_stall: int = 0,
        expected_resp: int = 0,
    ) -> int:
        if aw_delay < w_delay:
            self.metrics["aw_before_w_cases"] += 1
        elif w_delay < aw_delay:
            self.metrics["w_before_aw_cases"] += 1
        else:
            self.metrics["simultaneous_aw_w_cases"] += 1
        if strobes != 0xF:
            self.metrics["partial_writes"] += 1

        aw_task = cocotb.start_soon(self._send_aw(address, aw_delay))
        w_task = cocotb.start_soon(self._send_w(data, strobes, w_delay))
        aw_time = await aw_task
        w_time = await w_task
        observed_stall = 0
        for _ in range(response_stall):
            await RisingEdge(self.clock)
            if self.dut.s_axi_bvalid.value:
                self.metrics["write_response_stall_cycles"] += 1
                observed_stall += 1
        self.dut.s_axi_bready.value = 1
        while True:
            await RisingEdge(self.clock)
            if self.dut.s_axi_bvalid.value:
                response = int(self.dut.s_axi_bresp.value)
                break
        self.dut.s_axi_bready.value = 0
        self.metrics["axi_lite_writes"] += 1
        self.metrics["slverr_responses"] += int(response == 2)
        assert response == expected_resp
        if self.coverage is not None:
            ordering = (
                "same_cycle"
                if aw_time == w_time
                else "aw_before_w"
                if aw_time < w_time
                else "w_before_aw"
            )
            delay_cycles = abs(aw_time - w_time) // 10
            delay_name = length_bin(delay_cycles, RESPONSE_EDGES)
            b_stall_name = length_bin(observed_stall, RESPONSE_EDGES)
            kind = address_type(address, write=True)
            self.coverage.hit("lite.write_ordering", ordering)
            self.coverage.hit("lite.aw_w_delay", delay_name)
            self.coverage.hit("lite.b_stall_length", b_stall_name)
            self.coverage.hit("lite.address_type", kind)
            self.coverage.hit("lite.response_type", "okay" if response == 0 else "slverr")
            self.coverage.hit("lite.wstrb", f"{strobes:04b}")
            self.coverage.hit("cross.order_bstall", f"{ordering}_x_{b_stall_name}")
            self.coverage.hit(
                "cross.address_response", f"{kind}_x_{'okay' if response == 0 else 'slverr'}"
            )
            register = {
                0x08: "control",
                0x30: "irq_enable",
                0x34: "irq_status",
                0x38: "scratch",
            }.get(address)
            if register is not None:
                self.coverage.hit("lite.wstrb_register", register)
            if response == 0 and strobes & 1:
                if address == 0x08:
                    self.coverage.hit(
                        "lite.side_effect", "enable_set" if data & 1 else "enable_clear"
                    )
                    if data & 2:
                        self.coverage.hit("lite.side_effect", "soft_reset_write_one")
                elif address == 0x30:
                    self.coverage.hit(
                        "lite.side_effect", "irq_enable" if data & 1 else "irq_disable"
                    )
                elif address == 0x34 and data & 1:
                    self.coverage.hit("lite.side_effect", "irq_w1c")
            if response == 0 and address == 0x38 and strobes != 0xF:
                self.coverage.hit("lite.side_effect", "scratch_partial_update")
        return response

    async def read(
        self,
        address: int,
        *,
        response_stall: int = 0,
        expected_resp: int = 0,
    ) -> tuple[int, int]:
        self.dut.s_axi_araddr.value = address
        self.dut.s_axi_arvalid.value = 1
        while True:
            await RisingEdge(self.clock)
            if self.dut.s_axi_arready.value:
                break
        self.dut.s_axi_arvalid.value = 0
        observed_stall = 0
        for _ in range(response_stall):
            await RisingEdge(self.clock)
            if self.dut.s_axi_rvalid.value:
                self.metrics["read_stall_cycles"] += 1
                observed_stall += 1
        self.dut.s_axi_rready.value = 1
        while True:
            await RisingEdge(self.clock)
            if self.dut.s_axi_rvalid.value:
                data = int(self.dut.s_axi_rdata.value)
                response = int(self.dut.s_axi_rresp.value)
                break
        self.dut.s_axi_rready.value = 0
        self.metrics["axi_lite_reads"] += 1
        self.metrics["slverr_responses"] += int(response == 2)
        assert response == expected_resp
        if self.coverage is not None:
            kind = address_type(address, write=False)
            stall_name = length_bin(observed_stall, RESPONSE_EDGES)
            response_name = "okay" if response == 0 else "slverr"
            self.coverage.hit("lite.r_stall_length", stall_name)
            self.coverage.hit("lite.address_type", kind)
            self.coverage.hit("lite.response_type", response_name)
            self.coverage.hit("cross.address_response", f"{kind}_x_{response_name}")
            if response == 0 and address == 0x10:
                self.coverage.hit("lite.side_effect", "counter_read")
            if response == 0 and 0x14 <= address <= 0x2C:
                self.coverage.hit("lite.side_effect", "snapshot_read")
        return data, response
