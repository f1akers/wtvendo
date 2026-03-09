/**
 * @file keypad_input.cpp
 * @brief 4×4 membrane keypad implementation with auto event buffering.
 *
 * The Keypad library handles debouncing internally.  getKey() returns
 * 0 (NO_KEY) when nothing is pressed, so calling update() every
 * iteration is inherently non-blocking.
 *
 * Dependencies: Keypad library, pin_config.h, serial_comm.h
 */

#include "keypad_input.h"
#include "serial_comm.h"

// ── Static key map ──────────────────────────────────────────────────
const char KeypadInput::_keys[4][4] = {
    {'1', '2', '3', 'A'},
    {'4', '5', '6', 'B'},
    {'7', '8', '9', 'C'},
    {'*', '0', '#', 'D'}
};

// ── Constructor ─────────────────────────────────────────────────────

KeypadInput::KeypadInput()
    : _keypad(
          Keypad(makeKeymap(_keys),
                 const_cast<byte*>(KEYPAD_ROW_PINS),
                 const_cast<byte*>(KEYPAD_COL_PINS),
                 4, 4))
    , _lastKey(0)
{
}

// ── Public Methods ──────────────────────────────────────────────────

void KeypadInput::update()
{
    char key = _keypad.getKey();

    if (key != 0) {
        _lastKey = key;

        // Auto-enqueue event for item keys ('1'–'9')
        if (isItemKey(key)) {
            uint8_t payload = (uint8_t)key;
            eventBuffer.enqueue(EVT_KEYPRESS, &payload, 1);
        }
    }
}

char KeypadInput::getLastKey()
{
    char k = _lastKey;
    _lastKey = 0;  // Clear after read
    return k;
}

bool KeypadInput::isItemKey(char key)
{
    return (key >= '1' && key <= '9');
}

uint8_t KeypadInput::getSlotFromKey(char key)
{
    if (isItemKey(key)) {
        return (uint8_t)(key - '0');  // '1'→1, '2'→2, …, '9'→9
    }
    return 0;  // Invalid
}
