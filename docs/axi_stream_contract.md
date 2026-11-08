# AXI4-Stream-compatible Doppler wrapper contract

`rtl/axi/doppler_axi_stream_wrapper.sv` adapts the existing canonical `doppler_core` to fixed-width AXI4-Stream-style ports. It performs only input unpacking, result packing, reset adaptation, and result sequencing. It does not contain a sample-frame buffer, output FIFO, or duplicated DSP algorithm.

## Clock and reset

| Port | Direction | Meaning |
|---|---|---|
| `aclk` | Input | Single clock for the wrapper, both AXI streams, and `doppler_core` |
| `aresetn` | Input | Active-low **synchronous wrapper reset** |

There is one clock domain and no CDC. `aresetn` is sampled on `aclk`. Its registered value drives the existing core's active-low asynchronous `rst_n` input, so asserting wrapper reset on a rising edge clears the core immediately after that edge. Tests hold reset for at least three rising edges and verify that output valid clears. No assumption is made from the `aresetn` name alone; its external contract is synchronous.

## 32-bit input stream

| Port | Direction | Width | Meaning |
|---|---|---:|---|
| `s_axis_tdata` | Input | 32 | One complete complex Q1.15 sample |
| `s_axis_tvalid` | Input | 1 | Source presents a valid sample |
| `s_axis_tready` | Output | 1 | Core can accept the sample |
| `s_axis_tlast` | Input | 1 | End-of-frame marker |

Packing is fixed:

```text
31                 16 15                   0
+--------------------+----------------------+
| signed I, Q1.15    | signed Q, Q1.15      |
+--------------------+----------------------+
```

A beat transfers only when `s_axis_tvalid && s_axis_tready`. If valid is asserted while ready is low, the source holds data and `TLAST` stable. The wrapper directly connects valid, ready, data, and last to the existing core.

The existing frame checker remains authoritative: a legal frame has 256 accepted beats and `TLAST` on zero-based sample 255. Early `TLAST`, missing `TLAST`, DISCARD/oversized recovery, and reset-abort behavior are unchanged from `docs/streaming_core_contract.md`.

## 128-bit result stream

| Port | Direction | Width | Meaning |
|---|---|---:|---|
| `m_axis_tdata` | Output | 128 | One complete structured Doppler result |
| `m_axis_tvalid` | Output | 1 | Result beat is valid |
| `m_axis_tready` | Input | 1 | Sink accepts the result |
| `m_axis_tlast` | Output | 1 | Always 1; meaningful when valid is 1 |

Every result is exactly one beat:

```text
127 126 125      122 121             85 84             65
+-------+------------+-----------------+------------------+
| 00    | status[3:0]| peak_power[36:0]| velocity Q8     |
+-------+------------+-----------------+------------------+
64                     41 40        32 31                 0
+------------------------+------------+--------------------+
| signed frequency Q8 Hz | peak bin   | result_sequence    |
+------------------------+------------+--------------------+
```

Exact bit allocation:

| Bits | Field | Format |
|---|---|---|
| `[31:0]` | `result_sequence` | Unsigned 32-bit counter |
| `[40:32]` | `peak_bin` | Signed 9-bit FFT bin |
| `[64:41]` | `frequency_q8_hz` | Signed 24-bit Q8 Hz |
| `[84:65]` | `velocity_q8_mm_s` | Signed 20-bit Q8 mm/s |
| `[121:85]` | `peak_power` | Unsigned 37-bit integer |
| `[125:122]` | `status` | Existing four core status bits |
| `[127:126]` | Reserved | Always `2'b00` |

The output transfers only when `m_axis_tvalid && m_axis_tready`. Core result-ready is directly driven by AXI ready; no extra output FIFO is present.

## Result sequence

The default production reset value is zero. The first delivered result carries sequence 0. The counter increments once after each successful output handshake, never on input acceptance or on malformed/reset-aborted frames. It remains stable during output stalls and wraps naturally modulo `2^32`.

`result_sequence` is the number assigned to successfully delivered output results. It is not a host-supplied frame ID. There is no input frame ID, `TUSER`, or frame-ID FIFO. Verification overrides the elaboration-time reset parameter only in a dedicated simulation build to prove `FFFFFFFE`, `FFFFFFFF`, `00000000` wrap; the production default remains zero and there is no runtime backdoor.

## Backpressure and reset behavior

While `m_axis_tvalid=1` and `m_axis_tready=0`, valid, all 128 data bits, `TLAST`, every packed field, and the sequence remain stable. The core result is not consumed or overwritten. An 83-cycle directed stall and randomized stalls are checked cycle by cycle.

Synchronous reset aborts partial input, in-flight processing, and an unaccepted stalled result through the registered core-reset adaptation. It clears the production sequence to zero. The first result after reset again carries sequence 0. A reset-aborted frame produces no output beat.

Malformed input frames produce no result and do not increment sequence. The existing sticky frame-error behavior is preserved: the next chronological legal result after the error event carries status bit 0, subject to the exact semantics in `docs/streaming_core_contract.md`.

## Unsupported optional AXI signals

This version intentionally has no input or output `TKEEP`, `TSTRB`, `TUSER`, `TID`, or `TDEST`. Every input beat contains all four sample bytes and every output beat contains all sixteen result bytes. Partial-byte transfers are not supported.

## Verification evidence and limitations

The automated suite covers packing/unpacking, back-to-back frames, randomized input gaps and output backpressure, an 83-cycle output stall, reset at four phases, malformed recovery, numerical edges, ten directed signed bins, sequence wrap, and side-by-side equivalence with a direct `doppler_core` instance. Public-interface immediate assertions run under Icarus 13.0; concurrent SVA and `bind` remain unsupported by that simulator.

This is AXI4-Stream-compatible RTL only. It has not been packaged with Vivado IP Packager, connected to AXI DMA, implemented for XC7Z020, or run on Zynq hardware. AXI4-Lite control/status, interrupts, DMA integration, CDC, and hardware validation are future work.
