/**
 * @file serial_comm.h
 * @brief Serial protocol packet parser, response builder, command dispatch
 *        interface, and 16-slot circular event buffer.
 *
 * Implements the Pi ↔ Arduino binary protocol defined in
 * docs/serial-protocol.md.  Packets use the format:
 *
 *     [0xAA] [CMD] [LEN] [PAYLOAD 0–64] [XOR checksum]
 *
 * The Arduino is the slave: it parses inbound commands from the Pi on
 * Serial1 and sends exactly one response per command.  Unsolicited
 * events (keypad presses, sensor triggers) are stored in a circular
 * event buffer and delivered to the Pi via POLL_EVENTS (0x01).
 *
 * Dependencies: Arduino core (Serial1, millis)
 */

#ifndef SERIAL_COMM_H
#define SERIAL_COMM_H

#include <Arduino.h>

// ── Protocol Constants ──────────────────────────────────────────────
#define START_MARKER      0xAA
#define MAX_PAYLOAD_LEN   64

// ── Command Bytes (Pi → Arduino) ────────────────────────────────────
#define CMD_POLL_EVENTS      0x01
#define CMD_READ_SENSOR      0x02
#define CMD_LCD_WRITE        0x03
#define CMD_LCD_CLEAR        0x04
#define CMD_SERVO_DISPENSE   0x05
#define CMD_SERVO_TRAPDOOR   0x06
#define CMD_GET_KEYPAD       0x07

// ── Event Bytes (Arduino → Pi, via POLL_EVENTS) ────────────────────
#define EVT_KEYPRESS          0x10
#define EVT_OBJECT_DETECTED   0x11

// ── Response Codes ──────────────────────────────────────────────────
#define RESP_ACK   0xFE
#define RESP_NACK  0xFF

// ── NACK Error Codes ────────────────────────────────────────────────
#define ERR_UNKNOWN_CMD    0x01
#define ERR_INVALID_PAYLOAD 0x02
#define ERR_HARDWARE_FAULT 0x03
#define ERR_BUSY           0x04

// ── Event Buffer ────────────────────────────────────────────────────

/** Maximum number of events the ring buffer can hold. */
#define EVENT_BUFFER_SIZE  16

/**
 * @brief A single queued event (command byte + payload).
 */
struct Event {
    uint8_t cmd;
    uint8_t length;
    uint8_t payload[8];  // Events are small (≤ 2 bytes payload typically)
};

/**
 * @brief Fixed-size circular (ring) buffer for unsolicited events.
 *
 * When the buffer is full the oldest event is silently overwritten,
 * ensuring the Arduino never blocks on event production.
 */
class EventBuffer {
public:
    EventBuffer();

    /**
     * @brief Enqueue an event.  Overwrites oldest if full.
     * @param cmd     Event command byte (e.g. EVT_KEYPRESS).
     * @param payload Pointer to payload bytes (may be NULL if len == 0).
     * @param len     Payload length (0-8).
     */
    void enqueue(uint8_t cmd, const uint8_t* payload, uint8_t len);

    /**
     * @brief Dequeue the oldest event.
     * @param out  Pointer to Event struct to fill.
     * @return true if an event was dequeued, false if buffer was empty.
     */
    bool dequeue(Event* out);

    /** @return true when no events are queued. */
    bool isEmpty() const;

private:
    Event _buf[EVENT_BUFFER_SIZE];
    uint8_t _head;  // Next write position
    uint8_t _tail;  // Next read position
    uint8_t _count; // Current number of queued events
};

// ── Packet Structures ───────────────────────────────────────────────

/**
 * @brief Parsed inbound packet from the Pi.
 */
struct Packet {
    uint8_t cmd;
    uint8_t length;
    uint8_t payload[MAX_PAYLOAD_LEN];
    bool    valid;  // true if checksum verified OK
};

// ── Serial Communication Functions ──────────────────────────────────

/**
 * @brief Attempt to read and parse one packet from Serial1.
 *
 * Scans for the 0xAA start marker, reads CMD + LEN + PAYLOAD + CHK,
 * validates length (≤ 64) and XOR checksum.
 *
 * @param pkt  Pointer to Packet struct to populate.
 * @return true if a valid, complete packet was parsed.
 */
bool readPacket(Packet* pkt);

/**
 * @brief Send an ACK response on Serial1.
 * @param payload  Optional payload bytes (NULL if none).
 * @param len      Payload length (0 for bare ACK).
 */
void sendAck(const uint8_t* payload = nullptr, uint8_t len = 0);

/**
 * @brief Send a NACK / error response on Serial1.
 * @param errorCode  One of ERR_UNKNOWN_CMD, ERR_INVALID_PAYLOAD, etc.
 */
void sendNack(uint8_t errorCode);

/**
 * @brief Send an event packet on Serial1 (used inside POLL_EVENTS).
 * @param cmd      Event command byte (e.g. EVT_KEYPRESS).
 * @param payload  Payload bytes.
 * @param len      Payload length.
 */
void sendEvent(uint8_t cmd, const uint8_t* payload, uint8_t len);

/**
 * @brief Build and transmit a raw packet on Serial1.
 *
 * Computes XOR checksum automatically.
 *
 * @param cmd      Command / response byte.
 * @param payload  Payload bytes (may be NULL if len == 0).
 * @param len      Payload length.
 */
void sendPacket(uint8_t cmd, const uint8_t* payload, uint8_t len);

/**
 * @brief Compute XOR checksum over CMD, LENGTH, and PAYLOAD.
 */
uint8_t computeChecksum(uint8_t cmd, uint8_t len, const uint8_t* payload);

// ── Global Event Buffer (shared across modules) ────────────────────
extern EventBuffer eventBuffer;

#endif // SERIAL_COMM_H
