# Data Model: WTVendo — 001-vendo-system

**Date**: 2026-03-09
**Source**: [spec.md](spec.md), [research.md](research.md)

---

## Entities

### 1. BottleClass

Represents one of the 10 recognized bottle types output by the YOLO model.

| Field    | Type   | Description                                      |
| -------- | ------ | ------------------------------------------------ |
| `name`   | string | YOLO class label (e.g., `"large bottled water"`) |
| `points` | int    | Point value awarded for this bottle type         |

**Validation**: `name` must be one of the 10 defined classes. `points` must be > 0.

**Defined in**: `wtvendo-pi/wtvendo/config.py` as `BOTTLE_POINTS` dict.

**Instances** (point values are placeholders — tuned during testing):

| Class Name           | Points |
| -------------------- | ------ |
| large bottled water  | 5      |
| medium bottled water | 4      |
| medium soda          | 3      |
| medium thick bottle  | 3      |
| pepsi viper          | 3      |
| small bottled water  | 2      |
| small soda           | 2      |
| small thick bottle   | 2      |
| xs soda              | 1      |
| xs thick bottle      | 1      |

---

### 2. DispensingSlot

One of 9 physical coil-based dispensing channels for school supply items.

| Field              | Type      | Description                                 |
| ------------------ | --------- | ------------------------------------------- |
| `slot_number`      | int (1–9) | User-facing slot ID (keypad key)            |
| `channel`          | int (0–8) | PCA9685 servo channel (`slot_number - 1`)   |
| `item_name`        | string    | Display label for LCD (e.g., `"Pencil"`)    |
| `cost`             | int       | Point cost to dispense                      |
| `spin_duration_ms` | int       | Servo activation time in ms (default ~1200) |

**Validation**: `slot_number` 1–9, `channel` 0–8, `cost` > 0, `spin_duration_ms` > 0.

**Defined in**: `wtvendo-pi/wtvendo/config.py` as `ITEM_SLOTS` dict.

**Example configuration** (items and costs are placeholders):

| Slot | Channel | Item       | Cost | Duration |
| ---- | ------- | ---------- | ---- | -------- |
| 1    | 0       | Pencil     | 5    | 1200ms   |
| 2    | 1       | Eraser     | 3    | 1200ms   |
| 3    | 2       | Pen        | 8    | 1200ms   |
| 4    | 3       | Ruler      | 10   | 1200ms   |
| 5    | 4       | Sharpener  | 3    | 1200ms   |
| 6    | 5       | Notebook   | 15   | 1200ms   |
| 7    | 6       | Crayon     | 5    | 1200ms   |
| 8    | 7       | Marker     | 8    | 1200ms   |
| 9    | 8       | Glue Stick | 5    | 1200ms   |

---

### 3. Session

A transient interaction for one student. Not persisted.

| Field           | Type              | Description                                      |
| --------------- | ----------------- | ------------------------------------------------ |
| `points`        | int               | Current accumulated point balance                |
| `state`         | SessionState enum | Current state machine state                      |
| `last_activity` | float             | `time.monotonic()` timestamp of last interaction |
| `active`        | bool              | Whether session is currently active              |

**States** (enum):

```
IDLE → SCANNING → CLASSIFYING → POINTS_DISPLAY → ITEM_SELECT → DISPENSING
```

**State transitions**:

| From           | Trigger                                        | To                             |
| -------------- | ---------------------------------------------- | ------------------------------ |
| IDLE           | Object detected by HC-SR04                     | SCANNING                       |
| SCANNING       | Pi captures image                              | CLASSIFYING                    |
| CLASSIFYING    | Classification success (conf > 0.5)            | POINTS_DISPLAY                 |
| CLASSIFYING    | Classification failure (conf ≤ 0.5 or unknown) | IDLE (after rejection message) |
| POINTS_DISPLAY | Timeout (auto-advance ~3s) or keypad press     | ITEM_SELECT                    |
| ITEM_SELECT    | Valid item selected (enough points)            | DISPENSING                     |
| ITEM_SELECT    | Insert another bottle                          | SCANNING                       |
| ITEM_SELECT    | Inactivity timeout (60s)                       | IDLE (session reset)           |
| DISPENSING     | Servo ACK received, points deducted            | ITEM_SELECT (if points remain) |
| DISPENSING     | Servo ACK received, no points left             | IDLE (session ends)            |
| Any            | Inactivity timeout (60s)                       | IDLE (session reset)           |

**Validation**:

- `points` ≥ 0 at all times.
- Points are only deducted after servo ACK confirmation.
- `last_activity` is reset on every user interaction (bottle insert, keypad press).

**Lifecycle**:

- Created when first bottle is successfully classified.
- Destroyed when: student has no points after last dispense, explicit end (if keypad key mapped), or inactivity timeout.
- Not persisted across power cycles.

---

### 4. SerialMessage

A structured data packet exchanged between Pi and Arduino.

| Field      | Type  | Description                                 |
| ---------- | ----- | ------------------------------------------- |
| `start`    | byte  | Fixed: `0xAA`                               |
| `command`  | byte  | Command type identifier (see table below)   |
| `length`   | byte  | Payload length (0–64)                       |
| `payload`  | bytes | Variable-length data                        |
| `checksum` | byte  | XOR of command + length + all payload bytes |

**Validation**:

- `start` must equal `0xAA`.
- `length` must be 0–64.
- `checksum` must match computed XOR.
- `command` must be a recognized command code.

**Command types**: See [contracts/serial-protocol.md](contracts/serial-protocol.md).

---

### 5. Trapdoor

The servo-controlled hatch that clears the intake area.

| Field       | Type | Description                         |
| ----------- | ---- | ----------------------------------- |
| `channel`   | int  | Fixed: 9 (PCA9685 channel)          |
| `state`     | enum | `OPEN` or `CLOSED`                  |
| `open_pwm`  | int  | PWM pulse width for open (~2400µs)  |
| `close_pwm` | int  | PWM pulse width for closed (~600µs) |

**Behavior**: Opens after each classification (success or failure) to clear the bottle, then closes. Defaults to closed on startup and power loss.

---

## Relationships

```
Session --(accumulates)--> BottleClass.points
Session --(spends at)----> DispensingSlot.cost
Pi --(sends/receives)----> SerialMessage --(to/from)--> Arduino
Arduino --(controls)-----> DispensingSlot (servos ch 0–8)
Arduino --(controls)-----> Trapdoor (servo ch 9)
Arduino --(reads)--------> HC-SR04 sensor
Arduino --(reads)--------> 4×4 Keypad
Arduino --(writes)-------> 20×4 LCD
```

## Data Flow Summary

```
[HC-SR04] → Arduino detects object → queues EVENT_OBJECT_DETECTED
    ↓
Pi polls events → receives detection → captures camera frame
    ↓
Pi runs YOLO inference → classifies bottle (or rejects)
    ↓
Pi sends LCD_WRITE (points/rejection) → Pi sends SERVO_TRAPDOOR (open then close)
    ↓
Pi enters ITEM_SELECT → polls keypad events
    ↓
Student presses key → Arduino queues EVENT_KEYPRESS → Pi receives via poll
    ↓
Pi validates points ≥ cost → sends SERVO_DISPENSE → waits for ACK
    ↓
ACK received → deduct points → update LCD → back to ITEM_SELECT or IDLE
```
