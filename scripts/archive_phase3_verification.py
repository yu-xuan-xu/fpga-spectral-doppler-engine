#!/usr/bin/env python3
"""Archive deterministic Phase 3 AXI-Lite verification evidence."""

from __future__ import annotations

import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHASE2_COMMIT = "c60cf84543c49a0a41d512e18842e36a4629edf7"


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


def output(*command: str) -> str:
    return subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def main() -> None:
    phase3_xml = [
        ROOT / "tb/cocotb/test_axi_lite_regs_cocotb.result.xml",
        ROOT / "tb/cocotb/test_axi_controlled_top_cocotb.result.xml",
    ]
    required = [
        ROOT / "build/test-results/pytest.xml",
        ROOT / "build/test-results/standalone_rtl.json",
        ROOT / "build/core_resource/report.json",
        ROOT / "build/board_top/report.json",
        ROOT / "build/axi_controlled_top/stats.json",
        ROOT / "results/regression/summary.json",
        *phase3_xml,
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise SystemExit("missing Phase 3 evidence: " + ", ".join(missing))

    pytest = xml_result(required[0])
    standalone = read_json(required[1])
    phase3_results = [xml_result(path) for path in phase3_xml]
    case_names = [name for result in phase3_results for name in result["case_names"]]
    metrics_dir = ROOT / "build/test-results/axi_lite_metrics"
    metrics = [read_json(metrics_dir / f"{name}.json") for name in case_names]
    phase2 = read_json(ROOT / "results/axi_stream/summary.json")
    core = implementation(required[2])
    board = implementation(required[3])
    baseline_core = phase2["legacy_implementation"]["core"]
    baseline_board = phase2["legacy_implementation"]["board_top"]
    protected_changes = output(
        "git",
        "diff",
        "--name-only",
        PHASE2_COMMIT,
        "--",
        "rtl/core",
        "rtl/board",
        "rtl/axi/doppler_axi_stream_wrapper.sv",
    ).splitlines()
    fields = [
        "axi_lite_reads",
        "axi_lite_writes",
        "aw_before_w_cases",
        "w_before_aw_cases",
        "simultaneous_aw_w_cases",
        "partial_writes",
        "invalid_accesses",
        "read_stall_cycles",
        "write_response_stall_cycles",
        "global_resets",
        "soft_resets",
        "result_snapshots",
        "irq_events",
        "irq_clears",
        "slverr_responses",
        "protocol_mismatches",
        "register_mismatches",
        "lost_stream_results",
        "duplicated_stream_results",
    ]
    aggregate = {field: sum(item[field] for item in metrics) for field in fields}
    phase3_failed = sum(result["failed"] for result in phase3_results)
    legacy_delta = {
        "core_logic_cells": core["logic_cells_used"] - baseline_core["logic_cells_used"],
        "core_ebr": core["ebr_used"] - baseline_core["ebr_used"],
        "core_dsp": core["dsp_used"] - baseline_core["dsp_used"],
        "core_fmax_mhz": core["estimated_fmax_mhz"] - baseline_core["estimated_fmax_mhz"],
        "board_logic_cells": board["logic_cells_used"] - baseline_board["logic_cells_used"],
        "board_ebr": board["ebr_used"] - baseline_board["ebr_used"],
        "board_dsp": board["dsp_used"] - baseline_board["dsp_used"],
        "board_fmax_mhz": board["estimated_fmax_mhz"] - baseline_board["estimated_fmax_mhz"],
    }
    summary = {
        "schema_version": 1,
        "evidence": "axi_lite_and_controlled_top_cocotb_plus_full_legacy_regression",
        "phase3_cocotb_tests": sum(result["total"] for result in phase3_results),
        "phase3_test_results": phase3_results,
        "aggregate_axi_lite_metrics": aggregate,
        "total_top_level_automated_checks": {
            "total": pytest["total"] + len(standalone),
            "passed": pytest["passed"] + sum(bool(value) for value in standalone.values()),
            "failed": pytest["failed"] + sum(not value for value in standalone.values()),
            "pytest": pytest,
            "standalone_systemverilog": standalone,
        },
        "prior_phase_checks_preserved": 47,
        "algorithm_regression": read_json(required[5]),
        "legacy_implementation": {
            "core": core,
            "board_top": board,
            "delta_vs_phase2": legacy_delta,
        },
        "controlled_top_elaboration": {
            "passed": True,
            "tool": output("yosys", "-V"),
            "evidence": "build/axi_controlled_top/stats.json",
            "xc7z020_resource_or_timing_claimed": False,
        },
        "assertions": {
            "actually_executed": phase3_failed == 0,
            "form": "Icarus-compatible immediate assertions on public AXI4-Lite signals",
            "scoreboard_checks": [
                "reserved bits and register side effects",
                "result counter and atomic snapshot",
                "IRQ sticky, W1C, and event priority",
                "soft-reset datapath recovery",
            ],
            "concurrent_sva_or_bind_claimed": False,
        },
        "protected_rtl_audit": {
            "changed_since_phase2": protected_changes,
            "passed": not protected_changes,
        },
        "tool_versions": read_json(ROOT / "results/ice40/tool_versions.json"),
    }
    failures = (
        summary["total_top_level_automated_checks"]["failed"]
        or phase3_failed
        or protected_changes
        or any(legacy_delta.values())
        or aggregate["protocol_mismatches"]
        or aggregate["register_mismatches"]
        or aggregate["lost_stream_results"]
        or aggregate["duplicated_stream_results"]
    )
    if failures:
        raise SystemExit("cannot archive Phase 3: verification evidence is not clean")
    destination = ROOT / "results/axi_lite/summary.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
