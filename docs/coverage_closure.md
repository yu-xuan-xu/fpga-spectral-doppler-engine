# Phase 4 coverage closure

## Initial 100-seed result

Seeds 4100–4199 completed with zero failures. The first measured report hit 194 of 263
required bins (73.76%). The 69 holes clustered in intentionally rare conditions:

- exact global/soft reset locations and their post-reset checks;
- one-cycle stalls and pending-output context;
- invalid AXI-Lite accesses and selected ordering × response-stall crosses;
- IRQ pending/reset and simultaneous clear/result races;
- zero/near-zero, special-signal, and low-SNR peak-range conditions.

## Closure actions

`test_coverage_closure.py` added observed-event scenarios for all ten global-reset locations,
all six soft-reset locations, reset recovery, a reset-terminated one-cycle input stall, an
exact one-cycle output stall, next-frame activity during a pending result, disable/reset near
output backpressure, invalid addresses, representative AW/W × B-stall crosses, IRQ late
enable/multiple events/clear race/reset, five near-zero SNR conditions, missing low-SNR
peak-range conditions, and all six special signals.

The tests verify real register reads, stream transfers, result payloads and IRQ state before
crediting the corresponding bins.

## Final result

- Required functional bins: 149/149 (100%).
- Required cross bins: 114/114 (100%).
- Total required bins: 263/263 (100%).
- Unexplained required holes: 0.
- Defined waived bins: 4, with rationale in `coverage_model.md`.

No bins were removed between the initial and final report. The closure process changed test
stimulus and observation logic only; frozen design RTL was not modified.
