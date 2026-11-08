"""Frame labels used by regression reports and release metrics."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .config import DopplerConfig


@dataclass(frozen=True)
class FrameLabels:
    warmup: bool
    transition: bool
    alias: bool
    low_confidence: bool

    @property
    def scored(self) -> bool:
        return not (self.warmup or self.transition or self.alias or self.low_confidence)


def classify_frame(
    frame_index: int,
    programmed_frequency_hz: NDArray[np.float64],
    config: DopplerConfig,
    low_confidence: bool,
) -> FrameLabels:
    """Apply the frozen labels without silently dropping difficult frames."""
    span = float(np.ptp(programmed_frequency_hz))
    return FrameLabels(
        warmup=frame_index == 0,
        transition=span > config.bin_hz,
        alias=bool(np.any(np.abs(programmed_frequency_hz) >= config.sample_rate_hz / 2)),
        low_confidence=low_confidence,
    )
