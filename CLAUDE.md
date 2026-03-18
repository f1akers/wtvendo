# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WT-Vendo is a Raspberry Pi + Arduino Mega 2560 vending system that uses YOLO computer vision to classify recyclable bottles, award points, and dispense items via servo motors. Two components communicate over UART using a custom binary protocol.

- **Pi (`wtvendo-pi/`)**: Python 3.9, YOLO classifier, session state machine, serial master
- **Arduino (`wtvendo-ino/`)**: C/C++, sensors, servos, LCD, keypad, serial slave

## Commands

### Raspberry Pi

```bash
cd wtvendo-pi
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run
python -m wtvendo.main

# Test
pytest tests/unit/ -v
pytest tests/integration/ -v  # Requires Arduino connected

# Lint
ruff check .
```

### Arduino

Open `wtvendo-ino/wtvendo-ino.ino` in Arduino IDE 2.x. Install libraries listed in `wtvendo-ino/libraries.txt` via Library Manager. Target board: **Arduino Mega 2560**. Compile must produce zero warnings with `-Wall`.

## Architecture

### Serial Protocol (NON-NEGOTIABLE)

The canonical spec is `docs/serial-protocol.md`. Key facts:
- **Baud rate**: 115200, 8N1 on `Serial1` (pins 18/19 on Mega)
- **Packet format**: `[0xAA][CMD][LEN][PAYLOAD (0–64 bytes)][XOR checksum]`
- **Model**: Pi = master (initiates), Arduino = slave (responds). One message in flight at a time.
- **Timing**: 200ms response timeout, 3 retries, 50ms inter-retry delay
- Commands: `POLL_EVENTS(0x01)`, `READ_SENSOR(0x02)`, `LCD_WRITE(0x03)`, `LCD_CLEAR(0x04)`, `SERVO_DISPENSE(0x05)`, `SERVO_TRAPDOOR(0x06)`, `GET_KEYPAD(0x07)`
- Arduino events: `EVENT_KEYPRESS(0x10)`, `EVENT_OBJECT_DETECTED(0x11)` — queued in a 16-slot circular buffer

### Pi Modules (`wtvendo-pi/wtvendo/`)

| File | Responsibility |
|---|---|
| `config.py` | All constants: serial port, YOLO path, timeouts, bottle→points, slot costs |
| `serial_comm.py` | `SerialConnection` — `send_command()`, `poll_events()`, packet build/parse |
| `classifier.py` | `Classifier` — YOLO inference; `PiCamera2Backend` / `OpenCVBackend` |
| `session.py` | `Session` + `SessionState` enum — points, state transitions, inactivity |
| `lcd_messages.py` | Pure functions returning 4×20-char row strings for each screen |
| `main.py` | ~20Hz orchestration loop: poll events → state handler → LCD update |

### Arduino Modules (`wtvendo-ino/`)

| File | Responsibility |
|---|---|
| `pin_config.h` | All hardware pin/address/threshold constants — edit here, nowhere else |
| `serial_comm.h/cpp` | `readPacket()`, `processCommand()`, `EventBuffer` circular queue |
| `sensor.h/cpp` | HC-SR04 non-blocking state machine; enqueues `EVENT_OBJECT_DETECTED` |
| `servo_control.h/cpp` | PCA9685 wrapper; `startDispense()` non-blocking, `trapdoor*()` |
| `keypad_input.h/cpp` | Matrix scan; enqueues `EVENT_KEYPRESS` |
| `lcd_display.h/cpp` | hd44780 wrapper with dirty-check cache |
| `wtvendo-ino.ino` | `setup()` + cooperative `loop()` — no `delay()` anywhere |

### Session State Machine

```
IDLE → (bottle detected) → SCANNING → CLASSIFYING
  ↑                                        ↓ (conf > 0.5)
  └── (inactivity 60s) ←── POINTS_DISPLAY (3s) → ITEM_SELECT
                                                        ↓ (keypad)
                                                   DISPENSING → (servo ACK) → ITEM_SELECT
```

### Constitution Constraints

The project follows a constitution at `.specify/memory/constitution.md`. Key rules to preserve:
- **Max 300 lines per file**
- **No `delay()` in Arduino `loop()`** — all I/O must be non-blocking
- Pin assignments only in `pin_config.h` — no magic numbers inline
- All dependency versions must be pinned in `requirements.txt`
- YOLO model files are excluded from Git; SHA256 documented in `models/README.md`

## Key Configuration

All tunable parameters live in `wtvendo-pi/wtvendo/config.py`:
- Serial: `/dev/ttyACM0`, 115200 baud
- YOLO model: `models/model.pt`, 320×320, confidence 0.5
- Session inactivity timeout: 60s
- Bottle point values and item slot costs/durations

## Hardware

- Pi TX → Mega pin 19 (Serial1 RX); Pi RX ← Mega pin 18 (Serial1 TX); shared ground
- PCA9685 + LCD share I2C bus (SDA=D20, SCL=D21); addresses 0x40 and 0x27
- HC-SR04: TRIG=D22, ECHO=D23; detection threshold 150mm
- Keypad: rows D24–D27, cols D28–D31
- Servos: PCA9685 channels 0–8 (dispense, 360°), channel 9 (trapdoor, 180°)
