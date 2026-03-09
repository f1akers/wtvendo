# Feature Specification: WTVendo — Bottle-for-Supplies Vending System

**Feature Branch**: `001-vendo-system`  
**Created**: 2026-03-09  
**Status**: Draft  
**Input**: User description: "Vending machine system that detects water bottles, classifies them, and gives points to dispense school supply items using Raspberry Pi and Arduino"

## User Scenarios & Testing _(mandatory)_

### User Story 1 — Insert Bottle and Earn Points (Priority: P1)

A student walks up to the vending machine with a used water bottle. They place the bottle into the intake slot. The machine detects the bottle with the ultrasonic sensor, triggers the Raspberry Pi camera to classify it, identifies the bottle type, awards the correct number of points, and displays the updated point total on the LCD screen.

**Why this priority**: This is the core value loop — exchanging a bottle for points. Without it, nothing else in the system matters.

**Independent Test**: Place a known bottle type (e.g., "large bottled water") into the intake. Verify the ultrasonic sensor triggers detection, the Pi classifies it correctly, points are awarded and displayed on the LCD, and the trapdoor servo opens to clear the bottle.

**Acceptance Scenarios**:

1. **Given** the machine is idle and displaying a welcome message, **When** a student places a "medium bottled water" into the intake slot, **Then** the HC-SR04 detects the object and signals the Pi to capture and classify the bottle.
2. **Given** the Pi has classified a bottle as "small soda", **When** classification is complete, **Then** the corresponding point value is added to the session total and the LCD displays the updated points.
3. **Given** a bottle has been classified and points awarded, **When** the scoring is complete, **Then** the trapdoor servo (channel 9) opens to drop the bottle away and then closes, readying the machine for the next bottle.
4. **Given** the HC-SR04 triggers but the Pi classifies the object with confidence ≤ 0.5 or as an unknown object, **When** classification fails, **Then** the system rejects the item, displays a message on the LCD (e.g., "Item not recognized — please remove"), and does **not** award points.

---

### User Story 2 — Select and Dispense a School Supply Item (Priority: P1)

After accumulating enough points, the student uses the membrane keypad to browse or select a school supply item from the available options. The LCD shows available items and their point costs. If the student has enough points, the corresponding servo (channels 0–8) spins to dispense the item, and the point balance is deducted.

**Why this priority**: This completes the exchange — points for supplies. Together with Story 1, it forms the minimum viable product.

**Independent Test**: Pre-load a session with a known point balance. Use the keypad to select an item. Verify the LCD shows available items, the servo for the correct channel dispenses the item, points are deducted, and the updated balance is shown.

**Acceptance Scenarios**:

1. **Given** a student has accumulated 15 points and item on channel 3 costs 10 points, **When** the student presses the key for that item on the keypad, **Then** the servo on channel 3 spins the coil to dispense the item and the LCD shows the remaining 5 points.
2. **Given** a student has 5 points and the cheapest item costs 10 points, **When** the student tries to select that item, **Then** the LCD displays "Not enough points" and no servo activates.
3. **Given** a student has selected an item and it is being dispensed, **When** the servo finishes spinning, **Then** the LCD updates with the new balance and returns to the item selection screen.

---

### User Story 3 — Serial Communication Between Pi and Arduino (Priority: P1)

The Raspberry Pi and Arduino communicate over a serial (RX-TX) connection using a strict request-response protocol. Only one device sends at a time to avoid bus collisions. The Arduino acts as the peripheral controller (sensors, servos, LCD, keypad) and responds to commands from the Pi, which acts as the brain (classification, points logic, session state).

**Why this priority**: Every interaction between detection, classification, display, and dispensing depends on reliable communication. A collision or lost message breaks the entire flow.

**Independent Test**: Send a known request from the Pi (e.g., "read ultrasonic sensor") and verify the Arduino responds within the expected timeout. Simulate concurrent events (e.g., keypad press during classification) and verify no message collisions occur.

**Acceptance Scenarios**:

1. **Given** the Pi sends a "read sensor" request to the Arduino, **When** the Arduino receives it, **Then** the Arduino responds with the ultrasonic distance reading and no other message is sent until the response is received.
2. **Given** the Arduino detects a keypad press while a Pi request is in flight, **When** the keypad event occurs, **Then** the Arduino queues the keypad event and only sends it after the current request-response cycle completes.
3. **Given** the Pi sends a command and receives no response within the timeout period, **When** the timeout expires, **Then** the Pi retries the command up to a configurable number of attempts before flagging an error on the LCD.

---

