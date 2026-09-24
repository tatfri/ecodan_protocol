"""
Low level framing for the Ecodan / CN105 serial protocol.

Two framing "dialects" are used on the wire:

* Normal frames, used for all Get/Set/Connect/Configuration traffic::

      | Sync | Type | 0x02 | 0x7A | Length | Payload (Length bytes) | Checksum |
      | 0xFC |  ..  |      |      |        |                        |          |

* Handshake frames, only used for the initial 0x02 sequence exchanged when a
  connection is (re)established::

      | Sync | 0xFF | 0xFF | SubType | 0x00 | 0x00 | Length | Payload | Checksum |
      | 0x02 |      |      |         |      |      |        |         |          |

Both dialects share the same checksum algorithm: the checksum byte is chosen
so that the sum of every byte in the frame *except the sync byte* is 0 modulo
256.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

SYNC_NORMAL = 0xFC
SYNC_HANDSHAKE = 0x02


class FrameError(Exception):
    """Raised when a frame cannot be parsed or fails checksum validation."""


class PacketType(IntEnum):
    SET_REQUEST = 0x41
    SET_RESPONSE = 0x61
    GET_REQUEST = 0x42
    GET_RESPONSE = 0x62
    CONNECT_REQUEST = 0x5A
    CONNECT_RESPONSE = 0x7A
    CONFIG_REQUEST = 0x5B
    CONFIG_RESPONSE = 0x7B


def checksum(payload: bytes) -> int:
    """Compute the checksum byte for ``payload``.

    ``payload`` must be every frame byte *except* the leading sync byte and
    the checksum byte itself (i.e. type/subtype byte through the last payload
    byte, inclusive).
    """
    return (-sum(payload)) & 0xFF


@dataclass
class Frame:
    """A decoded normal (0xFC) protocol frame."""

    packet_type: int
    payload: bytes
    unknown1: int = 0x02
    unknown2: int = 0x7A

    def encode(self) -> bytes:
        header = bytes(
            [SYNC_NORMAL, self.packet_type, self.unknown1, self.unknown2, len(self.payload)]
        )
        body = header[1:] + self.payload
        return header + self.payload + bytes([checksum(body)])

    @property
    def command(self) -> Optional[int]:
        """The first payload byte, used as a sub-command id by most frames."""
        return self.payload[0] if self.payload else None

    @classmethod
    def decode(cls, data: bytes) -> "Frame":
        if len(data) < 6:
            raise FrameError(f"Frame too short: {data!r}")
        if data[0] != SYNC_NORMAL:
            raise FrameError(f"Unexpected sync byte: 0x{data[0]:02X}")
        packet_type, unknown1, unknown2, length = data[1], data[2], data[3], data[4]
        expected_len = 5 + length + 1
        if len(data) != expected_len:
            raise FrameError(
                f"Length mismatch: header declares {length} payload bytes, "
                f"got frame of {len(data)} bytes"
            )
        payload = data[5:5 + length]
        received_checksum = data[5 + length]
        computed = checksum(data[1:5 + length])
        if received_checksum != computed:
            raise FrameError(
                f"Checksum mismatch: expected 0x{computed:02X}, got 0x{received_checksum:02X}"
            )
        return cls(packet_type=packet_type, payload=payload, unknown1=unknown1, unknown2=unknown2)


@dataclass
class HandshakeFrame:
    """A decoded 0x02 handshake frame (used only during connection setup)."""

    subtype: int
    payload: bytes = field(default_factory=bytes)

    def encode(self) -> bytes:
        header = bytes([SYNC_HANDSHAKE, 0xFF, 0xFF, self.subtype, 0x00, 0x00, len(self.payload)])
        body = header[1:] + self.payload
        return header + self.payload + bytes([checksum(body)])

    @classmethod
    def decode(cls, data: bytes) -> "HandshakeFrame":
        if len(data) < 8:
            raise FrameError(f"Handshake frame too short: {data!r}")
        if data[0] != SYNC_HANDSHAKE:
            raise FrameError(f"Unexpected handshake sync byte: 0x{data[0]:02X}")
        subtype, length = data[3], data[6]
        expected_len = 7 + length + 1
        if len(data) != expected_len:
            raise FrameError(
                f"Handshake length mismatch: header declares {length} payload bytes, "
                f"got frame of {len(data)} bytes"
            )
        payload = data[7:7 + length]
        received_checksum = data[7 + length]
        computed = checksum(data[1:7 + length])
        if received_checksum != computed:
            raise FrameError(
                f"Handshake checksum mismatch: expected 0x{computed:02X}, "
                f"got 0x{received_checksum:02X}"
            )
        return cls(subtype=subtype, payload=payload)


# The two fixed handshake exchanges required before normal Get/Set traffic
# will be answered by the heat pump controller.
HANDSHAKE_FIRST_REQUEST = bytes([0x02, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x02])
HANDSHAKE_FIRST_RESPONSE = bytes(
    [0x02, 0xFF, 0xFF, 0x80, 0x00, 0x00, 0x0A, 0x01, 0x00, 0x40, 0x00, 0x00, 0x06, 0x02, 0x7A, 0x00, 0x00, 0xB5]
)
HANDSHAKE_SECOND_REQUEST = bytes([0x02, 0xFF, 0xFF, 0x01, 0x00, 0x00, 0x01, 0x00, 0x00])
HANDSHAKE_SECOND_RESPONSE = bytes([0x02, 0xFF, 0xFF, 0x81, 0x00, 0x00, 0x00, 0x81])

# Also sending the connect request is required before the heat pump controller
# will answer.
CONNECT_REQUEST = bytes([0xfc, 0x5a, 0x02, 0x7a, 0x02, 0xca, 0x01, 0x5d])
DISCONNECT_REQUEST = bytes([0xfc, 0x5a, 0x02, 0x7a, 0x02, 0xca, 0x02, 0x5c])
