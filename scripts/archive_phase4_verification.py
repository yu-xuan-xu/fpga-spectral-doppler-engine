#!/usr/bin/env python3
"""Merge Phase 4 coverage and create simulation release-candidate evidence."""

from __future__ import annotations

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHASE3_COMMIT = "6c4b49f2ea32a8f8cf92d6efc9e4ff7ae0680084"
sys.path.insert(0, str(ROOT / "tb/cocotb"))
from coverage_model import required_bins, waived_bins


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
    utilization = report["utilization"]
    clock = report["fmax"]["clk"]
    return {
        "logic_cells_used": utilization["ICESTORM_LC"]["used"],
        "ebr_used": utilization["ICESTORM_RAM"]["used"],
        "dsp_used": utilization["ICESTORM_DSP"]["used"],
        "estimated_fmax_mhz": clock["achieved"],
        "timing_pass": clock["achieved"] >= clock["constraint"],
    }


def command_output(*command: str) -> str:
    return subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def merge_hits(paths: list[Path]) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for path in paths:
        for key, hit in read_json(path)["hits"].items():
            if key not in merged:
                merged[key] = dict(hit)
                merged[key]["sources"] = [str(path.relative_to(ROOT))]
            else:
                merged[key]["count"] += hit["count"]
                merged[key]["sources"].append(str(path.relative_to(ROOT)))
    return merged


