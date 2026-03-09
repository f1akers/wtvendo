# Quickstart: WTVendo — 001-vendo-system

**Date**: 2026-03-09
**Branch**: `001-vendo-system`

---

## Prerequisites

### Hardware

- Raspberry Pi 4B with Pi Camera module (or USB webcam)
- Arduino Mega 2560
- PCA9685 PWM Servo Driver board
- 9× JDI 6221MG 360° continuous-rotation servos (dispensing)
- 1× JDI 6221MG 180° positional servo (trapdoor)
- HC-SR04 ultrasonic sensor
- 20×4 I2C LCD (address 0x27)
- 4×4 membrane switch keypad
- USB cable (Pi ↔ Arduino) or TX/RX wires + common ground
- Adequate power supply for all components

### Software

- Raspberry Pi OS (64-bit) with Python 3.9+
- Arduino IDE 2.x or PlatformIO
- Git

---

## Setup

### 1. Clone & Branch

```bash
git clone <repo-url> wt-vendo
cd wt-vendo
git checkout 001-vendo-system
```

### 2. Raspberry Pi (`wtvendo-pi/`)

```bash
cd wtvendo-pi

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Place YOLO model
# Download yolo26n.pt (see models/README.md for URL and SHA256)
cp /path/to/yolo26n.pt models/yolo26n.pt

# Verify model integrity
sha256sum models/yolo26n.pt
# Compare with hash in models/README.md

# (Optional) Export to NCNN for faster inference
python -c "from ultralytics import YOLO; YOLO('models/yolo26n.pt').export(format='ncnn', imgsz=320)"
```

### 3. Arduino (`wtvendo-ino/`)

Open `wtvendo-ino/wtvendo-ino.ino` in Arduino IDE 2.x.

Install required libraries (see `libraries.txt`):

- **Adafruit PWM Servo Driver Library** (>=3.0)
- **hd44780** (>=1.3)
- **Keypad** (>=3.1)

Select board: **Arduino Mega 2560**

Compile and upload.

### 4. Wiring

Connect per [research.md — §6 Wiring Reference](research.md#6-wiring-reference):

- Pi TX → Arduino Mega pin 19 (Serial1 RX)
- Pi RX ← Arduino Mega pin 18 (Serial1 TX)
- Common ground between Pi and Arduino
- PCA9685 SDA/SCL → Arduino D20/D21
- LCD SDA/SCL → Same I2C bus (shared with PCA9685)
- HC-SR04 TRIG → D22, ECHO → D23
- Keypad rows → D24–D27, cols → D28–D31
- Servos → PCA9685 channels 0–8 (dispense), 9 (trapdoor)

---

## Running

### Start Arduino

Power on or upload sketch. Arduino will:

- Initialize all peripherals
- Display welcome message on LCD
- Begin serial listener on Serial1
- Start polling sensor and keypad in non-blocking loop

### Start Pi

```bash
cd wtvendo-pi
source .venv/bin/activate
python -m wtvendo.main
```

Pi will:

- Load YOLO model (verify SHA256)
- Open serial connection to Arduino
- Enter main polling loop at IDLE state
- LCD shows "Insert a bottle to start!"

### Test the Flow

1. Place a known bottle in the intake slot
2. HC-SR04 triggers → Pi captures and classifies
3. LCD shows bottle type and points earned
4. Press keypad key (1–9) to select an item
5. If enough points, servo activates and dispenses item
6. LCD shows remaining points

---

## Configuration

All tunable values are in `wtvendo-pi/wtvendo/config.py`:

| Setting                | Default               | Description                      |
| ---------------------- | --------------------- | -------------------------------- |
| `SERIAL_PORT`          | `/dev/ttyACM0`        | Arduino serial port path         |
| `BAUD_RATE`            | 115200                | Must match Arduino               |
| `SERIAL_TIMEOUT`       | 0.2                   | Response timeout (seconds)       |
| `MAX_RETRIES`          | 3                     | Retries before error             |
| `CONFIDENCE_THRESHOLD` | 0.5                   | Min YOLO confidence              |
| `INACTIVITY_TIMEOUT`   | 60                    | Session timeout (seconds)        |
| `CAMERA_BACKEND`       | `"picamera2"`         | `"picamera2"` or `"opencv"`      |
| `MODEL_PATH`           | `"models/yolo26n.pt"` | Path to YOLO model               |
| `IMAGE_SIZE`           | 320                   | YOLO inference resolution        |
| `BOTTLE_POINTS`        | dict                  | Bottle class → point values      |
| `ITEM_SLOTS`           | dict                  | Slot → item name, cost, duration |

Arduino pin assignments are in `wtvendo-ino/pin_config.h`.

---

## Testing

### Pi Unit Tests

```bash
cd wtvendo-pi
source .venv/bin/activate
pytest tests/unit/ -v
```

### Pi Integration Tests (requires Arduino connected)

```bash
pytest tests/integration/ -v
```

### Arduino

Compile with `-Wall` — must produce zero warnings.

---

## Troubleshooting

| Problem                 | Check                                                |
| ----------------------- | ---------------------------------------------------- |
| LCD blank               | I2C address (0x27?), SDA/SCL wiring, pullups         |
| Serial timeout          | Baud rate match, TX/RX not swapped, common ground    |
| YOLO slow (>500ms)      | Export to NCNN, use 320×320, check CPU throttling    |
| Servo not spinning      | PCA9685 power, channel assignment, PWM calibration   |
| Sensor always triggered | Check TRIG/ECHO wiring, distance threshold in config |
| Camera not found        | `CAMERA_BACKEND` setting, device permissions         |
