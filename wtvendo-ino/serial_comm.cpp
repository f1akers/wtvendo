/**
 * @file serial_comm.cpp
 * @brief Implementation of the serial packet parser, response builder,
 *        and 16-slot circular event buffer.
 *
 * Protocol reference: docs/serial-protocol.md
 *
 * Dependencies: Arduino core (Serial)
 */

#include "serial_comm.h"

// ── Global Event Buffer Instance ────────────────────────────────────
EventBuffer eventBuffer;

// =====================================================================
//  EventBuffer Implementation
// =====================================================================

EventBuffer::EventBuffer()
    : _head(0), _tail(0), _count(0)
{
}

void EventBuffer::enqueue(uint8_t cmd, const uint8_t* payload, uint8_t len)
{
    // Clamp payload length to Event struct capacity
    if (len > sizeof(_buf[0].payload)) {
        len = sizeof(_buf[0].payload);
    }

    _buf[_head].cmd    = cmd;
    _buf[_head].length = len;
    if (payload && len > 0) {
        memcpy(_buf[_head].payload, payload, len);
    }

    _head = (_head + 1) % EVENT_BUFFER_SIZE;

    if (_count < EVENT_BUFFER_SIZE) {
        _count++;
    } else {
        // Buffer full — advance tail (oldest event lost)
        _tail = (_tail + 1) % EVENT_BUFFER_SIZE;
    }
}

bool EventBuffer::dequeue(Event* out)
{
    if (_count == 0) {
        return false;
    }

    *out = _buf[_tail];
    _tail = (_tail + 1) % EVENT_BUFFER_SIZE;
    _count--;
    return true;
}

bool EventBuffer::isEmpty() const
{
    return _count == 0;
}

// =====================================================================
//  Checksum
// =====================================================================

uint8_t computeChecksum(uint8_t cmd, uint8_t len, const uint8_t* payload)
{
    uint8_t chk = cmd ^ len;
    for (uint8_t i = 0; i < len; i++) {
        chk ^= payload[i];
    }
    return chk;
}

// =====================================================================
//  Packet Transmission
// =====================================================================

void sendPacket(uint8_t cmd, const uint8_t* payload, uint8_t len)
{
    uint8_t chk = computeChecksum(cmd, len, payload);

    Serial.write(START_MARKER);
    Serial.write(cmd);
    Serial.write(len);
    if (payload && len > 0) {
        Serial.write(payload, len);
    }
    Serial.write(chk);
    Serial.flush();  // Ensure all bytes are sent before returning
}

void sendAck(const uint8_t* payload, uint8_t len)
{
    sendPacket(RESP_ACK, payload, len);
}

void sendNack(uint8_t errorCode)
{
    sendPacket(RESP_NACK, &errorCode, 1);
}

void sendEvent(uint8_t cmd, const uint8_t* payload, uint8_t len)
{
    sendPacket(cmd, payload, len);
}

// =====================================================================
//  Packet Reception / Parsing
// =====================================================================

/**
 * Parser state machine states.
 * Persisted across calls so partial packets are handled correctly.
 */
static enum ParserState : uint8_t {
    PS_WAIT_START,
    PS_READ_CMD,
    PS_READ_LEN,
    PS_READ_PAYLOAD,
    PS_READ_CHECKSUM
} parserState = PS_WAIT_START;

static uint8_t  pktCmd;
static uint8_t  pktLen;
static uint8_t  pktPayload[MAX_PAYLOAD_LEN];
static uint8_t  pktIdx;

bool readPacket(Packet* pkt)
{
    while (Serial.available()) {
        uint8_t b = Serial.read();

        switch (parserState) {

        case PS_WAIT_START:
            if (b == START_MARKER) {
                parserState = PS_READ_CMD;
            }
            // else: discard — scan for start marker
            break;

        case PS_READ_CMD:
            pktCmd = b;
            parserState = PS_READ_LEN;
            break;

        case PS_READ_LEN:
            pktLen = b;
            if (pktLen > MAX_PAYLOAD_LEN) {
                // Invalid length — reset parser
                parserState = PS_WAIT_START;
                break;
            }
            pktIdx = 0;
            if (pktLen == 0) {
                parserState = PS_READ_CHECKSUM;
            } else {
                parserState = PS_READ_PAYLOAD;
            }
            break;

        case PS_READ_PAYLOAD:
            pktPayload[pktIdx++] = b;
            if (pktIdx >= pktLen) {
                parserState = PS_READ_CHECKSUM;
            }
            break;

        case PS_READ_CHECKSUM: {
            uint8_t expected = computeChecksum(pktCmd, pktLen, pktPayload);
            parserState = PS_WAIT_START;  // Reset for next packet

            if (b == expected) {
                pkt->cmd    = pktCmd;
                pkt->length = pktLen;
                memcpy(pkt->payload, pktPayload, pktLen);
                pkt->valid  = true;
                return true;
            } else {
                // Checksum mismatch — send NACK and discard
                sendNack(ERR_INVALID_PAYLOAD);
                pkt->valid = false;
                return false;
            }
        }

        } // switch
    } // while

    // No complete packet available yet
    return false;
}
