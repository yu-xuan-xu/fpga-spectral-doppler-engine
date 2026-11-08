#!/usr/bin/env python3
"""Generate small checked-in vectors for positive and reverse steady flow."""

from pathlib import Path

from doppler.config import DopplerConfig, FlowProfile
from doppler.export import export_case


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "testvectors" / "canonical"
    cases = {
        "steady_pos_bin16": DopplerConfig(
            profile=FlowProfile.STEADY,
            velocity_m_s=16 * 0.01203125,
            snr_db=None,
            clutter_ratio=0.5,
            seed=11,
        ),
        "steady_neg_bin16": DopplerConfig(
            profile=FlowProfile.REVERSE,
            velocity_m_s=16 * 0.01203125,
            snr_db=None,
            clutter_ratio=0.5,
            seed=12,
        ),
    }
    for name, config in cases.items():
        summary = export_case(config, root / name)
        print(
            f"{name}: {summary.scored_frames} frames, "
            f"fixed/float mismatches={summary.fixed_float_bin_mismatches}"
        )


if __name__ == "__main__":
    main()
