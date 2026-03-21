"""
WTVendo Raspberry Pi main entry point.

Orchestrates the full vending session lifecycle:
  1. Startup: load YOLO model, initialize camera, open serial connection
  2. Main loop (~20Hz): poll events → run state handler → send LCD updates
  3. Shutdown: close serial, release camera on KeyboardInterrupt

The Pi is the master device. It polls the Arduino for sensor/keypad events,
runs YOLO inference for bottle classification, manages session state and
points, and sends LCD/servo commands to the Arduino.

Run with:
    python -m wtvendo.main
"""

from __future__ import annotations

import atexit
import fcntl
import logging
import os
import struct
import sys
import time

from wtvendo.classifier import CameraBackend, Classifier, create_camera
from wtvendo.config import (
    CAMERA_BACKEND,
    CAMERA_NAME,
    IDLE_SCAN_INTERVAL,
    ITEM_SLOTS,
    POINTS_DISPLAY_DURATION,
)
from wtvendo.lcd_messages import (
    format_classification_failed,
    format_classified,
    format_comm_error,
    format_dispensing,
    format_insufficient,
    format_item_menu,
    format_scanning,
    format_welcome,
)
from wtvendo.serial_comm import (
    ACK,
    CMD_LCD_CLEAR,
    CMD_LCD_WRITE,
    CMD_SERVO_DISPENSE,
    CMD_SERVO_TRAPDOOR,
    EVENT_KEYPRESS,
    NACK,
    SerialConnection,
)
from wtvendo.session import Session, SessionState

logger = logging.getLogger(__name__)

# Main loop timing
LOOP_SLEEP: float = 0.005  # ~5ms → ~20Hz effective loop rate (with polling overhead)
TRAPDOOR_OPEN_DURATION: float = 2.0  # seconds to keep trapdoor open after classification


# ---------------------------------------------------------------------------
# LCD Helpers
# ---------------------------------------------------------------------------


def send_lcd_lines(conn: SerialConnection, lines: list[str]) -> None:
    """
    Send 4 LCD lines to the Arduino via LCD_WRITE commands.

    Each line is sent as a separate command: row + col(0) + text.

    Args:
        conn: Open serial connection.
        lines: List of 4 strings (each 20 chars, pre-padded).
    """
    for row, text in enumerate(lines):
        payload = bytes([row, 0]) + text.encode("ascii", errors="replace")
        try:
            conn.send_command(CMD_LCD_WRITE, payload)
        except (TimeoutError, ConnectionError):
            logger.warning("Failed to write LCD row %d", row)


def send_lcd_clear(conn: SerialConnection) -> None:
    """Send LCD_CLEAR command to Arduino."""
    try:
        conn.send_command(CMD_LCD_CLEAR)
    except (TimeoutError, ConnectionError):
        logger.warning("Failed to clear LCD")


# ---------------------------------------------------------------------------
# Trapdoor Control
# ---------------------------------------------------------------------------


def trapdoor_open(conn: SerialConnection) -> bool:
    """
    Open the trapdoor servo.

    Returns:
        True if ACK received, False on error.
    """
    try:
        cmd, _ = conn.send_command(CMD_SERVO_TRAPDOOR, bytes([0x01]))
        return cmd == ACK
    except (TimeoutError, ConnectionError):
        logger.error("Failed to open trapdoor")
        return False


def trapdoor_close(conn: SerialConnection) -> bool:
    """
    Close the trapdoor servo.

    Returns:
        True if ACK received, False on error.
    """
    try:
        cmd, _ = conn.send_command(CMD_SERVO_TRAPDOOR, bytes([0x00]))
        return cmd == ACK
    except (TimeoutError, ConnectionError):
        logger.error("Failed to close trapdoor")
        return False


# ---------------------------------------------------------------------------
# State Handlers
# ---------------------------------------------------------------------------


def handle_idle(
    session: Session,
    camera: CameraBackend,
    classifier: Classifier,
    lcd_dirty: list[bool],
    last_scan_time: list[float],
) -> None:
    """
    IDLE state: run ML inference every IDLE_SCAN_INTERVAL seconds.

    On bottle detected by YOLO → transition to SCANNING.
    """
    now = time.monotonic()
    if now - last_scan_time[0] < IDLE_SCAN_INTERVAL:
        return
    last_scan_time[0] = now

    try:
        frame = camera.capture()
    except RuntimeError:
        return

    if classifier.classify(frame) is not None:
        logger.info("Bottle detected by ML scan — starting scan")
        session.start_scan()
        lcd_dirty[0] = True


