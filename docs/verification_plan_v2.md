# Verification plan v2: controlled AXI Doppler accelerator

## Scope and evidence rules

This plan covers the frozen canonical algorithm core, Phase 1 streaming contract, Phase 2
AXI4-Stream wrapper, Phase 3 AXI4-Lite control plane, and Phase 4 system interactions.
Coverage credit requires an observed DUT event: accepted stream transfer, transferred
result, completed AXI-Lite response, or sampled reset. Generated stimulus alone receives no
credit. `PASS` below means executable evidence exists in this repository.

| ID | Requirement / behavior | Directed evidence | Random evidence | Assertion / scoreboard | Coverage point | Status |
|---|---|---|---|---|---|---|
| ALG-01 | Signed positive/negative/near-zero Doppler | Ten signed bins; numerical edges | Seeded signal parameters | Bit-accurate field comparison | direction; peak range | PASS |
| ALG-02 | Accuracy is qualified by SNR | 1,800-case Python matrix | Five SNR bins | Fixed vs float and RTL vs fixed | direction × SNR; peak range × SNR | PASS |
| ALG-03 | Wall clutter and amplitude behavior | Zero/full-scale/tie tests | Four clutter and three amplitude bins | Saturation/status comparison | direction × clutter; amplitude × saturation | PASS |
| ALG-04 | Special numerical signals | Zero, tie, full-scale, ±Nyquist closure | Random spectral frames | All result fields | special-signal bins | PASS |
| FRM-01 | Legal frame is 256 accepted samples with TLAST | Stream-contract legal tests | Mixed seeded frames | Accepted-sample frame tracker | legal frame | PASS |
| FRM-02 | Early/missing/oversized frames emit no direct result and recover | Malformed-frame tests | Seeded malformed frames | Expected-result queue | frame type × outcome | PASS |
| STR-01 | Transfer occurs only on VALID && READY | Phase 1/2 protocol tests | Random gaps/backpressure | Public immediate assertions and monitor | gap/stall lengths | PASS |
| STR-02 | Output payload is stable while stalled | Long output-stall test | Seeded ready delays | Immediate assertion and payload monitor | output stall/context | PASS |
| STR-03 | Results are neither lost, duplicated, nor reordered | Back-to-back/sequence tests | 100-seed scoreboard | Sequence and result queue | result behavior | PASS |
| STR-04 | Reset may lawfully abort pending work | Collect/process/result reset tests | Random soft-reset actions | Reset-aware scoreboard | frame × reset | PASS |
| LIT-01 | AW and W are independent | Phase 3 ordering test | Random channel delays | AXI transaction monitor | ordering and delay | PASS |
| LIT-02 | B/R responses tolerate backpressure | Phase 3 long stalls | Random response stalls | Immediate stability assertions | B/R stall lengths | PASS |
| LIT-03 | Invalid access returns SLVERR | Invalid/misaligned/RO-write test | Closure invalid operations | Response scoreboard | address × response | PASS |
| LIT-04 | WSTRB applies by byte | All 16 SCRATCH strobes | Random strobe per seed | Register mirror | WSTRB/register | PASS |
| LIT-05 | Register side effects match the map | Reset/scratch/control tests | Random read/write timing | Register-state scoreboard | side-effect bins | PASS |
| RST-01 | Global reset aborts AXI and datapath state | Phase 3 reset-mid-transaction | Ten targeted locations | Public-state post checks | global-reset location | PASS |
| RST-02 | Soft reset preserves AXI response engine, SCRATCH and IRQ_ENABLE | Phase 3 processing/result tests | Seeded collection/processing resets | Register/datapath scoreboard | soft-reset location | PASS |
| RST-03 | A legal frame succeeds after reset | Recovery directed tests | Every seed starts/recoveries | Result queue and sequence check | post-reset checks | PASS |
| IRQ-01 | Result event is sticky and gated only at external IRQ | Phase 3 IRQ tests | Random IRQ enable | IRQ/register mirror | IRQ enable × event | PASS |
| IRQ-02 | W1C, write-zero and multiple events behave correctly | IRQ directed/closure | Random clears | IRQ mirror | IRQ behavior | PASS |
| IRQ-03 | New result wins over simultaneous clear | Same-cycle race test | Timing randomized around results | Cycle-level scoreboard | clear × result | PASS |
| SYS-01 | Disable pauses input but not pending output | Mid-frame and pending-output tests | Seeded enable pauses | Accepted-sample scoreboard | enable transition × frame state | PASS |
| SYS-02 | Stream, reset, IRQ and control-plane crosses are exercised | Coverage-closure test | 100 seeds | Combined system observer | 114 required cross bins | PASS |
| LEG-01 | Canonical algorithm and legacy board remain unchanged | Protected-source audit | N/A | Git diff and legacy builds | resource delta | PASS |

## Explicitly out of scope

Vivado/XSim, SystemVerilog covergroups, UVM, AXI VIP, code/toggle coverage, IP packaging,
AXI DMA, Zynq PS, Vitis/ARM software, XC7Z020 implementation/timing, CDC, and physical
hardware validation are not passed items in this plan.
