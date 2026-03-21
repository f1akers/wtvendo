#!/usr/bin/env python3
"""Diagnostic script to test A4Tech camera detection and initialization."""

import logging
import sys
import time

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Test 1: List available cameras
print("=== Test 1: List available cameras ===")
try:
    from wtvendo.classifier import _list_video_devices
    devices = _list_video_devices()
    print(f"Found devices: {devices}")
except Exception as e:
    print(f"Error listing devices: {e}")

# Test 2: Try direct OpenCV scan
print("\n=== Test 2: Direct OpenCV scan (0-9) ===")
try:
    import cv2
    for idx in range(10):
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            print(f"Device {idx}: OPEN")
            # Check some properties
            w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            print(f"  - Resolution: {int(w)}x{int(h)}")
            cap.release()
        else:
            print(f"Device {idx}: closed")
except Exception as e:
    print(f"Error scanning: {e}")

# Test 3: Try to initialize A4Tech specifically
print("\n=== Test 3: Initialize A4Tech camera ===")
try:
    from wtvendo.classifier import create_camera
    print("Creating camera with camera_name='A4Tech'...")
    camera = create_camera("opencv", camera_name="A4Tech")
    print(f"Camera created: {camera}")
    print("Attempting to capture frame...")
    frame = camera.capture()
    print(f"Frame captured: {frame.shape}")
    print("Keeping camera open for 5 seconds...")
    time.sleep(5)
    print("Releasing camera...")
    camera.release()
    print("Done")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Test complete ===")