### User Story 4 — LCD Status Display (Priority: P2)

The LCD (20×4, I2C) continuously shows contextual information to the user: a welcome message when idle, classification status while scanning, point totals after scanning, item selection menu when choosing, and dispensing progress during item release.

**Why this priority**: User feedback is essential for usability, but the system could technically function without the LCD in a degraded mode.

**Independent Test**: Walk through the full flow (idle → insert bottle → classify → show points → select item → dispense) and verify each LCD state transition shows the correct message at each step.

**Acceptance Scenarios**:

1. **Given** the machine is idle with no session activity, **When** no bottle is detected, **Then** the LCD displays a welcome message (e.g., "Insert a bottle to start!").
2. **Given** a bottle has just been detected, **When** the Pi is classifying it, **Then** the LCD shows "Scanning bottle..." or similar status.
3. **Given** the student is in item selection mode, **When** the keypad is active, **Then** the LCD shows available items with point costs and highlights the current selection.

---

### User Story 5 — Session Lifecycle (Priority: P2)

A session begins when the first bottle is inserted and ends when the student finishes dispensing or after an inactivity timeout. Points accumulate across multiple bottle insertions within a single session. When the session ends, the point balance resets to zero.

**Why this priority**: Session management ensures points don't persist forever and the machine resets for the next student.

**Independent Test**: Insert multiple bottles, verify points accumulate. Wait for the inactivity timeout and verify points reset and the LCD returns to the welcome state.

**Acceptance Scenarios**:

1. **Given** a student inserts a first bottle, **When** it is classified, **Then** a new session starts and the points from that bottle are shown.
2. **Given** a session is active and the student inserts a second bottle, **When** it is classified, **Then** the new points are added to the existing session total.
3. **Given** a session is active, **When** no interaction occurs for the timeout duration, **Then** the session ends, points reset to zero, and the LCD returns to the welcome screen.

---

### Edge Cases

- What happens when the ultrasonic sensor triggers but no bottle is present (e.g., a hand passes through)? — The Pi classifies with low confidence and rejects; LCD displays "Item not recognized."
- What happens if a servo channel jams or fails to spin? — The system should detect a timeout (no expected feedback within time window) and display an error on the LCD for that slot.
- What happens if power is interrupted mid-session? — Points are lost (volatile session), and the system returns to idle on restart. The trapdoor servo defaults to closed.
- What happens if the student presses multiple keypad keys simultaneously? — The membrane keypad library returns the first detected key; additional keys are ignored.
- What happens if the Pi sends a command while the Arduino is still processing the previous one? — The request-response protocol prevents this; the Pi waits for a response or timeout before sending the next command.
- What happens if all 9 dispensing slots are empty? — The system should still accept bottles and accumulate points but inform the student "No items available" when they try to select.

## Requirements _(mandatory)_

### Functional Requirements

#### Bottle Detection & Classification

- **FR-001**: The system MUST use the HC-SR04 ultrasonic sensor to detect when an object is placed in the intake slot.
- **FR-002**: Upon object detection, the Arduino MUST send a notification to the Pi (via the request-response protocol) indicating an object is present.
- **FR-003**: The Raspberry Pi MUST capture an image using the Pi Camera (primary) and run the YOLO26 Nano model (.pt) to classify the bottle into one of the following classes: large bottled water, medium bottled water, medium soda, medium thick bottle, pepsi viper, small bottled water, small soda, small thick bottle, xs soda, xs thick bottle. If the Pi Camera does not provide sufficient image quality, the system supports switching to a USB webcam as a fallback (configuration change only, no code restructuring required).
- **FR-004**: If the model classifies the object with a confidence score ≤ 0.5 or does not recognize it, the system MUST reject the item and notify the user via the LCD.
- **FR-005**: After classification (success or failure), the trapdoor servo (channel 9, 180° servo) MUST open to drop the bottle and then return to the closed position.

#### Points System

- **FR-006**: Each bottle class MUST map to a hard-coded point value defined in the system configuration.
- **FR-007**: Points MUST accumulate across multiple bottle insertions within a single session.
- **FR-008**: When an item is dispensed, the system MUST deduct the item's point cost from the session total.
- **FR-009**: The system MUST prevent item dispensing if the session point balance is less than the item cost.

#### Item Dispensing

