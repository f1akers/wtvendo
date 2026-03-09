# Tasks: WTVendo — Bottle-for-Supplies Vending System

**Input**: Design documents from `/specs/001-vendo-system/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: Not explicitly requested — test directory scaffolding is included but test implementation tasks are deferred. Add test tasks if TDD is desired.

**Organization**: Tasks grouped by user story to enable independent implementation and testing. Each phase shows **Part 1 (Pi)** and **Part 2 (Arduino)** tasks to align with the two-session implementation plan from plan.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US4, US5)
- **Part 1**: Raspberry Pi (`wtvendo-pi/`) + shared docs (`docs/`)
- **Part 2**: Arduino (`wtvendo-ino/`)
- US3 (Serial Communication, P1) maps to **Phase 2 (Foundational)** since all user stories depend on it

## Path Conventions

- Pi source: `wtvendo-pi/wtvendo/`
- Pi models: `wtvendo-pi/models/`
- Pi tests: `wtvendo-pi/tests/`
- Arduino source: `wtvendo-ino/`
- Shared docs: `docs/`

## Two-Part Plan Overview

| Part       | Scope                   | Phases                                                        | Key Deliverables                                                  |
| ---------- | ----------------------- | ------------------------------------------------------------- | ----------------------------------------------------------------- |
| **Part 1** | `wtvendo-pi/` + `docs/` | Setup → Foundational → US1 → US2 → US5 → Integration → Polish | config, serial_comm, classifier, session, lcd_messages, main.py   |
| **Part 2** | `wtvendo-ino/`          | Setup → Foundational → US1 → US2 → US4 → Integration → Polish | pin_config, serial_comm, sensor, servo_control, keypad, lcd, .ino |

Both parts can proceed **in parallel** within each phase — Pi tasks never depend on Arduino tasks and vice versa. The serial protocol contract (`docs/serial-protocol.md`) is the only shared artifact.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize both project directories with scaffolding, dependency manifests, and shared protocol documentation.

### Part 1 (Pi)

- [x] T001 Create wtvendo-pi/ project structure with wtvendo/**init**.py package marker, .python-version (3.9), and .gitignore (_.pyc, **pycache**/, .venv/, models/_.pt, models/\*.bin) per plan.md project structure in wtvendo-pi/
- [x] T002 [P] Create dependency manifest with pinned versions for ultralytics (>=8.0), pyserial (>=3.5), picamera2 (>=0.3), opencv-python-headless (>=4.8), and numpy (>=1.24) in wtvendo-pi/requirements.txt
- [x] T003 [P] Create YOLO model placeholder with download URL, SHA256 hash field, model version, export instructions (NCNN at 320×320), and list of 10 class names per research.md §3 in wtvendo-pi/models/README.md

### Part 2 (Arduino)

- [x] T004 [P] Create wtvendo-ino/ project scaffolding with .gitignore (build artifacts) and libraries.txt listing Adafruit PWM Servo Driver Library >=3.0, hd44780 >=1.3, Keypad >=3.1, and Wire (built-in) per research.md §7 in wtvendo-ino/

### Shared

- [x] T005 [P] Publish serial protocol contract from specs/001-vendo-system/contracts/serial-protocol.md to docs/serial-protocol.md as the canonical shared reference

---

## Phase 2: Foundational — Serial Protocol & Core Configuration (US3)

**Purpose**: Implement the serial communication backbone and core configuration that ALL user stories depend on. Maps to **User Story 3** (Serial Communication Between Pi and Arduino, Priority: P1).

**⚠️ CRITICAL**: No user story implementation can begin until this phase is complete.

### Part 1 (Pi)

- [x] T006 Implement configuration module with all system constants: SERIAL_PORT ("/dev/ttyACM0"), BAUD_RATE (115200), SERIAL_TIMEOUT (0.2s), MAX_RETRIES (3), RETRY_DELAY (0.05s), CONFIDENCE_THRESHOLD (0.5), INACTIVITY_TIMEOUT (60s), CAMERA_BACKEND ("picamera2"), MODEL_PATH ("models/yolo26n.pt"), IMAGE_SIZE (320), BOTTLE_POINTS dict mapping 10 class names to point values per data-model.md §1, and ITEM_SLOTS dict mapping slots 1–9 to (item_name, cost, spin_duration_ms) per data-model.md §2 in wtvendo-pi/wtvendo/config.py
- [x] T007 Implement serial communication module with: build_packet(cmd, payload) assembling 0xAA + CMD + LEN + PAYLOAD + XOR checksum, parse_packet(buffer) with start marker scanning and checksum validation, SerialConnection class wrapping pyserial with open/close/is_open, send_command(cmd, payload) with 200ms timeout and 3 retries with 50ms inter-retry delay returning response or raising TimeoutError, poll_events() helper sending POLL_EVENTS (0x01) and returning list of (event_cmd, event_payload) tuples, and all command constants (POLL_EVENTS=0x01 through NACK=0xFF) per contracts/serial-protocol.md in wtvendo-pi/wtvendo/serial_comm.py

### Part 2 (Arduino)

- [x] T008 [P] Create pin configuration header with all hardware assignments: TRIG_PIN (22), ECHO_PIN (23), KEYPAD_ROW_PINS {24,25,26,27}, KEYPAD_COL_PINS {28,29,30,31}, PCA9685_ADDR (0x40), LCD_ADDR (0x27), SERIAL_BAUD (115200), DEBUG_BAUD (9600), TRAPDOOR_CHANNEL (9), DISPENSE_CHANNELS (0–8), sensor thresholds (DETECT_THRESHOLD_MM=150, EXIT_THRESHOLD_MM=200, CONSECUTIVE_READINGS=3), and servo PWM values (TRAPDOOR_OPEN_US=2400, TRAPDOOR_CLOSE_US=600, DISPENSE_FWD_US=1700, DISPENSE_STOP_US=1500) per research.md §4 and §6 in wtvendo-ino/pin_config.h
- [x] T009 [P] Implement serial communication module with: packet parser (readPacket() scanning for 0xAA start marker, validating length ≤64, computing and checking XOR checksum), response builder (sendAck(payload), sendNack(errorCode), sendEvent(cmd, payload)), command dispatch interface (processCommand(cmd, payload) stub with switch/case routing), and 16-slot circular event buffer (EventBuffer class with enqueue/dequeue/isEmpty, ring-buffer overwrite on full) reading from/writing to Serial1 per contracts/serial-protocol.md in wtvendo-ino/serial_comm.h and wtvendo-ino/serial_comm.cpp

**Checkpoint**: Serial protocol is functional on both sides. Pi can build/send commands and parse responses with retry. Arduino can parse commands, build responses, and buffer events. Configuration is centralized. All user story work can now begin.

---

## Phase 3: User Story 1 — Insert Bottle & Earn Points (Priority: P1) 🎯 MVP

**Goal**: Student places a bottle in the intake → HC-SR04 detects it → Pi captures image and classifies via YOLO → points awarded based on bottle class → LCD shows result → trapdoor opens to clear bottle.

**Independent Test**: Place a known bottle type (e.g., "large bottled water") into the intake. Verify the sensor triggers detection, Pi classifies it correctly, correct points are awarded and displayed on the LCD, and the trapdoor servo opens then closes.

### Part 1 (Pi)

- [x] T010 [P] [US1] Implement classifier module with: CameraBackend abstract base class defining capture() → numpy array, PiCamera2Backend using picamera2.capture_array() for single-frame on-demand capture, OpenCVBackend using cv2.VideoCapture(0) as USB webcam fallback, create_camera(backend_name) factory function selecting backend from CAMERA_BACKEND config, Classifier class loading YOLO model from MODEL_PATH with SHA256 verification (read hash from models/README.md, compare with hashlib.sha256), and classify(frame) method running model.predict(frame, imgsz=IMAGE_SIZE, conf=CONFIDENCE_THRESHOLD) returning (class_name, confidence) tuple or None if no detection per research.md §3 in wtvendo-pi/wtvendo/classifier.py
- [x] T011 [P] [US1] Implement session module with: SessionState enum (IDLE, SCANNING, CLASSIFYING, POINTS_DISPLAY, ITEM_SELECT, DISPENSING), Session class with points (int, init 0), state (SessionState, init IDLE), last_activity (time.monotonic()), active (bool) properties, add_points(bottle_class) method looking up BOTTLE_POINTS and accumulating, can_afford(slot) checking points >= ITEM_SLOTS[slot].cost, deduct_points(slot) subtracting cost (only call after ACK), reset() zeroing points and setting state to IDLE, and state transition methods: start_scan() IDLE→SCANNING, start_classify() SCANNING→CLASSIFYING, classification_done(class_name, confidence) CLASSIFYING→POINTS_DISPLAY with add_points, classification_failed() CLASSIFYING→IDLE, touch() resetting last_activity per data-model.md §3 in wtvendo-pi/wtvendo/session.py
- [x] T012 [P] [US1] Implement LCD message formatting helpers with functions returning list of 4 strings (one per LCD row, max 20 chars each): format_welcome() "Insert a bottle to" / "start!" / "" / "", format_scanning() "Scanning bottle..." / "" / "" / "", format_classified(class_name, points, total) showing bottle type, points earned this scan, and session total, format_points(total) showing accumulated balance, format_item_menu(slots, points) showing available items with costs and current balance, format_dispensing(item_name) "Dispensing..." / item name, format_error(message) generic error display, format_insufficient(item_cost, balance) "Not enough points", format_timeout_warning() "Session ending...", format_comm_error() "Communication error" — all padded/truncated to exactly 20 chars per line in wtvendo-pi/wtvendo/lcd_messages.py

### Part 2 (Arduino)

- [x] T013 [P] [US1] Implement non-blocking HC-SR04 ultrasonic sensor driver with: SensorState enum (IDLE, TRIGGER, WAIT_ECHO, READ), Sensor class initialized with TRIG_PIN and ECHO_PIN from pin_config.h, update() called every loop (checks 100ms interval via millis()), state machine: IDLE→TRIGGER (set trig HIGH 10µs then LOW), TRIGGER→WAIT_ECHO (wait for echo rising), WAIT_ECHO→READ (measure echo duration, convert to mm via duration\*0.343/2), READ→IDLE (store reading), getDistanceMM() returning last valid reading, 3-consecutive-readings-under-150mm detection with 200mm exit hysteresis, isObjectDetected() returning true when threshold met, and auto-enqueue EVENT_OBJECT_DETECTED (0x11) with uint16 distance payload to serial event buffer when detection triggers per research.md §4 in wtvendo-ino/sensor.h and wtvendo-ino/sensor.cpp
- [x] T014 [P] [US1] Implement PCA9685 servo control with: ServoControl class wrapping Adafruit_PWMServoDriver at PCA9685_ADDR, init() setting 50Hz frequency, trapdoorOpen() writing TRAPDOOR_OPEN_US to TRAPDOOR_CHANNEL, trapdoorClose() writing TRAPDOOR_CLOSE_US to TRAPDOOR_CHANNEL, startDispense(channel, duration_ms) starting spin at DISPENSE_FWD_US on channel 0–8 and recording start time, update() checking millis() elapsed and stopping at DISPENSE_STOP_US when duration expires (non-blocking), isDispensing() returning true while spin active, and microsecondsToPWM(us) helper converting microseconds to 12-bit PCA9685 PWM value at 50Hz per research.md §4 in wtvendo-ino/servo_control.h and wtvendo-ino/servo_control.cpp

**Checkpoint**: Bottle detection → classification → points pipeline works. Trapdoor clears bottles. The core MVP value loop (exchanging bottles for points) is functional and independently testable.

---

## Phase 4: User Story 2 — Select & Dispense a School Supply Item (Priority: P1) 🎯 MVP

**Goal**: Student uses membrane keypad to select an item → LCD shows available items and costs → if enough points, servo dispenses item → points deducted after ACK.

**Independent Test**: Pre-load a session with known point balance. Press keypad key for an item. Verify LCD shows items, correct servo activates, item dispenses, points are deducted, and updated balance is shown.

### Part 2 (Arduino)

- [x] T015 [P] [US2] Implement non-blocking 4×4 membrane keypad driver with: KeypadInput class using Keypad.h library with KEYPAD_ROW_PINS and KEYPAD_COL_PINS from pin_config.h, 4×4 key map matching physical layout ('1','2','3','A' / '4','5','6','B' / '7','8','9','C' / '\*','0','#','D'), update() calling getKey() each loop iteration (non-blocking), key-to-slot mapping (chars '1'–'9' → slot numbers 1–9), isItemKey(key) returning true for '1'–'9', getSlotFromKey(key) returning slot number, and auto-enqueue EVENT_KEYPRESS (0x10) with key ASCII byte payload to serial event buffer when key detected per research.md §4 in wtvendo-ino/keypad_input.h and wtvendo-ino/keypad_input.cpp

### Part 1 (Pi)

- [x] T016 [P] [US2] Extend session state machine with: POINTS_DISPLAY → ITEM_SELECT transition (auto-advance after 3s timeout or any keypad event), ITEM_SELECT state handler processing EVENT_KEYPRESS events (extract key char, map '1'–'9' to slot via int(key), validate can_afford(slot), reject with "Not enough points" LCD message if insufficient), ITEM_SELECT → DISPENSING transition (send SERVO_DISPENSE command with channel=slot-1 and duration_ms from ITEM_SLOTS), DISPENSING state waiting for ACK response then calling deduct_points(slot) (post-ACK deduction per research.md §5 critical rule), DISPENSING → ITEM_SELECT if points > 0 after deduction, DISPENSING → IDLE if points == 0 (session ends naturally), ITEM_SELECT → SCANNING on EVENT_OBJECT_DETECTED (student inserts another bottle), and touch() call on every interaction to reset inactivity timer in wtvendo-pi/wtvendo/session.py

**Checkpoint**: Full MVP loop works end-to-end: insert bottle → earn points → select item → dispense → points deducted. Students can exchange bottles for school supplies. US1 + US2 together form the minimum viable product.

---

## Phase 5: User Story 4 — LCD Status Display (Priority: P2)

**Goal**: LCD continuously shows contextual information at every state transition — welcome when idle, status while scanning, results after classification, menu during selection, progress during dispensing, errors when problems occur.

**Independent Test**: Walk through the full flow (idle → insert bottle → classify → show points → select item → dispense) and verify each LCD state transition displays the correct message within 1 second.

### Part 2 (Arduino)

- [x] T017 [US4] Implement LCD I2C display driver with: LcdDisplay class using hd44780 library with hd44780_I2Cexp I/O class for auto-detect at LCD_ADDR, init() calling begin(20, 4) for 20×4 display, 4-line content cache (char lineCache[4][21]) for dirty-checking changed content only, writeLine(row, col, text) comparing against cache and only writing changed characters via setCursor/print (overwrite-in-place, no full clear), clearDisplay() calling clear() and resetting cache, 200ms minimum update interval enforced via millis() rate-limiting (skip writes if called too frequently), and backlight control via backlight()/noBacklight() per research.md §4 in wtvendo-ino/lcd_display.h and wtvendo-ino/lcd_display.cpp

**Checkpoint**: LCD provides clear, flicker-free user feedback at every step of the interaction. System is usable by students without external instructions, guided solely by LCD prompts.

---

## Phase 6: User Story 5 — Session Lifecycle (Priority: P2)

**Goal**: Sessions start on first successful classification, accumulate points across multiple bottle insertions, automatically end after configurable inactivity timeout, and reset cleanly for the next student.

**Independent Test**: Insert multiple bottles and verify points accumulate across insertions. Wait for inactivity timeout (60s) and verify points reset to zero and LCD returns to welcome screen.

### Part 1 (Pi)

- [x] T018 [US5] Add session lifecycle management: track last_activity via time.monotonic() reset on every user interaction (bottle detection, keypad press, dispense completion), check_timeout() method comparing elapsed time against INACTIVITY_TIMEOUT each main loop tick, timeout triggers transition from any state → IDLE with points zeroed and session.active set to False, send LCD_CLEAR + welcome message on session end, handle edge case of timeout during DISPENSING state (complete current dispense ACK cycle before resetting), handle edge case of timeout during CLASSIFYING (cancel and reset), and emit session start (first classification) and session end events for optional future logging in wtvendo-pi/wtvendo/session.py

**Checkpoint**: Sessions have proper lifecycle management. Machine automatically resets for the next student after inactivity. Points don't persist indefinitely.

---

## Phase 7: Integration — Main Entry Points

**Purpose**: Wire all modules together into the main orchestration entry points for both platforms. This is where the full system comes alive.

### Part 1 (Pi)

- [x] T019 Implement Pi main entry point with: startup sequence (load and verify YOLO model SHA256, initialize camera backend, open serial connection with retry, create Session instance, send LCD welcome message), synchronous polling main loop at ~20Hz (poll_events() → process received events → run current state handler → send LCD updates → time.sleep(0.005)), state dispatch dict mapping SessionState → handler function (idle_handler: poll sensor events and transition on detection; scanning_handler: capture camera frame and transition to classifying; classifying_handler: run YOLO inference, award points or reject, command trapdoor open→close; points_display_handler: send LCD points message, auto-advance timer; item_select_handler: send LCD menu, process keypad events; dispensing_handler: send servo command, wait for ACK, deduct points), check_timeout() call every tick, graceful shutdown on KeyboardInterrupt (close serial, release camera), and entry via `if __name__ == "__main__"` / `python -m wtvendo.main` in wtvendo-pi/wtvendo/main.py

### Part 2 (Arduino)

- [x] T020 [P] Implement Arduino main sketch with: setup() initializing Serial (debug at DEBUG_BAUD), Serial1 (Pi at SERIAL_BAUD), Wire.begin() for I2C, ServoControl.init(), LcdDisplay.init() with welcome message, Sensor initialization with pin modes, KeypadInput initialization; loop() with cooperative non-blocking scheduling: serial packet processing every iteration (check Serial1.available(), parse packet, dispatch command), keypad update() every iteration, sensor update() with internal 100ms millis() check, servo update() for non-blocking spin tracking; command dispatcher switch/case on CMD byte: POLL_EVENTS (0x01) → dequeue one event from buffer or send empty ACK, READ_SENSOR (0x02) → send ACK with uint16 distance, LCD_WRITE (0x03) → extract row/col/text and call writeLine(), LCD_CLEAR (0x04) → call clearDisplay(), SERVO_DISPENSE (0x05) → extract channel/duration and call startDispense() then send ACK after completion, SERVO_TRAPDOOR (0x06) → call trapdoorOpen()/trapdoorClose() based on payload and send ACK, GET_KEYPAD (0x07) → send ACK with current key or 0x00; all string literals using F() macro, zero use of delay() or String class, SRAM budget tracking via comments per research.md §4 in wtvendo-ino/wtvendo-ino.ino

**Checkpoint**: Both platforms run their main loops. Pi orchestrates the full session lifecycle; Arduino responds to commands and queues events. The complete system is operational end-to-end.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, test scaffolding, and full-system validation.

- [x] T021 [P] Add module-level docstrings explaining purpose and usage, function/method docstrings with parameter and return descriptions, and inline comments for non-obvious logic (checksum calculation, state transitions, confidence thresholding) to all Pi source files in wtvendo-pi/wtvendo/ (config.py, serial_comm.py, classifier.py, session.py, lcd_messages.py, main.py)
- [x] T022 [P] Add file header comments with purpose and dependencies, function-level Doxygen-style comments (brief, param, return), and explanatory comments for hardware-specific magic values (PWM pulse widths, timing constants, I2C addresses, pin assignments) to all Arduino source files in wtvendo-ino/ (pin_config.h, serial_comm.h/.cpp, sensor.h/.cpp, servo_control.h/.cpp, keypad_input.h/.cpp, lcd_display.h/.cpp, wtvendo-ino.ino)
- [x] T023 [P] Create wtvendo-pi/tests/ directory structure with unit/**init**.py and integration/**init**.py per plan.md project structure (test scaffolding for future test implementation) in wtvendo-pi/tests/
- [ ] T024 Validate complete system by executing all quickstart.md test flow scenarios: power-on welcome display, bottle detection triggering classification, points award and LCD update, keypad item selection, servo dispensing, insufficient points rejection, session inactivity timeout and reset, and serial communication error handling

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) ─────────────► Phase 2 (Foundational / US3)
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
            Phase 3 (US1)       Phase 5 (US4)         (independent)
                    │                   │
                    ▼                   │
            Phase 4 (US2)               │
                    │                   │
            Phase 6 (US5)               │
                    │                   │
                    └───────┬───────────┘
                            ▼
                    Phase 7 (Integration)
                            │
                            ▼
                    Phase 8 (Polish)
```

