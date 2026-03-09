# Research: WTVendo — 001-vendo-system

**Date**: 2026-03-09
**Purpose**: Resolve all technical unknowns from the Technical Context before Phase 1 design.

---

## 1. Serial Protocol Design (Pi ↔ Arduino UART)

### Decision: Length-prefixed binary packets with XOR checksum

**Packet format**:

```
[START: 0xAA] [CMD: 1 byte] [LENGTH: 1 byte] [PAYLOAD: 0–64 bytes] [CHECKSUM: 1 byte XOR]
```

- **Start marker**: `0xAA` — distinctive alternating bit pattern. Marker conflicts are a non-issue because framing is length-based (the receiver never scans for markers inside payload).
- **Checksum**: XOR over CMD + LENGTH + PAYLOAD bytes. Trivial to implement on Arduino, sufficient for short wired connections (error rate is negligible at 115200 baud over 30cm wire).
- **Max payload**: 64 bytes — fits within Arduino's 64-byte serial buffer with room for header/checksum.
- **Byte order**: Big-endian (network order) for multi-byte fields.

**Rationale**: XOR checksum over CRC8 — simpler, fewer CPU cycles on AVR, sufficient for point-to-point wired link. Length-based framing over COBS — no encoding overhead, simpler parsing. Binary over text (JSON/CSV) — smaller messages, faster parsing on AVR.

**Alternatives considered**: COBS encoding (added complexity, no benefit on wired link), text/JSON protocol (parsing overhead on Arduino, larger messages), CRC8 (more robust but unnecessary for short wire).

### Decision: Pi-initiated polling for unsolicited events

- Arduino maintains a **circular event buffer** (16 slots) for unsolicited events (keypad presses, sensor triggers).
- Pi sends `POLL_EVENTS` command at the end of each main loop iteration (~20 Hz effective rate).
- Arduino responds with queued events (or empty response if none).
- This avoids bus collisions — only one device transmits at a time.

**Rationale**: Polling over interrupt-driven TX — prevents bus collisions without complex arbitration. 16-slot buffer at 20Hz poll rate gives 800ms of buffering, more than enough for human-speed interactions.

### Decision: 200ms timeout, 3 retries, 50ms inter-retry delay

- If no response within 200ms, Pi retries up to 3 times.
- After 3 failures, Pi flags a communication error on LCD.
- Session is preserved on transient failures; only persistent disconnection resets session.

---

## 2. Command Byte Assignments

| Code   | Command               | Direction           | Payload                      | Response                |
| ------ | --------------------- | ------------------- | ---------------------------- | ----------------------- |
| `0x01` | POLL_EVENTS           | Pi → Ard            | none                         | Event list or empty     |
| `0x02` | READ_SENSOR           | Pi → Ard            | none                         | Distance (2 bytes, mm)  |
| `0x03` | LCD_WRITE             | Pi → Ard            | row(1) + col(1) + text(N)    | ACK                     |
| `0x04` | LCD_CLEAR             | Pi → Ard            | none                         | ACK                     |
| `0x05` | SERVO_DISPENSE        | Pi → Ard            | channel(1) + duration_ms(2)  | ACK when done           |
| `0x06` | SERVO_TRAPDOOR        | Pi → Ard            | position(1): 0=close, 1=open | ACK                     |
| `0x07` | GET_KEYPAD            | Pi → Ard            | none                         | Key char or 0x00 (none) |
| `0x10` | EVENT_KEYPRESS        | Ard → Pi (via poll) | Key char (1 byte)            | —                       |
| `0x11` | EVENT_OBJECT_DETECTED | Ard → Pi (via poll) | Distance (2 bytes)           | —                       |
| `0xFE` | ACK                   | Ard → Pi            | optional status byte         | —                       |
| `0xFF` | NACK/ERROR            | Ard → Pi            | error code (1 byte)          | —                       |

---

## 3. YOLO Inference on Raspberry Pi 4B

### Decision: ultralytics library with NCNN export at 320×320

- **Model**: `yolo26n.pt` (YOLOv8 Nano variant), detection mode (not classification).
- **Export**: Convert `.pt` → NCNN format ahead of time. NCNN is ~4-5× faster than PyTorch on ARM Cortex-A72.
- **Input resolution**: 320×320 pixels — sufficient for bottle classification at close range, ~4× fewer FLOPs than 640×640.
- **Expected latency**: ~100-160ms per frame on Pi 4B (well within 500ms budget).
- **Confidence threshold**: Pass `conf=0.5` to `model.predict()` — YOLO filters pre-return. Zero detections = rejection (FR-004).
- **No FP16**: Cortex-A72 lacks FP16 hardware acceleration.
- **No threading**: Sequential workflow (capture → infer → act), GIL makes threading pointless for CPU-bound work.

