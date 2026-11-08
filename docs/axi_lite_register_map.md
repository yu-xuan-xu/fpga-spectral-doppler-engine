# AXI4-Lite control, status, and interrupt contract

## Scope and ports

`doppler_axi_lite_regs` is a reusable 32-bit AXI4-Lite slave. The
`doppler_axi_controlled_top` connects it to the existing
`doppler_axi_stream_wrapper` and canonical `doppler_core`; the algorithm and Phase 2 packet
format are unchanged.

The register slave exposes `s_axi_aclk`, active-low `s_axi_aresetn`, 32-bit AWADDR/WDATA/
ARADDR, 4-bit WSTRB, and all five AXI4-Lite VALID/READY channels. Datapath observation
inputs are `stream_input_ready`, `stream_output_valid`, `result_data[127:0]`,
`result_valid`, and `result_ready`. Its outputs are `enable`, one-cycle
`soft_reset_pulse`, and level-sensitive `irq`.

The controlled top exposes the same AXI4-Lite signals plus the Phase 2 input and output
stream ports. Both interfaces use `aclk` and `aresetn`; Phase 3 has no CDC.

## Transaction contract

- One write and one read may be outstanding independently.
- AW and W are saved independently and may arrive together, AW first, or W first.
- A write executes once after both halves are saved and no B response is pending.
- An AR is accepted only when no R response is pending.
- Stalled B responses hold BVALID/BRESP; stalled R responses hold RVALID/RDATA/RRESP.
- `OKAY=2'b00`; `SLVERR=2'b10`; DECERR is never generated.
- Misaligned, undefined, unsupported, and write-to-RO accesses return SLVERR without a
  register side effect.
- Global reset synchronously abandons captured request halves and pending responses; the
  master must retry them.

## Register map

| Offset | Name | Access | Reset | Definition |
|---:|---|---|---:|---|
| `0x00` | VERSION | RO | `0x02000000` | major 2, minor 0, patch 0 |
| `0x04` | CAPABILITIES | RO | `0x03104100` | fixed capabilities |
| `0x08` | CONTROL | RW/W1P | `0` | bit 0 ENABLE; bit 1 SOFT_RESET |
| `0x0c` | STATUS | RO | `0` | live/sticky status |
| `0x10` | RESULT_COUNT | RO | `0` | completed output transfers |
| `0x14` | LAST_SEQUENCE | RO | `0` | packet `[31:0]` |
| `0x18` | LAST_PEAK_BIN | RO | `0` | sign-extended packet `[40:32]` |
| `0x1c` | LAST_FREQUENCY | RO | `0` | sign-extended packet `[64:41]` |
| `0x20` | LAST_VELOCITY | RO | `0` | sign-extended packet `[84:65]` |
| `0x24` | LAST_POWER_LO | RO | `0` | power `[31:0]` |
| `0x28` | LAST_POWER_HI | RO | `0` | bits `[4:0]` = power `[36:32]` |
| `0x2c` | LAST_STATUS | RO | `0` | bits `[3:0]` = packet status |
| `0x30` | IRQ_ENABLE | RW | `0` | bit 0 result interrupt enable |
| `0x34` | IRQ_STATUS | RW1C | `0` | bit 0 sticky result event |
| `0x38` | SCRATCH | RW | `0` | software integration test |

All reserved bits read zero. CAPABILITIES packs `[9:0]=256` FFT points,
`[15:10]=16` bits per I/Q component, `[23:16]=16` result bytes, `[24]=1` signed
velocity, `[25]=1` complex I/Q, and `[31:26]=0`.

## WSTRB and fields

SCRATCH updates each selected byte. CONTROL and IRQ_ENABLE fields change only with
`WSTRB[0]`. IRQ_STATUS clears only when `WSTRB[0] && WDATA[0]`. A zero-strobe write to a
valid writable offset returns OKAY without changing state.

STATUS is `[0] enabled`, `[1] externally visible input_ready`, `[2] output_valid`,
`[3] irq_pending`, and `[4] last_result_valid`; `[31:5]` are zero. CONTROL bit 1 always
reads zero.

## Enable, soft reset, result snapshot, and IRQ

ENABLE defaults to zero, forcing external `s_axis_tready=0`. Disabling midway through a
frame pauses it without losing accepted samples; re-enabling resumes it. ENABLE does not
gate a pending output.

Writing CONTROL bit 1 with `WSTRB[0]` produces one datapath-reset cycle and clears ENABLE,
the core/wrapper and result sequence, RESULT_COUNT, all LAST_* registers,
`last_result_valid`, and IRQ_STATUS. The AXI4-Lite transaction engine, SCRATCH, and
IRQ_ENABLE are not reset, so the soft-reset write still receives its B response. Stream
handshakes are masked during the pulse.

Each `m_axis_tvalid && m_axis_tready` atomically increments RESULT_COUNT and copies LAST_*
from the transferred 128-bit packet. The count naturally wraps. Stalls, malformed frames,
and reset-aborted frames do not update it.

Every result transfer sets IRQ_STATUS even if IRQ_ENABLE is zero. External
`irq = IRQ_ENABLE[0] && IRQ_STATUS[0]`. Writing one clears the sticky event; writing zero
does nothing. A new result wins over a simultaneous software clear.

## Current limitations

Not completed in Phase 3: Vivado IP packaging, AXI VIP, UVM, AXI DMA, XC7Z020
implementation/timing, ARM software, Zynq Processing System integration, CDC, or hardware
validation. FFT size, wall-filter coefficient, and velocity calibration remain compile-time
constants and intentionally have no writable registers.
