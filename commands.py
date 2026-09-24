"""
Human-friendly names for the Get Request sub-commands (0x42 packets).

``GetCommand`` is an ``IntEnum``, so it can be used anywhere an ``int`` is
expected (``client.get(GetCommand.ZONE_SETPOINTS)`` or the equivalent
``client.get(0x09)``) while still printing/logging as a readable name.
"""

from __future__ import annotations

from enum import IntEnum


class GetCommand(IntEnum):
    DATE_TIME = 0x01
    DEFROST = 0x02
    ERROR_CODES = 0x03
    COMPRESSOR_FREQUENCY = 0x04
    HEAT_SOURCE = 0x05
    HEATER_POWER = 0x07
    ZONE_SETPOINTS = 0x09
    ZONE_AND_OUTSIDE_TEMPERATURES = 0x0B
    WATER_FLOW_TEMPERATURES = 0x0C
    BOILER_FLOW_TEMPERATURES = 0x0D
    THERMISTORS_2 = 0x0E
    THERMISTORS_3 = 0x0F
    EXTERNAL_THERMOSTATS = 0x10
    DIP_SWITCHES = 0x11
    RUN_HOURS = 0x13
    FLOW_RATE_AND_BOOSTER = 0x14
    PUMP_STATUS = 0x15
    PUMPS_RUNNING = 0x16
    OPERATION_MODE_FLAGS = 0x26
    OPERATION_MODE_FLAGS_2 = 0x28
    ZONE_TEMPERATURES = 0x29
    CONSUMED_ENERGY = 0xA1
    DELIVERED_ENERGY = 0xA2
    HARDWARE_CONFIGURATION = 0xC9