### Key Ordering Rules

- **Phase 2 → Phase 3**: Serial protocol and config must exist before any story implementation
- **Phase 3 → Phase 4**: US2 extends session.py created in US1
- **Phase 3 → Phase 6**: US5 extends session.py created in US1
- **Phase 2 → Phase 5**: US4 (LCD driver) only depends on Foundational, can start in parallel with Phase 3
- **Phase 7**: Requires all modules from Phases 3–6 to exist for wiring

### Part 1 ↔ Part 2 Independence

Pi and Arduino tasks within the **same phase** are always parallelizable:

| Phase   | Part 1 (Pi) Tasks | Part 2 (Arduino) Tasks | Can Parallel? |
| ------- | ----------------- | ---------------------- | ------------- |
| Phase 1 | T001, T002, T003  | T004                   | ✅ Yes        |
| Phase 2 | T006, T007        | T008, T009             | ✅ Yes        |
| Phase 3 | T010, T011, T012  | T013, T014             | ✅ Yes        |
| Phase 4 | T016              | T015                   | ✅ Yes        |
| Phase 5 | —                 | T017                   | N/A           |
| Phase 6 | T018              | —                      | N/A           |
| Phase 7 | T019              | T020                   | ✅ Yes        |
| Phase 8 | T021, T023        | T022                   | ✅ Yes        |

