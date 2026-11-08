# M2 physical-board validation checklist

Do not perform these steps or upgrade project claims until an UPduino is physically available.

- [ ] Photograph and record board revision, FPGA marking, oscillator jumper state, and USB identity.
- [ ] Confirm the correct UPduino schematic and choose safe UART/done pins; add and review a revision-specific PCF.
- [ ] Program a minimal blink design and archive the programmer log.
- [ ] Rebuild the tagged M1 design with the frozen PCF and confirm timing still passes.
- [ ] Connect only 3.3 V UART signaling; verify idle-high output and baud rate before decoding packets.
- [ ] Run both canonical direction cases and compare every packet field and CRC to the Python oracle.
- [ ] Run 100 consecutive repetitions with zero mismatches and archive raw serial data.
- [ ] Record any M2 RTL/configuration change, regenerate affected reports, and rerun the complete M1 suite.
- [ ] Add board photographs/video and exact hardware/programmer versions.
- [ ] Only then change wording from “synthesized for UP5K” to “deployed on UPduino.”
