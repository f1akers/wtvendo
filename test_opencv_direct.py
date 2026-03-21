#!/usr/bin/env python3
"""Test if OpenCV can directly capture from the A4Tech camera."""

import cv2
import time

print("Testing OpenCV camera access...")

# Try device 0 directly
print("\nOpening cv2.VideoCapture(0)...")
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("ERROR: Could not open device 0")
    exit(1)

print("✓ Device opened")

# Try to read a frame
print("\nAttempting to read frame...")
ret, frame = cap.read()

if not ret:
    print("ERROR: Could not read frame")
    print(f"  ret={ret}, frame={frame}")
else:
    print(f"✓ Frame captured: {frame.shape}")

# Try a few more times
print("\nTrying 5 captures...")
for i in range(5):
    ret, frame = cap.read()
    if ret:
        print(f"  Capture {i+1}: OK ({frame.shape})")
    else:
        print(f"  Capture {i+1}: FAILED")
    time.sleep(0.5)

print("\nReleasing camera...")
cap.release()
print("Done")