### Parallel Opportunities Within Phases

| Phase   | Parallel Groups                                                   |
| ------- | ----------------------------------------------------------------- |
| Phase 1 | T001 first → then T002 + T003 + T004 + T005 all parallel          |
| Phase 2 | T006 first (config) → T007 after; T008 + T009 parallel with T006  |
| Phase 3 | ALL tasks (T010–T014) in parallel — all different files/projects  |
| Phase 4 | ALL tasks (T015 + T016) in parallel — different projects          |
| Phase 7 | T019 + T020 in parallel — different projects                      |
| Phase 8 | T021 + T022 + T023 in parallel; T024 last (needs everything done) |

---

## Parallel Example: Phase 3 (User Story 1)

```text
# All five tasks can launch simultaneously — all are different files in different projects:

[P] T010 → wtvendo-pi/wtvendo/classifier.py     (Pi - YOLO inference)
[P] T011 → wtvendo-pi/wtvendo/session.py         (Pi - state machine)
[P] T012 → wtvendo-pi/wtvendo/lcd_messages.py    (Pi - message formatting)
[P] T013 → wtvendo-ino/sensor.h + sensor.cpp     (Arduino - HC-SR04 driver)
[P] T014 → wtvendo-ino/servo_control.h + .cpp    (Arduino - PCA9685 servos)
```

