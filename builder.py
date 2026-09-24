"""
Helpers for building outgoing Set/Get request frames.

All multi-byte numeric fields on the wire are big-endian, and temperature
values are stored as the real value multiplied by 100 (e.g. 21.5C -> 2150).
"""

from __future__ import annotations

from typing import Optional

from .frame import Frame, PacketType

PAYLOAD_SIZE = 16


def _pad(payload: bytearray) -> bytes:
    if len(payload) > PAYLOAD_SIZE:
        raise ValueError(f"Payload too long ({len(payload)} > {PAYLOAD_SIZE})")
    payload.extend([0] * (PAYLOAD_SIZE - len(payload)))
    return bytes(payload)


def _temp_to_raw(value: float) -> int:
    return int(round(value * 100))


def build_get_request(command: int) -> Frame:
    """Build a 0x42 Get Request frame for the given sub-command."""
    payload = bytearray([command])
    return Frame(packet_type=PacketType.GET_REQUEST, payload=_pad(payload))


# --- 0x32 : Update Settings -------------------------------------------------

FLAG_POWER = 0x0100
FLAG_UNKNOWN_MODE = 0x0200
FLAG_DHW_MODE = 0x0400
FLAG_HC1_MODE = 0x0800
FLAG_HC2_MODE = 0x1000
FLAG_DHW_SETPOINT = 0x2000
FLAG_Z1_SETPOINT = 0x8000
FLAG_Z2_SETPOINT = 0x0002
FLAG_MRC_PROHIBIT = 0x0008


