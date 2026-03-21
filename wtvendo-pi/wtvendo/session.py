"""
Session state machine module for WTVendo.

Manages the vending session lifecycle: state transitions, point accumulation,
item affordability checks, and inactivity timeout. The session is volatile —
not persisted across power cycles.

State flow:
    IDLE → SCANNING → CLASSIFYING → POINTS_DISPLAY → ITEM_SELECT → DISPENSING
                                                   ↗ (another bottle)
    Any state → IDLE (on inactivity timeout or session end)

Usage:
    from wtvendo.session import Session, SessionState

    session = Session()
    session.start_scan()               # IDLE → SCANNING
    session.start_classify()           # SCANNING → CLASSIFYING
    session.classification_done("large bottled water", 0.95)  # → POINTS_DISPLAY
    session.advance_to_item_select()   # → ITEM_SELECT
"""

from __future__ import annotations

import enum
import logging
import time
from typing import Optional

from wtvendo.config import (
    BOTTLE_POINTS,
    INACTIVITY_TIMEOUT,
    ITEM_SLOTS,
)

logger = logging.getLogger(__name__)


class SessionState(enum.Enum):
    """Enumeration of vending session states."""

    IDLE = "idle"
    SCANNING = "scanning"
    CLASSIFYING = "classifying"
    POINTS_DISPLAY = "points_display"
    ITEM_SELECT = "item_select"
    DISPENSING = "dispensing"


