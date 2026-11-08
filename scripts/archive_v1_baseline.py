#!/usr/bin/env python3
"""Create the compact, reproducible iCE40 v1 baseline evidence bundle."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
OUT = ROOT / "results" / "ice40"
DOCS = ROOT / "docs" / "baselines"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def command_version(*command: str) -> str:
    try:
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
    except FileNotFoundError:
        return "not installed"
    lines = (completed.stdout + completed.stderr).strip().splitlines()
    return lines[0] if lines else "unavailable"


def installed_without_version(command: str) -> str:
    return "installed; CLI does not report a version" if shutil.which(command) else "not installed"


def implementation_report(path: Path, *, top: str) -> dict:
    source = read_json(path)
    utilization = source["utilization"]
    clock = source["fmax"]["clk"]
    return {
        "evidence": "synthesis_and_place_route_only_not_hardware_validated",
        "target": "iCE40UP5K-SG48",
        "top": top,
        "logic_cells": utilization["ICESTORM_LC"],
        "embedded_ram_blocks": utilization["ICESTORM_RAM"],
        "dsp_blocks": utilization["ICESTORM_DSP"],
        "global_buffers": utilization["SB_GB"],
        "target_frequency_mhz": clock["constraint"],
        "estimated_fmax_mhz": clock["achieved"],
        "timing_pass": clock["achieved"] >= clock["constraint"],
    }


def top_cell_count(path: Path, top: str, cell_type: str) -> int:
    cells = read_json(path)["modules"][top].get("cells", {}).values()
    return sum(cell["type"] == cell_type for cell in cells)


def synthesized_cell_summary(path: Path, top: str) -> dict:
    cells = read_json(path)["modules"][top].get("cells", {}).values()
    types = [cell["type"] for cell in cells]
    return {
        "sb_lut4": types.count("SB_LUT4"),
        "sb_flip_flops": sum(cell_type.startswith("SB_DFF") for cell_type in types),
        "sb_carry": types.count("SB_CARRY"),
    }


def test_report() -> dict:
    root = ET.parse(BUILD / "test-results" / "pytest.xml").getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        raise RuntimeError("pytest JUnit XML contains no testsuite")
    cases = suite.findall(".//testcase")
    failed = sum(
        case.find("failure") is not None or case.find("error") is not None for case in cases
    )
    skipped = sum(case.find("skipped") is not None for case in cases)
    cocotb_cases = sum("test_cocotb" in case.attrib.get("classname", "") for case in cases)
    standalone = read_json(BUILD / "test-results" / "standalone_rtl.json")
    standalone_passed = sum(standalone.values())
    return {
        "pytest": {
            "total": len(cases),
            "passed": len(cases) - failed - skipped,
            "failed": failed,
            "skipped": skipped,
            "cocotb_runner_tests": cocotb_cases,
        },
        "standalone_systemverilog": {
            "total": len(standalone),
            "passed": standalone_passed,
            "failed": len(standalone) - standalone_passed,
            "cases": standalone,
        },
        "overall_automated_checks": {
            "total": len(cases) + len(standalone),
            "passed": len(cases) - failed - skipped + standalone_passed,
            "failed": failed + len(standalone) - standalone_passed,
        },
        "python_algorithm_configurations": 1800,
        "directed_signed_bin_cases": 10,
        "packet_crc_cases": 3,
        "recorded_random_seeds": {
            "algorithm_matrix": [1, 17, 101],
            "cocotb_core": [41],
            "model_unit_tests": [23, 99],
        },
    }


def main() -> None:
    required = [
        BUILD / "core_resource" / "report.json",
        BUILD / "core_resource" / "core.json",
        BUILD / "board_top" / "report.json",
        BUILD / "board_top" / "board.json",
        BUILD / "test-results" / "pytest.xml",
        BUILD / "test-results" / "standalone_rtl.json",
        ROOT / "results" / "regression" / "summary.json",
        OUT / "performance.json",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise SystemExit("missing baseline inputs: " + ", ".join(missing))

    core = implementation_report(required[0], top="doppler_resource_top")
    board = implementation_report(required[2], top="board_top")
    core["synthesized_cells"] = synthesized_cell_summary(required[1], "doppler_resource_top")
    board["synthesized_cells"] = synthesized_cell_summary(required[3], "board_top")
    logic_delta = board["logic_cells"]["used"] - core["logic_cells"]["used"]
    ebr_delta = board["embedded_ram_blocks"]["used"] - core["embedded_ram_blocks"]["used"]
    core_ram_cells = top_cell_count(required[1], "doppler_resource_top", "SB_RAM40_4K")
    board_ram_cells = top_cell_count(required[3], "board_top", "SB_RAM40_4K")
    board["resource_delta_vs_core"] = {
        "logic_cells_used": logic_delta,
        "embedded_ram_blocks_used": ebr_delta,
    }
    board["initialized_sample_memory_mapping"] = {
        "rtl_declaration": "initialized unpacked SystemVerilog memory arrays",
        "core_sb_ram40_4k_cells": core_ram_cells,
        "board_top_sb_ram40_4k_cells": board_ram_cells,
        "additional_ebr_vs_core": ebr_delta,
        "additional_logic_cells_vs_core": logic_delta,
        "sample_source_inferred_as_additional_ebr": False,
        "conclusion": (
            "The sample source adds no EBR cells and adds logic, so this build maps or "
            "optimizes the initialized sample source into logic rather than a distinct EBR."
        ),
        "scope": "post-synthesis/PnR netlist comparison; no physical-board validation",
    }

    tests = test_report()
    regression = read_json(ROOT / "results" / "regression" / "summary.json")
    tests["algorithm_regression"] = regression
    versions = {
        "python": platform.python_version(),
        "cocotb": importlib.metadata.version("cocotb"),
        "simulator": command_version("iverilog", "-V"),
        "yosys": command_version("yosys", "-V"),
        "nextpnr": command_version("nextpnr-ice40", "--version"),
        "icepack": installed_without_version("icepack"),
        "iceprog": installed_without_version("iceprog"),
        "operating_system": platform.platform(),
        "architecture": platform.machine(),
    }
    write_json(OUT / "core_report.json", core)
    write_json(OUT / "board_top_report.json", board)
    write_json(OUT / "test_summary.json", tests)
    write_json(OUT / "tool_versions.json", versions)

    performance = read_json(OUT / "performance.json")
    DOCS.mkdir(parents=True, exist_ok=True)
    DOCS.joinpath("v1_ice40.md").write_text(
        f"""# iCE40 v1 frozen baseline

