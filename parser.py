"""
Parsing of Get Response (0x62) payloads into Python dictionaries.

Every parser function receives the full 17-byte payload (index 0 is always
the echoed command byte) and returns a ``dict`` of decoded fields. Fields
whose exact byte layout is ambiguous in the upstream protocol documentation
are marked as such in comments; ``raw`` (hex string of the whole payload) is
always included so callers can cross-check / re-derive values themselves.

Reference: https://github.com/gekkekoe/esphome-ecodan-hp/blob/main/protocol.md
"""

from __future__ import annotations

from typing import Callable, Dict

from .frame import Frame


def _s16(payload: bytes, i: int) -> int:
    """Signed big-endian 16 bit integer starting at byte ``i``."""
    value = (payload[i] << 8) | payload[i + 1]
    if value >= 0x8000:
        value -= 0x10000
    return value


def _u16(payload: bytes, i: int) -> int:
    return (payload[i] << 8) | payload[i + 1]


def _u24(payload: bytes, i: int) -> int:
    return (payload[i] << 16) | (payload[i + 1] << 8) | payload[i + 2]


def _temp(payload: bytes, i: int) -> float:
    """A signed 16 bit temperature value, scaled by 100."""
    return _u16(payload, i) / 100.0


def _half_minus40(raw: int) -> float:
    """Common encoding: raw/2 - 40 degrees C."""
    return raw / 2.0 - 40.0


def _bcd(raw: int) -> str:
    return f"{(raw >> 4) & 0xF}.{raw & 0xF}"


def _parse_datetime(p: bytes) -> dict:
    return {
        "year": 2000 + p[1],
        "month": p[2],
        "day": p[3],
        "hour": p[4],
        "minute": p[5],
        "second": p[6],
        "firmware_version": f"{p[7]:02X}{p[8]:02X}",
    }


def _parse_defrost(p: bytes) -> dict:
    return {"defrost": bool(p[3])}


def _parse_refrigerant_zone(p: bytes) -> dict:
    return {
        "refrigerant_fault_code": p[1],
        "fault_code_numeric": p[2] * 100 + p[3],
        "fault_code_letter_1": chr(p[4]) if p[4] else "",
        "fault_code_letter_2": chr(p[5]) if p[5] else "",
        "multi_zone_running": p[8],
        "multi_zone_running_desc": {
            0: "idle", 1: "both zones", 2: "zone 1", 3: "zone 2",
        }.get(p[8], "unknown"),
        "unknown_status": p[9],
    }


def _parse_compressor_frequency(p: bytes) -> dict:
    return {"compressor_frequency_hz": p[1]}


def _parse_heat_source(p: bytes) -> dict:
    return {
        "dhw_temp_drop_active": p[5] == 7,
        "heat_source": p[6],
        "heat_source_desc": {
            0: "heatpump", 1: "immersion heater", 2: "booster heater",
            3: "booster heater + immersion heater", 4: "boiler",
        }.get(p[6], "unknown"),
        "heat_source_phase": p[7],
        "heat_source_phase_desc": {0: "normal", 1: "hp phase", 2: "heater phase"}.get(p[7], "unknown"),
    }


def _parse_heater_power(p: bytes) -> dict:
    return {
        "input_power_kw_band": p[4],
        "heater_power_kw": p[6],
        "total_input_energy_kwh": _u16(p, 10) / 10.0,
    }


def _parse_zone_setpoints(p: bytes) -> dict:
    return {
        "zone1_target_temp": _temp(p, 1),
        "zone2_target_temp": _temp(p, 3),
        "zone1_flow_setpoint": _temp(p, 5),
        "zone2_flow_setpoint": _temp(p, 7),
        "legionella_setpoint": _temp(p, 9),
        "dhw_max_temp_drop": _half_minus40(p[11]),
        "flow_max_temp": _half_minus40(p[12]),
        "flow_min_temp": _half_minus40(p[13]),
    }


