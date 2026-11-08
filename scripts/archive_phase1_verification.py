#!/usr/bin/env python3
"""Archive deterministic Phase 1 stream-contract verification evidence."""

from __future__ import annotations

import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHASE0_COMMIT = "539752b1f05e82eeef9f6dee8467a8a997f9222e"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def xml_result(path: Path) -> dict:
    root = ET.parse(path).getroot()
    cases = root.findall(".//testcase")
    failed = sum(
        case.find("failure") is not None or case.find("error") is not None for case in cases
    )
    skipped = sum(case.find("skipped") is not None for case in cases)
    return {
        "total": len(cases),
        "passed": len(cases) - failed - skipped,
        "failed": failed,
        "skipped": skipped,
        "case_names": [case.attrib["name"] for case in cases],
    }


def implementation(path: Path) -> dict:
    report = read_json(path)
    clock = report["fmax"]["clk"]
    utilization = report["utilization"]
    return {
        "logic_cells_used": utilization["ICESTORM_LC"]["used"],
        "ebr_used": utilization["ICESTORM_RAM"]["used"],
        "dsp_used": utilization["ICESTORM_DSP"]["used"],
        "target_frequency_mhz": clock["constraint"],
        "estimated_fmax_mhz": clock["achieved"],
        "timing_pass": clock["achieved"] >= clock["constraint"],
    }


def main() -> None:
    pytest_xml = ROOT / "build" / "test-results" / "pytest.xml"
    standalone_path = ROOT / "build" / "test-results" / "standalone_rtl.json"
    contract_xml = ROOT / "tb" / "cocotb" / "test_stream_contract_cocotb.result.xml"
    core_report = ROOT / "build" / "core_resource" / "report.json"
    board_report = ROOT / "build" / "board_top" / "report.json"
    regression_path = ROOT / "results" / "regression" / "summary.json"
    required = [
        pytest_xml,
        standalone_path,
        contract_xml,
        core_report,
        board_report,
        regression_path,
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise SystemExit("missing Phase 1 inputs: " + ", ".join(missing))

    pytest = xml_result(pytest_xml)
    contract = xml_result(contract_xml)
    standalone = read_json(standalone_path)
    core = implementation(core_report)
    board = implementation(board_report)
    baseline_core = read_json(ROOT / "results" / "ice40" / "core_report.json")
    baseline_board = read_json(ROOT / "results" / "ice40" / "board_top_report.json")
    changed_algorithm_files = subprocess.run(
        ["git", "diff", "--name-only", PHASE0_COMMIT, "--", "rtl/core"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.splitlines()
    canonical_cores = sorted(
        str(path.relative_to(ROOT)) for path in (ROOT / "rtl" / "core").glob("*doppler*core*.sv")
    )

    summary = {
        "schema_version": 1,
        "evidence": "rtl_simulation_python_regression_and_ice40_implementation",
        "legacy_phase0_automated_checks": 43,
        "current_top_level_automated_checks": {
            "total": pytest["total"] + len(standalone),
            "passed": pytest["passed"] + sum(bool(value) for value in standalone.values()),
            "failed": pytest["failed"] + sum(not value for value in standalone.values()),
            "pytest": pytest,
            "standalone_systemverilog": standalone,
        },
        "stream_contract_cocotb": contract,
        "assertions": {
            "file": "rtl/assertions/doppler_stream_sva.sv",
            "actually_executed": contract["failed"] == 0,
            "form": "Icarus-compatible immediate assertions on public interface",
            "checks": [
                "input payload stable while stalled",
                "result valid and payload stable while stalled",
                "result valid clear after reset",
                "accepted result count does not exceed accepted legal frame count",
            ],
            "tool_limit": (
                "Icarus Verilog 13.0 rejects property/assert property and bind syntax; "
                "concurrent SVA was not claimed."
            ),
        },
        "algorithm_regression": read_json(regression_path),
        "implementation": {
            "core": core,
            "board_top": board,
            "delta_vs_phase0": {
                "core_logic_cells": core["logic_cells_used"] - baseline_core["logic_cells"]["used"],
                "core_ebr": core["ebr_used"] - baseline_core["embedded_ram_blocks"]["used"],
                "core_dsp": core["dsp_used"] - baseline_core["dsp_blocks"]["used"],
                "core_fmax_mhz": core["estimated_fmax_mhz"] - baseline_core["estimated_fmax_mhz"],
                "board_logic_cells": board["logic_cells_used"]
                - baseline_board["logic_cells"]["used"],
                "board_ebr": board["ebr_used"] - baseline_board["embedded_ram_blocks"]["used"],
                "board_dsp": board["dsp_used"] - baseline_board["dsp_blocks"]["used"],
                "board_fmax_mhz": board["estimated_fmax_mhz"]
                - baseline_board["estimated_fmax_mhz"],
            },
        },
        "canonical_core_audit": {
            "canonical_core_files": canonical_cores,
            "algorithm_rtl_changed_since_phase0": changed_algorithm_files,
            "duplicate_algorithm_core_found": len(canonical_cores) != 1,
        },
    }
    if summary["current_top_level_automated_checks"]["failed"] or contract["failed"]:
        raise SystemExit("cannot archive failing Phase 1 verification")
    destination = ROOT / "results" / "stream_contract" / "summary.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
