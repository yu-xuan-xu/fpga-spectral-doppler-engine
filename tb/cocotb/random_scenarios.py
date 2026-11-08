"""Deterministic Phase 4 randomized scenario generation."""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass

SNR_VALUES = (-5.0, 5.0, 15.0, 25.0, 35.0)
CLUTTER_VALUES = (0.0, 0.15, 0.5, 1.0)
AMPLITUDE_VALUES = (0.12, 0.55, 0.92)
PEAK_BINS = (-127, -110, -64, -40, -16, -3, 0, 3, 16, 40, 64, 110, 127)


@dataclass(frozen=True)
class RandomScenario:
    seed: int
    peak_bin: int
    snr_db: float
    clutter_ratio: float
    amplitude: float
    input_gap_pattern: str
    output_stall_cycles: int
    aw_delay: int
    w_delay: int
    b_stall_cycles: int
    r_stall_cycles: int
    irq_enable: bool
    action: str
    frame_type: str

    def as_json(self) -> dict:
        return asdict(self)


def scenario_for_seed(seed: int) -> RandomScenario:
    rng = random.Random(seed)
    action_cycle = ("normal", "enable_pause", "soft_reset_collecting", "soft_reset_processing")
    frame_cycle = ("legal", "legal", "legal", "early_tlast", "missing_tlast")
    stall_choices = (0, 1, 3, 11, 31, 67)
    delay_choices = (0, 1, 3, 9, 17)
    gap_patterns = ("none", "one", "short", "medium", "long")
    return RandomScenario(
        seed=seed,
        peak_bin=rng.choice(PEAK_BINS),
        snr_db=rng.choice(SNR_VALUES),
        clutter_ratio=rng.choice(CLUTTER_VALUES),
        amplitude=rng.choice(AMPLITUDE_VALUES),
        input_gap_pattern=rng.choice(gap_patterns),
        output_stall_cycles=rng.choice(stall_choices),
        aw_delay=rng.choice(delay_choices),
        w_delay=rng.choice(delay_choices),
        b_stall_cycles=rng.choice(delay_choices),
        r_stall_cycles=rng.choice(delay_choices),
        irq_enable=bool(rng.randrange(2)),
        action=action_cycle[seed % len(action_cycle)],
        frame_type=frame_cycle[seed % len(frame_cycle)],
    )


def gap_cycles(pattern: str, index: int) -> int:
    if pattern == "none":
        return 0
    if pattern == "one":
        return int(index % 19 == 0)
    if pattern == "short":
        return 3 if index % 31 == 0 else 0
    if pattern == "medium":
        return 9 if index % 47 == 0 else 0
    if pattern == "long":
        return 17 if index in {0, 127, 255} else 0
    raise ValueError(pattern)