This baseline is derived by `scripts/archive_v1_baseline.py`. It records simulation and implementation-tool evidence only; no UPduino hardware was available.

## Implementation

| Build | Logic cells | EBR | DSP | Target | Estimated Fmax | Timing |
|---|---:|---:|---:|---:|---:|---|
| Core | {core["logic_cells"]["used"]} / {core["logic_cells"]["available"]} | {core["embedded_ram_blocks"]["used"]} | {core["dsp_blocks"]["used"]} | {core["target_frequency_mhz"]:.2f} MHz | {core["estimated_fmax_mhz"]:.2f} MHz | {"Pass" if core["timing_pass"] else "Fail"} |
| Initialized-memory-to-UART top | {board["logic_cells"]["used"]} / {board["logic_cells"]["available"]} | {board["embedded_ram_blocks"]["used"]} | {board["dsp_blocks"]["used"]} | {board["target_frequency_mhz"]:.2f} MHz | {board["estimated_fmax_mhz"]:.2f} MHz | {"Pass" if board["timing_pass"] else "Fail"} |

The wrapper adds {logic_delta} logic cells but {ebr_delta} EBR blocks. The RTL sample source is declared as memory, but the synthesized board top contains the same {board_ram_cells} `SB_RAM40_4K` cells as the core. Therefore the initialized sample source is not a distinct EBR in this build and is mapped or optimized into logic. This conclusion is specific to the archived netlists.

## Performance

Measured with continuous valid input, an always-ready output, and no random gaps or stalls:

- First sample to result valid: {performance["single_frame_no_stall"]["first_sample_latency_cycles"][0]:,} cycles.
- End of frame to result valid: {performance["single_frame_no_stall"]["end_of_frame_latency_cycles"][0]:,} cycles.
- Adjacent result handshakes: {performance["sustained_result_interval_cycles"]:,} cycles.
- Derived at 12 MHz: {performance["derived_throughput"]["at_12_mhz_target"]["frames_per_second"]:.2f} frames/s and {performance["derived_throughput"]["at_12_mhz_target"]["samples_per_second"]:.2f} samples/s.
- Derived at board-top estimated Fmax: {performance["derived_throughput"]["at_15_89_mhz_board_top_estimated_fmax"]["frames_per_second"]:.2f} frames/s and {performance["derived_throughput"]["at_15_89_mhz_board_top_estimated_fmax"]["samples_per_second"]:.2f} samples/s.

Cycle counts are measured in RTL simulation; rates are derived. The estimated-Fmax rate is theoretical, not hardware-measured.

## Evidence files

See `results/ice40/core_report.json`, `board_top_report.json`, `test_summary.json`, `performance.json`, and `tool_versions.json`.
""",
        encoding="utf-8",
    )
    DOCS.joinpath("v1_errata.md").write_text(
        """# v1 numerical-model erratum

The frozen `v1.0-ice40` tag is unchanged. Its RTL Hann-window output is a signed 16-bit value, but the Python fixed-point oracle in `python/doppler/fixed.py` saturated that intermediate to 18 bits.

A test-first boundary case using alternating full-scale positive and negative samples exposed the mismatch: the old oracle produced -32993, outside the RTL range, instead of saturating to -32768. New tests also cover positive and negative full scale, overflow/underflow, positive and negative rounding boundaries, and exact half-way rounding. The v2 branch corrects only the oracle saturation width to 16 bits.

Canonical vectors did not trigger the issue because their Hann-windowed intermediate values stayed within the signed 16-bit range. Re-running the complete 1,800-configuration Python matrix produced unchanged published summary metrics: 100% high-SNR direction accuracy, 100% high-SNR fixed/float agreement within one bin, and zero reported saturation events. The fix therefore corrects the boundary contract without changing the reported ordinary-configuration results.
""",
        encoding="utf-8",
    )
    if tests["overall_automated_checks"]["failed"]:
        raise SystemExit("cannot archive a failing test baseline")


if __name__ == "__main__":
    main()