def _parse_zone_outside_temps(p: bytes) -> dict:
    return {
        "zone1_temp": _temp(p, 1),
        "zone2_temp": _temp(p, 3),
        "refrigerant_temp": _temp(p, 8),
        "unknown_temp": _half_minus40(p[10]),
        "outside_temp": _half_minus40(p[11]),
    }


def _parse_water_flow_temps(p: bytes) -> dict:
    return {
        "flow_temp": _temp(p, 1),
        "return_temp": _temp(p, 4),
        "hot_water_temp": _temp(p, 7),
        "hot_water_temp2": _temp(p, 10),
    }


def _parse_boiler_flow_temps(p: bytes) -> dict:
    return {
        "boiler_flow_temp": _temp(p, 1),
        "boiler_return_temp": _temp(p, 4),
    }


def _parse_thermistors_1(p: bytes) -> dict:
    return {
        "zone1_flow_temp": _temp(p, 1),
        "zone1_return_temp": _temp(p, 4),
        "zone2_flow_temp": _temp(p, 7),
        "zone2_return_temp": _temp(p, 10),
    }


def _parse_thermistors_3(p: bytes) -> dict:
    return {
        "mixing_tank_temp": _temp(p, 1),
        "condensing_temp": _temp(p, 4),
        "unknown_temp": _half_minus40(p[6]),
        "outdoor_discharge_temp": p[7],
        "outdoor_liquid_pipe_temp": _half_minus40(p[8]),
        "outdoor_two_phase_pipe_temp": _half_minus40(p[9]),
        "outdoor_suction_temp": _half_minus40(p[10]),
        "outdoor_heat_sink_temp": p[11] - 40,
        "outdoor_compressor_surface_temp": p[12] - 40,
        "superheat": p[13],
        "subcool": _half_minus40(p[14]),
    }


def _parse_external_sources(p: bytes) -> dict:
    return {
        "thermostat1_request": bool(p[1]),
        "thermostat2_request": bool(p[2]),
        "outdoor_thermostat": bool(p[3]),
    }


def _parse_dip_switches(p: bytes) -> dict:
    return {
        "switch1": p[1],
        "switch2": p[3],
        "switch3": p[5],
        "switch4": p[7],
        "switch5": p[9],
        "switch6": p[11],
    }


def _parse_run_hours(p: bytes) -> dict:
    return {
        "unknown": p[1],
        "run_hours": _u24(p, 3),
        "primary_flow_rate": p[10],
    }


def _parse_flow_rate_booster(p: bytes) -> dict:
    return {
        "booster_heater_1_active": bool(p[2]),
        "booster_heater_2_active": bool(p[3]),
        "immersion_heater_active": bool(p[5]),
        "primary_flow_rate_lpm": p[10],
    }


def _parse_pump_status(p: bytes) -> dict:
    return {
        "pump1_on": bool(p[1]),
        "pump2_on": bool(p[4]),
        "pump3_on": bool(p[5]),
        "valve1_on": bool(p[6]),
        "valve2_on": bool(p[7]),
        "mixing_valve_status": p[10],
        "mixing_valve_status_desc": {0: "idle", 1: "closing", 2: "opening", 3: "closed"}.get(p[10], "unknown"),
    }


def _parse_pumps_running(p: bytes) -> dict:
    return {"pump4": p[1], "pump_out13": p[2], "pump_out3": p[3]}


def _parse_operation_flags(p: bytes) -> dict:
    return {
        "power": bool(p[3]),
        "operation_mode": p[4],
        "operation_mode_desc": {
            0: "off", 1: "hot water", 2: "heating", 5: "frost protect", 6: "legionella",
        }.get(p[4], "unknown"),
        "dhw_mode": p[5],
        "dhw_mode_desc": {0: "normal", 1: "economy"}.get(p[5], "unknown"),
        "zone1_op_mode": p[6],
        "zone2_op_mode": p[7],
        "dhw_setpoint": _temp(p, 8),
        "heating_flow_setpoint": _temp(p, 10),
        "unknown_setpoint": _temp(p, 12),
    }


