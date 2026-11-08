# Implementation status

M1 hardware-independent implementation is complete. M2 physical-board validation is deferred because no UPduino is currently available.

## Completed and verified

- Deterministic five-profile synthetic generator; floating and bit-accurate fixed models.
- Versioned canonical vectors with filter, window, FFT, and power intermediates.
- 256-point resource-shared streaming RTL with legal-frame buffering, sticky status, confidence flag, and stable result backpressure.
- Cocotb ordered scoreboard for all output fields, malformed frames, reset aborts, gaps, stalls, and ten signed directed bins.
- Public streaming contract with six focused cocotb scenarios and Icarus-compatible immediate assertions.
- AXI4-Stream-compatible 32-bit sample input and 128-bit single-beat result wrapper with sequence tracking and ten focused cocotb scenarios.
- Frozen 1,800-configuration regression with raw CSV, summary, and plots.
- Offline initialized sample source, result packetizer, CRC-16/CCITT-FALSE, UART transmitter, and Python host decoder.
- Core and offline board top synthesize, place, and route for iCE40UP5K-SG48 at 12 MHz.

## Evidence boundary

The core uses 4,068 logic cells; the offline board top uses 5,131 logic cells and has little remaining margin. Both close 12 MHz. Generated bitstreams are unverified on hardware, physical pins are not frozen, and no board performance claim is made.

See `docs/results_m1.md` for measured values, `docs/streaming_core_contract.md` for the verified interface behavior, and `docs/m2_board_validation_checklist.md` for the remaining physical work.
