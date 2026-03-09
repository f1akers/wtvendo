/**
 * @file keypad_input.h
 * @brief Non-blocking 4×4 membrane keypad driver.
 *
 * Uses the Keypad library's getKey() for non-blocking reads each
 * loop iteration.  When a key in the '1'–'9' range is detected it is
 * automatically enqueued as an EVENT_KEYPRESS event into the global
 * serial event buffer for the Pi to poll.
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
     * Call every loop() iteration.  If a key is detected:
     *   - It is stored internally (retrievable via getLastKey())
     *   - If it is an item key ('1'–'9'), an EVENT_KEYPRESS is
     *     enqueued into the global event buffer automatically.
     */
    void update();

    /**
     * @brief Get the last detected key press.
     * @return char  ASCII key character, or 0 if no key since last call.
     */
    char getLastKey();

    /**
     * @brief Check whether a key character maps to a dispensing slot.
     * @param key  ASCII key character.
     * @return true if key is '1' through '9'.
     */
    static bool isItemKey(char key);

    /**
     * @brief Convert a key character to a slot number.
     * @param key  ASCII key character ('1'–'9').
     * @return uint8_t  Slot number (1–9).  Returns 0 for invalid keys.
     */
    static uint8_t getSlotFromKey(char key);

private:
    /** @brief 4×4 key map matching the physical membrane layout. */
    static const char _keys[4][4];

    Keypad _keypad;
    char   _lastKey;  ///< Most recent key press (0 = none)
};

#endif // KEYPAD_INPUT_H
