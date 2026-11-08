#!/usr/bin/env python3
"""Read one FPGA result packet from a 115200-8-N-1 serial link."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

import serial
from doppler.protocol import PACKET_SIZE, ResultPacket


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("port")
    parser.add_argument("--timeout", type=float, default=3.0)
    args = parser.parse_args()
    with serial.Serial(args.port, 115200, timeout=args.timeout) as link:
        packet = ResultPacket.decode(link.read(PACKET_SIZE))
    print(json.dumps(asdict(packet), indent=2))


if __name__ == "__main__":
    main()
