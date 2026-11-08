# Demo

The [signed tone demo](../README.md#see-it-run) runs the core in simulation and compares its output with the Python model.

The separate offline UART top feeds an initialized sample memory into the Doppler core. Its packetizer sends a 20-byte result with a CRC-16/CCITT-FALSE checksum over 115200 8N1 UART. The cocotb test checks the packet bytes against the host codec.

`read_result.py PORT` reads and validates a physical serial packet. See the [board checklist](../docs/m2_board_validation_checklist.md) for the pending hardware checks.
