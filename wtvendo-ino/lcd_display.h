/**
 * @file lcd_display.h
 * @brief I2C 20×4 LCD display driver with dirty-checking line cache.
 *
 * Uses the hd44780 library with hd44780_I2Cexp I/O class for automatic
 * I2C address and pin-mapping detection.  A 4-line content cache avoids
 * rewriting unchanged characters, eliminating flicker.  Writes are
 * rate-limited to a minimum of LCD_UPDATE_MS (200 ms) between refreshes.
 *
 * Dependencies: hd44780 library (>=1.3), Wire, pin_config.h
 */

#ifndef LCD_DISPLAY_H
#define LCD_DISPLAY_H

#include <Arduino.h>
#include <Wire.h>
#include <hd44780.h>
#include <hd44780ioClass/hd44780_I2Cexp.h>
#include "pin_config.h"

/** Number of columns per LCD row. */
#define LCD_COLS  20
/** Number of rows on the LCD. */
#define LCD_ROWS  4

/**
 * @brief 20×4 I2C LCD display wrapper with per-character dirty cache.
 */
class LcdDisplay {
public:
    LcdDisplay();

    /**
     * @brief Initialize the LCD hardware.
     *
     * Calls begin(20, 4), turns on backlight, clears display, and
     * resets the line cache.  Call once in setup().
     *
     * @return true if initialization succeeded.
     */
    bool init();

    /**
     * @brief Write a text string at a given row and column.
     *
     * Only characters that differ from the cached content are actually
     * written to the LCD, reducing I2C traffic and eliminating flicker.
     * Text is truncated to fit within the 20-column row.
     *
     * Rate-limited: if called more frequently than LCD_UPDATE_MS the
     * write is deferred until the next allowed update window.
     *
     * @param row   Row index (0–3).
     * @param col   Starting column (0–19).
     * @param text  Null-terminated ASCII string.
     */
    void writeLine(uint8_t row, uint8_t col, const char* text);

    /**
     * @brief Clear the entire display and reset the line cache.
     */
    void clearDisplay();

    /** @brief Turn the LCD backlight on. */
    void backlightOn();

    /** @brief Turn the LCD backlight off. */
    void backlightOff();

private:
    hd44780_I2Cexp _lcd;

    /**
     * @brief Per-character content cache.
     *
     * lineCache[row][col] holds the last character written at that
     * position.  Initialised to spaces.  An extra byte per row
     * provides null-termination for convenience.
     */
    char _lineCache[LCD_ROWS][LCD_COLS + 1];

    /** @brief millis() timestamp of the last LCD write operation. */
    uint32_t _lastWriteTime;

    /** @brief Reset all cache entries to spaces. */
    void resetCache();
};

#endif // LCD_DISPLAY_H
