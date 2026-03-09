<!--
  Sync Impact Report
  ==================
  Version change: 0.0.0 → 1.0.0 (initial ratification)
  Modified principles: N/A (initial version)
  Added sections:
    - Core Principles (6 principles)
    - Technology Stack & Constraints
    - Development Workflow
    - Governance
  Removed sections: N/A
  Templates requiring updates:
    - .specify/templates/plan-template.md ✅ no changes needed (generic)
    - .specify/templates/spec-template.md ✅ no changes needed (generic)
    - .specify/templates/tasks-template.md ✅ no changes needed (generic)
    - .specify/templates/checklist-template.md ✅ no changes needed (generic)
    - .specify/templates/agent-file-template.md ✅ no changes needed (generic)
  Follow-up TODOs: None
-->

# WT-Vendo Constitution

## Core Principles

### I. Modular Architecture

All code MUST be organized into well-defined, single-responsibility
modules:

- **Arduino (`wtvendo-ino`)**: The `.ino` entry point MUST only
  contain `setup()` and `loop()` orchestration. All functional logic
  MUST reside in dedicated header (`.h`) and implementation (`.cpp`)
  files grouped by concern (e.g., `serial_comm.h`, `motor_control.h`,
  `sensors.h`).
- **Raspberry Pi (`wtvendo-pi`)**: Python code MUST follow a package
  layout with `__init__.py` modules. Separate modules MUST exist for
  serial communication, YOLO inference, business logic, and
  configuration.
- No file MUST exceed 300 lines. If it does, it MUST be split.

**Rationale**: Modular code enables independent development, testing,
and maintenance of hardware-coupled components that are otherwise
difficult to debug as monoliths.

### II. Serial Protocol Integrity (NON-NEGOTIABLE)

All UART (RX-TX) communication between the Raspberry Pi and Arduino
MUST adhere to these rules:

- Baud rate MUST be **115200** on both devices—defined as a shared
  constant (`BAUD_RATE`) in both codebases.
- Serial configuration MUST be **8N1** (8 data bits, no parity,
  1 stop bit).
- Every message MUST use a defined packet format with a start marker,
  command byte, payload, and checksum/terminator.
- Both sides MUST implement non-blocking serial reads with timeouts
  (Arduino: `Serial.available()` polling; Pi: `pyserial` with
  `timeout` parameter).
- A message protocol document MUST be maintained at
  `docs/serial-protocol.md` specifying all command codes, payload
  formats, and expected responses.

**Rationale**: Mismatched baud rates or undocumented protocols are the
#1 cause of silent failures in embedded multi-device systems. A single
source of truth for the protocol prevents integration defects.

### III. Hardware-Software Separation

Hardware interaction code MUST be isolated from business logic:

- **Arduino**: Hardware pin assignments MUST be defined in a single
  `pin_config.h` file. Actuator/sensor drivers MUST expose abstract
  interfaces (e.g., `void dispenseItem(uint8_t slot)`) that hide
  GPIO details.
- **Pi**: Camera capture and YOLO model inference MUST be wrapped
  behind a service interface. No raw OpenCV or ultralytics calls in
  the main application loop.
- All magic numbers (pin numbers, thresholds, timing constants) MUST
  be defined as named constants, never inline literals.

**Rationale**: Separating hardware concerns enables unit testing of
logic without physical hardware and simplifies porting to different
pin configurations or sensor models.

### IV. Reproducible Environments

Every component MUST declare its dependencies explicitly:

- **Pi (`wtvendo-pi`)**: A `requirements.txt` MUST list all Python
  packages with pinned versions (e.g., `pyserial==3.5`). A
  `.python-version` or equivalent MUST declare Python 3.9+.
- **Arduino (`wtvendo-ino`)**: A `libraries.txt` or comment block in
  the main `.ino` MUST list all required Arduino libraries and their
  tested versions.
- **Both**: A `.gitignore` in each subfolder MUST exclude build
  artifacts, IDE-specific files, and generated binaries.
- YOLO model files (`*.pt`) MUST NOT be committed to Git. They MUST
  be documented in a `models/README.md` with download instructions,
  SHA256 hashes, and version metadata.

**Rationale**: Reproducibility prevents "works on my machine" failures
across development and deployment on the target Raspberry Pi hardware.

### V. Defensive Embedded Coding