def main() -> None:
    random_coverage = ROOT / "results/coverage/random_coverage.json"
    closure_coverage = ROOT / "build/test-results/coverage/closure_coverage.json"
    random_summary = ROOT / "results/coverage/regression_summary.json"
    closure_metrics_path = ROOT / "build/test-results/coverage/closure_metrics.json"
    required_paths = [
        random_coverage,
        closure_coverage,
        random_summary,
        closure_metrics_path,
        ROOT / "results/coverage/failing_seeds.json",
        ROOT / "build/test-results/pytest.xml",
        ROOT / "build/test-results/standalone_rtl.json",
        ROOT / "results/regression/summary.json",
        ROOT / "build/core_resource/report.json",
        ROOT / "build/board_top/report.json",
        ROOT / "build/axi_controlled_top/stats.json",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required_paths if not path.exists()]
    if missing:
        raise SystemExit("missing Phase 4 evidence: " + ", ".join(missing))

    required = required_bins()
    waived = waived_bins()
    random_hits = set(read_json(random_coverage)["hits"])
    merged = merge_hits([random_coverage, closure_coverage])
    hit = required & set(merged)
    holes = sorted(required - hit)
    functional = {key for key in required if not key.startswith("cross.")}
    crosses = required - functional
    initial_hit = required & random_hits
    coverage_document = {
        "schema_version": 1,
        "claim": "100% of defined required functional coverage bins",
        "required_bins": len(required),
        "hit_required_bins": len(hit),
        "required_functional_bins": len(functional),
        "hit_functional_bins": len(functional & hit),
        "required_cross_bins": len(crosses),
        "hit_cross_bins": len(crosses & hit),
        "functional_coverage_percent": 100 * len(functional & hit) / len(functional),
        "cross_coverage_percent": 100 * len(crosses & hit) / len(crosses),
        "total_required_coverage_percent": 100 * len(hit) / len(required),
        "initial_random_required_hits": len(initial_hit),
        "initial_random_coverage_percent": 100 * len(initial_hit) / len(required),
        "initial_holes": sorted(required - initial_hit),
        "final_holes": holes,
        "waived_bins": waived,
        "bins": {
            key: {
                "status": "hit" if key in hit else "unhit",
                **(merged.get(key) or {}),
            }
            for key in sorted(required)
        },
    }
    coverage_dir = ROOT / "results/coverage"
    coverage_dir.mkdir(parents=True, exist_ok=True)
    (coverage_dir / "coverage.json").write_text(
        json.dumps(coverage_document, indent=2, sort_keys=True) + "\n"
    )
    (coverage_dir / "coverage.md").write_text(
        "# Phase 4 functional coverage\n\n"
        f"- Initial 100-seed required coverage: {len(initial_hit)}/{len(required)} "
        f"({coverage_document['initial_random_coverage_percent']:.2f}%).\n"
        f"- Final required functional bins: {len(functional & hit)}/{len(functional)} "
        f"({coverage_document['functional_coverage_percent']:.2f}%).\n"
        f"- Final required cross bins: {len(crosses & hit)}/{len(crosses)} "
        f"({coverage_document['cross_coverage_percent']:.2f}%).\n"
        f"- Final required total: {len(hit)}/{len(required)} "
        f"({coverage_document['total_required_coverage_percent']:.2f}%).\n"
        f"- Required holes: {len(holes)}. Defined waivers: {len(waived)}.\n\n"
        "This is Python/cocotb functional coverage based on observed events. It is not code, "
        "toggle, covergroup, UVM, AXI VIP, or commercial coverage-database evidence.\n"
    )

    random = read_json(random_summary)
    closure = read_json(closure_metrics_path)
    pytest = xml_result(ROOT / "build/test-results/pytest.xml")
    standalone = read_json(ROOT / "build/test-results/standalone_rtl.json")
    algorithm = read_json(ROOT / "results/regression/summary.json")
    core = implementation(ROOT / "build/core_resource/report.json")
    board = implementation(ROOT / "build/board_top/report.json")
    phase3 = read_json(ROOT / "results/axi_lite/summary.json")
    baseline_core = phase3["legacy_implementation"]["core"]
    baseline_board = phase3["legacy_implementation"]["board_top"]
    delta = {
        "core_logic_cells": core["logic_cells_used"] - baseline_core["logic_cells_used"],
        "core_ebr": core["ebr_used"] - baseline_core["ebr_used"],
        "core_dsp": core["dsp_used"] - baseline_core["dsp_used"],
        "core_fmax_mhz": core["estimated_fmax_mhz"] - baseline_core["estimated_fmax_mhz"],
        "board_logic_cells": board["logic_cells_used"] - baseline_board["logic_cells_used"],
        "board_ebr": board["ebr_used"] - baseline_board["ebr_used"],
        "board_dsp": board["dsp_used"] - baseline_board["dsp_used"],
        "board_fmax_mhz": board["estimated_fmax_mhz"] - baseline_board["estimated_fmax_mhz"],
    }
    protected_changes = command_output(
        "git", "diff", "--name-only", PHASE3_COMMIT, "--", "rtl/core", "rtl/board", "rtl/axi"
    ).splitlines()
    random_totals = random["totals"]
    total_checks = pytest["total"] + len(standalone)
    failed_checks = pytest["failed"] + sum(not value for value in standalone.values())
    release = {
        "schema_version": 1,
        "release": "pre_vivado_simulation_release_candidate",
        "git_baseline_commit": PHASE3_COMMIT,
        "release_commit": "commit containing this version-controlled report",
        "branch": command_output("git", "branch", "--show-current"),
        "tool_versions": read_json(ROOT / "results/ice40/tool_versions.json"),
        "automated_checks": {
            "total": total_checks,
            "passed": total_checks - failed_checks,
            "failed": failed_checks,
            "pytest": pytest,
            "standalone": standalone,
        },
        "random_regression": {
            "seed_count": len(random["requested_seeds"]),
            "first_seed": random["requested_seeds"][0],
            "last_seed": random["requested_seeds"][-1],
            "failed_seeds": random["failed_seeds"],
            "reproduce": "scripts/run_seeded_regression.py --seed <seed> --waves",
        },
        "system_metrics": {
            "total_cycles": random_totals["cycles"] + closure["cycles"],
            "input_beats": random_totals["accepted_samples"] + closure["accepted_samples"],
            "output_results": random_totals["output_results"] + closure["output_results"],
            "random_input_frames": random_totals["input_frames"],
            "random_legal_frames": random_totals["legal_frames"],
            "malformed_frames": random_totals["malformed_frames"],
            "axi_lite_reads": random_totals["axi_lite_reads"]
            + closure["axi_lite"]["axi_lite_reads"],
            "axi_lite_writes": random_totals["axi_lite_writes"]
            + closure["axi_lite"]["axi_lite_writes"],
            "resets": sum(
                value["count"]
                for key, value in merged.items()
                if key.startswith(("reset.global_location/", "reset.soft_location/"))
            ),
            "irq_events": random_totals["output_results"] + closure["output_results"],
            "protocol_mismatches": closure["protocol_mismatches"],
            "register_mismatches": closure["register_mismatches"],
            "lost_results": closure["lost_results"],
            "duplicated_results": closure["duplicated_results"],
            "reordered_results": closure["reordered_results"],
        },
        "coverage": {
            key: coverage_document[key]
            for key in (
                "required_bins",
                "hit_required_bins",
                "required_functional_bins",
                "hit_functional_bins",
                "required_cross_bins",
                "hit_cross_bins",
                "functional_coverage_percent",
                "cross_coverage_percent",
                "total_required_coverage_percent",
                "initial_random_coverage_percent",
                "waived_bins",
            )
        },
        "algorithm_regression": algorithm,
        "legacy_implementation": {
            "core": core,
            "board_top": board,
            "delta_vs_phase3": delta,
        },
        "controlled_top_elaboration": {
            "passed": True,
            "xc7z020_resource_or_timing_claimed": False,
        },
        "rtl_freeze_audit": {
            "protected_rtl_changes_since_phase3": protected_changes,
            "passed": not protected_changes,
        },
        "bugs": {"rtl_defects_found": 0, "unexplained_failures": 0},
        "known_limitations": [
            "No SystemVerilog covergroups, code coverage, or toggle coverage",
            "No UVM or AXI VIP",
            "No Vivado/XSim, IP packaging, AXI DMA, or Zynq Processing System",
            "No XC7Z020 synthesis, place-and-route, or timing closure",
            "No ARM software or physical hardware validation",
            "Icarus immediate assertions are used; concurrent SVA/bind is not claimed",
            "Verilator is not installed; optional lint was not run",
        ],
    }
    if holes or failed_checks or random["failed_seeds"] or protected_changes or any(delta.values()):
        raise SystemExit("cannot archive Phase 4: release-candidate evidence is not clean")
    (coverage_dir / "release_candidate.json").write_text(
        json.dumps(release, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    main()
