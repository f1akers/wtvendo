/**
 * @file wtvendo-ino.ino
 * @brief WTVendo Arduino main sketch — setup() + cooperative loop().
 *
 * Orchestrates all peripheral modules via a non-blocking cooperative
 * multitasking loop.  The Arduino acts as a slave device: it processes
 * commands from the Raspberry Pi over Serial1, manages hardware
 * peripherals, and queues unsolicited events for the Pi to poll.
 *
 * Module responsibilities:
 *   serial_comm   — Parse inbound packets, build responses, event buffer
 *   servo_control — PCA9685 trapdoor + dispensing servo control
 *   keypad_input  — 4×4 membrane keypad with event auto-enqueue
 *   lcd_display   — 20×4 I2C LCD with dirty-checking cache
 *
 * Timing budget per loop() iteration (typical):
 *   Serial processing:  ~10 µs  (if bytes available)
 *   Keypad polling:     ~50 µs  (matrix scan)
 *   Servo update:       ~5 µs   (millis() comparison)
 *   Total:              ~65 µs  (well under 1 ms)
 *
 * SRAM budget estimate (Arduino Mega 2560 — 8192 bytes):
 *   Event buffer:       16 × 10 = 160 bytes
 *   LCD cache:          4 × 21  = 84 bytes
 *   Packet buffers:     ~70 bytes
 *   Servo state:        ~12 bytes
 *   Keypad:             ~40 bytes
 *   Stack + overhead:   ~300 bytes
 *   Total:              ~666 bytes (~8.1% of 8 KB)
 *   ✓ Well under 75% SRAM budget
 *
 * Dependencies: All wtvendo-ino modules, Wire library
 *
 * Protocol reference: docs/serial-protocol.md
 */

#include <Wire.h>
#include "pin_config.h"
#include "serial_comm.h"
#include "servo_control.h"
#include "keypad_input.h"
#include "lcd_display.h"

// ── Module Instances ────────────────────────────────────────────────
static ServoControl servos;
static KeypadInput  keypad;
static LcdDisplay   lcd;

// ── Forward Declarations ────────────────────────────────────────────
void processCommand(const Packet& pkt);
void handlePollEvents();
void handleLcdWrite(const Packet& pkt);
void handleLcdClear();
void handleServoDispense(const Packet& pkt);
void handleServoTrapdoor(const Packet& pkt);
void handleGetKeypad();

// =====================================================================
//  setup()
// =====================================================================

void setup()
{
    // ── Pi communication serial (pins 0/1) ──────────────────────────
    Serial.begin(SERIAL_BAUD);

    // ── I2C bus ─────────────────────────────────────────────────────
    Wire.begin();

    // ── Servo driver ────────────────────────────────────────────────
    servos.init();

    // ── LCD ─────────────────────────────────────────────────────────
    if (lcd.init()) {
        // Show welcome message using F() macro to keep strings in flash
        lcd.writeLine(0, 0, "*** WT-Vendo ***");
        lcd.writeLine(1, 0, "");
        lcd.writeLine(2, 0, "Insert a bottle");
        lcd.writeLine(3, 0, "to get started!");
    }

    // ── Keypad (no explicit init needed — constructor configures) ───
}

// =====================================================================
//  loop() — Cooperative Non-Blocking Scheduler
// =====================================================================

void loop()
{
    // ── 1. Serial packet processing (every iteration) ───────────────
    //    Check for inbound command from Pi and process immediately.
    Packet pkt;
    if (readPacket(&pkt)) {
        if (pkt.valid) {
            processCommand(pkt);
        }
        // Invalid packets are already NACK'd by readPacket()
    }

    // ── 2. Keypad polling (every iteration) ─────────────────────────
    //    Non-blocking scan.  Events auto-enqueued by KeypadInput.
    keypad.update();

    // ── 3. Servo spin tracking (every iteration) ────────────────────
    //    Stops dispensing/trapdoor servo when duration expires.
    servos.update();

    // ── 4. LCD queue flush (every iteration) ─────────────────────────
    //    Writes one pending row per call, rate-limited by LCD_UPDATE_MS.
    lcd.update();
}

// =====================================================================
//  Command Dispatcher
// =====================================================================

/**
 * @brief Route an inbound command to the appropriate handler.
 *
 * Unknown commands receive a NACK with ERR_UNKNOWN_CMD.
 *
 * @param pkt  Validated inbound packet.
 */
