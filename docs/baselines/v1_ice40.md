# iCE40 v1 frozen baseline

This baseline is derived by `scripts/archive_v1_baseline.py`. It records simulation and implementation-tool evidence only; no UPduino hardware was available.

## Implementation

| Build | Logic cells | EBR | DSP | Target | Estimated Fmax | Timing |
|---|---:|---:|---:|---:|---:|---|
| Core | 4068 / 5280 | 4 | 8 | 12.00 MHz | 17.07 MHz | Pass |
| Initialized-memory-to-UART top | 5131 / 5280 | 4 | 8 | 12.00 MHz | 15.89 MHz | Pass |

The wrapper adds 1063 logic cells but 0 EBR blocks. The RTL sample source is declared as memory, but the synthesized board top contains the same 4 `SB_RAM40_4K` cells as the core. Therefore the initialized sample source is not a distinct EBR in this build and is mapped or optimized into logic. This conclusion is specific to the archived netlists.

## Performance

Measured with continuous valid input, an always-ready output, and no random gaps or stalls:

- First sample to result valid: 15,877 cycles.
- End of frame to result valid: 15,622 cycles.
- Adjacent result handshakes: 15,575 cycles.
- Derived at 12 MHz: 770.47 frames/s and 197239.17 samples/s.
- Derived at board-top estimated Fmax: 1020.07 frames/s and 261138.77 samples/s.

Cycle counts are measured in RTL simulation; rates are derived. The estimated-Fmax rate is theoretical, not hardware-measured.

## Evidence files

See `results/ice40/core_report.json`, `board_top_report.json`, `test_summary.json`, `performance.json`, and `tool_versions.json`.
