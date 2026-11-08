"""Deterministic synthetic complex Doppler signal generation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .config import DopplerConfig, FlowProfile


@dataclass(frozen=True)
class SyntheticSignal:
    iq: NDArray[np.complex128]
    clean_iq: NDArray[np.complex128]
    velocity_m_s: NDArray[np.float64]
    doppler_hz: NDArray[np.float64]
    clutter: NDArray[np.complex128]
    noise: NDArray[np.complex128]
    config: DopplerConfig


def _velocity_profile(config: DopplerConfig, t: NDArray[np.float64]) -> NDArray[np.float64]:
    v = abs(config.velocity_m_s)
    direction = -1.0 if config.velocity_m_s < 0 else 1.0
    phase = 2 * np.pi * config.pulse_rate_hz * t
    if config.profile is FlowProfile.STEADY:
        return np.full_like(t, config.velocity_m_s)
    if config.profile is FlowProfile.REVERSE:
        return np.full_like(t, -v)
    if config.profile is FlowProfile.PULSATILE:
        return direction * v * (0.55 + 0.45 * (0.5 - 0.5 * np.cos(phase)))
    if config.profile is FlowProfile.ACCELERATED:
        ramp = np.mod(config.pulse_rate_hz * t, 1.0)
        return direction * v * (0.35 + 1.30 * np.minimum(ramp / 0.7, 1.0))
    if config.profile is FlowProfile.IRREGULAR:
        rng = np.random.default_rng(config.seed)
        knots = np.arange(0.0, t[-1] + 0.25, 0.08)
        levels = v * rng.uniform(0.25, 1.25, size=knots.size)
        return direction * np.interp(t, knots, levels)
    raise ValueError(f"unsupported profile {config.profile}")


def generate_signal(config: DopplerConfig) -> SyntheticSignal:
    """Generate repeatable I/Q, truth, clutter, and noise arrays."""
    rng = np.random.default_rng(config.seed)
    t = np.arange(config.sample_count, dtype=np.float64) / config.sample_rate_hz
    velocity = _velocity_profile(config, t)
    frequency = np.asarray(config.velocity_to_frequency(velocity), dtype=np.float64)
    phase = config.initial_phase_rad + 2 * np.pi * np.cumsum(frequency) / config.sample_rate_hz
    clean = config.signal_amplitude * np.exp(1j * phase)

    clutter_phase = rng.uniform(-np.pi, np.pi)
    clutter_amplitude = config.signal_amplitude * config.clutter_ratio
    clutter = clutter_amplitude * np.exp(1j * (2 * np.pi * config.clutter_hz * t + clutter_phase))

    if config.snr_db is None:
        noise = np.zeros_like(clean)
    else:
        signal_power = config.signal_amplitude**2
        noise_power = signal_power / (10 ** (config.snr_db / 10))
        sigma = np.sqrt(noise_power / 2)
        noise = sigma * (rng.standard_normal(t.size) + 1j * rng.standard_normal(t.size))

    iq = clean + clutter + noise
    return SyntheticSignal(iq, clean, velocity, frequency, clutter, noise, config)