def handle_scanning(
    session: Session,
    conn: SerialConnection,
    camera: CameraBackend,
    classifier: Classifier,
    lcd_dirty: list[bool],
) -> None:
    """
    SCANNING state: capture camera frame and begin classification.

    Captures a single frame, then transitions to CLASSIFYING and immediately
    runs inference (since it's synchronous and fast enough at ~100-160ms).
    """
    # Show scanning message
    send_lcd_lines(conn, format_scanning())

    session.start_classify()

    try:
        frame = camera.capture()
    except RuntimeError as exc:
        logger.error("Camera capture failed: %s", exc)
        session.classification_failed()
        send_lcd_lines(conn, format_classification_failed())
        lcd_dirty[0] = True
        return

    # Run YOLO inference
    result = classifier.classify(frame)

    if result is None:
        logger.info("No bottle detected by YOLO — classification failed")
        session.classification_failed()
        send_lcd_lines(conn, format_classification_failed())
        lcd_dirty[0] = True
        return

    class_name, confidence = result
    awarded = session.classification_done(class_name, confidence)

    logger.info(
        "Classified '%s' (conf=%.3f) — +%d pts (total: %d)",
        class_name,
        confidence,
        awarded,
        session.points,
    )

    # Show classification result
    send_lcd_lines(conn, format_classified(class_name, awarded, session.points))

    # Open trapdoor to clear the bottle, then close
    _open_close_trapdoor(conn)

    lcd_dirty[0] = True


def _open_close_trapdoor(conn: SerialConnection) -> None:
    """Open the trapdoor, wait, then close it to clear the intake."""
    trapdoor_open(conn)
    time.sleep(TRAPDOOR_OPEN_DURATION)
    trapdoor_close(conn)


def handle_points_display(
    session: Session,
    conn: SerialConnection,
    events: list[tuple[int, bytes]],
    lcd_dirty: list[bool],
) -> None:
    """
    POINTS_DISPLAY state: show points for a few seconds, then auto-advance.

    Auto-advances to ITEM_SELECT after POINTS_DISPLAY_DURATION seconds,
    or immediately on any keypad event.
    """
    # Check for keypad press to skip ahead
    for event_cmd, _ in events:
        if event_cmd == EVENT_KEYPRESS:
            session.advance_to_item_select()
            lcd_dirty[0] = True
            return

    # Auto-advance after display duration
    if session.points_display_start is not None:
        elapsed = time.monotonic() - session.points_display_start
        if elapsed >= POINTS_DISPLAY_DURATION:
            session.advance_to_item_select()
            lcd_dirty[0] = True


def handle_item_select(
    session: Session,
    conn: SerialConnection,
    events: list[tuple[int, bytes]],
    lcd_dirty: list[bool],
    camera: CameraBackend,
    classifier: Classifier,
    last_scan_time: list[float],
) -> None:
    """
    ITEM_SELECT state: process keypad events; scan for another bottle via ML.

    - On YOLO bottle detection (every IDLE_SCAN_INTERVAL s) → SCANNING
    - On EVENT_KEYPRESS '1'–'9': validate affordability and start dispensing
    """
    # Check for new bottle insertion via timed ML scan
    now = time.monotonic()
    if now - last_scan_time[0] >= IDLE_SCAN_INTERVAL:
        last_scan_time[0] = now
        try:
            frame = camera.capture()
            if classifier.classify(frame) is not None:
                logger.info("Another bottle detected — returning to SCANNING")
                session.start_scan()
                lcd_dirty[0] = True
                return
        except RuntimeError:
            pass

    for event_cmd, event_payload in events:
        if event_cmd == EVENT_KEYPRESS and len(event_payload) >= 1:
            key_char = chr(event_payload[0])
            session.touch()

            # Only process item keys '1'–'9'
            if key_char.isdigit() and key_char != "0":
                slot = int(key_char)

                if slot not in ITEM_SLOTS:
                    logger.warning("Invalid slot %d", slot)
                    continue

                item_name, cost, _, _ = ITEM_SLOTS[slot]

                if not session.can_afford(slot):
                    logger.info(
                        "Insufficient points for slot %d (%s, cost=%d, have=%d)",
                        slot,
                        item_name,
                        cost,
                        session.points,
                    )
                    send_lcd_lines(conn, format_insufficient(cost, session.points))
                    # Brief display, then return to menu
                    time.sleep(1.5)
                    lcd_dirty[0] = True
                    return

                # Start dispensing
                session.start_dispensing(slot)
                lcd_dirty[0] = True
                return


