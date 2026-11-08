#!/usr/bin/env python3
"""Run or reproduce the Phase 4 seeded cocotb system regression."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_START = 4100
DEFAULT_COUNT = 100


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--seed", type=int, help="reproduce one exact random seed")
    group.add_argument(
        "--count", type=int, default=DEFAULT_COUNT, help="number of consecutive seeds"
    )
    parser.add_argument("--start", type=int, default=DEFAULT_START)
    parser.add_argument("--waves", action="store_true", help="write an Icarus waveform")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seeds = (
        [args.seed] if args.seed is not None else list(range(args.start, args.start + args.count))
    )
    result_dir = ROOT / "results/coverage"
    result_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"seed_{seeds[0]}" if len(seeds) == 1 else f"seeds_{seeds[0]}_{seeds[-1]}"
    output_path = result_dir / (
        f"reproduction_{suffix}.json" if len(seeds) == 1 else "regression_summary.json"
    )
    coverage_path = (
        ROOT / "build/test-results/coverage/reproduction_coverage.json"
        if len(seeds) == 1
        else result_dir / "random_coverage.json"
    )
    environment = os.environ.copy()
    environment.update(
        {
            "DOPPLER_RANDOM_SEEDS": ",".join(str(seed) for seed in seeds),
            "DOPPLER_RANDOM_OUTPUT": str(output_path),
            "DOPPLER_RANDOM_COVERAGE": str(coverage_path),
            "DOPPLER_WAVES": "1" if args.waves else "0",
        }
    )
    command = [
        str(ROOT / ".venv/bin/pytest"),
        "-q",
        "tests/test_cocotb.py::test_random_system_regression_cocotb",
    ]
    completed = subprocess.run(command, cwd=ROOT, env=environment, check=False)
    failure_files = [
        ROOT / f"build/test-results/coverage/failure_seed_{seed}.json"
        for seed in seeds
        if (ROOT / f"build/test-results/coverage/failure_seed_{seed}.json").exists()
    ]
    failing = (
        []
        if completed.returncode == 0
        else [int(path.stem.rsplit("_", 1)[1]) for path in failure_files]
    )
    if completed.returncode and not failing:
        failing = seeds
    (result_dir / "failing_seeds.json").write_text(
        json.dumps(
            {
                "failing_seeds": failing,
                "reproduce": "scripts/run_seeded_regression.py --seed <seed> --waves",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    if completed.returncode:
        if not args.waves:
            for seed in failing:
                wave_environment = environment.copy()
                wave_environment["DOPPLER_RANDOM_SEEDS"] = str(seed)
                wave_environment["DOPPLER_WAVES"] = "1"
                subprocess.run(command, cwd=ROOT, env=wave_environment, check=False)
                candidates = [
                    ROOT / "build/cocotb_random_system/dump.fst",
                    ROOT / "tb/cocotb/dump.fst",
                ]
                for candidate in candidates:
                    if candidate.exists():
                        shutil.copy2(candidate, result_dir / f"failure_seed_{seed}.fst")
                        break
        raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
