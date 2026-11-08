# M1 requirements

| ID | Requirement | Verification |
|---|---|---|
| SIG-001 | Accept signed 16-bit complex Q1.15 I/Q at 20 kS/s in 256-sample frames. | Unit and integration tests |
| SIG-002 | Support deterministic steady, pulsatile, accelerated, reverse, and irregular synthetic profiles with saved seeds. | Python tests |
| SIG-003 | Use the frozen 5 MHz, 1540 m/s, zero-degree educational velocity conversion. | Python and mapper exhaustive tests |
| DSP-001 | Apply the complex first-order `63/64` wall filter with state continuous across legal frames. | Per-sample oracle comparison |
| DSP-002 | Apply the symmetric 256-point Hann window defined with denominator 255. | Coefficient and per-sample tests |
| DSP-003 | Compute a forward 256-point complex FFT with total scale `1/256`. | Per-bin oracle comparison |
| DSP-004 | Compute exact integer power `Re^2 + Im^2`. | Unit and integration tests |
| DSP-005 | Exclude signed bins `-1, 0, +1`; apply the frozen deterministic tie rule. | Directed peak tests |
| DSP-006 | Produce exact Q8 frequency `bin*20000` and Q8 mm/s velocity `bin*3080`. | Exhaustive signed-bin test |
| NUM-001 | Use nearest rounding with exact half cases away from zero at all specified shifts. | Arithmetic boundary tests |
| NUM-002 | Saturate at specified observable stage widths; never silently wrap. | Boundary and overflow tests |
| STR-001 | Transfer data only on valid/ready and keep stalled payloads stable. | Assertions and randomized stalls |
| STR-002 | Accept exactly 256 samples per legal frame with `last` on sample 255. | Frame-checker tests |
| STR-003 | Discard malformed or reset-aborted frames and emit no corresponding result. | Protocol directed tests |
| STR-004 | Emit exactly one stable result for each accepted legal frame. | Scoreboard and assertions |
| STA-001 | Report frame error, arithmetic overflow, and low confidence with deterministic clear behavior. | Status tests |
| VER-001 | Match the fixed-point oracle for all scored RTL fields with zero mismatches. | Cocotb scoreboard |
| VER-002 | Run at least 1,800 deterministic algorithm configurations and preserve failure artifacts. | Full regression summary |
| PERF-001 | Close timing at 12 MHz on iCE40UP5K-SG48. | nextpnr report |
| PERF-002 | Sustain at least 43 frames/s in the final offline design. | Cycle measurement |
| SYS-001 | Simulate BRAM playback through result packetization and 115200-8-N-1 UART. | Offline board-top test |
| REL-001 | Reproduce checks, reports, plots, and demo from documented commands without a board. | Release audit |
| SAFE-001 | Label the project educational/non-medical and distinguish simulation, synthesis, and hardware evidence. | Documentation review |