def handle_dispensing(
    session: Session,
    conn: SerialConnection,
    lcd_dirty: list[bool],
) -> None:
    """
    DISPENSING state: send servo command, wait for ACK, deduct points.

    The SERVO_DISPENSE command blocks on the Arduino side until the servo
    completes spinning. The Pi waits for the ACK, then deducts points
    (post-ACK deduction per research.md §5 critical rule).
    """
    # Determine which slot is being dispensed (stored implicitly via state)
    # We need to track the current dispensing slot — use a module-level var
    # This is set by the caller before entering DISPENSING state.
    # For now, the slot is passed via the _dispensing_slot attribute.
    slot = session.dispensing_slot
    if slot is None:
        logger.error("No dispensing slot set — returning to ITEM_SELECT")
        session.state = SessionState.ITEM_SELECT
        lcd_dirty[0] = True
        return

    item_name, _, duration_ms, direction = ITEM_SLOTS[slot]

    # Show dispensing message
    send_lcd_lines(conn, format_dispensing(item_name))

    # Build payload: channel(1) + duration_ms(2, big-endian) + direction(1)
    # direction: 0x00 = CCW (default), 0x01 = CW
    channel = slot - 1  # Slot 1–9 → channel 0–8
    dir_byte = 0x01 if direction == "cw" else 0x00
    payload = struct.pack(">BHB", channel, duration_ms, dir_byte)

    try:
        resp_cmd, resp_payload = conn.send_command(CMD_SERVO_DISPENSE, payload)
    except TimeoutError:
        logger.error("Servo dispense timeout for slot %d", slot)
        send_lcd_lines(conn, format_comm_error())
        time.sleep(2)
        session.state = SessionState.ITEM_SELECT
        lcd_dirty[0] = True
        return
    except ConnectionError:
        logger.error("Serial disconnected during dispensing")
        send_lcd_lines(conn, format_comm_error())
        time.sleep(2)
        session.reset()
        lcd_dirty[0] = True
        return

    if resp_cmd == ACK:
        # Post-ACK deduction — critical rule
        session.dispensing_done(slot)
        logger.info("Dispense complete for slot %d (%s)", slot, item_name)
    elif resp_cmd == NACK:
        error_code = resp_payload[0] if resp_payload else 0
        logger.error("NACK on dispense slot %d, error=0x%02X", slot, error_code)
        session.state = SessionState.ITEM_SELECT

    lcd_dirty[0] = True


# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------


def _init_camera_with_fallback() -> CameraBackend:
    """Try the configured backend, then fall back to the other on first failure."""
    backends = [CAMERA_BACKEND, "opencv" if CAMERA_BACKEND == "picamera2" else "picamera2"]
    for backend in backends:
        logger.info("Trying camera backend: %s", backend)
        # Try primary backend up to 3 times; fallback backend only once to avoid
        # interfering with hardware (e.g., picamera2 holding USB cameras hostage)
        retries = 3 if backend == backends[0] else 1
        for attempt in range(1, retries + 1):
            try:
                # Pass CAMERA_NAME only for opencv backend
                camera_name = CAMERA_NAME if backend == "opencv" else None
                camera = create_camera(backend, camera_name=camera_name)
                logger.info("Camera initialized with %s backend", backend)
                return camera
            except (RuntimeError, ImportError, ValueError) as exc:
                logger.warning(
                    "%s camera init attempt %d/%d failed: %s",
                    backend, attempt, retries, exc,
                )
                # If primary backend fails on first attempt, skip retries and fallback immediately
                if backend == backends[0] and attempt == 1:
                    logger.info(
                        "Primary backend failed immediately — skipping retries, trying fallback"
                    )
                    break
                if attempt < retries:
                    time.sleep(2)
    logger.critical("Could not initialize any camera backend")
    sys.exit(1)


def startup() -> tuple[SerialConnection, CameraBackend, Classifier, Session]:
    """
    Initialize all system components.

    Returns:
        (serial_conn, camera, classifier, session) tuple.

    Raises:
        SystemExit: If critical components fail to initialize.
    """
    logger.info("=== WTVendo Pi Starting ===")

    # 1. Load and verify YOLO model
    logger.info("Loading YOLO model...")
    classifier = Classifier()
    try:
        classifier.load()
    except (FileNotFoundError, RuntimeError) as exc:
        logger.critical("Failed to load YOLO model: %s", exc)
        sys.exit(1)

    # 2. Initialize camera (retry primary, then fall back to other backend)
    camera = _init_camera_with_fallback()

    # 3. Open serial connection
    logger.info("Opening serial connection...")
    conn = SerialConnection()
    retries = 3
    for attempt in range(1, retries + 1):
        try:
            conn.open()
            break
        except Exception as exc:
            logger.warning("Serial open attempt %d/%d failed: %s", attempt, retries, exc)
            if attempt == retries:
                logger.critical("Could not open serial port after %d attempts", retries)
                sys.exit(1)
            time.sleep(1)

    # 4. Create session
    session = Session()

    # 5. Send welcome message to LCD
    logger.info("Sending welcome message to LCD...")
    send_lcd_clear(conn)
    send_lcd_lines(conn, format_welcome())

    logger.info("=== WTVendo Pi Ready ===")
    return conn, camera, classifier, session


