#!/usr/bin/env python3
"""Export a case directory from a JSON Doppler configuration."""

from __future__ import annotations

import argparse

from doppler.config import DopplerConfig
from doppler.export import export_case


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="input DopplerConfig JSON")
    parser.add_argument("output", help="destination case directory")
    args = parser.parse_args()
    summary = export_case(DopplerConfig.from_json(args.config), args.output)
    print(
        f"exported {summary.scored_frames} scored frames; "
        f"fixed/float bin mismatches={summary.fixed_float_bin_mismatches}"
    )


if __name__ == "__main__":
    main()
