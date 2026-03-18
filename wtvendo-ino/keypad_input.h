/**
 * @file keypad_input.h
 * @brief Non-blocking 4×4 membrane keypad driver.
 *
 * Uses the Keypad library's getKey() for non-blocking reads each
 * loop iteration.  Every key press is enqueued as an EVENT_KEYPRESS
 * event into the global serial event buffer for the Pi to handle.
 *
 * Key layout (matches physical membrane keypad):
 *
 *     1  2  3  A
 *     4  5  6  B
 *     7  8  9  C
 *     *  0  #  D
 *
 * Dependencies: Keypad library (>=3.1), pin_config.h, serial_comm.h
 */

#ifndef KEYPAD_INPUT_H
#define KEYPAD_INPUT_H

#include <Arduino.h>
#include <Keypad.h>
#include "pin_config.h"

/**
 * @brief Non-blocking 4×4 keypad wrapper with event buffering.
 */
class KeypadInput {
public:
    KeypadInput();

    /**
     * @brief Poll the keypad for a new key press.
     *
     * Call every loop() iteration.  Every detected key is stored
     * internally and enqueued as an EVENT_KEYPRESS into the global
     * event buffer for the Pi to process.
     */
    void update();

    /**
     * @brief Get the last detected key press and clear it.
     * @return char  ASCII key character, or 0 if no key since last call.
     */
    char getLastKey();

private:
    /** @brief 4×4 key map matching the physical membrane layout. */
    static const char _keys[4][4];

    Keypad _keypad;
    char   _lastKey;  ///< Most recent key press (0 = none)
};

#endif // KEYPAD_INPUT_H
