/**
 * @file sensor.h
 * @brief Non-blocking HC-SR04 ultrasonic sensor driver.
 *
 * Uses a state-machine approach to avoid blocking the main loop with
 * pulseIn().  Measurements are taken at SENSOR_POLL_MS intervals
 * (default 100 ms).  Detection requires CONSECUTIVE_READINGS consecutive
 * readings below DETECT_THRESHOLD_MM, with EXIT_THRESHOLD_MM hysteresis
 * to prevent flicker.
 *
 * When an object is first detected the driver automatically enqueues an
 * EVENT_OBJECT_DETECTED event into the global serial event buffer.
 *
 * Dependencies: pin_config.h, serial_comm.h (eventBuffer)
 */

#ifndef SENSOR_H
#define SENSOR_H

#include <Arduino.h>

/**
 * @brief Non-blocking HC-SR04 measurement & detection state machine.
 */
class Sensor {
public:
    /**
     * @brief Construct a new Sensor.
     * @param trigPin  Digital pin connected to HC-SR04 TRIG.
     * @param echoPIn  Digital pin connected to HC-SR04 ECHO.
     */
    Sensor(uint8_t trigPin, uint8_t echoPin);

    /** @brief Configure pin modes.  Call once in setup(). */
    void init();

    /**
     * @brief Advance the measurement state machine.
     *
     * Call every loop() iteration.  Internally rate-limited to one
     * measurement cycle per SENSOR_POLL_MS.  When a new valid distance
     * is obtained the detection logic is evaluated.
     */
    void update();

    /**
     * @brief Last valid distance reading in millimetres.
     * @return uint16_t  Distance (mm), or 0xFFFF if no valid reading yet.
     */
    uint16_t getDistanceMM() const;

    /**
     * @brief Whether an object is currently detected (within threshold).
     */
    bool isObjectDetected() const;

private:
    /** Internal state machine phases. */
    enum SensorState : uint8_t {
        IDLE,           ///< Waiting for next measurement interval
        TRIGGER,        ///< Sending 10 µs trigger pulse
        WAIT_ECHO,      ///< Waiting for echo pin to go HIGH
        READ            ///< Measuring echo HIGH duration → distance
    };

    uint8_t  _trigPin;
    uint8_t  _echoPin;

    SensorState _state;
    uint32_t _lastMeasureTime;   ///< millis() of last measurement start
    uint32_t _triggerStart;      ///< micros() when trigger pin went HIGH
    uint32_t _echoStart;         ///< micros() when echo pin went HIGH

    uint16_t _distanceMM;        ///< Most recent valid distance (mm)
    bool     _detected;          ///< Current detection state (with hysteresis)
    uint8_t  _consecutiveCount;  ///< Consecutive close readings counter
    bool     _eventSent;         ///< True after event queued for current detection

    /** @brief Process a new distance reading through detection logic. */
    void evaluateDetection(uint16_t distance);
};

#endif // SENSOR_H
