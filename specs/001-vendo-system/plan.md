# Implementation Plan: WTVendo — Bottle-for-Supplies Vending System

**Branch**: `001-vendo-system` | **Date**: 2026-03-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-vendo-system/spec.md`

## Summary

A vending machine system that detects used water bottles via an ultrasonic sensor, classifies them using a YOLO model on a Raspberry Pi, awards points per bottle type, and lets students spend points to dispense school supply items via servo-driven coils. The Pi (Python) acts as the brain (classification, session/points logic) and the Arduino (C++) acts as the peripheral controller (sensors, servos, LCD, keypad), communicating over a strict request-response UART serial protocol.

## Technical Context

**Language/Version**: Python 3.9+ (Pi), C/C++ Arduino framework (Arduino)
**Primary Dependencies**: `ultralytics` (YOLO), `pyserial`, `picamera2`/OpenCV (Pi); Adafruit PWM Servo Driver, LiquidCrystal_I2C, Keypad (Arduino)
**Storage**: N/A (volatile session state only, no persistence)
**Testing**: `pytest` (Pi), AUnit/ArduinoFake (Arduino where feasible)
**Target Platform**: Raspberry Pi 4B (Raspberry Pi OS 64-bit, headless), Arduino (AVR/ESP32)
**Project Type**: Embedded multi-device system (Pi + Arduino)
**Performance Goals**: Classification ≤500ms/frame, serial round-trip ≤200ms, end-to-end bottle→points ≤5s, dispense ≤3s
**Constraints**: Arduino SRAM <75%, Pi headless (no GUI), YOLO model not committed to Git, non-blocking Arduino loop (no `delay()`)
**Scale/Scope**: 1 machine, 1 user at a time, 10 bottle classes, 9 dispensing slots, volatile sessions

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle                         | Status  | Notes                                                                                                                                                                |
| --------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| I. Modular Architecture           | ✅ PASS | Arduino: `.ino` orchestration only, logic in `.h`/`.cpp` modules. Pi: Python package with separate modules for serial, inference, logic, config. No file >300 lines. |
| II. Serial Protocol Integrity     | ✅ PASS | 115200 baud, 8N1, packet format with start marker + command byte + payload + checksum. Non-blocking reads. Protocol documented in `docs/serial-protocol.md`.         |
| III. Hardware-Software Separation | ✅ PASS | Pin assignments in `pin_config.h`. Drivers expose abstract interfaces. Pi camera/YOLO behind service interfaces. No magic numbers.                                   |
| IV. Reproducible Environments     | ✅ PASS | Pi: `requirements.txt` with pinned versions, `.python-version`. Arduino: `libraries.txt`. `.gitignore` per subfolder. YOLO model in `models/README.md` with SHA256.  |
| V. Defensive Embedded Coding      | ✅ PASS | No `delay()` in loop, non-blocking timing, graceful serial error handling, try/except on Pi I/O, explicit buffer sizes.                                              |
| VI. Simplicity & YAGNI            | ✅ PASS | Flat structure, minimal abstractions, no speculative features.                                                                                                       |

**Gate result: PASS** — No violations. Proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/001-vendo-system/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (serial protocol contracts)
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
wtvendo-pi/
├── wtvendo/
│   ├── __init__.py
│   ├── main.py              # Entry point, orchestration loop
│   ├── config.py            # Points table, item costs, timeouts, serial config
│   ├── serial_comm.py       # Serial protocol (send/receive, retry, timeout)
│   ├── classifier.py        # YOLO inference service wrapper
│   ├── session.py           # Session state and points management
│   └── lcd_messages.py      # LCD message formatting helpers
├── tests/
│   ├── unit/
│   │   ├── test_serial_comm.py
│   │   ├── test_classifier.py
│   │   ├── test_session.py
│   │   └── test_config.py
│   └── integration/
│       └── test_serial_loop.py
├── models/
│   └── README.md            # YOLO model download instructions, SHA256
├── requirements.txt
├── .python-version
└── .gitignore

wtvendo-ino/
├── wtvendo-ino.ino          # setup() + loop() orchestration only
├── pin_config.h             # All pin/channel assignments
├── serial_comm.h / .cpp     # Serial protocol (parse, respond, queue)
├── servo_control.h / .cpp   # PCA9685 servo driver abstraction
├── sensor.h / .cpp          # HC-SR04 ultrasonic sensor driver
├── lcd_display.h / .cpp     # LCD I2C display abstraction
├── keypad_input.h / .cpp    # 4x4 membrane keypad abstraction
├── libraries.txt            # Required Arduino libraries + versions
└── .gitignore

docs/
└── serial-protocol.md       # Serial protocol specification (shared truth)
```

**Structure Decision**: Two-project embedded layout matching the physical architecture — `wtvendo-pi/` (Python package) and `wtvendo-ino/` (Arduino sketch with modular headers). Shared protocol documentation in `docs/`. This matches the existing repository directory structure.

## Implementation Parts

> Tasks will be split into two parts as requested:

| Part       | Scope                   | Description                                                                                                     |
| ---------- | ----------------------- | --------------------------------------------------------------------------------------------------------------- |
| **Part 1** | `wtvendo-pi/` + `docs/` | Raspberry Pi implementation: serial comm, YOLO classifier, session/points logic, main loop, serial protocol doc |
| **Part 2** | `wtvendo-ino/`          | Arduino implementation: serial comm, servo control, sensor driver, LCD display, keypad input, main sketch       |

## Complexity Tracking

> No constitution violations — table not required.
