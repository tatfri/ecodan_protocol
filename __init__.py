"""
Python module for reading from and writing to a Mitsubishi Ecodan (CN105 / FTC)
air source heat pump controller over its RS485/TTL serial protocol, using
pyserial.

Protocol reference:
https://github.com/gekkekoe/esphome-ecodan-hp/blob/main/protocol.md

Quick start
-----------
    from ecodan_protocol import EcodanClient

    with EcodanClient("/dev/ttyUSB0") as client:
        client.connect()  # perform the 0x02 handshake sequence
        status = client.get_zone_setpoints()   # or: client.get(GetCommand.ZONE_SETPOINTS)
        print(status)

        client.set_options(power=True, dhw_setpoint=48.0)
"""

from .frame import Frame, PacketType, checksum, FrameError
from .commands import GetCommand
from .parser import parse_get_response
from .builder import (
    build_get_request,
    build_set_options,
    build_hot_water_and_holiday,
    build_thermostat_setpoints,
)
from .client import EcodanClient

__all__ = [
    "Frame",
    "PacketType",
    "checksum",
    "FrameError",
    "GetCommand",
    "parse_get_response",
    "build_get_request",
    "build_set_options",
    "build_hot_water_and_holiday",
    "build_thermostat_setpoints",
    "EcodanClient",
]
