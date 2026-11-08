#!/usr/bin/env python3
"""Archive deterministic Phase 2 AXI-stream verification evidence."""

from __future__ import annotations

import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHASE1_COMMIT = "3270079869fe114a46a1738df464307a864e4d4d"


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
        "simulated_runtime_ns": sum(float(case.attrib.get("sim_time_ns", 0)) for case in cases),
    }


def implementation(path: Path) -> dict:
    report = read_json(path)
    utilization = report["utilization"]
    clock = report["fmax"]["clk"]
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
    axi_xml_paths = [
        ROOT / "tb" / "cocotb" / "test_axi_stream_cocotb.result.xml",
        ROOT / "tb" / "cocotb" / "test_axi_sequence_wrap_cocotb.result.xml",
        ROOT / "tb" / "cocotb" / "test_axi_legacy_equivalence_cocotb.result.xml",
    ]
    core_report_path = ROOT / "build" / "core_resource" / "report.json"
    board_report_path = ROOT / "build" / "board_top" / "report.json"
    regression_path = ROOT / "results" / "regression" / "summary.json"
    required = [
        pytest_xml,
        standalone_path,
        core_report_path,
        board_report_path,
        regression_path,
        *axi_xml_paths,
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise SystemExit("missing Phase 2 inputs: " + ", ".join(missing))

    pytest = xml_result(pytest_xml)
    standalone = read_json(standalone_path)
    axi_results = [xml_result(path) for path in axi_xml_paths]
    case_names = [name for result in axi_results for name in result["case_names"]]
    metrics_directory = ROOT / "build" / "test-results" / "axi_metrics"
    metrics = [read_json(metrics_directory / f"{name}.json") for name in case_names]
    expected_outputs = sum(item["expected_output_beats"] for item in metrics)
    observed_outputs = sum(item["axi_output_beats"] for item in metrics)
    phase1 = read_json(ROOT / "results" / "stream_contract" / "summary.json")
    core = implementation(core_report_path)
    board = implementation(board_report_path)
    baseline_core = phase1["implementation"]["core"]
    baseline_board = phase1["implementation"]["board_top"]
    axi_failed = sum(result["failed"] for result in axi_results)
    random_seeds = sorted({seed for item in metrics for seed in item["random_seeds"]})
    changed_legacy_rtl = subprocess.run(
        ["git", "diff", "--name-only", PHASE1_COMMIT, "--", "rtl/core", "rtl/board"],
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
        "evidence": "cocotb_axi_simulation_python_regression_and_legacy_ice40_builds",
        "new_axi_cocotb_tests": sum(result["total"] for result in axi_results),
        "total_top_level_automated_checks": {
            "total": pytest["total"] + len(standalone),
            "passed": pytest["passed"] + sum(bool(value) for value in standalone.values()),
            "failed": pytest["failed"] + sum(not value for value in standalone.values()),
            "pytest": pytest,
            "standalone_systemverilog": standalone,
        },
        "axi_test_results": axi_results,
        "aggregate_axi_metrics": {
            "frames_transferred": sum(item["frames_transferred"] for item in metrics),
            "axi_input_beats": sum(item["axi_input_beats"] for item in metrics),
            "axi_output_beats": observed_outputs,
            "expected_output_beats": expected_outputs,
            "input_stall_cycles": sum(item["input_stall_cycles"] for item in metrics),
            "output_stall_cycles": sum(item["output_stall_cycles"] for item in metrics),
            "reset_injections": sum(item["reset_injections"] for item in metrics),
            "malformed_frames": sum(item["malformed_frames"] for item in metrics),
            "random_seeds": random_seeds,
            "packing_field_checks": sum(item["packing_checks"] for item in metrics),
            "sequence_checks": sum(item["sequence_checks"] for item in metrics),
            "legacy_core_equivalence_checks": sum(item["legacy_checks"] for item in metrics),
            "lost_results": max(expected_outputs - observed_outputs, 0),
            "duplicated_results": max(observed_outputs - expected_outputs, 0),
            "reordered_results": 0 if axi_failed == 0 else "test failure; inspect XML",
            "packing_mismatches": 0 if axi_failed == 0 else "test failure; inspect XML",
            "sequence_mismatches": 0 if axi_failed == 0 else "test failure; inspect XML",
            "legacy_core_mismatches": 0 if axi_failed == 0 else "test failure; inspect XML",
            "simulated_runtime_ns": sum(result["simulated_runtime_ns"] for result in axi_results),
        },
        "algorithm_regression": read_json(regression_path),
        "legacy_implementation": {
            "core": core,
            "board_top": board,
            "delta_vs_phase1": {
                "core_logic_cells": core["logic_cells_used"] - baseline_core["logic_cells_used"],
                "core_ebr": core["ebr_used"] - baseline_core["ebr_used"],
                "core_dsp": core["dsp_used"] - baseline_core["dsp_used"],
                "core_fmax_mhz": core["estimated_fmax_mhz"] - baseline_core["estimated_fmax_mhz"],
                "board_logic_cells": board["logic_cells_used"] - baseline_board["logic_cells_used"],
                "board_ebr": board["ebr_used"] - baseline_board["ebr_used"],
                "board_dsp": board["dsp_used"] - baseline_board["dsp_used"],
                "board_fmax_mhz": board["estimated_fmax_mhz"]
                - baseline_board["estimated_fmax_mhz"],
            },
        },
        "assertions": {
            "actually_executed": axi_failed == 0,
            "form": "Icarus-compatible immediate assertions on public AXI signals",
            "concurrent_sva_or_bind_claimed": False,
        },
        "canonical_core_audit": {
            "canonical_core_files": canonical_cores,
            "legacy_rtl_changed_since_phase1": changed_legacy_rtl,
            "duplicate_algorithm_core_found": len(canonical_cores) != 1,
        },
        "tool_versions": read_json(ROOT / "results" / "ice40" / "tool_versions.json"),
    }
    if summary["total_top_level_automated_checks"]["failed"] or axi_failed:
        raise SystemExit("cannot archive failing Phase 2 verification")
    destination = ROOT / "results" / "axi_stream" / "summary.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
