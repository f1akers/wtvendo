/**
 * @file servo_control.cpp
 * @brief PCA9685 servo control implementation.
 *
 * PWM at 50 Hz (20 ms period).  12-bit resolution (4096 ticks per period).
 *
 * Pulse width mapping at 50 Hz:
 *   600  µs → ~123 ticks  (trapdoor closed position)
 *   1300 µs → ~266 ticks  (continuous servo CCW)
 *   1700 µs → ~348 ticks  (continuous servo CW)
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
    , _trapdoorSweeping(false)
    , _tdCurrentUs(TRAPDOOR_CLOSE_US)
    , _tdTargetUs(TRAPDOOR_CLOSE_US)
    , _tdLastStepMs(0)
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

// ── Trapdoor (180° positional, gradual sweep) ──────────────────────

void ServoControl::trapdoorOpen()
{
    _pwm.wakeup();
    digitalWrite(OE_PIN, LOW);
    _tdTargetUs      = TRAPDOOR_OPEN_US;
    _tdLastStepMs    = millis();
    _trapdoorSweeping = true;
    _trapdoorOpen    = true;
    // Write current position immediately so the servo is driven
    _pwm.setPWM(TRAPDOOR_CHANNEL, 0, microsecondsToPWM(_tdCurrentUs));
}

void ServoControl::trapdoorClose()
{
    _pwm.wakeup();
    digitalWrite(OE_PIN, LOW);
    _tdTargetUs      = TRAPDOOR_CLOSE_US;
    _tdLastStepMs    = millis();
    _trapdoorSweeping = true;
    _trapdoorOpen    = false;
    _pwm.setPWM(TRAPDOOR_CHANNEL, 0, microsecondsToPWM(_tdCurrentUs));
}

// ── Dispensing ──────────────────────────────────────────────────────

void ServoControl::startDispense(uint8_t channel, uint16_t durationMs, bool clockwise)
{
    // Validate channel range
    if (channel > DISPENSE_CH_MAX) {
        return;
    }

    _dispChannel    = channel;
    _dispDurationMs = durationMs;
    _dispStartMs    = millis();
    _dispensing     = true;

    uint16_t pulseUs = clockwise ? DISPENSE_CW_US : DISPENSE_CCW_US;

    _pwm.wakeup();
    digitalWrite(OE_PIN, LOW);
    _pwm.setPWM(channel, 0, microsecondsToPWM(pulseUs));
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

    // Step trapdoor toward target position
    if (_trapdoorSweeping) {
        uint32_t now = millis();
        if (now - _tdLastStepMs >= TRAPDOOR_STEP_MS) {
            _tdLastStepMs = now;
            if (_tdCurrentUs < _tdTargetUs) {
                _tdCurrentUs += TRAPDOOR_STEP_US;
                if (_tdCurrentUs > _tdTargetUs) _tdCurrentUs = _tdTargetUs;
            } else if (_tdCurrentUs > _tdTargetUs) {
                _tdCurrentUs -= TRAPDOOR_STEP_US;
                if (_tdCurrentUs < _tdTargetUs) _tdCurrentUs = _tdTargetUs;
            }
            _pwm.setPWM(TRAPDOOR_CHANNEL, 0, microsecondsToPWM(_tdCurrentUs));
            if (_tdCurrentUs == _tdTargetUs) {
                _trapdoorSweeping = false;
            }
        }
    }

    // On busy→idle transition: disable outputs and sleep the PCA9685.
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
    return _dispensing || _trapdoorSweeping;
}

// ── PWM Conversion ──────────────────────────────────────────────────

uint16_t ServoControl::microsecondsToPWM(uint16_t us) const
{
    // 50 Hz → 20000 µs period, 12-bit resolution → 4096 ticks
    // ticks = us * 4096 / 20000
    return (uint16_t)((uint32_t)us * 4096UL / 20000UL);
}
