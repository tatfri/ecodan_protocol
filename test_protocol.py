import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ecodan_protocol.frame import (
    Frame,
    HandshakeFrame,
    checksum,
    HANDSHAKE_FIRST_REQUEST,
    HANDSHAKE_FIRST_RESPONSE,
    HANDSHAKE_SECOND_REQUEST,
    HANDSHAKE_SECOND_RESPONSE,
)
from ecodan_protocol.builder import build_get_request, build_set_options
from ecodan_protocol.parser import parse_get_response


def test_handshake_frames_round_trip():
    for raw in (
        HANDSHAKE_FIRST_REQUEST,
        HANDSHAKE_FIRST_RESPONSE,
        HANDSHAKE_SECOND_REQUEST,
        HANDSHAKE_SECOND_RESPONSE,
    ):
        hf = HandshakeFrame.decode(raw)
        assert hf.encode() == raw, raw.hex()


def test_prohibit_cool_zone1_checksum():
    # From protocol.md: prohibit cool zone 1
    payload = bytes([0x34, 0x10, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    frame = Frame(packet_type=0x41, payload=payload)
    encoded = frame.encode()
    assert encoded[-1] == 0xEE, f"got 0x{encoded[-1]:02X}"


def test_prohibit_heating_zone2_checksum():
    payload = bytes([0x34, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    frame = Frame(packet_type=0x41, payload=payload)
    encoded = frame.encode()
    assert encoded[-1] == 0xDE, f"got 0x{encoded[-1]:02X}"


def test_get_request_roundtrip():
    frame = build_get_request(0x09)
    encoded = frame.encode()
    decoded = Frame.decode(encoded)
    assert decoded.payload[0] == 0x09
    assert len(decoded.payload) == 16


def test_set_options_flags():
    frame = build_set_options(power=True, dhw_setpoint=48.5)
    assert frame.payload[3] == 1
    raw_sp = frame.payload[8] | (frame.payload[9] << 8)
    assert raw_sp == 4850
    flags = frame.payload[1] | (frame.payload[2] << 8)
    assert flags == (0x0001 | 0x0020)


def test_parse_get_response_zone_setpoints():
    payload = bytearray(16)
    payload[0] = 0x09
    raw = 2150  # 21.50 C
    payload[1] = raw & 0xFF
    payload[2] = (raw >> 8) & 0xFF
    result = parse_get_response(bytes(payload))
    assert result["command"] == 0x09
    assert abs(result["data"]["zone1_target_temp"] - 21.5) < 1e-6


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"OK: {t.__name__}")
    print(f"{len(tests)} tests passed")
