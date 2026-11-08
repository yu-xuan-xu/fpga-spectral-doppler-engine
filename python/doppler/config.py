"""Frozen v1 signal configuration and metadata helpers."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path


class FlowProfile(str, Enum):
    STEADY = "steady"
    PULSATILE = "pulsatile"
    ACCELERATED = "accelerated"
    REVERSE = "reverse"
    IRREGULAR = "irregular"


@dataclass(frozen=True)
class DopplerConfig:
    profile: FlowProfile = FlowProfile.STEADY
    sample_rate_hz: int = 20_000
    fft_size: int = 256
    frame_count: int = 4
    carrier_hz: float = 5_000_000.0
    sound_speed_m_s: float = 1540.0
    probe_angle_deg: float = 0.0
    velocity_m_s: float = 0.1925
    signal_amplitude: float = 0.55
    snr_db: float | None = 30.0
    clutter_ratio: float = 0.5
    clutter_hz: float = 20.0
    initial_phase_rad: float = 0.0
    pulse_rate_hz: float = 2.0
    seed: int = 1

    def __post_init__(self) -> None:
        if self.sample_rate_hz <= 0 or self.fft_size != 256 or self.frame_count < 2:
            raise ValueError("v1 requires Fs > 0, a 256-point FFT, and at least two frames")
        if self.carrier_hz <= 0 or self.sound_speed_m_s <= 0:
            raise ValueError("physical constants must be positive")
        if abs(self.probe_angle_deg) >= 90:
            raise ValueError("probe angle must have a nonzero cosine")
        if not 0 < self.signal_amplitude < 1:
            raise ValueError("signal_amplitude must be between zero and one")
        if self.clutter_ratio < 0 or self.pulse_rate_hz <= 0:
            raise ValueError("clutter_ratio must be nonnegative and pulse rate positive")
        nyquist_velocity = self.frequency_to_velocity(self.sample_rate_hz / 2)
        if abs(self.velocity_m_s) >= nyquist_velocity:
            raise ValueError("velocity aliases at the configured sample rate")

    @property
    def sample_count(self) -> int:
        return self.fft_size * self.frame_count

    @property
    def bin_hz(self) -> float:
        return self.sample_rate_hz / self.fft_size

    def velocity_to_frequency(self, velocity_m_s):
        scale = 2 * self.carrier_hz * math.cos(math.radians(self.probe_angle_deg))
        return velocity_m_s * scale / self.sound_speed_m_s

    def frequency_to_velocity(self, frequency_hz):
        scale = 2 * self.carrier_hz * math.cos(math.radians(self.probe_angle_deg))
        return frequency_hz * self.sound_speed_m_s / scale

    def to_json(self, path: str | Path) -> None:
        data = asdict(self)
        data["profile"] = self.profile.value
        Path(path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def from_json(cls, path: str | Path) -> DopplerConfig:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        data["profile"] = FlowProfile(data["profile"])
        return cls(**data)