def build_set_options(
    power: Optional[bool] = None,
    unknown_mode: Optional[int] = None,
    dhw_mode: Optional[int] = None,
    hc1_mode: Optional[int] = None,
    hc2_mode: Optional[int] = None,
    dhw_setpoint: Optional[float] = None,
    z1_setpoint: Optional[float] = None,
    z2_setpoint: Optional[float] = None,
    mrc_prohibit: Optional[int] = None,
) -> Frame:
    """Build a 0x32 (Update Settings) Set Request frame.

    Only the fields passed (not ``None``) will have their corresponding flag
    bit set, so the heat pump only applies the fields you provide.

    ``dhw_mode``: 0 = normal, 1 = eco.
    ``hc1_mode`` / ``hc2_mode``: 0=heating temp, 1=heating flow,
        2=heating compensation curve, 3=cooling temp, 4=cooling flow, 5=dry up.
    ``mrc_prohibit``: bitmask, see protocol docs. Do not set on Shizuoka models.
    """
    flags = 0
    payload = bytearray([0x32, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

    if power is not None:
        flags |= FLAG_POWER
        payload[3] = 1 if power else 0
    if unknown_mode is not None:
        flags |= FLAG_UNKNOWN_MODE
        payload[4] = unknown_mode
    if dhw_mode is not None:
        flags |= FLAG_DHW_MODE
        payload[5] = dhw_mode
    if hc1_mode is not None:
        flags |= FLAG_HC1_MODE
        payload[6] = hc1_mode
    if hc2_mode is not None:
        flags |= FLAG_HC2_MODE
        payload[7] = hc2_mode
    if dhw_setpoint is not None:
        flags |= FLAG_DHW_SETPOINT
        raw = _temp_to_raw(dhw_setpoint)
        payload[8], payload[9] = (raw >> 8) & 0xFF, raw & 0xFF
    if z1_setpoint is not None:
        flags |= FLAG_Z1_SETPOINT
        raw = _temp_to_raw(z1_setpoint)
        payload[10], payload[11] = (raw >> 8) & 0xFF, raw & 0xFF
    if z2_setpoint is not None:
        flags |= FLAG_Z2_SETPOINT
        raw = _temp_to_raw(z2_setpoint)
        payload[12], payload[13] = (raw >> 8) & 0xFF, raw & 0xFF
    if mrc_prohibit is not None:
        flags |= FLAG_MRC_PROHIBIT
        payload[14], payload[15] = (mrc_prohibit >> 8) & 0xFF, mrc_prohibit & 0xFF

    payload[1], payload[2] = (flags >> 8) & 0xFF, flags & 0xFF
    return Frame(packet_type=PacketType.SET_REQUEST, payload=bytes(payload))


# --- 0x34 : Hot Water and Holiday Mode --------------------------------------

FLAG_DHW_FORCE = 0x0100
FLAG_HOLIDAY_MODE = 0x0200
FLAG_DHW_INHIBIT = 0x0400
FLAG_HEATING_Z1_INHIBIT = 0x0800
FLAG_COOLING_Z1_INHIBIT = 0x1000
FLAG_HEATING_Z2_INHIBIT = 0x2000
FLAG_COOLING_Z2_INHIBIT = 0x4000
FLAG_SERVER_CONTROL_MODE = 0x8000


def build_hot_water_and_holiday(
    dhw_force: Optional[bool] = None,
    holiday_mode: Optional[bool] = None,
    dhw_inhibit: Optional[bool] = None,
    heating_z1_inhibit: Optional[bool] = None,
    cooling_z1_inhibit: Optional[bool] = None,
    heating_z2_inhibit: Optional[bool] = None,
    cooling_z2_inhibit: Optional[bool] = None,
    server_control_mode: Optional[bool] = None,
) -> Frame:
    """Build a 0x34 (Hot Water and Holiday Mode) Set Request frame.

    The ``*_inhibit`` fields only take effect while ``server_control_mode``
    is enabled ("Server Control Mode").
    """
    flags = 0
    payload = bytearray([0x34, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

    def set_bit(value, flag_bit, byte_index):
        nonlocal flags
        if value is not None:
            flags |= flag_bit
            payload[byte_index] = 1 if value else 0

    set_bit(dhw_force, FLAG_DHW_FORCE, 3)
    set_bit(holiday_mode, FLAG_HOLIDAY_MODE, 4)
    set_bit(dhw_inhibit, FLAG_DHW_INHIBIT, 5)
    set_bit(heating_z1_inhibit, FLAG_HEATING_Z1_INHIBIT, 6)
    set_bit(cooling_z1_inhibit, FLAG_COOLING_Z1_INHIBIT, 7)
    set_bit(heating_z2_inhibit, FLAG_HEATING_Z2_INHIBIT, 8)
    set_bit(cooling_z2_inhibit, FLAG_COOLING_Z2_INHIBIT, 9)
    set_bit(server_control_mode, FLAG_SERVER_CONTROL_MODE, 10)

    payload[1], payload[2] = (flags >> 8) & 0xFF, flags & 0xFF
    return Frame(packet_type=PacketType.SET_REQUEST, payload=bytes(payload))


# --- 0x35 : Set Thermostat Setpoints -----------------------------------------

FLAG_COOL_HEAT = 0x0001
FLAG_Z1_TSTAT_SETPOINT = 0x0002
FLAG_Z2_TSTAT_SETPOINT = 0x0008


def build_thermostat_setpoints(
    cooling: Optional[bool] = None,
    z1_setpoint: Optional[float] = None,
    z2_setpoint: Optional[float] = None,
) -> Frame:
    """Build a 0x35 (Set Thermostat Setpoints) Set Request frame."""
    flags = 0
    payload = bytearray([0x35, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

    if cooling is not None:
        flags |= FLAG_COOL_HEAT
        payload[3] = 1 if cooling else 0
    if z1_setpoint is not None:
        flags |= FLAG_Z1_TSTAT_SETPOINT
        raw = _temp_to_raw(z1_setpoint)
        payload[4], payload[5] = (raw >> 8) & 0xFF, raw & 0xFF
    if z2_setpoint is not None:
        flags |= FLAG_Z2_TSTAT_SETPOINT
        raw = _temp_to_raw(z2_setpoint)
        payload[6], payload[7] = (raw >> 8) & 0xFF, raw & 0xFF

    payload[1], payload[2] = (flags >> 8) & 0xFF, flags & 0xFF
    return Frame(packet_type=PacketType.SET_REQUEST, payload=bytes(payload))
