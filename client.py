"""
pyserial based client for talking to a Mitsubishi Ecodan (CN105/FTC) heat
pump controller.

Example
-------
    from ecodan_protocol import EcodanClient

    with EcodanClient("/dev/ttyUSB0") as client:
        client.connect()
        print(client.get(0x09))
        client.set_options(power=True, dhw_setpoint=48.0)
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import serial

from .frame import (
    Frame,
    FrameError,
    PacketType,
    HANDSHAKE_FIRST_REQUEST,
    HANDSHAKE_FIRST_RESPONSE,
    HANDSHAKE_SECOND_REQUEST,
    HANDSHAKE_SECOND_RESPONSE,
    CONNECT_REQUEST,
    DISCONNECT_REQUEST,
    SYNC_NORMAL,
)
from .builder import (
    build_get_request,
    build_set_options,
    build_hot_water_and_holiday,
    build_thermostat_setpoints,
)
from .commands import GetCommand
from .parser import parse_get_response

log = logging.getLogger(__name__)

DEFAULT_BAUDRATE = 2400


class EcodanProtocolError(Exception):
    """Raised for protocol level failures (bad response, timeout, NAK, ...)."""


class EcodanClient:
    """Synchronous serial client for the Ecodan CN105/FTC protocol."""

    def __init__(
        self,
        port: str,
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = 2.0,
        serial_kwargs: Optional[dict] = None,
    ):
        kwargs = dict(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
        )
        if serial_kwargs:
            kwargs.update(serial_kwargs)
        self._serial = serial.Serial(**kwargs)

    # -- context manager -----------------------------------------------
    def __enter__(self) -> "EcodanClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        self._write_raw(DISCONNECT_REQUEST)
        if self._serial.is_open:
            self._serial.close()

    # -- low level I/O ---------------------------------------------------
    def _read_exact(self, n: int) -> bytes:
        data = self._serial.read(n)
        log.debug("RX:", data.hex())
        if len(data) != n:
            raise EcodanProtocolError(f"Timed out reading {n} bytes, got {len(data)}")
        return data

    def _write_raw(self, data: bytes) -> None:
        log.debug("TX: %s", data.hex())
        self._serial.write(data)
        self._serial.flush()

    def _read_raw_frame(self) -> bytes:
        """Read one frame (normal or handshake), resynchronising on the sync byte."""
        while True:
            sync = self._read_exact(1)
            if sync[0] == SYNC_NORMAL:
                header = self._read_exact(4)
                length = header[3]
                payload_and_checksum = self._read_exact(length + 1)
                data = sync + header + payload_and_checksum
                log.debug("RX: %s", data.hex())
                return data
            elif sync[0] == 0x02:
                header = self._read_exact(6)
                length = header[5]
                payload_and_checksum = self._read_exact(length + 1)
                data = sync + header + payload_and_checksum
                log.debug("RX: %s", data.hex())
                return data
            # Unknown byte on the wire: drop it and keep looking for a sync byte.
            log.debug("Discarding stray byte 0x%02X while resynchronising", sync[0])

    def _write_frame(self, frame: Frame) -> None:
        self._write_raw(frame.encode())

    def _read_frame(self) -> Frame:
        raw = self._read_raw_frame()
        return Frame.decode(raw)

    # -- connection setup -------------------------------------------------
    def connect(self, retries: int = 3, delay: float = 1.0) -> None:
        """Perform the two-step 0x02 handshake required before Get/Set traffic works.

        Mirrors the sequence the Mitsubishi wifi adapter performs against the
        controller. Safe to call again to re-establish a lost connection.
        """
        for attempt in range(1, retries + 1):
            try:
                self._serial.reset_input_buffer()
                self._write_raw(HANDSHAKE_FIRST_REQUEST)
                response = self._read_exact(len(HANDSHAKE_FIRST_RESPONSE))
                if response != HANDSHAKE_FIRST_RESPONSE:
                    raise EcodanProtocolError(
                        f"Unexpected first handshake response: {response.hex()}"
                    )

                self._write_raw(HANDSHAKE_SECOND_REQUEST)
                response = self._read_exact(len(HANDSHAKE_SECOND_RESPONSE))
                if response != HANDSHAKE_SECOND_RESPONSE:
                    raise EcodanProtocolError(
                        f"Unexpected second handshake response: {response.hex()}"
                    )
                log.debug("Ecodan handshake completed")
                self._write_raw(CONNECT_REQUEST)
                self._read_exact(7)
                return
            except EcodanProtocolError:
                log.debug("Handshake attempt %d/%d failed", attempt, retries)
                if attempt == retries:
                    raise
                time.sleep(delay)

    # -- Get Request / Response -------------------------------------------
    def get_raw(self, command: int) -> Frame:
        """Send a Get Request for ``command`` and return the raw response Frame."""
        self._write_frame(build_get_request(command))
        frame = self._read_frame()
        if frame.packet_type != PacketType.GET_RESPONSE:
            raise EcodanProtocolError(
                f"Expected Get Response (0x62), got 0x{frame.packet_type:02X}"
            )
        return frame

    def get(self, command: int) -> dict:
        """Send a Get Request for ``command`` and return the parsed response."""
        return parse_get_response(self.get_raw(command))

    # -- Set Request / Response -------------------------------------------
    def _send_set(self, frame: Frame) -> bool:
        self._write_frame(frame)
        response = self._read_frame()
        if response.packet_type != PacketType.SET_RESPONSE:
            raise EcodanProtocolError(
                f"Expected Set Response (0x61), got 0x{response.packet_type:02X}"
            )
        return response.command == 0x00

    def set_options(self, **kwargs) -> bool:
        """Send a 0x32 (Update Settings) Set Request. See ``build_set_options``."""
        return self._send_set(build_set_options(**kwargs))

    def set_hot_water_and_holiday(self, **kwargs) -> bool:
        """Send a 0x34 (Hot Water and Holiday Mode) Set Request."""
        return self._send_set(build_hot_water_and_holiday(**kwargs))

    def set_thermostat_setpoints(self, **kwargs) -> bool:
        """Send a 0x35 (Set Thermostat Setpoints) Set Request."""
        return self._send_set(build_thermostat_setpoints(**kwargs))

    # -- descriptive convenience wrappers around get() --------------------
    # Each of these is exactly `self.get(GetCommand.XXX)`; provided so callers
    # don't need to know or look up the underlying command byte.
    def get_date_time(self) -> dict:
        return self.get(GetCommand.DATE_TIME)

    def get_error_codes(self) -> dict:
        return self.get(GetCommand.ERROR_CODES)

    def get_compressor_frequency(self) -> dict:
        return self.get(GetCommand.COMPRESSOR_FREQUENCY)

    def get_heat_source(self) -> dict:
        return self.get(GetCommand.HEAT_SOURCE)

    def get_heater_power(self) -> dict:
        return self.get(GetCommand.HEATER_POWER)

    def get_zone_setpoints(self) -> dict:
        return self.get(GetCommand.ZONE_SETPOINTS)

    def get_zone_and_outside_temperatures(self) -> dict:
        return self.get(GetCommand.ZONE_AND_OUTSIDE_TEMPERATURES)

    def get_water_flow_temperatures(self) -> dict:
        return self.get(GetCommand.WATER_FLOW_TEMPERATURES)

    def get_run_hours(self) -> dict:
        return self.get(GetCommand.RUN_HOURS)

    def get_pump_status(self) -> dict:
        return self.get(GetCommand.PUMP_STATUS)

    def get_operation_mode(self) -> dict:
        return self.get(GetCommand.OPERATION_MODE_FLAGS)

    def get_zone_temperatures(self) -> dict:
        return self.get(GetCommand.ZONE_TEMPERATURES)

    def get_consumed_energy(self) -> dict:
        return self.get(GetCommand.CONSUMED_ENERGY)

    def get_delivered_energy(self) -> dict:
        return self.get(GetCommand.DELIVERED_ENERGY)

    def get_hardware_configuration(self) -> dict:
        return self.get(GetCommand.HARDWARE_CONFIGURATION)
