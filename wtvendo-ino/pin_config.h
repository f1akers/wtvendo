/**
 * @file pin_config.h
 * @brief Hardware pin assignments, I2C addresses, serial baud rates,
 *        sensor thresholds, and servo PWM calibration values.
 *
 * All hardware-specific constants are centralized here so that wiring
 * changes only require edits in one place.  Values come from
 * research.md §4 and §6 (wiring reference).
 *
 * Target board: Arduino Uno
 */

#ifndef PIN_CONFIG_H
#define PIN_CONFIG_H

// ── 4×4 Membrane Keypad ─────────────────────────────────────────────
//    Row pins are outputs (directly driven by Keypad library)
//    Col pins are inputs  (read by Keypad library)
//    Indices 0-3 → rows (D2–D5); indices 4-7 → cols (D6–D8, D10)
const byte KEYPAD_ROW_PINS[4] = {10, 8, 7, 6};
const byte KEYPAD_COL_PINS[4] = {5, 4, 3, 2};

// ── I2C Bus Pins ─────────────────────────────────────────────────────
//    A4 and A5 are the hardware I2C pins on the Uno.  Wire.begin() uses
//    them automatically — no SoftWire library needed.
#define I2C_SCL_PIN  A5   // SCL — hardware I2C on Uno
#define I2C_SDA_PIN  A4   // SDA — hardware I2C on Uno

// ── I2C Addresses ───────────────────────────────────────────────────
#define PCA9685_ADDR  0x40   // 16-channel PWM servo driver
#define LCD_ADDR      0x27   // 20×4 character LCD (PCF8574 backpack)

// ── Serial Baud Rate ─────────────────────────────────────────────────
//    Hardware Serial (pins 0/1) is used exclusively for Pi ↔ Arduino
//    protocol.  No separate debug serial — do not add Serial.print()
//    calls as they will corrupt the packet stream.
#define SERIAL_BAUD   115200

// ── PCA9685 Output Enable ────────────────────────────────────────────
//    OE is active LOW.  Drive it LOW explicitly so clone boards without a
//    built-in pull-down resistor don't leave servo outputs floating on boot.
#define OE_PIN  A0

// ── PCA9685 Servo Channels ──────────────────────────────────────────
//    Channels 0–5: 360° continuous-rotation dispensing servos
//    Channel  6  : trapdoor servo (currently 360° continuous rotation)
#define TRAPDOOR_CHANNEL   6
#define DISPENSE_CH_MIN    0
#define DISPENSE_CH_MAX    5

// ── Servo PWM Pulse Widths (microseconds) ───────────────────────────
//    Trapdoor — 180° positional
#define TRAPDOOR_OPEN_US   1950   // 75% open position (was 2400)
#define TRAPDOOR_CLOSE_US  600    // Fully closed position

//    Dispensing servos (360° continuous rotation)
#define DISPENSE_CCW_US    1300   // Counterclockwise spin (below neutral)
#define DISPENSE_CW_US     1700   // Clockwise spin (above neutral)
#define DISPENSE_STOP_US   1500   // Neutral / stopped

// ── Timing Constants ────────────────────────────────────────────────
#define LCD_UPDATE_MS      200    // Minimum LCD refresh interval

// ── Keypad Noise Filtering ─────────────────────────────────────────
#define KEYPAD_DEBOUNCE_MS  100   // Keypad library debounce (default 10)
#define KEYPAD_COOLDOWN_MS  300   // Min ms between accepted key events

#endif // PIN_CONFIG_H
