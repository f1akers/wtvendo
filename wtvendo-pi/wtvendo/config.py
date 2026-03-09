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

# ---------------------------------------------------------------------------
# Serial Communication
# ---------------------------------------------------------------------------

SERIAL_PORT: str = os.environ.get("WTVENDO_SERIAL_PORT", "/dev/ttyACM0")
"""Arduino serial port path. Override via WTVENDO_SERIAL_PORT env var."""

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

MODEL_PATH: str = os.path.join(os.path.dirname(__file__), "..", "models", "yolo26n.pt")
"""Path to the YOLO model weights file."""

IMAGE_SIZE: int = 320
"""YOLO inference input resolution (320×320)."""

CONFIDENCE_THRESHOLD: float = 0.5
"""Minimum detection confidence to accept a classification."""

# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------

CAMERA_BACKEND: str = "picamera2"
"""Camera backend: 'picamera2' (Pi Camera) or 'opencv' (USB webcam)."""

# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

INACTIVITY_TIMEOUT: float = 60.0
"""Seconds of inactivity before session auto-resets."""

POINTS_DISPLAY_DURATION: float = 3.0
"""Seconds to display points before auto-advancing to item select."""

# ---------------------------------------------------------------------------
# Bottle Point Values
# ---------------------------------------------------------------------------

BOTTLE_POINTS: dict[str, int] = {
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
"""Mapping of YOLO class name → point value awarded per bottle."""

# ---------------------------------------------------------------------------
# Dispensing Slots
# ---------------------------------------------------------------------------

# Each slot: (item_name, cost_in_points, spin_duration_ms)
ITEM_SLOTS: dict[int, tuple[str, int, int]] = {
    1: ("Pencil", 5, 1200),
    2: ("Eraser", 3, 1200),
    3: ("Pen", 8, 1200),
    4: ("Ruler", 10, 1200),
    5: ("Sharpener", 3, 1200),
    6: ("Notebook", 15, 1200),
    7: ("Crayon", 5, 1200),
    8: ("Marker", 8, 1200),
    9: ("Glue Stick", 5, 1200),
}
"""
Slot number (1–9) → (display_name, point_cost, servo_spin_duration_ms).

Slot number maps to keypad key. PCA9685 channel = slot_number - 1.
Items and costs are placeholders — tune during testing.
"""
