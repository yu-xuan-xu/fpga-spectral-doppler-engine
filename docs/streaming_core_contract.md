# Doppler streaming-core contract

This document describes the behavior of the existing canonical `rtl/core/doppler_core.sv`. It does not introduce a second algorithm core or change the v1 algorithm.

## Input stream

The input payload is signed 16-bit Q1.15 complex data on `s_i` and `s_q`. A sample is accepted only on a rising edge where both `s_valid` and `s_ready` are high. Cycles with either signal low do not advance the frame.

The source may insert arbitrary gaps by deasserting `s_valid`. When it asserts `s_valid` while `s_ready` is low, it must hold `s_valid`, `s_i`, `s_q`, and `s_last` stable until the transfer occurs. The core may deassert `s_ready` while it replays a captured frame or while internal processing prevents another capture.

A legal frame contains exactly 256 accepted samples. `s_last` is low on accepted samples 1 through 255 and high on accepted sample 256 (zero-based index 255).

## Malformed frames and recovery

The frame checker implements the following existing behavior:

- **Early `s_last`:** if `s_last` is accepted before sample 256, the partial frame is discarded, the capture index returns to zero, and a frame-error event is recorded. The next accepted sample begins a new candidate frame.
- **Missing `s_last`:** if accepted sample 256 has `s_last=0`, that candidate frame is discarded and the checker enters DISCARD state.
- **Oversized/discard sequence:** while in DISCARD, accepted samples are ignored until one arrives with `s_last=1`. That terminating sample only re-establishes framing; it is not sample 1 of a new frame. The following accepted sample starts a new candidate frame.
- **Reset-aborted frame:** asserting `rst_n=0` discards a partial captured frame, any frame in processing, and any unaccepted pending result. Frame, DSP, filter-history, sticky-status, and output-valid state return to reset values. An aborted frame produces no result.

A malformed frame never enters the algorithm pipeline and never produces a result by itself. Its error event sets sticky status bit 0. That bit is included in the next chronological structured result produced after the event and is cleared when a result handshake occurs. The status is not associated through a frame-ID queue; if an earlier legal frame is already in flight, the next chronological result is the one that can carry the sticky error. Multiple malformed events before that handshake collapse into the same one-bit indication.

## Result stream

Each legal frame that is not reset-aborted produces one structured result:

| Signal | Meaning |
|---|---|
| `m_peak_bin[8:0]` | Signed FFT peak bin |
| `m_frequency_q8_hz[23:0]` | Signed frequency in Q8 Hz |
| `m_velocity_q8_mm_s[19:0]` | Signed velocity in Q8 mm/s |
| `m_peak_power[36:0]` | Unsigned peak power |
| `m_status[0]` | Sticky malformed-frame/FFT-frame error |
| `m_status[1]` | Low confidence |
| `m_status[2]` | Arithmetic overflow observed |
| `m_status[3]` | Reserved, currently zero |

A result is accepted only on a rising edge where `m_valid && m_ready` is true. While `m_valid=1` and `m_ready=0`, `m_valid` and every payload field remain stable. The consumer may stall for an arbitrary number of cycles. Results are accepted in legal-frame order, without loss or duplication.

## Automated enforcement

`rtl/assertions/doppler_stream_sva.sv` observes only the public core interface. In the assertion-enabled simulation shell it checks:

- source payload stability while input is stalled;
- all result fields and `m_valid` remain stable while output is stalled;
- `m_valid` is cleared while reset is active;
- accepted-sample framing and DISCARD recovery using public handshakes;
- accepted result count never exceeds accepted legal-frame count, covering malformed/reset-aborted frames and duplicate result transfers.

The ordered cocotb scoreboard checks exact result payloads, one result per legal frame, ordering, reset at collection/processing/stalled-result phases, malformed recovery, and no loss or duplication. It also verifies zero, full-scale, exact-rounding-pattern, exact spectral-tie, near-Nyquist, and ten directed signed-bin cases.

Icarus Verilog 13.0 in the current environment rejects `property`, `assert property`, and `bind` syntax. Therefore these checks use immediate SystemVerilog assertions in a simulation-only wrapper rather than claiming unsupported concurrent SVA execution. Cross-frame ordering and exact expected payloads remain in cocotb because expressing them through internal hierarchical state would create a brittle binding to implementation details.
