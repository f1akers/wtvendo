/**
 * @file sensor.cpp
 * @brief HC-SR04 non-blocking ultrasonic sensor implementation.
 *
 * Measurement cycle (state machine):
 *   IDLE → TRIGGER → WAIT_ECHO → READ → IDLE
 *
 * Distance = echoHighDuration_us × 0.343 / 2  (speed of sound ≈ 343 m/s)
 *
 * Detection logic:
 *   - 3 consecutive readings < 165 mm → object detected
 *   - Stays detected until reading > 220 mm (hysteresis)
 *   - EVENT_OBJECT_DETECTED queued once per detection episode
 *
 * Dependencies: pin_config.h, serial_comm.h (eventBuffer)
 */

#include "sensor.h"
#include "pin_config.h"
#include "serial_comm.h"

// Maximum echo wait time in microseconds (~4 m round-trip ≈ 23 ms)
static const uint32_t ECHO_TIMEOUT_US = 25000;

Sensor::Sensor(uint8_t trigPin, uint8_t echoPin)
    : _trigPin(trigPin)
    , _echoPin(echoPin)
    , _state(IDLE)
    , _lastMeasureTime(0)
    , _triggerStart(0)
    , _echoStart(0)
    , _distanceMM(0xFFFF)
    , _detected(false)
    , _consecutiveCount(0)
    , _eventSent(false)
{
}

void Sensor::init()
{
    pinMode(_trigPin, OUTPUT);
    pinMode(_echoPin, INPUT);
    digitalWrite(_trigPin, LOW);
}

void Sensor::update()
{
    uint32_t now = millis();

    switch (_state) {

    case IDLE:
        // Rate-limit: start a new measurement every SENSOR_POLL_MS
        if (now - _lastMeasureTime >= SENSOR_POLL_MS) {
            _lastMeasureTime = now;
            _state = TRIGGER;
        }
        break;

    case TRIGGER:
        // Send 10 µs HIGH pulse on trigger pin
        digitalWrite(_trigPin, HIGH);
        _triggerStart = micros();
        _state = WAIT_ECHO;
        break;

    case WAIT_ECHO: {
        uint32_t elapsed = micros() - _triggerStart;

        // Hold trigger HIGH for at least 10 µs
        if (elapsed < 10) {
            break;
        }
        digitalWrite(_trigPin, LOW);

        // Wait for echo pin to go HIGH (start of return pulse)
        if (digitalRead(_echoPin) == HIGH) {
            _echoStart = micros();
            _state = READ;
        } else if (elapsed > ECHO_TIMEOUT_US) {
            // No echo received — sensor timeout, no valid reading
            _state = IDLE;
        }
        break;
    }

    case READ: {
        if (digitalRead(_echoPin) == LOW) {
            // Echo pin went LOW — measurement complete
            uint32_t duration = micros() - _echoStart;

            // distance_mm = duration_us * 0.343 / 2
            // Use integer math: distance_mm = duration * 343 / 2000
            uint16_t distance = (uint16_t)((uint32_t)duration * 343UL / 2000UL);

            _distanceMM = distance;
            evaluateDetection(distance);
            _state = IDLE;
        } else if (micros() - _echoStart > ECHO_TIMEOUT_US) {
            // Echo stuck HIGH — timeout
            _state = IDLE;
        }
        break;
    }

    } // switch
}

uint16_t Sensor::getDistanceMM() const
{
    return _distanceMM;
}

bool Sensor::isObjectDetected() const
{
    return _detected;
}

void Sensor::evaluateDetection(uint16_t distance)
{
    if (!_detected) {
        // Not yet detected — count consecutive close readings
        if (distance < DETECT_THRESHOLD_MM) {
            _consecutiveCount++;
            if (_consecutiveCount >= CONSECUTIVE_READINGS) {
                _detected = true;
                _eventSent = false;

                // Enqueue EVENT_OBJECT_DETECTED with uint16 distance (big-endian)
                uint8_t payload[2];
                payload[0] = (uint8_t)(distance >> 8);   // MSB
                payload[1] = (uint8_t)(distance & 0xFF);  // LSB
                eventBuffer.enqueue(EVT_OBJECT_DETECTED, payload, 2);
                _eventSent = true;
            }
        } else {
            // Reading above threshold — reset consecutive counter
            _consecutiveCount = 0;
        }
    } else {
        // Currently detected — use hysteresis to exit
        if (distance > EXIT_THRESHOLD_MM) {
            _detected = false;
            _consecutiveCount = 0;
            _eventSent = false;
        }
    }
}
