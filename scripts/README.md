# Scripts

Repeatable commands for environment checks, vector generation, regression, synthesis, place-and-route, and report collection.

- `run_checks.sh`: lint, formatting, Python/cocotb tests, and standalone RTL simulations.
- `run_regression.py`: frozen 1,800-configuration algorithm matrix plus plots.
- `build_core_resource.sh`: protocol-complete reusable core fit and timing.
- `build_board_top.sh`: offline initialized-memory-to-UART top fit, timing, and unverified image.
- `archive_v1_baseline.py`: filters test, implementation, performance, and tool evidence into the versioned iCE40 baseline.
- `archive_phase1_verification.py`: records stream-contract tests, executed assertions, regressions, and resource deltas.
- `archive_phase2_verification.py`: aggregates AXI test XML and per-scenario metrics with regression and legacy-build evidence.
- `elaborate_axi_controlled_top.sh`: checks synthesizable elaboration of the Phase 3 top without XC7Z020 resource or timing claims.
- `archive_phase3_verification.py`: aggregates AXI-Lite tests and confirms legacy implementation remains unchanged.
- `run_seeded_regression.py`: runs 100 reproducible controlled-system seeds or reproduces one seed with optional waves.
- `archive_phase4_verification.py`: merges observed functional coverage and emits the pre-Vivado simulation release candidate.
- `summarize_implementation.py` / `summarize_board_top.py`: compact machine-readable evidence.
