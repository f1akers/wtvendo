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
    , _lastEventMs(0)
    , _pendingKey(0)
{
    _keypad.setDebounceTime(KEYPAD_DEBOUNCE_MS);
}

// ── Public Methods ──────────────────────────────────────────────────

void KeypadInput::update()
{
    // Phase 2: confirm pending key is still physically held
    if (_pendingKey != 0) {
        char pending = _pendingKey;
        _pendingKey = 0;

        // Re-scan the matrix and check if the key is still down
        _keypad.getKeys();
        for (uint8_t i = 0; i < LIST_MAX; i++) {
            if (_keypad.key[i].kchar == pending &&
                (_keypad.key[i].kstate == PRESSED ||
                 _keypad.key[i].kstate == HOLD)) {
                // Confirmed — real press
                _lastKey = pending;
                _lastEventMs = millis();
                uint8_t payload = (uint8_t)pending;
                eventBuffer.enqueue(EVT_KEYPRESS, &payload, 1);
                return;
            }
        }
        // Key released between scans — noise, discard
        return;
    }

    // Phase 1: detect new key press candidate
    char key = _keypad.getKey();
    if (key != 0) {
        uint32_t now = millis();
        if (now - _lastEventMs < KEYPAD_COOLDOWN_MS) {
            return;
        }
        // Don't enqueue yet — mark as pending for confirmation
        _pendingKey = key;
    }
}

char KeypadInput::getLastKey()
{
    char k = _lastKey;
    _lastKey = 0;  // Clear after read
    return k;
}