class Session:
    """
    Manages a single student's vending session.

    Tracks accumulated points, current state, and inactivity timing.
    Points are awarded on successful bottle classification and deducted
    only after receiving a servo ACK for dispensing.

    Attributes:
        points: Current accumulated point balance (≥ 0).
        state: Current SessionState.
        active: Whether a session is currently in progress.
        last_activity: Monotonic timestamp of the last user interaction.
    """

    def __init__(self) -> None:
        self.points: int = 5000
        self.state: SessionState = SessionState.IDLE
        self.active: bool = False
        self.last_activity: float = time.monotonic()
        self._last_class_name: Optional[str] = None
        self._last_confidence: Optional[float] = None
        self._points_display_start: Optional[float] = None
        self._dispensing_slot: Optional[int] = None

    # ------------------------------------------------------------------
    # Point Operations
    # ------------------------------------------------------------------

    def add_points(self, bottle_class: str) -> int:
        """
        Award points for a classified bottle.

        Args:
            bottle_class: YOLO class name (must be in BOTTLE_POINTS).

        Returns:
            Points awarded (0 if class not recognized).
        """
        awarded = BOTTLE_POINTS.get(bottle_class, 0)
        if awarded > 0:
            self.points += awarded
            logger.info(
                "Awarded %d points for '%s' (total: %d)",
                awarded,
                bottle_class,
                self.points,
            )
        else:
            logger.warning("Unknown bottle class '%s' — no points awarded", bottle_class)
        return awarded

    def can_afford(self, slot: int) -> bool:
        """
        Check if the session has enough points for a dispensing slot.

        Args:
            slot: Slot number (1–9).

        Returns:
            True if points ≥ slot cost.
        """
        if slot not in ITEM_SLOTS:
            return False
        _, cost, _, _ = ITEM_SLOTS[slot]
        return self.points >= cost

    def deduct_points(self, slot: int) -> int:
        """
        Deduct points for a dispensed item. Call only after servo ACK.

        Args:
            slot: Slot number (1–9).

        Returns:
            Points deducted.

        Raises:
            ValueError: If slot is invalid or insufficient points.
        """
        if slot not in ITEM_SLOTS:
            raise ValueError(f"Invalid slot number: {slot}")
        _, cost, _, _ = ITEM_SLOTS[slot]
        if self.points < cost:
            raise ValueError(
                f"Insufficient points: have {self.points}, need {cost}"
            )
        self.points -= cost
        logger.info("Deducted %d points for slot %d (remaining: %d)", cost, slot, self.points)
        return cost

    # ------------------------------------------------------------------
    # State Transitions
    # ------------------------------------------------------------------

    def start_scan(self) -> None:
        """
        Transition IDLE → SCANNING on object detection.

        Also transitions ITEM_SELECT → SCANNING when a student inserts
        another bottle during item selection.
        """
        if self.state not in (SessionState.IDLE, SessionState.ITEM_SELECT):
            logger.warning(
                "start_scan() called in invalid state %s", self.state.value
            )
            return
        self.state = SessionState.SCANNING
        self.touch()
        logger.debug("State → SCANNING")

    def start_classify(self) -> None:
        """Transition SCANNING → CLASSIFYING after camera capture."""
        if self.state != SessionState.SCANNING:
            logger.warning(
                "start_classify() called in invalid state %s", self.state.value
            )
            return
        self.state = SessionState.CLASSIFYING
        logger.debug("State → CLASSIFYING")

    def classification_done(self, class_name: str, confidence: float) -> int:
        """
        Transition CLASSIFYING → POINTS_DISPLAY on successful classification.

        Awards points based on the bottle class and records the result for
        display purposes.

        Args:
            class_name: Detected bottle class name.
            confidence: Detection confidence (0.0–1.0).

        Returns:
            Points awarded.
        """
        if self.state != SessionState.CLASSIFYING:
            logger.warning(
                "classification_done() called in invalid state %s", self.state.value
            )
            return 0
        self._last_class_name = class_name
        self._last_confidence = confidence
        awarded = self.add_points(class_name)
        self.state = SessionState.POINTS_DISPLAY
        self._points_display_start = time.monotonic()
        self.active = True
        self.touch()
        logger.debug(
            "State → POINTS_DISPLAY ('%s', conf=%.3f, +%d pts)",
            class_name,
            confidence,
            awarded,
        )
        return awarded

    def classification_failed(self) -> None:
        """Transition CLASSIFYING → IDLE on classification failure."""
        if self.state != SessionState.CLASSIFYING:
            logger.warning(
                "classification_failed() called in invalid state %s",
                self.state.value,
            )
            return
        self._last_class_name = None
        self._last_confidence = None
        # If no points have been earned yet, end the session
        if self.points == 0:
            self.state = SessionState.IDLE
            self.active = False
        else:
            # Return to item select if student has existing points
            self.state = SessionState.ITEM_SELECT
        self.touch()
        logger.debug("Classification failed → State: %s", self.state.value)

    def advance_to_item_select(self) -> None:
        """Transition POINTS_DISPLAY → ITEM_SELECT (auto-advance or keypad)."""
        if self.state != SessionState.POINTS_DISPLAY:
            logger.warning(
                "advance_to_item_select() called in invalid state %s",
                self.state.value,
            )
            return
        self.state = SessionState.ITEM_SELECT
        self.touch()
        logger.debug("State → ITEM_SELECT")

    def start_dispensing(self, slot: int) -> None:
        """
        Transition ITEM_SELECT → DISPENSING on valid item selection.

        Args:
            slot: Selected slot number (1–9).
        """
        if self.state != SessionState.ITEM_SELECT:
            logger.warning(
                "start_dispensing() called in invalid state %s",
                self.state.value,
            )
            return
        self.state = SessionState.DISPENSING
        self._dispensing_slot = slot
        self.touch()
        logger.debug("State → DISPENSING (slot %d)", slot)

    def dispensing_done(self, slot: int) -> None:
        """
        Complete dispensing: deduct points and transition to next state.

        After ACK from servo, deduct the cost. If points remain, go back
        to ITEM_SELECT; otherwise end the session (IDLE).

        Args:
            slot: Slot that was dispensed.
        """
        if self.state != SessionState.DISPENSING:
            logger.warning(
                "dispensing_done() called in invalid state %s",
                self.state.value,
            )
            return
        self.deduct_points(slot)
        self._dispensing_slot = None
        self.touch()

        if self.points > 0:
            self.state = SessionState.ITEM_SELECT
            logger.debug("State → ITEM_SELECT (remaining: %d pts)", self.points)
        else:
            self.reset()
            logger.debug("No points remaining — session ended")

    # ------------------------------------------------------------------
    # Session Lifecycle
    # ------------------------------------------------------------------

    def touch(self) -> None:
        """Reset the inactivity timer. Call on every user interaction."""
        self.last_activity = time.monotonic()

    def check_timeout(self) -> bool:
        """
        Check if the session has timed out due to inactivity.

        Returns:
            True if timed out and session was reset. False otherwise.
        """
        if self.state == SessionState.IDLE:
            return False

        # Don't timeout during active dispensing — let it complete
        if self.state == SessionState.DISPENSING:
            return False

        elapsed = time.monotonic() - self.last_activity
        if elapsed >= INACTIVITY_TIMEOUT:
            logger.info(
                "Session timeout after %.1fs of inactivity (state=%s, points=%d)",
                elapsed,
                self.state.value,
                self.points,
            )
            self.reset()
            return True

        return False

    def reset(self) -> None:
        """Reset the session to IDLE with zero points."""
        prev_state = self.state
        prev_points = self.points
        self.points = 0
        self.state = SessionState.IDLE
        self.active = False
        self._last_class_name = None
        self._last_confidence = None
        self._points_display_start = None
        self._dispensing_slot = None
        self.last_activity = time.monotonic()
        logger.info(
            "Session reset (was %s with %d pts)", prev_state.value, prev_points
        )

    # ------------------------------------------------------------------
    # Properties for Display
    # ------------------------------------------------------------------

    @property
    def last_class_name(self) -> Optional[str]:
        """Last classified bottle name (for LCD display)."""
        return self._last_class_name

    @property
    def last_confidence(self) -> Optional[float]:
        """Last classification confidence (for LCD display)."""
        return self._last_confidence

    @property
    def points_display_start(self) -> Optional[float]:
        """Monotonic timestamp when POINTS_DISPLAY state began."""
        return self._points_display_start

    @property
    def dispensing_slot(self) -> Optional[int]:
        """Slot currently being dispensed (1–9), or None."""
        return self._dispensing_slot
