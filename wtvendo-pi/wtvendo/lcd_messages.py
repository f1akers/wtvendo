"""
LCD message formatting helpers for WTVendo.

Each function returns a list of 4 strings, one per LCD row, each exactly
20 characters (padded or truncated). The 20×4 I2C LCD is driven by the
Arduino; the Pi formats messages and sends them via LCD_WRITE commands.

Usage:
    from wtvendo.lcd_messages import format_welcome, format_classified

    lines = format_welcome()
    for row, text in enumerate(lines):
        serial_conn.send_command(CMD_LCD_WRITE, bytes([row, 0]) + text.encode())
"""

from __future__ import annotations

from wtvendo.config import ITEM_SLOTS

# LCD dimensions
LCD_COLS: int = 20
LCD_ROWS: int = 4


def _pad(text: str, width: int = LCD_COLS) -> str:
    """Pad or truncate a string to exactly ``width`` characters."""
    return text[:width].ljust(width)


def _format_lines(line0: str = "", line1: str = "", line2: str = "", line3: str = "") -> list[str]:
    """Build a 4-line LCD screen with each line padded to 20 chars."""
    return [_pad(line0), _pad(line1), _pad(line2), _pad(line3)]


# ---------------------------------------------------------------------------
# Screen Formatters
# ---------------------------------------------------------------------------


def format_welcome() -> list[str]:
    """Welcome screen shown when machine is idle."""
    return _format_lines(
        "*** WT-Vendo ***",
        "",
        "Insert a bottle",
        "to get started!",
    )


def format_scanning() -> list[str]:
    """Shown while the system is analyzing a bottle."""
    return _format_lines(
        "Scanning bottle...",
    )


def format_classified(class_name: str, points_earned: int, total_points: int) -> list[str]:
    """
    Show classification result: bottle type, points earned, and total.

    Args:
        class_name: Detected bottle class name.
        points_earned: Points awarded for this bottle.
        total_points: Session total after award.
    """
    # Truncate class name to fit on one line
    name_display = class_name[:LCD_COLS]
    earned_line = f"+{points_earned} pts!"
    total_line = f"Total: {total_points} pts"
    return _format_lines(name_display, earned_line, total_line)


def format_points(total: int) -> list[str]:
    """Show the accumulated point balance."""
    return _format_lines(
        f"Points: {total}",
        "",
        "Press 1-9 to select",
        "or insert a bottle",
    )


def format_item_menu(points: int) -> list[str]:
    """
    Show available items with costs and current balance.

    Displays a scrollable-style summary of affordable items. Due to the 4-line
    LCD limit, shows the first 3 affordable items plus balance. Students see
    the full slot→item mapping on a printed label next to the machine.

    Args:
        points: Current session point balance.
    """
    line0 = f"Balance: {points} pts"

    # Collect affordable items for display hint
    affordable = []
    for slot_num in sorted(ITEM_SLOTS.keys()):
        name, cost, _ = ITEM_SLOTS[slot_num]
        if points >= cost:
            affordable.append(f"{slot_num}:{name[:6]}={cost}")

    if not affordable:
        return _format_lines(line0, "No items affordable", "Insert more bottles!")

    # Show up to 3 items on lines 1–3
    lines = [line0]
    for i in range(min(3, len(affordable))):
        lines.append(affordable[i])

    # Pad remaining lines
    while len(lines) < LCD_ROWS:
        lines.append("")

    return [_pad(line) for line in lines[:LCD_ROWS]]


def format_dispensing(item_name: str) -> list[str]:
    """Show dispensing progress."""
    return _format_lines(
        "Dispensing...",
        item_name[:LCD_COLS],
        "",
        "Please wait",
    )


def format_error(message: str) -> list[str]:
    """Show a generic error message."""
    # Split long messages across two lines
    if len(message) <= LCD_COLS:
        return _format_lines("Error:", message)
    return _format_lines(
        "Error:",
        message[:LCD_COLS],
        message[LCD_COLS : LCD_COLS * 2],
    )


def format_insufficient(item_cost: int, balance: int) -> list[str]:
    """Show insufficient points message."""
    return _format_lines(
        "Not enough points!",
        f"Need: {item_cost} pts",
        f"Have: {balance} pts",
        "Insert more bottles",
    )


def format_timeout_warning() -> list[str]:
    """Show session ending warning (optional, before full timeout)."""
    return _format_lines(
        "Session ending...",
        "Insert a bottle or",
        "press a key to",
        "continue",
    )


def format_comm_error() -> list[str]:
    """Show communication error message."""
    return _format_lines(
        "Communication error",
        "Please wait...",
        "",
        "Retrying...",
    )


def format_classification_failed() -> list[str]:
    """Show message when bottle classification fails."""
    return _format_lines(
        "Could not identify",
        "bottle type.",
        "",
        "Try again!",
    )