- **FR-010**: The system MUST support 9 dispensing slots (servo channels 0–8), each driven by a JDI 6221MG 360° continuous-rotation servo that spins a coil to release an item.
- **FR-011**: The 4×4 membrane switch keypad (keys: 1–9, 0, A–D, \*, #) MUST allow the student to select which item to dispense. Keys 1–9 map directly to dispensing slots (channels 0–8 respectively).
- **FR-012**: Upon valid selection, the corresponding servo MUST activate for a defined rotation duration sufficient to push one item out.
- **FR-013**: The trapdoor servo (channel 9, JDI 6221MG 180° servo) MUST open and close to clear bottles from the intake area.

#### Serial Communication (RX-TX)

- **FR-014**: The Pi and Arduino MUST communicate over a serial UART connection using a request-response protocol where only one message is in transit at a time.
- **FR-015**: The Pi MUST act as the primary initiator of requests (master), and the Arduino MUST respond to each request before the Pi sends the next.
- **FR-016**: If the Arduino has unsolicited data (e.g., a keypad press or sensor trigger), it MUST queue the event and transmit it only when polled by the Pi or after the current request-response cycle completes.
- **FR-017**: Each message MUST include a message type identifier so the receiver can parse and route it correctly.
- **FR-018**: The Pi MUST implement a configurable timeout for each request, with a retry mechanism (up to a configurable max retries) before flagging a communication error.

#### LCD Display

- **FR-019**: The system MUST use a 20×4 I2C LCD connected to the Arduino via SDA/SCL to display status messages to the user.
- **FR-020**: The LCD MUST display context-appropriate messages: welcome/idle, scanning status, classification result, accumulated points, item selection menu, dispensing status, and error messages.

#### Servo Driver

- **FR-021**: The system MUST use an Adafruit PCA9685 PWM Servo Driver board connected via I2C (SDA/SCL) to control all servos.
- **FR-022**: Channels 0–8 MUST drive JDI 6221MG 360° continuous-rotation servos for item dispensing.
- **FR-023**: Channel 9 MUST drive a JDI 6221MG 180° positional servo for the trapdoor mechanism.

#### Session Management

- **FR-024**: A session MUST begin when the first bottle of a new interaction is classified successfully.
- **FR-025**: A session MUST end when the student explicitly ends it (if such an option exists on the keypad) or after an inactivity timeout.
- **FR-026**: When a session ends, the accumulated points MUST reset to zero.

### Key Entities

- **Bottle Class**: One of 10 recognized bottle types. Each maps to a fixed point value. The Pi's classification model outputs this.
- **Session**: A transient interaction encompassing one student's bottle insertions and item selections. Tracks accumulated points. Not persisted across power cycles.
- **Dispensing Slot**: One of 9 physical coil-based dispensing channels (0–8), each holding a school supply item.
- **Serial Message**: A structured data packet exchanged between Pi and Arduino, containing a message type, payload, and optional checksum for integrity.
- **Trapdoor**: The servo-controlled hatch (channel 9) that opens to clear the intake area after each bottle scan.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: The system correctly classifies at least 90% of known bottle types placed in the intake slot under normal lighting conditions.
- **SC-002**: An end-to-end cycle (bottle insertion → classification → points displayed) completes within 5 seconds.
- **SC-003**: Item dispensing (keypad selection → servo activation → item released) completes within 3 seconds.
- **SC-004**: No serial message collisions occur during normal operation (verified by logging over 100 consecutive transactions).
- **SC-005**: The LCD displays the correct contextual message within 1 second of each state transition.
- **SC-006**: The system handles at least 50 consecutive bottle-scan-and-dispense cycles without requiring a restart or encountering communication errors.
- **SC-007**: Students can complete the full flow (insert bottle → see points → select item → receive item) without external instructions, guided only by LCD prompts.

## Assumptions

- The Pi Camera module is the primary image capture device, already connected and configured. A USB webcam is available as a fallback if Pi Camera quality is insufficient.
- The YOLO26 Nano model (.pt file) is pre-trained and available on the Pi; training is out of scope for this feature.
- Power supply is sufficient to drive the Pi, Arduino, servo driver board, and all servos simultaneously.
- The vending machine enclosure and physical coil mechanism are already designed; this spec covers the electronic and software control only.
- The HC-SR04 is positioned to reliably detect a bottle placed in the intake slot at close range.
- The Arduino and Pi share a common ground for serial communication.
- Only one student uses the machine at a time (no multi-user concurrency).
- The inactivity timeout duration will be configured during implementation (reasonable default: 60 seconds).
- Point values per bottle class and costs per item will be defined as constants in code and adjusted during testing.
- The I2C bus is shared between the LCD and the PCA9685 servo driver, using different I2C addresses (LCD typically 0x27, PCA9685 typically 0x40).
