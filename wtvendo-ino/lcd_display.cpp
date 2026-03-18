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
{
    for (uint8_t r = 0; r < LCD_ROWS; r++) {
        _lastWriteTime[r] = 0;
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

    return true;
}

void LcdDisplay::writeLine(uint8_t row, uint8_t col, const char* text)
{
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

void LcdDisplay::clearDisplay()
{
    _lcd.clear();
    resetCache();
}

void LcdDisplay::backlightOn()
{
    _lcd.backlight();
}

void LcdDisplay::backlightOff()
{
    _lcd.noBacklight();
}

void LcdDisplay::resetCache()
{
    for (uint8_t r = 0; r < LCD_ROWS; r++) {
        memset(_lineCache[r], ' ', LCD_COLS);
        _lineCache[r][LCD_COLS] = '\0';
    }
}
