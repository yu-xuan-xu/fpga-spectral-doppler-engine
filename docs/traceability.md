# Requirement-to-test traceability

## Completed evidence

| Requirement | Current/planned evidence |
|---|---|
| SIG-001, SIG-003 | `tests/test_models.py`, mapper exhaustive test |
| SIG-002 | `test_all_profiles_are_deterministic`, regression matrix |
| DSP-001, NUM-001, NUM-002 | Fixed intermediate export and wall-filter unit scoreboard |
| DSP-002 | Hann asset regeneration and window unit scoreboard |
| DSP-003 | Directed FFT RTL vectors and representative cocotb integration checks |
| DSP-004 | Power unit scoreboard and integration scoreboard |
| DSP-005 | Tie, guard-bin, and signed-boundary directed tests |
| DSP-006 | Exhaustive `-128..127` mapper test |
| STR-001..STR-004 | Public-interface immediate assertions plus ordered cocotb gaps, backpressure, reset, malformed-frame, recovery, loss/duplicate/order tests |
| AXIS-001..AXIS-004 | AXI packing, sequence, stalls, reset, malformed recovery, wrap, and direct-core equivalence in `results/axi_stream/summary.json` |
| STA-001 | Frame/status directed tests |
| VER-001 | Canonical and directed cocotb integration summaries |
| VER-002 | `results/regression/summary.json` and `full_matrix.csv` |
| PERF-001 | `build/board_top/report.json` and published summary |
| PERF-002 | Deterministic cocotb latency/throughput characterization in `results/ice40/performance.json` |
| SYS-001 | Packet/CRC cocotb test, UART RTL, board-top fit report |
| REL-001, SAFE-001 | Clean reproduction and release checklist |

This table is updated as tests are added. A requirement is complete only when its evidence is automated and passing.

Completed scope includes the 1,800-configuration Python evaluation, representative RTL/cocotb tests, randomized input gaps and output stalls, early/missing `last`, reset interruption, ten directed signed-bin cases, packet/CRC byte comparison, and iCE40 synthesis/place-and-route.

## Planned evidence — not completed

- Running all 1,800 algorithm configurations through RTL.
- Concurrent SVA/bind execution on a simulator that supports it, and functional coverage. Icarus-compatible immediate assertions are complete.
- Random FFT full-spectrum, every-bin RTL scoreboard comparisons.
- UART bit-level verification and complete board-top serial simulation.
- Vivado implementation and Zynq hardware deployment.
