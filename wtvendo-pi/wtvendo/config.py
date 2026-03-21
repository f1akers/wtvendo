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

_default_port = "COM4" if os.name == "nt" else "/dev/ttyUSB0"
SERIAL_PORT: str = os.environ.get("WTVENDO_SERIAL_PORT", _default_port)
"""Arduino serial port path. Override via WTVENDO_SERIAL_PORT env var.
Windows default: COM3. Linux/Pi default: /dev/ttyUSB0."""

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

CAMERA_BACKEND: str = os.environ.get(
    "WTVENDO_CAMERA_BACKEND",
    "opencv" if os.name == "nt" else "picamera2",
)
"""Camera backend: 'picamera2' (Pi Camera) or 'opencv' (USB webcam).
Auto-selects 'opencv' on Windows. Override via WTVENDO_CAMERA_BACKEND env var."""

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
# Exchange rate: ~5 pts ≈ ₱1 (cost-neutral to the community).
# Larger / thicker plastic = more material recycled = more points.
# Rule of thumb: a student bringing ~5 bottles earns a basic item;
# ~15-20 bottles earns a notebook.
#
#   Size tier    | Thin plastic | Thick plastic
#   -------------|--------------|---------------
#   Large        |      8 pts   |      —
#   Medium       |    5–6 pts   |    6 pts
#   Small        |    3–4 pts   |    4 pts
#   XS           |      2 pts   |    3 pts
#
BOTTLE_POINTS: dict[str, int] = {
    "large bottled water":  8,  # ~1.5L+, most plastic
    "medium bottled water": 6,  # ~500–750mL
    "medium soda":          5,  # ~330–500mL thin
    "medium thick bottle":  6,  # ~330–500mL thick plastic
    "pepsi viper":          5,  # ~330mL distinctive shape
    "small bottled water":  4,  # ~250–350mL
    "small soda":           3,  # ~250mL thin
    "small thick bottle":   4,  # ~250mL thick plastic
    "xs soda":              2,  # <250mL thin
    "xs thick bottle":      3,  # <250mL thick
}
"""
Mapping of YOLO class name → points awarded per bottle.

Points are calibrated so ~5 avg bottles ≈ 1 basic school supply.
Thick bottles score higher than thin of the same size — they use
more raw plastic and are harder for recyclers to process, so the
extra reward nudges students to bring those in too.
"""

# ---------------------------------------------------------------------------
# Dispensing Slots
# ---------------------------------------------------------------------------
#
# Item costs in points, derived from approximate Philippine retail prices
# (₱5–₱100 range) at the 5 pts ≈ ₱1 exchange rate.
# No markup — the machine is a recycling incentive, not a profit center.
#
#   Item          | ~Retail price | Point cost | Bottles needed (avg 5 pts)
#   --------------|---------------|------------|---------------------------
#   Pencil        |    ₱5–₱8     |     20     |  ~4 bottles
#   Eraser        |    ₱5–₱10    |     25     |  ~5 bottles
#   Sharpener     |   ₱10–₱15   |     30     |  ~6 bottles
#   Pen (ballpen) |   ₱10–₱15   |     35     |  ~7 bottles
#   Glue Stick    |   ₱15–₱20   |     40     |  ~8 bottles
#   Ruler         |   ₱15–₱20   |     45     |  ~9 bottles
#   Marker        |   ₱20–₱30   |     50     | ~10 bottles
#   Crayon Set    |   ₱25–₱40   |     60     | ~12 bottles
#   Notebook      |   ₱30–₱45   |     80     | ~16 bottles
#
# Each slot: (item_name, cost_in_points, spin_duration_ms)
ITEM_SLOTS: dict[int, tuple[str, int, int]] = {
    1: ("Pencil",    20, 5300),
    2: ("Eraser",    25, 5300),
    3: ("Sharpener", 30, 5300),
    4: ("Pen",       35, 5300),
    5: ("Glue Stick",40, 5300),
    6: ("Ruler",     45, 5300),
}
"""
Slot number (1–6) → (display_name, point_cost, servo_spin_duration_ms).

Slots are ordered cheapest-to-most-expensive so keypad key 1 always
gets the most accessible item. PCA9685 channel = slot_number - 1.
"""
