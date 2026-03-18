/**
 * @file servo_control.cpp
 * @brief PCA9685 servo control implementation.
 *
 * PWM at 50 Hz (20 ms period).  12-bit resolution (4096 ticks per period).
 *
 * Pulse width mapping at 50 Hz:
 *   600 µs  → ~123 ticks  (trapdoor closed)
 *   1500 µs → ~307 ticks  (continuous servo neutral / stop)
 *   1700 µs → ~348 ticks  (continuous servo forward)
 *   2400 µs → ~491 ticks  (trapdoor open)
 *
 * Dependencies: Adafruit PWM Servo Driver Library, Wire, pin_config.h
 */

#include "servo_control.h"

ServoControl::ServoControl()
    : _pwm(PCA9685_ADDR)
    , _dispensing(false)
    , _dispChannel(0)
    , _dispStartMs(0)
    , _dispDurationMs(0)
{
}

void ServoControl::init()
{
    // Pull OE LOW before begin() so outputs are enabled as soon as PWM starts.
    // Active LOW — clone boards without a built-in pull-down need this explicit.
    pinMode(OE_PIN, OUTPUT);
    digitalWrite(OE_PIN, LOW);

    _pwm.begin();
    _pwm.setPWMFreq(50);  // 50 Hz for standard hobby servos
    delay(10);            // Allow oscillator to stabilize

    // Ensure trapdoor starts closed
    trapdoorClose();

    // Ensure all dispensing channels are stopped
    uint16_t stopPWM = microsecondsToPWM(DISPENSE_STOP_US);
    for (uint8_t ch = DISPENSE_CH_MIN; ch <= DISPENSE_CH_MAX; ch++) {
        _pwm.setPWM(ch, 0, stopPWM);
    }
}

// ── Trapdoor ────────────────────────────────────────────────────────

void ServoControl::trapdoorOpen()
{
    _pwm.setPWM(TRAPDOOR_CHANNEL, 0, microsecondsToPWM(TRAPDOOR_OPEN_US));
}

void ServoControl::trapdoorClose()
{
    _pwm.setPWM(TRAPDOOR_CHANNEL, 0, microsecondsToPWM(TRAPDOOR_CLOSE_US));
}

// ── Dispensing ──────────────────────────────────────────────────────

void ServoControl::startDispense(uint8_t channel, uint16_t durationMs)
{
    // Validate channel range
    if (channel > DISPENSE_CH_MAX) {
        return;
    }

    _dispChannel    = channel;
    _dispDurationMs = durationMs;
    _dispStartMs    = millis();
    _dispensing     = true;

    // Start forward spin
    _pwm.setPWM(channel, 0, microsecondsToPWM(DISPENSE_FWD_US));
}

void ServoControl::update()
{
    if (!_dispensing) {
        return;
    }

    // Check if spin duration has elapsed
    if (millis() - _dispStartMs >= _dispDurationMs) {
        // Stop the servo (neutral position)
        _pwm.setPWM(_dispChannel, 0, microsecondsToPWM(DISPENSE_STOP_US));
        _dispensing = false;
    }
}

bool ServoControl::isDispensing() const
{
    return _dispensing;
}

// ── PWM Conversion ──────────────────────────────────────────────────

uint16_t ServoControl::microsecondsToPWM(uint16_t us) const
{
    // 50 Hz → 20000 µs period, 12-bit resolution → 4096 ticks
    // ticks = us * 4096 / 20000
    return (uint16_t)((uint32_t)us * 4096UL / 20000UL);
}