**Rationale**: NCNN over ONNX/TFLite — best ARM NEON optimization, ultralytics has built-in export. 320×320 over 640×640 — bottle classification at vending distance doesn't need high resolution. Detection over classification model — handles "nothing present" naturally via zero detections.

**Alternatives considered**: TFLite export (slightly slower on Pi 4B), continuous video stream (wastes CPU when idle), classification model yolov8n-cls (doesn't handle empty frames gracefully).

### Decision: picamera2 primary, OpenCV fallback

- **Primary**: `picamera2` with `capture_array()` for on-demand single-frame capture (not continuous streaming).
- **Fallback**: OpenCV `cv2.VideoCapture(0)` for USB webcam — same NumPy array output.
- **Abstraction**: `CameraBackend` interface with `create_camera(config)` factory. Swap via `CAMERA_BACKEND` in config.

### Decision: Model stored in wtvendo-pi/models/, git-ignored

- `.pt` and NCNN exported files in `wtvendo-pi/models/` (in `.gitignore`).
- `models/README.md` committed with: download URL, SHA256 hash, version, class names.
- SHA256 verified at startup before loading model.

---

## 4. Arduino Peripheral Management

### Decision: PCA9685 via Adafruit library, cooperative non-blocking loop

**Servo control (PCA9685)**:

- Library: `Adafruit_PWMServoDriver`
- 360° continuous-rotation servos (ch 0–8): Neutral ~1500µs, forward ~1700µs. Dispense = forward spin for ~1200ms then stop at neutral.
- 180° trapdoor servo (ch 9): Closed ~600µs, open ~2400µs.
- All on same 50Hz PCA9685 board — no conflicts.
- PWM values will need per-servo calibration during testing.

**HC-SR04 non-blocking**:

- State machine (IDLE → TRIGGER → WAIT_ECHO → READ) replaces blocking `pulseIn()`.
- Poll every 100ms.
- Bottle detection: 3 consecutive readings under 150mm threshold.
- Hysteresis: exit threshold at 200mm to prevent detection flicker.

**I2C bus sharing**:

- PCA9685 (0x40) and LCD (0x27) on same bus at 100kHz — no issues.
- Combined onboard pullups sufficient.
- Wire library 32-byte buffer handles both devices.

**LCD (20×4 I2C)**:

- Library: `hd44780` with `hd44780_I2Cexp` — auto-detects address/pin mapping.
- Overwrite-in-place with 4-line cache — only write changed content to eliminate flicker.
- Rate-limited to 200ms update interval.

**4×4 Keypad**:

- Library: `Keypad.h` — non-blocking `getKey()`.
- Keys 1–9 → dispense slots 0–8 via `key - '1'` arithmetic.
- Other keys reserved or ignored.

**Non-blocking loop**:

- Flat cooperative multitasking with `millis()`.
- Every iteration: serial processing, keypad check, servo state.
- Every 100ms: sensor reading.
- Every 200ms: LCD update.
- Typical loop time: ~200µs.

**Rationale**: hd44780 over LiquidCrystal_I2C — more robust auto-detect. State machine sensor over pulseIn() — guarantees non-blocking. Cooperative over preemptive — simpler, sufficient for this workload.

### Decision: Target Arduino Mega 2560

- SRAM: Estimated ~1000 bytes (12% of Mega's 8KB) — well under 75%.
- Use `F()` macro for all string literals.
- Avoid `String` class — use `char[]` buffers.
- Serial1 for Pi (pins 18/19), Serial0 for debug logging.

**Rationale**: Mega over Uno — more SRAM (8KB vs 2KB), dedicated Serial1 for Pi communication (Serial0 stays available for debug), more digital pins for keypad/sensor.

---

## 5. Pi Session & Points Management

### Decision: Enum + dispatch dict state machine, synchronous polling loop

**States**: `IDLE → SCANNING → CLASSIFYING → POINTS_DISPLAY → ITEM_SELECT → DISPENSING`

- `enum.Enum` for states, dispatch dict mapping state → handler function.
- Each handler returns the next state.
- Clean, flat, no external library needed.

**Main loop**: Synchronous polling with 5ms sleep.

- Sequential workflow: poll events → run state handler → send commands → sleep.
- No asyncio (serial is sync, YOLO is CPU-bound), no threads (GIL, complexity).

**Inactivity timeout**: `time.monotonic()` checked every loop tick.

- Any interaction resets timestamp.
- After 60s (configurable): session resets, return to IDLE.

**Points configuration**: Plain `dict` in `config.py`:

```python
BOTTLE_POINTS = {
    "large bottled water": 5,
    "medium bottled water": 4,
    "medium soda": 3,
    "medium thick bottle": 3,
    "pepsi viper": 3,
    "small bottled water": 2,
    "small soda": 2,
    "small thick bottle": 2,
    "xs soda": 1,
    "xs thick bottle": 1,
}
ITEM_COSTS = {1: 10, 2: 10, 3: 8, 4: 8, 5: 5, 6: 5, 7: 5, 8: 3, 9: 3}
```

(Point values and costs are placeholders — to be tuned during testing.)

**Critical rule**: Deduct points AFTER receiving servo ACK, never before — prevents point loss on dispense failure.

### Decision: Preserve session on transient errors, reset on persistent disconnect

- Serial timeout/retry: session preserved, retry up to 3 times per command.
- 3+ consecutive command failures: display error on LCD, reset session.
- Power cycle: volatile session starts fresh at IDLE.

**Rationale**: Sync over async — simplest for sequential single-user workflow. Dict over JSON/YAML — no file I/O, values tuned at dev time. Post-ACK deduction — atomicity guarantee.

---

## 6. Wiring Reference

| Component           | Arduino Mega Pin / Bus | Notes                          |
| ------------------- | ---------------------- | ------------------------------ |
| HC-SR04 TRIG        | Digital D22            | Defined in `pin_config.h`      |
| HC-SR04 ECHO        | Digital D23            | Defined in `pin_config.h`      |
| PCA9685 SDA         | D20 (SDA)              | I2C bus, address 0x40          |
| PCA9685 SCL         | D21 (SCL)              | I2C bus                        |
| LCD SDA             | D20 (shared)           | I2C bus, address 0x27          |
| LCD SCL             | D21 (shared)           | I2C bus                        |
| Keypad Row 0–3      | D24, D25, D26, D27     | Defined in `pin_config.h`      |
| Keypad Col 0–3      | D28, D29, D30, D31     | Defined in `pin_config.h`      |
| Pi TX → Arduino RX1 | Serial1 RX (pin 19)    | UART 115200 8N1, common ground |
| Pi RX ← Arduino TX1 | Serial1 TX (pin 18)    | UART                           |

---

## 7. Library Versions

### Pi (`requirements.txt`)

| Package                | Version | Purpose                               |
| ---------------------- | ------- | ------------------------------------- |
| ultralytics            | >=8.0   | YOLO model loading & inference        |
| pyserial               | >=3.5   | UART serial communication             |
| picamera2              | >=0.3   | Pi Camera capture                     |
| opencv-python-headless | >=4.8   | Image processing, USB webcam fallback |
| numpy                  | >=1.24  | Array operations (implicit dep)       |

### Arduino (`libraries.txt`)

| Library                   | Version    | Purpose               |
| ------------------------- | ---------- | --------------------- |
| Adafruit PWM Servo Driver | >=3.0      | PCA9685 servo control |
| hd44780                   | >=1.3      | LCD I2C display       |
| Keypad                    | >=3.1      | 4×4 membrane keypad   |
| Wire                      | (built-in) | I2C bus               |

---

## Summary of Resolved Unknowns

| Unknown                     | Resolution                                               |
| --------------------------- | -------------------------------------------------------- |
| Serial protocol format      | `0xAA` + CMD + LEN + PAYLOAD + XOR checksum              |
| Unsolicited event handling  | Arduino circular event buffer + Pi polling               |
| YOLO performance on Pi 4B   | NCNN export + 320×320 = ~100-160ms                       |
| Camera abstraction          | Factory pattern, config-only swap                        |
| Model storage               | git-ignored `models/` dir + README with SHA256           |
| Servo control (360° + 180°) | PCA9685 library, PWM pulse width control                 |
| Non-blocking Arduino loop   | Cooperative `millis()`-based multitasking                |
| I2C bus sharing             | Same bus, different addresses, no issues                 |
| Session/state management    | Enum state machine, sync polling, volatile               |
| Points deduction timing     | Post-ACK deduction for atomicity                         |
| Target Arduino board        | Arduino Mega 2560 (SRAM headroom, multiple serial ports) |
