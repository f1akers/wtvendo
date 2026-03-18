/**
 * @file pin_config.h
 * @brief Hardware pin assignments, I2C addresses, serial baud rates,
 *        sensor thresholds, and servo PWM calibration values.
 *
 * All hardware-specific constants are centralized here so that wiring
 * changes only require edits in one place.  Values come from
 * research.md §4 and §6 (wiring reference).
 *
 * Target board: Arduino Mega 2560
 */

#ifndef PIN_CONFIG_H
#define PIN_CONFIG_H

// ── HC-SR04 Ultrasonic Sensor ────────────────────────────────────────
#define TRIG_PIN  22   // Digital output – 10 µs pulse triggers measurement
#define ECHO_PIN  23   // Digital input  – high-duration ∝ distance

// ── 4×4 Membrane Keypad ─────────────────────────────────────────────
//    Row pins are outputs (directly driven by Keypad library)
//    Col pins are inputs  (read by Keypad library)
const byte KEYPAD_ROW_PINS[4] = {24, 25, 26, 27};
const byte KEYPAD_COL_PINS[4] = {28, 29, 30, 31};

// ── I2C Addresses ───────────────────────────────────────────────────
#define PCA9685_ADDR  0x40   // 16-channel PWM servo driver
#define LCD_ADDR      0x27   // 20×4 character LCD (PCF8574 backpack)

// ── Serial Baud Rates ───────────────────────────────────────────────
#define SERIAL_BAUD   115200  // Serial1 – Pi ↔ Arduino protocol link
#define DEBUG_BAUD    9600    // Serial0 – USB debug console

// ── PCA9685 Output Enable ────────────────────────────────────────────
//    OE is active LOW.  Drive it LOW explicitly so clone boards without a
//    built-in pull-down resistor don't leave servo outputs floating on boot.
#define OE_PIN  9

// ── PCA9685 Servo Channels ──────────────────────────────────────────
//    Channels 0–8: 360° continuous-rotation dispensing servos
//    Channel  9  : 180° positional trapdoor servo
#define TRAPDOOR_CHANNEL   9
#define DISPENSE_CH_MIN    0
#define DISPENSE_CH_MAX    8

// ── Sensor Detection Thresholds ─────────────────────────────────────
#define DETECT_THRESHOLD_MM    150   // Object closer than this → detected
#define EXIT_THRESHOLD_MM      200   // Must exceed this to clear detection
#define CONSECUTIVE_READINGS   3     // Consecutive readings needed to confirm

// ── Servo PWM Pulse Widths (microseconds) ───────────────────────────
//    Trapdoor (180° positional)
#define TRAPDOOR_OPEN_US   2400   // Fully open position
#define TRAPDOOR_CLOSE_US  600    // Fully closed position

//    Dispensing servos (360° continuous rotation)
#define DISPENSE_FWD_US    1700   // Forward spin (dispense)
#define DISPENSE_STOP_US   1500   // Neutral / stopped

// ── Timing Constants ────────────────────────────────────────────────
#define SENSOR_POLL_MS     100    // HC-SR04 measurement interval
#define LCD_UPDATE_MS      200    // Minimum LCD refresh interval

#endif // PIN_CONFIG_H
