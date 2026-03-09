# Serial Protocol Contract: Pi ↔ Arduino

**Version**: 1.0.0
**Date**: 2026-03-09
**Transport**: UART 115200 baud, 8N1
**Source of truth**: This file is the canonical protocol reference. Both `wtvendo-pi` and `wtvendo-ino` MUST implement exactly what is specified here. This file will be copied to `docs/serial-protocol.md` during implementation.

---

## Packet Format

All communication uses a binary, length-prefixed packet format:

```
Offset  Size   Field       Description
──────  ─────  ──────────  ─────────────────────────────────
0       1      START       Fixed: 0xAA
1       1      CMD         Command type byte
2       1      LENGTH      Payload length (0–64)
3       0–64   PAYLOAD     Command-specific data
3+LEN   1      CHECKSUM    XOR of CMD + LENGTH + all PAYLOAD bytes
```

**Total packet size**: 4 + LENGTH bytes (min 4, max 68).

### Rules

1. **Start marker**: Every packet begins with `0xAA`. Receivers discard bytes until `0xAA` is found.
2. **Length**: Maximum 64 bytes. Receivers MUST reject packets with LENGTH > 64.
3. **Checksum**: XOR of `CMD ^ LENGTH ^ PAYLOAD[0] ^ PAYLOAD[1] ^ ... ^ PAYLOAD[LENGTH-1]`. For LENGTH=0, checksum = `CMD ^ 0x00`.
4. **Byte order**: Multi-byte integers are big-endian (MSB first).
5. **Framing**: Length-based. Receivers do NOT scan for markers inside payload.

---

## Communication Model

- **Pi** is the **master** (initiator). It sends commands and waits for responses.
- **Arduino** is the **slave** (responder). It processes commands and sends exactly one response per command.
- **One message in flight at a time**. Pi MUST NOT send a new command until it receives a response or times out.
- **Pi polling**: Pi polls for Arduino events via `POLL_EVENTS` (0x01) at the end of each main loop iteration.

### Timing

| Parameter         | Value                   | Configurable    |
| ----------------- | ----------------------- | --------------- |
| Response timeout  | 200ms                   | Yes (Pi config) |
| Max retries       | 3                       | Yes (Pi config) |
| Inter-retry delay | 50ms                    | Yes (Pi config) |
| Poll frequency    | ~20Hz (every main loop) | Implicit        |

---

## Command Reference

### Pi → Arduino Commands

#### 0x01 — POLL_EVENTS

Poll for queued unsolicited events on the Arduino.

- **Payload**: none (LENGTH = 0)
- **Response**: One of:
  - `ACK (0xFE)` with LENGTH=0 if no events queued
  - Event packet(s): CMD = event type, payload = event data. Arduino sends the oldest queued event. Pi must poll again for additional events.

#### 0x02 — READ_SENSOR

Read the HC-SR04 ultrasonic distance.

- **Payload**: none (LENGTH = 0)
- **Response**: `ACK (0xFE)` with LENGTH=2, payload = distance in mm (uint16, big-endian). Returns `0xFFFF` if no valid reading.

#### 0x03 — LCD_WRITE

Write text to a specific position on the LCD.

- **Payload** (LENGTH = 2 + text length):
  - Byte 0: row (0–3)
  - Byte 1: col (0–19)
  - Bytes 2+: ASCII text (max 20 chars for one line)
- **Response**: `ACK (0xFE)` with LENGTH=0

#### 0x04 — LCD_CLEAR

Clear the entire LCD display.

- **Payload**: none (LENGTH = 0)
- **Response**: `ACK (0xFE)` with LENGTH=0

#### 0x05 — SERVO_DISPENSE

Activate a dispensing servo for a specified duration.

- **Payload** (LENGTH = 3):
  - Byte 0: channel (0–8)
  - Bytes 1–2: duration in ms (uint16, big-endian)
- **Response**: `ACK (0xFE)` with LENGTH=0, sent AFTER the servo has completed spinning (blocking on Arduino side for this command).

#### 0x06 — SERVO_TRAPDOOR

Open or close the trapdoor servo.

- **Payload** (LENGTH = 1):
  - Byte 0: position — `0x00` = close, `0x01` = open
- **Response**: `ACK (0xFE)` with LENGTH=0

#### 0x07 — GET_KEYPAD

Read the current keypad state (immediate, not queued).

- **Payload**: none (LENGTH = 0)
- **Response**: `ACK (0xFE)` with LENGTH=1, payload = key character ASCII (`'0'`–`'9'`, `'A'`–`'D'`, `'*'`, `'#'`) or `0x00` if no key pressed.

### Arduino → Pi Events (via POLL_EVENTS response)

#### 0x10 — EVENT_KEYPRESS

A key was pressed on the keypad.

- **Payload** (LENGTH = 1): key character ASCII

#### 0x11 — EVENT_OBJECT_DETECTED

The ultrasonic sensor detected an object within threshold.

- **Payload** (LENGTH = 2): distance in mm (uint16, big-endian)

### Response Codes

#### 0xFE — ACK

Command was processed successfully.

- **Payload**: Command-specific (see each command's Response section)

#### 0xFF — NACK / ERROR

Command failed.

- **Payload** (LENGTH = 1): error code
  - `0x01`: Unknown command
  - `0x02`: Invalid payload
  - `0x03`: Hardware fault (servo/sensor failure)
  - `0x04`: Busy (previous command still executing)

---

## Event Buffer (Arduino Side)

- Circular buffer, 16 slots.
- Events are queued when they occur (sensor trigger, keypad press) regardless of current command processing.
- Events are dequeued one at a time via `POLL_EVENTS`.
- If buffer is full, oldest event is overwritten (ring buffer behavior).
- Events are NOT sent unsolicited — only via `POLL_EVENTS` response.

---

## Error Handling

| Scenario                  | Pi Behavior                            | Arduino Behavior                       |
| ------------------------- | -------------------------------------- | -------------------------------------- |
| No response within 200ms  | Retry (up to 3 times)                  | N/A                                    |
| All retries exhausted     | Display error on LCD, preserve session | N/A                                    |
| Invalid checksum received | Discard packet, retry                  | Discard packet, send NACK (0xFF, 0x02) |
| Unknown command received  | N/A                                    | Send NACK (0xFF, 0x01)                 |
| Invalid start marker      | Discard until 0xAA found               | Discard until 0xAA found               |

---

## Example Transaction

**Pi requests ultrasonic reading**:

```
Pi  → Ard: [0xAA] [0x02] [0x00] [0x02]
                    CMD    LEN    CHK (0x02 ^ 0x00 = 0x02)

Ard → Pi:  [0xAA] [0xFE] [0x02] [0x00] [0x64] [0x9A]
                    ACK    LEN    100mm (0x0064)  CHK (0xFE ^ 0x02 ^ 0x00 ^ 0x64 = 0x9A)
```

**Pi writes "15 pts" to LCD row 3, col 0**:

```
Pi  → Ard: [0xAA] [0x03] [0x07] [0x03] [0x00] [0x31] [0x35] [0x20] [0x70] [0x74] [0x73] [CHK]
                    CMD    LEN    row=3  col=0  '1'    '5'    ' '    'p'    't'    's'
```
