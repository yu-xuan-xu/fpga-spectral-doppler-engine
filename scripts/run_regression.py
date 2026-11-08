#!/usr/bin/env python3
"""Run the frozen 1,800-configuration M1 algorithm regression."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from doppler.classification import classify_frame
from doppler.config import DopplerConfig, FlowProfile
from doppler.fixed import FixedFilterState, process_fixed_frame
from doppler.floating import FloatFilterState, process_float_frame
from doppler.generator import generate_signal


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "results" / "regression"
    output.mkdir(parents=True, exist_ok=True)
    velocity_bins = [-64, -32, -16, -8, -4, 4, 8, 16, 32, 64]
    snrs = [None, 30.0, 20.0, 10.0]
    clutter_ratios = [0.0, 0.5, 2.0]
    seeds = [1, 17, 101]
    rows = []
    case_id = 0
    for profile in FlowProfile:
        for velocity_bin in velocity_bins:
            for snr_db in snrs:
                for clutter_ratio in clutter_ratios:
                    for seed in seeds:
                        case_id += 1
                        config = DopplerConfig(
                            profile=profile,
                            frame_count=2,
                            velocity_m_s=velocity_bin * 0.01203125,
                            snr_db=snr_db,
                            clutter_ratio=clutter_ratio,
                            seed=seed,
                        )
                        signal = generate_signal(config)
                        fixed_state, float_state = FixedFilterState(), FloatFilterState()
                        for frame_index in range(2):
                            start = frame_index * 256
                            frame = signal.iq[start : start + 256]
                            fixed = process_fixed_frame(frame, config, fixed_state)
                            floating = process_float_frame(frame, config, float_state)
                            fixed_state, float_state = fixed.state, floating.state
                        programmed = float(np.mean(signal.velocity_m_s[256:512]))
                        labels = classify_frame(
                            1, signal.doppler_hz[256:512], config, fixed.low_confidence
                        )
                        rows.append(
                            {
                                "case_id": case_id,
                                "profile": profile.value,
                                "velocity_bin_setting": velocity_bin,
                                "snr_db": "infinite" if snr_db is None else snr_db,
                                "clutter_ratio": clutter_ratio,
                                "seed": seed,
                                "programmed_velocity_m_s": programmed,
                                "float_bin": floating.peak_bin,
                                "fixed_bin": fixed.peak_bin,
                                "bin_difference": fixed.peak_bin - floating.peak_bin,
                                "fixed_error_m_s": fixed.velocity_q8_mm_s / 256000 - programmed,
                                "direction_correct": int(
                                    np.sign(fixed.peak_bin) == np.sign(programmed)
                                ),
                                "low_confidence": int(labels.low_confidence),
                                "transition": int(labels.transition),
                                "alias": int(labels.alias),
                                "scored": int(labels.scored),
                                "saturation_count": fixed.saturation_count,
                            }
                        )
    csv_path = output / "full_matrix.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    scored = [row for row in rows if row["scored"]]
    high_snr = [row for row in rows if row["snr_db"] == "infinite" or float(row["snr_db"]) >= 20]
    summary = {
        "configuration_count": len(rows),
        "scored_count": len(scored),
        "low_confidence_count": sum(row["low_confidence"] for row in rows),
        "transition_count": sum(row["transition"] for row in rows),
        "alias_count": sum(row["alias"] for row in rows),
        "fixed_float_within_one_bin_high_snr_fraction": float(
            np.mean([abs(row["bin_difference"]) <= 1 for row in high_snr])
        ),
        "direction_accuracy_high_snr": float(
            np.mean([row["direction_correct"] for row in high_snr])
        ),
        "mean_absolute_error_m_s_scored": float(
            np.mean([abs(row["fixed_error_m_s"]) for row in scored]) if scored else np.nan
        ),
        "maximum_saturation_count": max(row["saturation_count"] for row in rows),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    _plots(rows, output)
    print(json.dumps(summary, indent=2))


@plt.rc_context(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica", "Arial", "Liberation Sans", "DejaVu Sans"],
    }
)
def _plots(rows: list[dict], output: Path) -> None:
    programmed = np.array([row["programmed_velocity_m_s"] for row in rows])
    estimated = np.array([row["fixed_bin"] * 0.01203125 for row in rows])
    limits = [min(programmed.min(), estimated.min()), max(programmed.max(), estimated.max())]
    fig, ax = plt.subplots(figsize=(5.2, 5.0), layout="constrained")
    ax.plot(limits, limits, color="0.65", linewidth=1, label="Equal velocities")
    ax.scatter(programmed, estimated, s=9, color="0.12", alpha=0.35)
    ax.set(xlabel="Programmed velocity (m/s)", ylabel="Fixed point estimate (m/s)")
    ax.set_aspect("equal", adjustable="box")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper left", frameon=False)
    fig.savefig(output / "programmed_vs_fixed.png", dpi=160)
    plt.close(fig)

    snr_labels = ["infinite", "30.0", "20.0", "10.0"]
    errors = [
        [abs(row["fixed_error_m_s"]) * 1000 for row in rows if str(row["snr_db"]) == snr]
        for snr in snr_labels
    ]
    fig, ax = plt.subplots(figsize=(6.4, 4.2), layout="constrained")
    ax.boxplot(
        errors,
        tick_labels=["inf", "30", "20", "10"],
        showfliers=False,
        patch_artist=True,
        boxprops={"facecolor": "0.9", "edgecolor": "0.25"},
        medianprops={"color": "0.1"},
    )
    ax.set(xlabel="SNR (dB)", ylabel="Absolute velocity error (mm/s)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(output / "error_by_snr.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
