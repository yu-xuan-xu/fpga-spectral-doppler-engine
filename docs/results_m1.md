# M1 measured results

All values below are hardware-independent evidence. No physical UPduino was available, so none of these results claim on-board operation.

## Algorithm regression

The frozen matrix contains 1,800 deterministic configurations: five profiles, ten signed velocity settings, four SNR settings, three clutter ratios, and three seeds. Raw rows are in `results/regression/full_matrix.csv`.

| Metric | Result |
|---|---:|
| Configurations | 1,800 |
| Fixed/float within one bin at SNR >= 20 dB | 100% |
| Direction accuracy at SNR >= 20 dB | 100% |
| Scored-frame mean absolute velocity error | 0.392 mm/s |
| Explicit low-confidence labels | 944 |
| Explicit transition labels | 360 |
| Alias labels | 0 |
| Maximum arithmetic saturation count | 0 |

Low-confidence and transition rows remain in the CSV; the `scored` column identifies the release-metric subset.

## RTL verification

- The frozen v1 checkpoint had 30 Python/cocotb tests; Phase 0 adds numerical boundary and deterministic performance tests for 40 passing pytest cases, plus three standalone SystemVerilog tests.
- Cocotb: randomized input gaps and output stalls, early/missing `last`, reset-aborted partial frame, output stability under stall, and ten directed signed bins all passed.
- SystemVerilog: standalone FFT, end-to-end core, and exhaustive mapper tests passed.
- Ordered cocotb comparisons cover peak bin, frequency, velocity, peak power, and status.
- Measured processing latency with randomized output stalls: 15,622 cycles (1.302 ms at 12 MHz), within the 120,000-cycle requirement.
- Deterministic no-stall measurement: 15,877 cycles from first accepted sample to result valid, 15,622 cycles from accepted end-of-frame to result valid, and 15,575 cycles between continuous result handshakes. The structured report derives 770.47 frames/s at 12 MHz.

These are representative RTL checks, not a 1,800-configuration RTL regression. At the M1 checkpoint, SystemVerilog Assertions were not implemented; Phase 1 subsequently added Icarus-compatible public-interface immediate assertions. Concurrent SVA/bind, functional coverage, random full-spectrum every-bin FFT checking, UART bit-level verification, and complete board-top serial simulation remain unimplemented.

## UP5K implementation

The protocol-complete core was synthesized and placed for `iCE40UP5K-SG48` using the internal oscillator wrapper. The generated image remains unverified on hardware.

| Resource/timing | Result |
|---|---:|
| Logic cells | 4,068 / 5,280 (77%) |
| Embedded RAM blocks | 4 / 30 (13%) |
| DSP blocks | 8 / 8 (100%) |
| Global buffers | 7 / 8 (87%) |
| Timing constraint | 12.0 MHz |
| Achieved Fmax | 17.07 MHz |
| Timing result | Pass |

Machine-readable implementation and regression summaries are in `results/up5k_core_summary.json` and `results/regression/summary.json`.

## Offline board-top demonstration

The synthesizable demonstration path reads a canonical frame from initialized memory, runs the complete core, builds a versioned 20-byte result packet with CRC-16/CCITT-FALSE, and transmits it at 115200-8-N-1. RTL packet bytes match the Python host decoder in cocotb.

The complete top fits and closes 12 MHz at 5,131 / 5,280 logic cells (97%), 4 / 30 embedded RAM blocks, and 8 / 8 DSP blocks; achieved Fmax is 15.89 MHz. This narrow logic margin is an explicit M2 risk. The image is generated but unverified on hardware and has no frozen physical pin mapping until the actual board revision is confirmed.

The initialized sample source is declared as RTL memory, but the board top adds zero EBR and 1,063 logic cells relative to the core build. Netlist comparison therefore shows no distinct sample-source EBR in this implementation; the path is accurately described as initialized-memory-to-UART.

Vivado implementation and Zynq hardware deployment have not been run and are not claimed.