---

## Implementation Strategy

### Two-Session Plan

The implementation is split into two independent work sessions matching the physical architecture:

**Session 1 — Part 1 (Pi + Docs)**: `wtvendo-pi/` and `docs/`

| Order | Tasks                  | Deliverable                                       |
| ----- | ---------------------- | ------------------------------------------------- |
| 1     | T001, T002, T003, T005 | Project scaffolding + dependencies + protocol doc |
| 2     | T006, T007             | Config module + serial protocol implementation    |
| 3     | T010, T011, T012       | Classifier + session state machine + LCD helpers  |
| 4     | T016                   | Item selection and dispensing logic               |
| 5     | T018                   | Session lifecycle (timeout, reset)                |
| 6     | T019                   | Main entry point with full orchestration loop     |
| 7     | T021, T023             | Documentation + test scaffolding                  |

**Session 2 — Part 2 (Arduino)**: `wtvendo-ino/`

| Order | Tasks      | Deliverable                                    |
| ----- | ---------- | ---------------------------------------------- |
| 1     | T004       | Project scaffolding + library manifest         |
| 2     | T008, T009 | Pin config + serial protocol with event buffer |
| 3     | T013, T014 | Sensor driver + servo control                  |
| 4     | T015       | Keypad driver                                  |
| 5     | T017       | LCD display driver                             |
| 6     | T020       | Main sketch with setup() + cooperative loop()  |
| 7     | T022       | Hardware documentation + comments              |