def _parse_various_flags_28(p: bytes) -> dict:
    return {
        "forced_dhw_active": bool(p[3]),
        "holiday_mode": bool(p[4]),
        "prohibit_dhw": bool(p[5]),
        "prohibit_heating_zone1": bool(p[6]),
        "prohibit_cooling_zone1": bool(p[7]),
        "prohibit_heating_zone2": bool(p[8]),
        "prohibit_cooling_zone2": bool(p[9]),
        "server_control_mode_active": bool(p[10]),
    }


def _parse_heating_thermostats(p: bytes) -> dict:
    return {
        "cooling": bool(p[3]),
        "zone1_temp": _temp(p, 4),
        "zone2_temp": _temp(p, 6),
    }


def _parse_energy(p: bytes) -> dict:
    # Byte layout for the 3-byte energy counters is not fully confirmed
    # upstream; treated as little-endian totals in kWh.
    return {
        "year": p[1],
        "month": p[2],
        "day": p[3],
        "heat_energy_kwh": _u24(p, 4),
        "cool_energy_kwh": _u24(p, 7),
        "dhw_energy_kwh": p[10],
    }


def _parse_hardware_configuration(p: bytes) -> dict:
    ftc_versions = {
        0: "FTC2B", 1: "FTC4", 2: "FTC5", 3: "FTC6", 5: "FTC7",
        128: "CAHV1A", 129: "CAHV1B", 130: "CRHV1A", 131: "CRHV1B",
        132: "EAHV1A", 133: "EAHV1B", 134: "QAHV1A", 135: "QAHV1B", 144: "PWFY1",
    }
    return {
        "protocol_version": _bcd(p[1]),
        "model_version": _bcd(p[3]),
        "capacity": p[5],
        "ftc_version": p[6],
        "ftc_version_desc": ftc_versions.get(p[6], "unknown"),
    }


_PARSERS: Dict[int, Callable[[bytes], dict]] = {
    0x01: _parse_datetime,
    0x02: _parse_defrost,
    0x03: _parse_refrigerant_zone,
    0x04: _parse_compressor_frequency,
    0x05: _parse_heat_source,
    0x07: _parse_heater_power,
    0x09: _parse_zone_setpoints,
    0x0B: _parse_zone_outside_temps,
    0x0C: _parse_water_flow_temps,
    0x0D: _parse_boiler_flow_temps,
    0x0E: _parse_thermistors_1,
    0x0F: _parse_thermistors_3,
    0x10: _parse_external_sources,
    0x11: _parse_dip_switches,
    0x13: _parse_run_hours,
    0x14: _parse_flow_rate_booster,
    0x15: _parse_pump_status,
    0x16: _parse_pumps_running,
    0x26: _parse_operation_flags,
    0x28: _parse_various_flags_28,
    0x29: _parse_heating_thermostats,
    0xA1: _parse_energy,
    0xA2: _parse_energy,
    0xC9: _parse_hardware_configuration,
}


def parse_get_response(frame: "Frame | bytes") -> dict:
    """Decode a Get Response (0x62) frame's payload into a dict.

    Accepts either a :class:`~ecodan_protocol.frame.Frame` or a raw 17 byte
    payload. Returns ``{"command": int, "raw": "hex", "data": {...}}``. If no
    specific parser is registered for the command, ``data`` is empty and
    only ``raw`` is populated.
    """
    payload = frame.payload if isinstance(frame, Frame) else bytes(frame)
    if not payload:
        return {"command": None, "raw": "", "data": {}}

    command = payload[0]
    parser = _PARSERS.get(command)
    data = parser(payload) if parser else {}
    return {"command": command, "raw": payload.hex(), "data": data}
