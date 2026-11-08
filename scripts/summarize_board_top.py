#!/usr/bin/env python3
"""Archive compact implementation evidence for the offline board top."""

import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    report = json.loads((root / "build" / "board_top" / "report.json").read_text())
    clock = report["fmax"]["clk"]
    summary = {
        "evidence": "synthesis_and_place_route_only_not_hardware_validated",
        "top": "board_top",
        "target": "iCE40UP5K-SG48",
        "demo_path": "initialized sample memory -> Doppler core -> packet/CRC -> UART",
        "constraint_mhz": clock["constraint"],
        "achieved_fmax_mhz": clock["achieved"],
        "timing_pass": clock["achieved"] >= clock["constraint"],
        "utilization": report["utilization"],
        "risk": "97% logic-cell utilization leaves minimal M2 change margin",
    }
    destination = root / "results" / "up5k_board_top_summary.json"
    destination.write_text(json.dumps(summary, indent=2) + "\n")
    print(destination)


if __name__ == "__main__":
    main()
