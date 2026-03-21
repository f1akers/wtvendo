"""
Serial communication module for WTVendo Pi ↔ Arduino UART protocol.

Implements the binary packet protocol defined in docs/serial-protocol.md:
  - Packet format: [0xAA] [CMD] [LENGTH] [PAYLOAD...] [CHECKSUM]
  - Checksum: XOR of CMD ^ LENGTH ^ PAYLOAD bytes
  - Pi is master (initiator), Arduino is slave (responder)
  - One message in flight at a time with 200ms timeout and 3 retries

Usage:
    from wtvendo.serial_comm import SerialConnection

    conn = SerialConnection()
    conn.open()
    events = conn.poll_events()
    conn.close()
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import serial

from wtvendo.config import (
    BAUD_RATE,
    MAX_RETRIES,
    RETRY_DELAY,
    SERIAL_PORT,
    SERIAL_PORT_CANDIDATES,
    SERIAL_TIMEOUT,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Command Constants (per docs/serial-protocol.md §Command Reference)
# ---------------------------------------------------------------------------

# Pi → Arduino commands
CMD_POLL_EVENTS: int = 0x01
CMD_LCD_WRITE: int = 0x03
CMD_LCD_CLEAR: int = 0x04
CMD_SERVO_DISPENSE: int = 0x05
CMD_SERVO_TRAPDOOR: int = 0x06
CMD_GET_KEYPAD: int = 0x07

# Arduino → Pi events (returned via POLL_EVENTS)
EVENT_KEYPRESS: int = 0x10

# Response codes
ACK: int = 0xFE
NACK: int = 0xFF

# NACK error codes
ERR_UNKNOWN_CMD: int = 0x01
ERR_INVALID_PAYLOAD: int = 0x02
ERR_HARDWARE_FAULT: int = 0x03
ERR_BUSY: int = 0x04

# Protocol constants
START_MARKER: int = 0xAA
MAX_PAYLOAD_LENGTH: int = 64


# ---------------------------------------------------------------------------
# Packet Building & Parsing
# ---------------------------------------------------------------------------


def build_packet(cmd: int, payload: bytes = b"") -> bytes:
    """
    Assemble a serial packet: 0xAA + CMD + LEN + PAYLOAD + XOR checksum.

    Args:
        cmd: Command byte (0x01–0xFF).
        payload: Variable-length payload (0–64 bytes).

    Returns:
        Complete packet as bytes.

    Raises:
        ValueError: If payload exceeds 64 bytes.
    """
    if len(payload) > MAX_PAYLOAD_LENGTH:
        raise ValueError(
            f"Payload length {len(payload)} exceeds max {MAX_PAYLOAD_LENGTH}"
        )

    length = len(payload)

    # Checksum = XOR of CMD ^ LENGTH ^ all PAYLOAD bytes
    checksum = cmd ^ length
    for b in payload:
        checksum ^= b

    return bytes([START_MARKER, cmd, length]) + payload + bytes([checksum])


def parse_packet(buffer: bytes) -> Optional[tuple[int, bytes]]:
    """
    Parse a single packet from a byte buffer, scanning for the start marker.

    Scans for 0xAA, then reads CMD + LENGTH + PAYLOAD + CHECKSUM.
    Validates length (≤64) and checksum.

    Args:
        buffer: Raw bytes received from serial port.

    Returns:
        (cmd, payload) tuple on success, or None if no valid packet found.
    """
    # Scan for start marker
    idx = 0
    while idx < len(buffer):
        if buffer[idx] == START_MARKER:
            break
        idx += 1
    else:
        return None  # No start marker found

    # Need at least: START + CMD + LENGTH + CHECKSUM = 4 bytes minimum
    remaining = len(buffer) - idx
    if remaining < 4:
        return None  # Incomplete header

    cmd = buffer[idx + 1]
    length = buffer[idx + 2]

    if length > MAX_PAYLOAD_LENGTH:
        logger.warning("Packet length %d exceeds max %d — discarding", length, MAX_PAYLOAD_LENGTH)
        return None

    # Total packet size: START(1) + CMD(1) + LEN(1) + PAYLOAD(length) + CHK(1)
    total_size = 4 + length
    if remaining < total_size:
        return None  # Incomplete packet

    payload = buffer[idx + 3 : idx + 3 + length]
    received_checksum = buffer[idx + 3 + length]

    # Compute expected checksum
    expected_checksum = cmd ^ length
    for b in payload:
        expected_checksum ^= b

    if received_checksum != expected_checksum:
        logger.warning(
            "Checksum mismatch: expected 0x%02X, got 0x%02X",
            expected_checksum,
            received_checksum,
        )
        return None

    return (cmd, bytes(payload))


# ---------------------------------------------------------------------------
# Serial Connection
# ---------------------------------------------------------------------------


class SerialConnection:
    """
    Wraps pyserial for Pi ↔ Arduino UART communication.

    Handles connection lifecycle, packet send/receive with timeout and retry,
    and event polling.

    Attributes:
        port: Serial port path (e.g., '/dev/ttyACM0').
        baud_rate: UART baud rate.
        timeout: Response timeout in seconds.
        max_retries: Number of retries on timeout.
        retry_delay: Delay in seconds between retries.
    """

    def __init__(
        self,
        port: str = SERIAL_PORT,
        baud_rate: int = BAUD_RATE,
        timeout: float = SERIAL_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        retry_delay: float = RETRY_DELAY,
    ) -> None:
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._serial: Optional[serial.Serial] = None

    @property
    def is_open(self) -> bool:
        """True if the serial port is currently open."""
        return self._serial is not None and self._serial.is_open

    def open(self) -> None:
        """
        Open the serial connection, auto-detecting the port if needed.

        If the configured port fails, tries each candidate in
        ``SERIAL_PORT_CANDIDATES`` before giving up.

        Raises:
            serial.SerialException: If no candidate port can be opened.
        """
        if self.is_open:
            return

        # Build ordered list: configured port first, then candidates
        ports_to_try: list[str] = [self.port]
        for candidate in SERIAL_PORT_CANDIDATES:
            if candidate not in ports_to_try:
                ports_to_try.append(candidate)

        last_exc: Exception | None = None
        for port in ports_to_try:
            try:
                self._serial = serial.Serial(
                    port=port,
                    baudrate=self.baud_rate,
                    timeout=self.timeout,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                )
                # Pulse DTR low → triggers Uno reset via the DTR capacitor,
                # then wait for the bootloader to finish before communicating.
                self._serial.dtr = False
                time.sleep(2.0)
                self._serial.reset_input_buffer()
                self.port = port
                logger.info("Serial connection opened on %s at %d baud", port, self.baud_rate)
                return
            except serial.SerialException as exc:
                logger.info("Port %s unavailable: %s", port, exc)
                last_exc = exc
                self._serial = None

        raise serial.SerialException(
            f"No Arduino found on any port ({', '.join(ports_to_try)})"
        ) from last_exc

    def close(self) -> None:
        """Close the serial connection gracefully."""
        if self._serial is not None:
            self._serial.close()
            self._serial = None
            logger.info("Serial connection closed")

    def _read_response(self) -> Optional[tuple[int, bytes]]:
        """
        Read and parse a single response packet from Arduino.

        Reads bytes until a complete valid packet is found or timeout occurs.
        The pyserial timeout handles the wait; we accumulate bytes and try to
        parse after each read.

        Returns:
            (cmd, payload) tuple on success, or None on timeout/invalid data.
        """
        if not self.is_open or self._serial is None:
            return None

        buf = bytearray()
        deadline = time.monotonic() + self.timeout

        while time.monotonic() < deadline:
            # Read available bytes (non-blocking due to pyserial timeout)
            waiting = self._serial.in_waiting
            if waiting > 0:
                buf.extend(self._serial.read(waiting))
            else:
                # Small read to advance with timeout
                chunk = self._serial.read(1)
                if chunk:
                    buf.extend(chunk)

            # Try to parse
            result = parse_packet(bytes(buf))
            if result is not None:
                return result

        logger.warning(
            "Read timeout — received %d bytes, no valid packet. Raw: %s",
            len(buf),
            buf.hex(" ") if buf else "<empty>",
        )
        return None

    def send_command(
        self, cmd: int, payload: bytes = b""
    ) -> tuple[int, bytes]:
        """
        Send a command and wait for a response with retry logic.

        Builds a packet, sends it, and waits up to ``timeout`` seconds for a
        response. On timeout, retries up to ``max_retries`` times with
        ``retry_delay`` between attempts.

        Args:
            cmd: Command byte.
            payload: Optional command payload.

        Returns:
            (response_cmd, response_payload) tuple.

        Raises:
            TimeoutError: If all retries are exhausted with no valid response.
            ConnectionError: If serial port is not open.
        """
        if not self.is_open or self._serial is None:
            raise ConnectionError("Serial port is not open")

        packet = build_packet(cmd, payload)

        for attempt in range(1, self.max_retries + 1):
            # Flush input buffer before sending to discard stale data
            self._serial.reset_input_buffer()

            self._serial.write(packet)
            self._serial.flush()

            logger.debug(
                "Sent cmd=0x%02X len=%d (attempt %d/%d)",
                cmd,
                len(payload),
                attempt,
                self.max_retries,
            )

            response = self._read_response()
            if response is not None:
                resp_cmd, resp_payload = response
                logger.debug(
                    "Received response cmd=0x%02X len=%d",
                    resp_cmd,
                    len(resp_payload),
                )
                return response

            if attempt < self.max_retries:
                logger.warning(
                    "Timeout on attempt %d/%d — retrying in %.0fms",
                    attempt,
                    self.max_retries,
                    self.retry_delay * 1000,
                )
                time.sleep(self.retry_delay)

        raise TimeoutError(
            f"No response after {self.max_retries} attempts for cmd 0x{cmd:02X}"
        )

    def read_unsolicited_events(self) -> list[tuple[int, bytes]]:
        """
        Read any unsolicited event packets pushed by the Arduino.

        The Arduino pushes keypad events immediately without waiting for
        a poll.  This method reads all complete packets currently in the
        serial buffer without sending any command.

        Returns:
            List of (event_cmd, event_payload) tuples. Empty if nothing
            available.
        """
        if not self.is_open or self._serial is None:
            return []

        events: list[tuple[int, bytes]] = []
        buf = bytearray()

        # Drain everything currently in the serial buffer
        waiting = self._serial.in_waiting
        if waiting > 0:
            buf.extend(self._serial.read(waiting))

        # Parse all complete packets from the buffer
        while buf:
            result = parse_packet(bytes(buf))
            if result is None:
                break
            cmd, payload = result
            # Calculate how many bytes this packet consumed
            # Find the start marker and skip past the full packet
            start_idx = bytes(buf).index(START_MARKER)
            packet_len = 4 + len(payload)  # START + CMD + LEN + PAYLOAD + CHK
            buf = buf[start_idx + packet_len:]

            if cmd == EVENT_KEYPRESS:
                events.append((cmd, payload))
            else:
                logger.debug("Unsolicited packet cmd=0x%02X (ignored)", cmd)

        return events

    def poll_events(self) -> list[tuple[int, bytes]]:
        """
        Read keypad state from the Arduino via GET_KEYPAD command.

        Instead of relying on the Arduino's event buffer (which accumulates
        ghost presses from electrical noise), this reads the single most
        recent confirmed keypress directly.  Only one key can be pending
        at a time, eliminating queue-based ghost buildup.

        Returns the result in the same (event_cmd, event_payload) format
        so existing state handlers work unchanged.

        Returns:
            List of (event_cmd, event_payload) tuples. Empty list if no key
            pressed or on communication error.
        """
        try:
            resp_cmd, resp_payload = self.send_command(CMD_GET_KEYPAD)
        except (TimeoutError, ConnectionError) as exc:
            logger.warning("poll_events failed: %s", exc)
            return []

        # ACK with payload byte — 0x00 means no key, otherwise ASCII key
        if resp_cmd == ACK and len(resp_payload) >= 1 and resp_payload[0] != 0x00:
            return [(EVENT_KEYPRESS, resp_payload)]

        return []
