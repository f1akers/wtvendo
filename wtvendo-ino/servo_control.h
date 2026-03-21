/**
 * @file servo_control.h
 * @brief PCA9685-based servo control for dispensing coils and trapdoor.
 *
 * Wraps the Adafruit_PWMServoDriver library.  Provides non-blocking
 * timed dispensing (forward spin for N ms then stop) and immediate
 * trapdoor open/close positioning.
 *
 * Channels 0–5: 360° continuous-rotation dispensing servos
 * Channel  6:   trapdoor servo (180° positional)
 *
 * Dependencies: Adafruit PWM Servo Driver Library, pin_config.h
 */

#ifndef SERVO_CONTROL_H
#define SERVO_CONTROL_H

#include <Arduino.h>
#include <Adafruit_PWMServoDriver.h>
#include "pin_config.h"

/**
 * @brief High-level servo control for the vending machine.
 */
class ServoControl {
public:
    ServoControl();

    /**
     * @brief Initialize PCA9685 at 50 Hz.  Call once in setup().
     */
    void init();

    // ── Trapdoor ────────────────────────────────────────────────────

    /** @brief Move trapdoor servo to open position (180°). */
    void trapdoorOpen();

    /** @brief Move trapdoor servo to closed position (180°). */
    void trapdoorClose();

    // ── Dispensing ──────────────────────────────────────────────────

    /**
     * @brief Start a dispensing servo spinning.
     *
     * Non-blocking — records start time and duration.  Call update()
     * every loop() iteration to automatically stop when elapsed.
     *
     * @param channel      PCA9685 channel (0–8).
     * @param durationMs   How long to spin in milliseconds.
     * @param clockwise    true = CW (1700µs), false = CCW (1300µs).
     */
    void startDispense(uint8_t channel, uint16_t durationMs, bool clockwise = false);

    /**
     * @brief Check elapsed time and stop servo when duration expires.
     *
     * Call every loop() iteration.  No-op when no dispense is active.
     */
    void update();

    /**
     * @brief Whether a dispensing operation is currently in progress.
     */
    bool isDispensing() const;

    /**
     * @brief Whether any servo (dispense or trapdoor) is currently active.
     */
    bool isBusy() const;

private:
    Adafruit_PWMServoDriver _pwm;

    // Active dispense tracking
    bool     _dispensing;
    uint8_t  _dispChannel;
    uint32_t _dispStartMs;
    uint16_t _dispDurationMs;

    // Trapdoor state tracking (180° positional mode)
    bool _trapdoorOpen;

    /**
     * @brief Convert a pulse width in microseconds to a 12-bit PCA9685
     *        PWM tick count at 50 Hz (20 ms period).
     *
     * Formula: ticks = us × 4096 / 20000
     *
     * @param us  Pulse width in microseconds (e.g. 600–2400).
     * @return uint16_t  12-bit PWM value for setPWM().
     */
    uint16_t microsecondsToPWM(uint16_t us) const;
};

#endif // SERVO_CONTROL_H
