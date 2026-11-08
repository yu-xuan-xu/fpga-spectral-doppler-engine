"""Floating-point golden pipeline."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .common import peak_metrics
from .config import DopplerConfig


@dataclass(frozen=True)
class FloatFilterState:
    previous_x: complex = 0j
    previous_y: complex = 0j


@dataclass(frozen=True)
class FloatFrameResult:
    peak_bin: int
    frequency_hz: float
    velocity_m_s: float
    peak_power: float
    second_power: float
    low_confidence: bool
    spectrum_power: NDArray[np.float64]
    filtered: NDArray[np.complex128]
    windowed: NDArray[np.complex128]
    spectrum: NDArray[np.complex128]
    state: FloatFilterState


def wall_filter(
    samples: NDArray[np.complex128], state: FloatFilterState | None = None
) -> tuple[NDArray[np.complex128], FloatFilterState]:
    state = state or FloatFilterState()
    output = np.empty_like(samples)
    previous_x, previous_y = state.previous_x, state.previous_y
    for index, sample in enumerate(samples):
        filtered = sample - previous_x + (63.0 / 64.0) * previous_y
        output[index] = filtered
        previous_x, previous_y = sample, filtered
    return output, FloatFilterState(previous_x, previous_y)


def process_float_frame(
    samples: NDArray[np.complex128],
    config: DopplerConfig,
    state: FloatFilterState | None = None,
) -> FloatFrameResult:
    if samples.shape != (config.fft_size,):
        raise ValueError("one frame must contain exactly 256 complex samples")
    filtered, state_out = wall_filter(samples, state)
    windowed = filtered * np.hanning(config.fft_size)
    spectrum = np.fft.fft(windowed) / config.fft_size
    power = np.asarray(np.abs(spectrum) ** 2, dtype=np.float64)
    _, signed, peak_power, second_power, low_confidence = peak_metrics(power)
    frequency = signed * config.bin_hz
    return FloatFrameResult(
        signed,
        frequency,
        float(config.frequency_to_velocity(frequency)),
        float(peak_power),
        float(second_power),
        low_confidence,
        power,
        filtered,
        windowed,
        spectrum,
        state_out,
    )