void processCommand(const Packet& pkt)
{
    switch (pkt.cmd) {

    case CMD_POLL_EVENTS:
        handlePollEvents();
        break;

    case CMD_LCD_WRITE:
        handleLcdWrite(pkt);
        break;

    case CMD_LCD_CLEAR:
        handleLcdClear();
        break;

    case CMD_SERVO_DISPENSE:
        handleServoDispense(pkt);
        break;

    case CMD_SERVO_TRAPDOOR:
        handleServoTrapdoor(pkt);
        break;

    case CMD_GET_KEYPAD:
        handleGetKeypad();
        break;

    default:
        sendNack(ERR_UNKNOWN_CMD);
        break;
    }
}

// =====================================================================
//  Command Handlers
// =====================================================================

/**
 * @brief POLL_EVENTS (0x01) — Dequeue one event or send empty ACK.
 *
 * If the event buffer has queued events, the oldest is sent as a
 * full event packet (CMD = event type).  If empty, a bare ACK is sent.
 */
void handlePollEvents()
{
    Event evt;
    if (eventBuffer.dequeue(&evt)) {
        sendEvent(evt.cmd, evt.payload, evt.length);
    } else {
        sendAck();  // Empty ACK — no events
    }
}

/**
 * @brief LCD_WRITE (0x03) — Write text to a specific LCD position.
 *
 * Payload format: [row(1)] [col(1)] [text(N)]
 * Validates row (0–3) and col (0–19).
 */
void handleLcdWrite(const Packet& pkt)
{
    if (pkt.length < 3) {
        sendNack(ERR_INVALID_PAYLOAD);
        return;
    }

    uint8_t row = pkt.payload[0];
    uint8_t col = pkt.payload[1];

    if (row >= LCD_ROWS || col >= LCD_COLS) {
        sendNack(ERR_INVALID_PAYLOAD);
        return;
    }

    // Extract text — build null-terminated string from payload
    // Text starts at payload[2], length = pkt.length - 2
    uint8_t textLen = pkt.length - 2;
    char textBuf[LCD_COLS + 1];
    uint8_t copyLen = (textLen < LCD_COLS) ? textLen : LCD_COLS;
    memcpy(textBuf, &pkt.payload[2], copyLen);
    textBuf[copyLen] = '\0';

    lcd.queueWrite(row, col, textBuf);
    sendAck();
}

/**
 * @brief LCD_CLEAR (0x04) — Clear the entire LCD display.
 */
void handleLcdClear()
{
    lcd.clearDisplay();
    sendAck();
}

/**
 * @brief SERVO_DISPENSE (0x05) — Activate a dispensing servo.
 *
 * Payload: [channel(1)] [duration_ms(2, big-endian)]
 *
 * Non-blocking: starts the servo spin and ACKs immediately.  The servo
 * is stopped automatically by servos.update() in loop() when the
 * duration expires.  ACKing immediately avoids Pi-side timeouts (the
 * 200 ms serial timeout is shorter than typical 1200 ms spin).
 *
 * The isDispensing() guard rejects concurrent requests with ERR_BUSY.
 */
void handleServoDispense(const Packet& pkt)
{
    if (pkt.length < 3) {
        sendNack(ERR_INVALID_PAYLOAD);
        return;
    }

    uint8_t  channel    = pkt.payload[0];
    uint16_t durationMs = ((uint16_t)pkt.payload[1] << 8) | pkt.payload[2];

    if (channel > DISPENSE_CH_MAX) {
        sendNack(ERR_INVALID_PAYLOAD);
        return;
    }

    if (servos.isDispensing()) {
        sendNack(ERR_BUSY);
        return;
    }

    servos.startDispense(channel, durationMs);
    sendAck();
}

/**
 * @brief SERVO_TRAPDOOR (0x06) — Open or close the trapdoor.
 *
 * Payload: [position(1)] — 0x00 = close, 0x01 = open
 */
void handleServoTrapdoor(const Packet& pkt)
{
    if (pkt.length < 1) {
        sendNack(ERR_INVALID_PAYLOAD);
        return;
    }

    uint8_t position = pkt.payload[0];

    if (position == 0x01) {
        servos.trapdoorOpen();
    } else {
        servos.trapdoorClose();
    }

    sendAck();
}

/**
 * @brief GET_KEYPAD (0x07) — Return current keypad state.
 *
 * Responds with ACK + 1-byte key character, or 0x00 if no key pressed.
 * This reads the immediate state, not the event queue.
 */
void handleGetKeypad()
{
    char key = keypad.getLastKey();
    uint8_t payload = (key != 0) ? (uint8_t)key : 0x00;
    sendAck(&payload, 1);
}
