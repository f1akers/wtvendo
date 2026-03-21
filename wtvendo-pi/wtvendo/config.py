"""
Configuration module for WTVendo Raspberry Pi application.

Centralizes all system constants: serial communication parameters, YOLO model
settings, camera configuration, bottle point values, and dispensing slot
definitions. All values are tunable at development time — no runtime config
file is required.

Usage:
    from wtvendo.config import SERIAL_PORT, BAUD_RATE, BOTTLE_POINTS
"""

import os
from typing import Optional

# ---------------------------------------------------------------------------
# Serial Communication
# ---------------------------------------------------------------------------

_default_port = "COM4" if os.name == "nt" else "/dev/ttyACM0"
SERIAL_PORT: str = os.environ.get("WTVENDO_SERIAL_PORT", _default_port)
"""Arduino serial port path. Override via WTVENDO_SERIAL_PORT env var.
Windows default: COM4. Linux/Pi default: /dev/ttyACM0."""

SERIAL_PORT_CANDIDATES: list[str] = (
    ["COM4", "COM3"] if os.name == "nt" else ["/dev/ttyACM0", "/dev/ttyUSB0"]
)
"""Ports to try in order when auto-detecting the Arduino."""

BAUD_RATE: int = 115200
"""UART baud rate — must match Arduino SERIAL_BAUD."""

SERIAL_TIMEOUT: float = 0.2
"""Response timeout in seconds before retry."""

MAX_RETRIES: int = 3
"""Number of retries on serial timeout before raising error."""

RETRY_DELAY: float = 0.05
"""Delay in seconds between retries (50 ms)."""

# ---------------------------------------------------------------------------
# YOLO Model
# ---------------------------------------------------------------------------

MODEL_PATH: str = os.path.join(os.path.dirname(__file__), "..", "models", "model.pt")
"""Path to the YOLO model weights file."""

IMAGE_SIZE: int = 320
"""YOLO inference input resolution (320×320)."""

CONFIDENCE_THRESHOLD: float = 0.5
"""Minimum detection confidence to accept a classification."""

# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------

CAMERA_BACKEND: str = os.environ.get("WTVENDO_CAMERA_BACKEND", "opencv")
"""Camera backend: 'opencv' (USB webcam, default) or 'picamera2' (Pi Camera).
OpenCV is primary; picamera2 is the fallback. Override via WTVENDO_CAMERA_BACKEND."""

CAMERA_DEVICE_INDEX: Optional[int] = 1
"""Hardcoded /dev/video index for the USB webcam. Set to None to auto-detect.
Override via WTVENDO_CAMERA_INDEX env var (e.g. "0", "2", or "" for auto)."""

_cam_idx_env = os.environ.get("WTVENDO_CAMERA_INDEX")
if _cam_idx_env is not None:
    CAMERA_DEVICE_INDEX = int(_cam_idx_env) if _cam_idx_env.strip() else None

CAMERA_DEVICE_NAME: str = os.environ.get("WTVENDO_CAMERA_NAME", "A4Tech")
"""Substring to match when searching for the USB webcam by device name.
Only used when CAMERA_DEVICE_INDEX is None. Override via WTVENDO_CAMERA_NAME."""

# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

INACTIVITY_TIMEOUT: float = 60.0
"""Seconds of inactivity before session auto-resets."""

IDLE_SCAN_INTERVAL: float = 3.0
"""Seconds between ML camera scans when idle or waiting for another bottle."""

POINTS_DISPLAY_DURATION: float = 3.0
"""Seconds to display points before auto-advancing to item select."""

# ---------------------------------------------------------------------------
# Bottle Point Values
# ---------------------------------------------------------------------------
#
BOTTLE_POINTS: dict[str, int] = {
    "large bottled water":  5,
    "medium bottled water": 3,
    "medium thick bottle":  3,
    "medium soda":          3,
    "pepsi viper":          5,
    "small bottled water":  2,
    "small soda":           2,
    "small thick bottle":   2,
    "xs soda":              1,
    "xs thick":             1,
}
"""Mapping of YOLO class name → points awarded per bottle."""

# ---------------------------------------------------------------------------
# Dispensing Slots
# ---------------------------------------------------------------------------
#
# Each slot: (item_name, cost_in_points, spin_duration_ms, direction)
# direction: "ccw" = counterclockwise (1300µs), "cw" = clockwise (1700µs)
# Some coils were wound in opposite directions — set direction per slot.
ITEM_SLOTS: dict[int, tuple[str, int, int, str]] = {
    1: ("Yellow Pad 1/2",    2, 5300, "cw"),
    2: ("Ballpen",           1, 5300, "ccw"),
    3: ("Pencil",            1, 5300, "ccw"),
    4: ("Correction Tape",   3, 5300, "ccw"),
    5: ("Index Paper",       2, 5300, "ccw"),
    6: ("Bondpaper",         6, 5300, "ccw"),
}
"""
Slot number (1–6) → (display_name, point_cost, servo_spin_duration_ms, direction).

Direction controls spin: "ccw" (default) or "cw" for coils wound the other way.
PCA9685 channel = slot_number - 1.
"""