def main_loop(
    conn: SerialConnection,
    camera: CameraBackend,
    classifier: Classifier,
    session: Session,
) -> None:
    """
    Synchronous polling main loop running at ~20Hz.

    Each iteration:
      1. Poll Arduino for events
      2. Run current state handler
      3. Send LCD updates if state changed
      4. Check inactivity timeout
      5. Sleep to maintain loop rate
    """
    lcd_dirty: list[bool] = [False]
    last_lcd_state: SessionState | None = None
    last_scan_time: list[float] = [0.0]  # Shared idle/item-select scan timer

    logger.info("Entering main loop")

    while True:
        loop_start = time.monotonic()

        # 1. Poll events from Arduino
        events = conn.poll_events()

        # 2. Dispatch to current state handler
        current_state = session.state

        if current_state == SessionState.IDLE:
            handle_idle(session, camera, classifier, lcd_dirty, last_scan_time)

        elif current_state == SessionState.SCANNING:
            handle_scanning(session, conn, camera, classifier, lcd_dirty)

        elif current_state == SessionState.CLASSIFYING:
            # CLASSIFYING is handled synchronously within handle_scanning
            # If we land here, something unexpected happened — reset
            logger.warning("Unexpected CLASSIFYING state in main loop — resetting to IDLE")
            session.classification_failed()
            lcd_dirty[0] = True

        elif current_state == SessionState.POINTS_DISPLAY:
            handle_points_display(session, conn, events, lcd_dirty)

        elif current_state == SessionState.ITEM_SELECT:
            handle_item_select(
                session, conn, events, lcd_dirty, camera, classifier, last_scan_time
            )

        elif current_state == SessionState.DISPENSING:
            handle_dispensing(session, conn, lcd_dirty)

        # 3. Send LCD update on state change
        if lcd_dirty[0] or session.state != last_lcd_state:
            _update_lcd_for_state(session, conn)
            last_lcd_state = session.state
            lcd_dirty[0] = False

        # 4. Check inactivity timeout
        if session.check_timeout():
            logger.info("Session timed out — sending welcome screen")
            send_lcd_clear(conn)
            send_lcd_lines(conn, format_welcome())
            last_lcd_state = SessionState.IDLE

        # 5. Sleep to maintain loop rate
        elapsed = time.monotonic() - loop_start
        sleep_time = max(0, LOOP_SLEEP - elapsed)
        if sleep_time > 0:
            time.sleep(sleep_time)


def _update_lcd_for_state(session: Session, conn: SerialConnection) -> None:
    """
    Send the appropriate LCD content for the current session state.

    Called when state changes or lcd_dirty is set.
    """
    state = session.state

    if state == SessionState.IDLE:
        send_lcd_lines(conn, format_welcome())

    elif state == SessionState.SCANNING:
        send_lcd_lines(conn, format_scanning())

    elif state == SessionState.POINTS_DISPLAY:
        if session.last_class_name is not None:
            awarded = session.points  # Already accumulated
            send_lcd_lines(
                conn,
                format_classified(
                    session.last_class_name,
                    0,  # Recalculation not needed; display already sent in handler
                    session.points,
                ),
            )

    elif state == SessionState.ITEM_SELECT:
        send_lcd_lines(conn, format_item_menu(session.points))

    # DISPENSING and CLASSIFYING LCD updates are handled in their handlers


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------


def _acquire_lock() -> None:
    """Ensure only one instance of wtvendo is running via a PID file lock."""
    lock_path = "/tmp/wtvendo.lock"
    lock_fd = open(lock_path, "w")  # noqa: SIM115
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("Another wtvendo instance is already running — exiting.", file=sys.stderr)
        sys.exit(0)
    lock_fd.write(str(os.getpid()))
    lock_fd.flush()
    atexit.register(lambda: lock_fd.close())


def main() -> None:
    """Application entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    _acquire_lock()

    conn: SerialConnection | None = None
    camera: CameraBackend | None = None

    try:
        conn, camera, classifier, session = startup()
        main_loop(conn, camera, classifier, session)
    except KeyboardInterrupt:
        logger.info("Shutdown requested (Ctrl+C)")
    except Exception:
        logger.exception("Unhandled exception in main loop")
    finally:
        # Graceful shutdown
        if conn is not None and conn.is_open:
            try:
                send_lcd_clear(conn)
            except Exception:
                pass
            conn.close()
        if camera is not None:
            try:
                camera.release()
            except Exception:
                pass
        logger.info("=== WTVendo Pi Stopped ===")


if __name__ == "__main__":
    main()
