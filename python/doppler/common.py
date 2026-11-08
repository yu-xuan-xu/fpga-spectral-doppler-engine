"""Shared spectrum conventions."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

GUARD_BINS = {-1, 0, 1}
CONFIDENCE_RATIO = 3


def raw_to_signed_bin(index: int, size: int = 256) -> int:
    return index if index <= size // 2 - 1 else index - size


def select_peak(power: NDArray[np.integer | np.floating]) -> tuple[int, int]:
    """Return raw index and signed bin using the frozen deterministic tie rule."""
    candidates = [
        i for i in range(power.size) if raw_to_signed_bin(i, power.size) not in GUARD_BINS
    ]
    max_power = max(power[i] for i in candidates)
    tied = [i for i in candidates if power[i] == max_power]
    tied.sort(
        key=lambda i: (abs(raw_to_signed_bin(i, power.size)), raw_to_signed_bin(i, power.size))
    )
    raw = tied[0]
    return raw, raw_to_signed_bin(raw, power.size)


def peak_metrics(
    power: NDArray[np.integer | np.floating],
) -> tuple[int, int, int | float, int | float, bool]:
    """Return peak location, top two allowed powers, and frozen confidence flag."""
    raw, signed = select_peak(power)
    allowed = [i for i in range(power.size) if raw_to_signed_bin(i, power.size) not in GUARD_BINS]
    runner_up = max((power[i] for i in allowed if i != raw), default=0)
    peak = power[raw]
    low_confidence = bool(peak == 0 or peak < CONFIDENCE_RATIO * runner_up)
    return raw, signed, peak.item(), runner_up.item(), low_confidence
