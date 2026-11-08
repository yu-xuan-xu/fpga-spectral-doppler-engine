#!/usr/bin/env python3
"""Create a compact, versioned implementation summary from nextpnr JSON."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def version(command: list[str]) -> str:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    lines = (completed.stdout + completed.stderr).strip().splitlines()
    return lines[0] if lines else "installed (version flag unavailable)"


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    report_path = root / "build" / "core_resource" / "report.json"
    report = json.loads(report_path.read_text())
    clock = report["fmax"]["clk"]
    summary = {
        "evidence": "synthesis_and_place_route_only_not_hardware_validated",
        "target": "iCE40UP5K-SG48",
        "constraint_mhz": clock["constraint"],
        "achieved_fmax_mhz": clock["achieved"],
        "timing_pass": clock["achieved"] >= clock["constraint"],
        "latency_limit_cycles": 120000,
        "utilization": report["utilization"],
        "tools": {
            "yosys": version(["yosys", "--version"]),
            "nextpnr": version(["nextpnr-ice40", "--version"]),
            "iverilog": version(["iverilog", "-V"]),
            "icepack": version(["icepack", "-V"]),
        },
    }
    destination = root / "results" / "up5k_core_summary.json"
    destination.write_text(json.dumps(summary, indent=2) + "\n")
    print(destination)


if __name__ == "__main__":
    main()