All code targeting microcontrollers or real-time loops MUST follow
defensive practices:

- No `delay()` calls in Arduino `loop()` except during
  initialization. Use non-blocking timing (`millis()` comparisons).
- All serial reads MUST handle incomplete, corrupted, or unexpected
  data gracefully (discard and log, never crash).
- Watchdog timers SHOULD be enabled on Arduino to recover from hangs.
- Python serial code on Pi MUST use `try/except` around all I/O
  operations and implement reconnection logic.
- Buffer sizes MUST be explicitly defined and overflow MUST be
  handled.

**Rationale**: Embedded systems run unattended. Defensive coding
ensures the vending machine recovers from transient faults without
manual intervention.

### VI. Simplicity & YAGNI

- Start with the simplest implementation that fulfills the
  requirement. Do not add abstraction layers, design patterns, or
  features until a concrete need is demonstrated.
- Each new file, class, or module MUST have a stated purpose. If it
  exists only for "future flexibility," it MUST be removed.
- Prefer flat structures over deep nesting in both Arduino and Python
  code.

**Rationale**: Embedded projects with tight resource constraints
benefit most from minimal, readable code. Premature abstraction
increases cognitive load and binary size.

## Technology Stack & Constraints

| Component             | Technology          | Version/Details                |
| --------------------- | ------------------- | ------------------------------ |
| Microcontroller       | Arduino (AVR/ESP32) | Arduino IDE 2.x / PlatformIO   |
| Single-board computer | Raspberry Pi 4B     | Raspberry Pi OS (64-bit)       |
| Pi language           | Python              | 3.9+                           |
| Arduino language      | C/C++               | Arduino framework              |
| Object detection      | YOLOv8 Nano         | `yolo26n.pt` via `ultralytics` |
| Serial communication  | UART RX-TX          | 115200 baud, 8N1               |
| Serial library (Pi)   | `pyserial`          | 3.5+                           |
| Camera                | Pi Camera / USB     | Via `picamera2` or OpenCV      |

**Constraints**:

- Pi MUST run headless in production; no GUI dependencies unless
  explicitly scoped for debug mode.
- Arduino SRAM usage MUST stay below 75% to leave headroom for stack.
- YOLO inference MUST complete within 500ms per frame on Pi 4B to
  maintain acceptable vending response time.
- Total serial round-trip (command + response) MUST complete within
  200ms under normal conditions.

## Development Workflow

1. **Branching**: All work MUST happen on feature branches named
   `<issue#>-<short-description>`. Direct pushes to `main` are
   forbidden.
2. **Commit messages**: MUST follow Conventional Commits format
   (e.g., `feat(ino): add motor driver module`,
   `fix(pi): handle serial timeout`). Scope MUST be `ino` or `pi`.
3. **Pre-merge checks**:
   - Arduino code MUST compile without warnings (`-Wall`).
   - Python code MUST pass `ruff` linting with zero errors.
   - Serial protocol changes MUST update `docs/serial-protocol.md`
     before merge.
4. **Testing**:
   - Python modules MUST have unit tests runnable via `pytest`.
   - Arduino logic modules SHOULD have desktop-compilable unit tests
     where feasible (e.g., via `AUnit` or `ArduinoFake`).
   - Integration tests for serial communication SHOULD use a loopback
     or mock serial device.
5. **Deployment**: Pi deployment MUST use a documented script or
   `Makefile` target that installs dependencies from
   `requirements.txt` and validates the YOLO model file exists.

## Governance

This constitution is the authoritative reference for all WT-Vendo
development decisions. It supersedes informal practices, verbal
agreements, and ad-hoc tooling choices.

- **Amendments**: Any change to this constitution MUST be proposed via
  a pull request with a clear rationale. The version MUST be
  incremented per semantic versioning (see below).
- **Versioning**: MAJOR for principle removals/redefinitions, MINOR
  for new principles or material expansions, PATCH for wording
  clarifications.
- **Compliance**: Every pull request review MUST verify that changes
  do not violate constitution principles. Violations MUST be resolved
  before merge or granted an explicit, documented exception with an
  expiry date.
- **Guidance file**: Runtime development guidance lives in
  `.specify/memory/agent-guidelines.md` and MUST stay consistent
  with this constitution.

**Version**: 1.0.0 | **Ratified**: 2026-03-09 | **Last Amended**: 2026-03-09
