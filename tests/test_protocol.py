import pytest
from doppler.protocol import PACKET_SIZE, ResultPacket, crc16_ccitt


def test_crc_known_check_and_packet_roundtrip():
    assert crc16_ccitt(b"123456789") == 0x29B1
    expected = ResultPacket(1, 0, 16, 320000, 49280, 81753044)
    encoded = expected.encode()
    assert len(encoded) == PACKET_SIZE
    assert ResultPacket.decode(encoded) == expected


def test_packet_rejects_corruption():
    packet = bytearray(ResultPacket(1, 0, -16, -320000, -49280, 81753044).encode())
    packet[9] ^= 1
    with pytest.raises(ValueError, match="CRC"):
        ResultPacket.decode(packet)
