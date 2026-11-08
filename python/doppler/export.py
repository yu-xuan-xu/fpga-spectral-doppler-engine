"""Canonical vector and result export."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .classification import classify_frame
from .config import DopplerConfig
from .fixed import FixedFilterState, process_fixed_frame, quantize_q15
from .floating import FloatFilterState, process_float_frame
from .generator import generate_signal

MODEL_VERSION = "m1-oracle-1.0"
SPEC_VERSION = "1.3"


@dataclass(frozen=True)
class ExportSummary:
    directory: Path
    scored_frames: int
    fixed_float_bin_mismatches: int


def export_case(config: DopplerConfig, directory: str | Path) -> ExportSummary:
    """Export one deterministic case using the frozen repository contract."""
    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)
    signal = generate_signal(config)
    config.to_json(destination / "config.json")
    (destination / "metadata.json").write_text(
        json.dumps(
            {
                "model_version": MODEL_VERSION,
                "specification_version": SPEC_VERSION,
                "rounding": "nearest_ties_away_from_zero",
                "fft_normalization": "1/256",
                "warmup_frames": 1,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    input_i = quantize_q15(signal.iq.real)
    input_q = quantize_q15(signal.iq.imag)
    with (destination / "input_iq_q15.mem").open("w", encoding="ascii") as stream:
        for i_value, q_value in zip(input_i, input_q, strict=True):
            packed = ((int(i_value) & 0xFFFF) << 16) | (int(q_value) & 0xFFFF)
            stream.write(f"{packed:08x}\n")

    fixed_rows, float_rows = [], []
    fixed_state, float_state = FixedFilterState(), FloatFilterState()
    mismatch_count = 0
    for frame_index in range(config.frame_count):
        start = frame_index * config.fft_size
        frame = signal.iq[start : start + config.fft_size]
        float_result = process_float_frame(frame, config, float_state)
        fixed_result = process_fixed_frame(frame, config, fixed_state)
        float_state, fixed_state = float_result.state, fixed_result.state
        _write_intermediates(destination, frame_index, fixed_result)
        if frame_index == 0:  # warm-up frame is exported but not scored
            continue
        mismatch_count += float_result.peak_bin != fixed_result.peak_bin
        programmed = float(np.mean(signal.velocity_m_s[start : start + config.fft_size]))
        labels = classify_frame(
            frame_index,
            signal.doppler_hz[start : start + config.fft_size],
            config,
            fixed_result.low_confidence,
        )
        fixed_rows.append(
            {
                "frame": frame_index,
                "peak_bin": fixed_result.peak_bin,
                "frequency_q8_hz": fixed_result.frequency_q8_hz,
                "velocity_q8_mm_s": fixed_result.velocity_q8_mm_s,
                "peak_power": fixed_result.peak_power,
                "second_power": fixed_result.second_power,
                "saturation_count": fixed_result.saturation_count,
                "overflow": int(fixed_result.saturation_count > 0),
                "low_confidence": int(labels.low_confidence),
                "transition": int(labels.transition),
                "alias": int(labels.alias),
                "scored": int(labels.scored),
            }
        )
        float_rows.append(
            {
                "frame": frame_index,
                "programmed_velocity_m_s": programmed,
                "peak_bin": float_result.peak_bin,
                "frequency_hz": float_result.frequency_hz,
                "velocity_m_s": float_result.velocity_m_s,
                "error_m_s": float_result.velocity_m_s - programmed,
                "low_confidence": int(float_result.low_confidence),
                "transition": int(labels.transition),
                "alias": int(labels.alias),
            }
        )

    _write_csv(destination / "expected_frames.csv", fixed_rows)
    _write_csv(destination / "float_results.csv", float_rows)
    return ExportSummary(destination, len(fixed_rows), mismatch_count)


def _write_intermediates(destination: Path, frame_index: int, result) -> None:
    frame_dir = destination / "intermediate" / f"frame_{frame_index:03d}"
    frame_dir.mkdir(parents=True, exist_ok=True)
    arrays = {
        "filter_i_s18.mem": (result.filtered_i, 18),
        "filter_q_s18.mem": (result.filtered_q, 18),
        "window_i_s16.mem": (result.window_i, 16),
        "window_q_s16.mem": (result.window_q, 16),
        "fft_i_s16.mem": (result.fft_i, 16),
        "fft_q_s16.mem": (result.fft_q, 16),
        "power_u37.mem": (result.spectrum_power, 37),
    }
    for name, (values, bits) in arrays.items():
        mask = (1 << bits) - 1
        width = (bits + 3) // 4
        with (frame_dir / name).open("w", encoding="ascii") as stream:
            for value in values:
                stream.write(f"{int(value) & mask:0{width}x}\n")


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("at least one scored frame is required")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
