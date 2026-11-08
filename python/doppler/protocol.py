"""Binary result-packet encoder/decoder shared by demo tools and tests."""

from __future__ import annotations

from dataclasses import dataclass

PACKET_SIZE = 20
SYNC = b"\xa5\x5a"


def crc16_ccitt(data: bytes, initial: int = 0xFFFF) -> int:
    crc = initial
    for byte in data:
        for bit_index in range(8):
            feedback = ((crc >> 15) & 1) ^ ((byte >> (7 - bit_index)) & 1)
            crc = (crc << 1) & 0xFFFF
            if feedback:
                crc ^= 0x1021
    return crc


@dataclass(frozen=True)
class ResultPacket:
    case_id: int
    status: int
    peak_bin: int
    frequency_q8_hz: int
    velocity_q8_mm_s: int
    peak_power: int

    def encode(self) -> bytes:
        payload = bytearray(SYNC)
        payload.extend((1, self.case_id, self.status & 0x0F))
        payload.extend(int(self.peak_bin).to_bytes(2, "big", signed=True))
        payload.extend(int(self.frequency_q8_hz).to_bytes(3, "big", signed=True))
        payload.extend(int(self.velocity_q8_mm_s).to_bytes(3, "big", signed=True))
        payload.extend(int(self.peak_power).to_bytes(5, "big", signed=False))
        payload.extend(crc16_ccitt(payload).to_bytes(2, "big"))
        return bytes(payload)

    @classmethod
    def decode(cls, packet: bytes) -> ResultPacket:
        if len(packet) != PACKET_SIZE or packet[:2] != SYNC or packet[2] != 1:
            raise ValueError("invalid result packet framing or version")
        if crc16_ccitt(packet[:-2]) != int.from_bytes(packet[-2:], "big"):
            raise ValueError("result packet CRC mismatch")
        return cls(
            packet[3],
            packet[4] & 0x0F,
            int.from_bytes(packet[5:7], "big", signed=True),
            int.from_bytes(packet[7:10], "big", signed=True),
            int.from_bytes(packet[10:13], "big", signed=True),
            int.from_bytes(packet[13:18], "big", signed=False),
        )
