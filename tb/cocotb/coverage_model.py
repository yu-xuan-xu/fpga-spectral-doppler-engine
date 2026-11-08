"""Observed-event functional coverage for the controlled Doppler accelerator."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from cocotb.triggers import RisingEdge


def length_bin(length: int, edges: tuple[tuple[int, int | None, str], ...]) -> str:
    for low, high, name in edges:
        if length >= low and (high is None or length <= high):
            return name
    raise ValueError(f"length {length} has no coverage bin")


GAP_EDGES = ((0, 0, "0"), (1, 1, "1"), (2, 3, "2-3"), (4, 15, "4-15"), (16, None, "16+"))
STALL_EDGES = (
    (0, 0, "0"),
    (1, 1, "1"),
    (2, 3, "2-3"),
    (4, 15, "4-15"),
    (16, 63, "16-63"),
    (64, None, "64+"),
)
RESPONSE_EDGES = GAP_EDGES


def required_bins() -> set[str]:
    bins: set[str] = set()

    def add(point: str, values) -> None:
        bins.update(f"{point}/{value}" for value in values)

    add("stream.input_gap_length", ("0", "1", "2-3", "4-15", "16+"))
    add("stream.input_stall_length", ("0", "1", "2-3", "4-15", "16-63", "64+"))
    add("stream.output_stall_length", ("0", "1", "2-3", "4-15", "16-63", "64+"))
    add(
        "stream.output_stall_context",
        (
            "result_first_appears",
            "already_stalled",
            "next_frame_input_active",
            "disable_nearby",
            "reset_nearby",
        ),
    )
    add(
        "stream.frame_type",
        ("legal", "early_tlast", "missing_tlast", "oversized_discard", "reset_aborted"),
    )
    add(
        "stream.result_behavior",
        (
            "normal_handshake",
            "delayed_handshake",
            "reset_aborted_pending_result",
            "back_to_back_results",
        ),
    )
    add("lite.write_ordering", ("same_cycle", "aw_before_w", "w_before_aw"))
    add("lite.aw_w_delay", ("0", "1", "2-3", "4-15", "16+"))
    add("lite.b_stall_length", ("0", "1", "2-3", "4-15", "16+"))
    add("lite.r_stall_length", ("0", "1", "2-3", "4-15", "16+"))
    add(
        "lite.address_type",
        (
            "valid_ro_read",
            "valid_rw_read",
            "valid_rw_write",
            "ro_write",
            "undefined_address",
            "misaligned_address",
        ),
    )
    add("lite.response_type", ("okay", "slverr"))
    add("lite.wstrb", (f"{value:04b}" for value in range(16)))
    add("lite.wstrb_register", ("control", "irq_enable", "irq_status", "scratch"))
    add(
        "lite.side_effect",
        (
            "enable_set",
            "enable_clear",
            "soft_reset_write_one",
            "irq_enable",
            "irq_disable",
            "irq_w1c",
            "scratch_partial_update",
            "counter_read",
            "snapshot_read",
        ),
    )
    add(
        "reset.global_location",
        (
            "idle",
            "collecting",
            "processing",
            "result_valid_and_ready",
            "result_stalled",
            "aw_pending",
            "w_pending",
            "b_response_stalled",
            "ar_accepted",
            "r_response_stalled",
        ),
    )
    add(
        "reset.soft_location",
        ("idle", "collecting", "processing", "result_stalled", "irq_pending", "after_result"),
    )
    add(
        "reset.post_check",
        (
            "no_stale_result",
            "sequence_restart",
            "result_count_clear",
            "snapshot_valid_clear",
            "irq_status_clear",
            "enable_clear",
            "scratch_contract",
            "irq_enable_contract",
            "axi_lite_responsive",
            "subsequent_legal_frame",
        ),
    )
    add(
        "irq.behavior",
        (
            "result_while_disabled",
            "enable_with_status_pending",
            "result_while_enabled",
            "software_clear",
            "write_zero",
            "multiple_results_before_clear",
            "clear_and_result_same_cycle",
            "soft_reset_while_pending",
            "global_reset_while_pending",
        ),
    )
    directions = ("negative", "zero_or_near_zero", "positive")
    peak_ranges = (
        "-128_to_-96",
        "-95_to_-33",
        "-32_to_-1",
        "0",
        "1_to_32",
        "33_to_95",
        "96_to_127",
    )
    snrs = ("lt_0", "0_to_9", "10_to_19", "20_to_29", "30_plus")
    clutters = ("none", "low", "medium", "high")
    amplitudes = ("low", "nominal", "near_full_scale")
    add("algorithm.direction", directions)
    add("algorithm.peak_bin_range", peak_ranges)
    add("algorithm.snr", snrs)
    add("algorithm.clutter", clutters)
    add("algorithm.amplitude", amplitudes)
    add(
        "algorithm.special_signal",
        (
            "zero",
            "exact_tie",
            "full_scale_positive",
            "full_scale_negative",
            "near_nyquist_positive",
            "near_nyquist_negative",
        ),
    )
    for direction in directions:
        for snr in snrs:
            bins.add(f"cross.direction_snr/{direction}_x_{snr}")
        for clutter in clutters:
            bins.add(f"cross.direction_clutter/{direction}_x_{clutter}")
        for backpressure in ("none", "short", "long"):
            bins.add(f"cross.direction_backpressure/{direction}_x_{backpressure}")
    for peak_range in peak_ranges:
        for snr in snrs:
            bins.add(f"cross.peak_range_snr/{peak_range}_x_{snr}")
    for amplitude in amplitudes:
        bins.add(f"cross.amplitude_saturation/{amplitude}_x_not_saturated")
    for stall in ("0", "1", "2-3", "4-15", "16-63", "64+"):
        bins.add(f"cross.legal_output_stall/{stall}")
    for ordering in ("same_cycle", "aw_before_w", "w_before_aw"):
        for stall in ("0", "2-3", "16+"):
            bins.add(f"cross.order_bstall/{ordering}_x_{stall}")
    add(
        "cross.address_response",
        (
            "valid_ro_read_x_okay",
            "valid_rw_read_x_okay",
            "valid_rw_write_x_okay",
            "ro_write_x_slverr",
            "undefined_address_x_slverr",
            "misaligned_address_x_slverr",
        ),
    )
    add("cross.irq_enable_result", ("enabled", "disabled"))
    add("cross.irq_clear_result", ("clear_only", "clear_x_result"))
    add("cross.irq_pending_soft_reset", ("pending", "not_pending"))
    add(
        "cross.soft_reset_state",
        ("idle", "collecting", "processing", "result_stalled", "irq_pending", "after_result"),
    )
    add(
        "cross.enable_frame_state",
        ("set_x_idle", "clear_x_idle", "clear_x_collecting", "set_x_collecting"),
    )
    add(
        "cross.frame_reset",
        (
            "reset_aborted_x_collecting",
            "reset_aborted_x_processing",
            "reset_aborted_x_result_stalled",
        ),
    )
    return bins


def waived_bins() -> dict[str, str]:
    return {
        "stream.result_behavior/sequence_wrap": (
            "Natural wrap requires 2^32 controlled-top results; Phase 2 separately verifies the "
            "same wrapper with a near-wrap reset parameter."
        ),
        **{
            f"cross.amplitude_saturation/{amplitude}_x_saturated": (
                "Unreachable for legal Q1.15 input with the frozen wall-filter width and per-stage "
                "FFT scaling; 1,800-case regression also observes zero saturation."
            )
            for amplitude in ("low", "nominal", "near_full_scale")
        },
    }


@dataclass(frozen=True)
class BinHit:
    count: int
    first_seed: int
    first_cycle: int
    first_scenario: str


class CoverageTracker:
    """Records hit metadata without crediting unaccepted stimulus."""

    def __init__(self, *, test_name: str):
        self.test_name = test_name
        self.cycle = 0
        self.seed = 0
        self.scenario = test_name
        self.hits: dict[str, BinHit] = {}

    def context(self, *, seed: int, scenario: str) -> None:
        self.seed = seed
        self.scenario = scenario

    def hit(self, point: str, value: str) -> None:
        key = f"{point}/{value}"
        prior = self.hits.get(key)
        if prior is None:
            self.hits[key] = BinHit(1, self.seed, self.cycle, self.scenario)
        else:
            self.hits[key] = BinHit(
                prior.count + 1,
                prior.first_seed,
                prior.first_cycle,
                prior.first_scenario,
            )

    def hit_length(self, point: str, length: int, *, response: bool = False) -> str:
        name = length_bin(length, RESPONSE_EDGES if response else STALL_EDGES)
        self.hit(point, name)
        return name

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "test_name": self.test_name,
                    "hits": {key: asdict(value) for key, value in sorted(self.hits.items())},
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )


def direction_bin(value: int) -> str:
    if value < 0:
        return "negative"
    if value > 0:
        return "positive"
    return "zero_or_near_zero"


def peak_range_bin(value: int) -> str:
    ranges = (
        (-128, -96, "-128_to_-96"),
        (-95, -33, "-95_to_-33"),
        (-32, -1, "-32_to_-1"),
        (0, 0, "0"),
        (1, 32, "1_to_32"),
        (33, 95, "33_to_95"),
        (96, 127, "96_to_127"),
    )
    return length_bin(value, ranges)


def snr_bin(value: float) -> str:
    if value < 0:
        return "lt_0"
    if value < 10:
        return "0_to_9"
    if value < 20:
        return "10_to_19"
    if value < 30:
        return "20_to_29"
    return "30_plus"


def clutter_bin(value: float) -> str:
    if value == 0:
        return "none"
    if value < 0.3:
        return "low"
    if value < 0.8:
        return "medium"
    return "high"


def amplitude_bin(value: float) -> str:
    if value < 0.25:
        return "low"
    if value < 0.85:
        return "nominal"
    return "near_full_scale"


def address_type(address: int, *, write: bool) -> str:
    if address & 3:
        return "misaligned_address"
    ro = set(range(0x00, 0x30, 4))
    rw = {0x08, 0x30, 0x34, 0x38}
    if write and address in ro - rw:
        return "ro_write"
    if address not in ro | rw:
        return "undefined_address"
    if write:
        return "valid_rw_write"
    return "valid_rw_read" if address in rw else "valid_ro_read"


class ObservedSystemCoverage:
    """Samples stream/reset state only from clocked DUT observations."""

    def __init__(self, dut, coverage: CoverageTracker):
        self.dut = dut
        self.coverage = coverage
        self._prior_resetn = False
        self._accepted_in_frame = 0
        self._discarding = False
        self._processing = False
        self._input_stall = 0
        self._output_stall = 0
        self._last_input_cycle: int | None = None
        self._outputs_since_reset = 0
        self._aw_pending = False
        self._w_pending = False
        self._ar_pending = False
        self._r_was_stalled = False
        self._last_accelerator_state = "idle"
        self._last_irq_pending = False
        self.current_frame_kind = "none"
        self.enable_transition = "none"

    def accelerator_state(self) -> str:
        if self.dut.m_axis_tvalid.value and not self.dut.m_axis_tready.value:
            return "result_stalled"
        if self.dut.m_axis_tvalid.value and self.dut.m_axis_tready.value:
            return "result_valid_and_ready"
        if self._accepted_in_frame:
            return "collecting"
        if self._processing:
            return "processing"
        return "idle"

    def _reset_location(self) -> str:
        if self.dut.s_axi_bvalid.value and not self.dut.s_axi_bready.value:
            return "b_response_stalled"
        if self._r_was_stalled:
            return "r_response_stalled"
        if self._aw_pending and not self._w_pending:
            return "aw_pending"
        if self._w_pending and not self._aw_pending:
            return "w_pending"
        if self._ar_pending:
            return "ar_accepted"
        return self._last_accelerator_state

    def _finish_stalls(self) -> None:
        if self._input_stall:
            self.coverage.hit_length("stream.input_stall_length", self._input_stall)
            self._input_stall = 0
        if self._output_stall:
            self.coverage.hit_length("stream.output_stall_length", self._output_stall)
            self._output_stall = 0

    async def run(self) -> None:
        while True:
            await RisingEdge(self.dut.aclk)
            self.coverage.cycle += 1
            resetn = bool(self.dut.aresetn.value)
            if not resetn:
                if self._prior_resetn:
                    location = self._reset_location()
                    self.coverage.hit("reset.global_location", location)
                    if location in {"collecting", "processing", "result_stalled"}:
                        self.coverage.hit("stream.frame_type", "reset_aborted")
                        self.coverage.hit("cross.frame_reset", f"reset_aborted_x_{location}")
                    if location == "result_stalled":
                        self.coverage.hit("stream.result_behavior", "reset_aborted_pending_result")
                self._finish_stalls()
                self._accepted_in_frame = 0
                self._discarding = False
                self._processing = False
                self._outputs_since_reset = 0
                self._aw_pending = False
                self._w_pending = False
                self._ar_pending = False
                self._r_was_stalled = False
                self._last_irq_pending = False
                self._prior_resetn = False
                continue
            self._prior_resetn = True

            if hasattr(self.dut, "control_regs") and self.dut.control_regs.soft_reset_pulse.value:
                pending = self._last_irq_pending
                if pending:
                    location = "irq_pending"
                elif self._outputs_since_reset:
                    location = "after_result"
                else:
                    location = self._last_accelerator_state
                self.coverage.hit("reset.soft_location", location)
                self.coverage.hit("cross.soft_reset_state", location)
                self.coverage.hit(
                    "cross.irq_pending_soft_reset", "pending" if pending else "not_pending"
                )
                if location in {"collecting", "processing", "result_stalled"}:
                    self.coverage.hit("stream.frame_type", "reset_aborted")
                if location == "result_stalled":
                    self.coverage.hit("stream.result_behavior", "reset_aborted_pending_result")
                self._finish_stalls()
                self._accepted_in_frame = 0
                self._discarding = False
                self._processing = False
                self._outputs_since_reset = 0

            aw_transfer = bool(self.dut.s_axi_awvalid.value and self.dut.s_axi_awready.value)
            w_transfer = bool(self.dut.s_axi_wvalid.value and self.dut.s_axi_wready.value)
            ar_transfer = bool(self.dut.s_axi_arvalid.value and self.dut.s_axi_arready.value)
            if aw_transfer:
                self._aw_pending = True
            if w_transfer:
                self._w_pending = True
            if self.dut.s_axi_bvalid.value and self.dut.s_axi_bready.value:
                self._aw_pending = False
                self._w_pending = False
            if ar_transfer:
                self._ar_pending = True
            if self.dut.s_axi_rvalid.value and self.dut.s_axi_rready.value:
                self._ar_pending = False
            self._r_was_stalled = bool(
                self.dut.s_axi_rvalid.value and not self.dut.s_axi_rready.value
            )

            input_transfer = bool(self.dut.s_axis_tvalid.value and self.dut.s_axis_tready.value)
            if self.dut.s_axis_tvalid.value and not self.dut.s_axis_tready.value:
                self._input_stall += 1
            elif input_transfer:
                self.coverage.hit_length("stream.input_stall_length", self._input_stall)
                self._input_stall = 0
                gap = (
                    0
                    if self._last_input_cycle is None
                    else self.coverage.cycle - self._last_input_cycle - 1
                )
                self.coverage.hit("stream.input_gap_length", length_bin(gap, GAP_EDGES))
                self._last_input_cycle = self.coverage.cycle
                self._accepted_in_frame += 1
                last = bool(self.dut.s_axis_tlast.value)
                if self._discarding:
                    self.coverage.hit("stream.frame_type", "oversized_discard")
                    if last:
                        self._discarding = False
                        self._accepted_in_frame = 0
                elif last:
                    if self._accepted_in_frame == 256:
                        self.coverage.hit("stream.frame_type", "legal")
                        self.current_frame_kind = "legal"
                        self._processing = True
                    else:
                        self.coverage.hit("stream.frame_type", "early_tlast")
                        self.current_frame_kind = "early_tlast"
                    self._accepted_in_frame = 0
                elif self._accepted_in_frame == 256:
                    self.coverage.hit("stream.frame_type", "missing_tlast")
                    self.current_frame_kind = "missing_tlast"
                    self._discarding = True
                    self._accepted_in_frame = 0
            elif self._input_stall:
                pass

            output_transfer = bool(self.dut.m_axis_tvalid.value and self.dut.m_axis_tready.value)
            if self.dut.m_axis_tvalid.value and not self.dut.m_axis_tready.value:
                if self._output_stall == 0:
                    self.coverage.hit("stream.output_stall_context", "result_first_appears")
                    if self.dut.s_axis_tvalid.value:
                        self.coverage.hit("stream.output_stall_context", "next_frame_input_active")
                else:
                    self.coverage.hit("stream.output_stall_context", "already_stalled")
                    if self.dut.s_axis_tvalid.value:
                        self.coverage.hit("stream.output_stall_context", "next_frame_input_active")
                self._output_stall += 1
            elif output_transfer:
                stall_name = self.coverage.hit_length(
                    "stream.output_stall_length", self._output_stall
                )
                behavior = "normal_handshake" if self._output_stall == 0 else "delayed_handshake"
                self.coverage.hit("stream.result_behavior", behavior)
                self.coverage.hit("cross.legal_output_stall", stall_name)
                self._output_stall = 0
                self._processing = False
                self._outputs_since_reset += 1
                if self._outputs_since_reset > 1:
                    self.coverage.hit("stream.result_behavior", "back_to_back_results")
            self._last_accelerator_state = self.accelerator_state()
            if hasattr(self.dut, "control_regs"):
                self._last_irq_pending = bool(self.dut.control_regs.irq_status.value)
