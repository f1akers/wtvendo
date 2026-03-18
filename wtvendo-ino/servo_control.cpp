/**
 * @file servo_control.cpp
 * @brief PCA9685 servo control implementation.
 *
 * PWM at 50 Hz (20 ms period).  12-bit resolution (4096 ticks per period).
 *
 * Pulse width mapping at 50 Hz:
 *   1300 µs → ~266 ticks  (continuous servo reverse — trapdoor close)
 *   1500 µs → ~307 ticks  (continuous servo neutral / stop)
 *   1700 µs → ~348 ticks  (continuous servo forward — dispense / trapdoor open)
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
    , _trapdoorSpinning(false)
    , _trapdoorStartMs(0)
    , _trapdoorDurationMs(0)
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

    // Ensure trapdoor starts off (360° mode — no hold needed)
    _pwm.setPWM(TRAPDOOR_CHANNEL, 0, 4096);

    // Fully disable all dispensing channels (no PWM signal)
    // Using neutral pulse (1500µs) leaves some servos creeping due to
    // dead-band variation, so we turn the output off entirely.
    for (uint8_t ch = DISPENSE_CH_MIN; ch <= DISPENSE_CH_MAX; ch++) {
        _pwm.setPWM(ch, 0, 4096);
    }
}

// ── Trapdoor (360° continuous rotation) ─────────────────────────────

void ServoControl::trapdoorOpen()
{
    _pwm.setPWM(TRAPDOOR_CHANNEL, 0, microsecondsToPWM(TRAPDOOR_FWD_US));
    _trapdoorSpinning   = true;
    _trapdoorStartMs    = millis();
    _trapdoorDurationMs = TRAPDOOR_OPEN_MS;
}

void ServoControl::trapdoorClose()
{
    _pwm.setPWM(TRAPDOOR_CHANNEL, 0, microsecondsToPWM(TRAPDOOR_REV_US));
    _trapdoorSpinning   = true;
    _trapdoorStartMs    = millis();
    _trapdoorDurationMs = TRAPDOOR_CLOSE_MS;
}

// 180° positional trapdoor (uncomment when replacement arrives):
// void ServoControl::trapdoorOpen()
// {
//     _pwm.setPWM(TRAPDOOR_CHANNEL, 0, microsecondsToPWM(TRAPDOOR_OPEN_US));
// }
//
// void ServoControl::trapdoorClose()
// {
//     _pwm.setPWM(TRAPDOOR_CHANNEL, 0, microsecondsToPWM(TRAPDOOR_CLOSE_US));
// }

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
    // Stop dispensing servo when duration expires
    if (_dispensing) {
        if (millis() - _dispStartMs >= _dispDurationMs) {
            _pwm.setPWM(_dispChannel, 0, 4096);
            _dispensing = false;
        }
    }

    // Stop trapdoor servo when spin duration expires (360° mode)
    if (_trapdoorSpinning) {
        if (millis() - _trapdoorStartMs >= _trapdoorDurationMs) {
            _pwm.setPWM(TRAPDOOR_CHANNEL, 0, 4096);
            _trapdoorSpinning = false;
        }
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
