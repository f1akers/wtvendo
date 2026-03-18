/**
 * @file servo_control.h
 * @brief PCA9685-based servo control for dispensing coils and trapdoor.
 *
 * Wraps the Adafruit_PWMServoDriver library.  Provides non-blocking
 * timed dispensing (forward spin for N ms then stop) and immediate
 * trapdoor open/close positioning.
 *
 * Channels 0–5: 360° continuous-rotation dispensing servos
 * Channel  6:   trapdoor servo (currently 360° continuous rotation)
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

    /** @brief Spin trapdoor servo to open (360° timed spin). */
    void trapdoorOpen();

    /** @brief Spin trapdoor servo to close (360° timed spin). */
    void trapdoorClose();

    // 180° positional trapdoor (uncomment when replacement arrives):
    // void trapdoorOpen();   // → setPWM(TRAPDOOR_CHANNEL, 0, TRAPDOOR_OPEN_US)
    // void trapdoorClose();  // → setPWM(TRAPDOOR_CHANNEL, 0, TRAPDOOR_CLOSE_US)

    // ── Dispensing ──────────────────────────────────────────────────

    /**
     * @brief Start a dispensing servo spinning forward.
     *
     * Non-blocking — records start time and duration.  Call update()
     * every loop() iteration to automatically stop when elapsed.
     *
     * @param channel      PCA9685 channel (0–8).
     * @param durationMs   How long to spin in milliseconds.
     */
    void startDispense(uint8_t channel, uint16_t durationMs);

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

private:
    Adafruit_PWMServoDriver _pwm;

    // Active dispense tracking
    bool     _dispensing;
    uint8_t  _dispChannel;
    uint32_t _dispStartMs;
    uint16_t _dispDurationMs;

    // Active trapdoor spin tracking (360° mode)
    bool     _trapdoorSpinning;
    uint32_t _trapdoorStartMs;

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
