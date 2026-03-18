/**
 * @file lcd_display.cpp
 * @brief LCD I2C display implementation with dirty-checking cache.
 *
 * The dirty-check strategy compares each incoming character against the
 * cached value.  Only changed characters trigger an I2C setCursor/print
 * call.  This minimises bus traffic, avoids full-screen clear flicker,
 * and keeps the update well within the 200 ms rate-limit budget.
 *
 * Dependencies: hd44780 library (>=1.3), Wire, pin_config.h
 */

#include "lcd_display.h"

LcdDisplay::LcdDisplay()
    : _ready(false)
{
    for (uint8_t r = 0; r < LCD_ROWS; r++) {
        _lastWriteTime[r] = 0;
        _rowPending[r] = false;
    }
    resetCache();
}

bool LcdDisplay::init()
{
    int status = _lcd.begin(LCD_COLS, LCD_ROWS);
    if (status != 0) {
        // hd44780 returns non-zero on failure
        return false;
    }

    _lcd.backlight();
    _lcd.clear();
    resetCache();
    _ready = true;

    return true;
}

void LcdDisplay::writeLine(uint8_t row, uint8_t col, const char* text)
{
    if (!_ready) return;

    // Validate row/col
    if (row >= LCD_ROWS || col >= LCD_COLS || text == nullptr) {
        return;
    }

    // Rate-limit per row to LCD_UPDATE_MS minimum interval
    uint32_t now = millis();
    if (now - _lastWriteTime[row] < LCD_UPDATE_MS) {
        return;
    }

    // Walk through the text, only writing characters that differ
    uint8_t c = col;
    for (const char* p = text; *p != '\0' && c < LCD_COLS; p++, c++) {
        if (_lineCache[row][c] != *p) {
            _lcd.setCursor(c, row);
            _lcd.print(*p);
            _lineCache[row][c] = *p;
        }
    }

    // Pad remainder of the row with spaces (clear trailing stale chars)
    for (; c < LCD_COLS; c++) {
        if (_lineCache[row][c] != ' ') {
            _lcd.setCursor(c, row);
            _lcd.print(' ');
            _lineCache[row][c] = ' ';
        }
    }

    _lastWriteTime[row] = now;
}

void LcdDisplay::queueWrite(uint8_t row, uint8_t col, const char* text)
{
    if (row >= LCD_ROWS || col >= LCD_COLS || text == nullptr) {
        return;
    }

    // If row isn't already pending, seed from current cache
    if (!_rowPending[row]) {
        memcpy(_pendingText[row], _lineCache[row], LCD_COLS + 1);
    }

    // Overlay new text starting at col
    uint8_t c = col;
    for (const char* p = text; *p != '\0' && c < LCD_COLS; p++, c++) {
        _pendingText[row][c] = *p;
    }
    // Pad remainder with spaces
    for (; c < LCD_COLS; c++) {
        _pendingText[row][c] = ' ';
    }
    _pendingText[row][LCD_COLS] = '\0';
    _rowPending[row] = true;
}

void LcdDisplay::update()
{
    if (!_ready) return;

    uint32_t now = millis();

    for (uint8_t row = 0; row < LCD_ROWS; row++) {
        if (!_rowPending[row]) {
            continue;
        }
        if (now - _lastWriteTime[row] < LCD_UPDATE_MS) {
            continue;
        }

        // Dirty-check write — only changed characters hit I2C
        for (uint8_t c = 0; c < LCD_COLS; c++) {
            if (_lineCache[row][c] != _pendingText[row][c]) {
                _lcd.setCursor(c, row);
                _lcd.print(_pendingText[row][c]);
                _lineCache[row][c] = _pendingText[row][c];
            }
        }

        _lastWriteTime[row] = now;
        _rowPending[row] = false;
        break;  // One row per call — spread I2C traffic
    }
}

void LcdDisplay::clearDisplay()
{
    if (!_ready) return;
    _lcd.clear();
    resetCache();
}

void LcdDisplay::backlightOn()
{
    if (!_ready) return;
    _lcd.backlight();
}

void LcdDisplay::backlightOff()
{
    if (!_ready) return;
    _lcd.noBacklight();
}

void LcdDisplay::resetCache()
{
    for (uint8_t r = 0; r < LCD_ROWS; r++) {
        memset(_lineCache[r], ' ', LCD_COLS);
        _lineCache[r][LCD_COLS] = '\0';
        memset(_pendingText[r], ' ', LCD_COLS);
        _pendingText[r][LCD_COLS] = '\0';
        _rowPending[r] = false;
    }
}
