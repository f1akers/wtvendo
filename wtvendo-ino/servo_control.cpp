/**
 * @file servo_control.cpp
 * @brief PCA9685 servo control implementation.
 *
 * PWM at 50 Hz (20 ms period).  12-bit resolution (4096 ticks per period).
 *
 * Pulse width mapping at 50 Hz:
 *   600  µs → ~123 ticks  (trapdoor closed position)
 *   1300 µs → ~266 ticks  (continuous servo reverse)
 *   1500 µs → ~307 ticks  (continuous servo neutral / stop)
 *   2400 µs → ~491 ticks  (trapdoor open position)
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
    , _trapdoorOpen(false)
{
}

void ServoControl::init()
{
    // OE (active LOW) controls all PCA9685 outputs.
    // Start HIGH (disabled) — only pull LOW when a servo needs to spin.
    // This eliminates PWM noise that couples into keypad lines.
    pinMode(OE_PIN, OUTPUT);
    digitalWrite(OE_PIN, HIGH);

    _pwm.begin();
    _pwm.setPWMFreq(50);  // 50 Hz for standard hobby servos
    delay(10);            // Allow oscillator to stabilize

    // Pre-set all channels to off so they're safe when OE goes LOW
    _pwm.setPWM(TRAPDOOR_CHANNEL, 0, 4096);
    for (uint8_t ch = DISPENSE_CH_MIN; ch <= DISPENSE_CH_MAX; ch++) {
        _pwm.setPWM(ch, 0, 4096);
    }

    // Sleep the PCA9685 — stops the internal 25MHz oscillator,
    // eliminating EMI that couples into keypad lines.
    // OE HIGH + sleep = completely silent until a servo is needed.
    _pwm.sleep();
}

// ── Trapdoor (180° positional) ──────────────────────────────────────

void ServoControl::trapdoorOpen()
{
    _pwm.wakeup();
    digitalWrite(OE_PIN, LOW);
    _pwm.setPWM(TRAPDOOR_CHANNEL, 0, microsecondsToPWM(TRAPDOOR_OPEN_US));
    _trapdoorOpen = true;
}

void ServoControl::trapdoorClose()
{
    _pwm.wakeup();
    digitalWrite(OE_PIN, LOW);
    _pwm.setPWM(TRAPDOOR_CHANNEL, 0, microsecondsToPWM(TRAPDOOR_CLOSE_US));
    _trapdoorOpen = false;
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

    _pwm.wakeup();
    digitalWrite(OE_PIN, LOW);
    _pwm.setPWM(channel, 0, microsecondsToPWM(DISPENSE_FWD_US));
}

void ServoControl::update()
{
    bool wasBusy = isBusy();

    // Stop dispensing servo when duration expires
    if (_dispensing) {
        if (millis() - _dispStartMs >= _dispDurationMs) {
            _pwm.setPWM(_dispChannel, 0, 4096);
            _dispensing = false;
        }
    }

    // On busy→idle transition: disable outputs and sleep the PCA9685.
    // Sleep stops the 25MHz oscillator — eliminates EMI into keypad lines.
    // Only fires once (not every iteration) to avoid repeated I2C writes.
    // Note: trapdoor is 180° positional — it holds position via OE staying
    // LOW while dispensing is active, then parks when OE goes HIGH.
    if (wasBusy && !isBusy()) {
        digitalWrite(OE_PIN, HIGH);
        _pwm.sleep();
    }
}

bool ServoControl::isDispensing() const
{
    return _dispensing;
}

bool ServoControl::isBusy() const
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