**Final (both sessions)**: T024 — Full system validation against quickstart.md

### MVP First (US1 + US2)

1. Complete Phase 1 (Setup) + Phase 2 (Foundational / US3)
2. Complete Phase 3 (US1: Insert Bottle & Earn Points)
3. Complete Phase 4 (US2: Select & Dispense)
4. **STOP and VALIDATE**: Test full bottle → points → item → dispense loop
5. This is the MVP — students can exchange bottles for supplies

### Incremental Delivery

1. Setup + Foundational → Serial communication works ✅
2. Add US1 → Bottle detection and classification works ✅
3. Add US2 → Full exchange loop works → **MVP deployed** ✅
4. Add US4 → Polished LCD feedback ✅
5. Add US5 → Automatic session management ✅
6. Each story adds value without breaking previous stories

---

## Task Summary

| Metric                           | Count |
| -------------------------------- | ----- |
| **Total tasks**                  | 24    |
| Part 1 (Pi) tasks                | 13    |
| Part 2 (Arduino) tasks           | 9     |
| Shared tasks                     | 2     |
| Phase 1 (Setup) tasks            | 5     |
| Phase 2 (Foundational/US3) tasks | 4     |
| Phase 3 (US1) tasks              | 5     |
| Phase 4 (US2) tasks              | 2     |
| Phase 5 (US4) tasks              | 1     |
| Phase 6 (US5) tasks              | 1     |
| Phase 7 (Integration) tasks      | 2     |
| Phase 8 (Polish) tasks           | 4     |
| Parallelizable tasks [P]         | 17    |
| Sequential (blocking) tasks      | 7     |

## Notes

- All task descriptions include exact file paths for implementation
- [P] tasks target different files — safe for parallel execution
- [Story] labels trace tasks back to spec.md user stories
- Commit after each task or logical group for incremental progress
- Stop at any phase checkpoint to validate independently
- The serial protocol contract is the **single source of truth** — both sides implement from it
- YOLO model (.pt) is NOT committed to Git — only models/README.md with SHA256
- Arduino uses F() macro for all strings, no delay(), no String class
- Points are deducted AFTER servo ACK — never before (atomicity guarantee)
