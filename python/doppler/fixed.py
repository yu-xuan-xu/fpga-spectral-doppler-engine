"""Bit-accurate integer model for the v1 RTL arithmetic contract."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .common import peak_metrics
from .config import DopplerConfig


def saturate(value: int, bits: int) -> int:
    return min(max(int(value), -(1 << (bits - 1))), (1 << (bits - 1)) - 1)


def round_shift(value: int, shift: int) -> int:
    """Signed nearest rounding with exact half cases away from zero."""
    if shift <= 0:
        return int(value) << -shift
    magnitude = abs(int(value))
    rounded = (magnitude + (1 << (shift - 1))) >> shift
    return rounded if value >= 0 else -rounded


def quantize_q15(values) -> NDArray[np.int64]:
    values = np.asarray(values, dtype=np.float64)
    magnitude = np.floor(np.abs(values) * 32768.0 + 0.5)
    signed = np.where(values < 0, -magnitude, magnitude).astype(np.int64)
    return np.clip(signed, -32768, 32767)


def hann_q15(size: int = 256) -> NDArray[np.int64]:
    coeff = np.floor(np.hanning(size) * 32767.0 + 0.5).astype(np.int64)
    coeff[0] = coeff[-1] = 0
    return coeff


@dataclass(frozen=True)
class FixedFilterState:
    previous_x_i: int = 0
    previous_x_q: int = 0
    previous_y_i: int = 0
    previous_y_q: int = 0


@dataclass(frozen=True)
class FixedFrameResult:
    peak_bin: int
    frequency_q8_hz: int
    velocity_q8_mm_s: int
    peak_power: int
    second_power: int
    low_confidence: bool
    spectrum_power: NDArray[np.int64]
    filtered_i: NDArray[np.int64]
    filtered_q: NDArray[np.int64]
    window_i: NDArray[np.int64]
    window_q: NDArray[np.int64]
    fft_i: NDArray[np.int64]
    fft_q: NDArray[np.int64]
    state: FixedFilterState
    saturation_count: int


def _filter_axis(samples: NDArray[np.int64], previous_x: int, previous_y: int):
    output = np.empty(samples.size, dtype=np.int64)
    saturation_count = 0
    for index, sample in enumerate(samples):
        wide = int(sample) - previous_x + round_shift(63 * previous_y, 6)
        filtered = saturate(wide, 18)
        saturation_count += filtered != wide
        output[index] = filtered
        previous_x, previous_y = int(sample), filtered
    return output, previous_x, previous_y, saturation_count


def _bit_reverse(index: int, width: int) -> int:
    return int(f"{index:0{width}b}"[::-1], 2)


def fixed_fft(i_data: NDArray[np.int64], q_data: NDArray[np.int64]):
    """Radix-2 DIT FFT with Q1.15 twiddles and one-bit scaling per stage."""
    size = i_data.size
    width = size.bit_length() - 1
    real = np.array([i_data[_bit_reverse(i, width)] for i in range(size)], dtype=np.int64)
    imag = np.array([q_data[_bit_reverse(i, width)] for i in range(size)], dtype=np.int64)
    saturation_count = 0
    span = 2
    while span <= size:
        half = span // 2
        angles = -2 * np.pi * np.arange(half) / span
        twiddle_r = quantize_q15(np.cos(angles))
        twiddle_i = quantize_q15(np.sin(angles))
        for base in range(0, size, span):
            for offset in range(half):
                upper = base + offset
                lower = upper + half
                product_r = round_shift(
                    int(real[lower]) * int(twiddle_r[offset])
                    - int(imag[lower]) * int(twiddle_i[offset]),
                    15,
                )
                product_i = round_shift(
                    int(real[lower]) * int(twiddle_i[offset])
                    + int(imag[lower]) * int(twiddle_r[offset]),
                    15,
                )
                a_r, a_i = int(real[upper]), int(imag[upper])
                new_values = (
                    round_shift(a_r + product_r, 1),
                    round_shift(a_i + product_i, 1),
                    round_shift(a_r - product_r, 1),
                    round_shift(a_i - product_i, 1),
                )
                saturated = tuple(saturate(value, 16) for value in new_values)
                saturation_count += sum(a != b for a, b in zip(new_values, saturated, strict=True))
                real[upper], imag[upper], real[lower], imag[lower] = saturated
        span *= 2
    return real, imag, saturation_count


def process_fixed_frame(
    samples: NDArray[np.complex128],
    config: DopplerConfig,
    state: FixedFilterState | None = None,
) -> FixedFrameResult:
    if samples.shape != (config.fft_size,):
        raise ValueError("one frame must contain exactly 256 complex samples")
    state = state or FixedFilterState()
    input_i, input_q = quantize_q15(samples.real), quantize_q15(samples.imag)
    filtered_i, px_i, py_i, sat_i = _filter_axis(input_i, state.previous_x_i, state.previous_y_i)
    filtered_q, px_q, py_q, sat_q = _filter_axis(input_q, state.previous_x_q, state.previous_y_q)
    coeff = hann_q15(config.fft_size)
    window_i = np.array(
        [saturate(round_shift(int(x) * int(w), 15), 16) for x, w in zip(filtered_i, coeff)],
        dtype=np.int64,
    )
    window_q = np.array(
        [saturate(round_shift(int(x) * int(w), 15), 16) for x, w in zip(filtered_q, coeff)],
        dtype=np.int64,
    )
    fft_i, fft_q, sat_fft = fixed_fft(window_i, window_q)
    power = fft_i * fft_i + fft_q * fft_q
    _, signed, peak_power, second_power, low_confidence = peak_metrics(power)
    return FixedFrameResult(
        signed,
        signed * config.sample_rate_hz,
        signed * 3080,
        int(peak_power),
        int(second_power),
        low_confidence,
        power,
        filtered_i,
        filtered_q,
        window_i,
        window_q,
        fft_i,
        fft_q,
        FixedFilterState(px_i, px_q, py_i, py_q),
        sat_i + sat_q + sat_fft,
    )
