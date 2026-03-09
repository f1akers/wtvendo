"""
YOLO bottle classifier module for WTVendo.

Provides camera abstraction and YOLO inference for classifying bottle types.
Supports picamera2 (Pi Camera) and OpenCV (USB webcam) backends via a factory
function. The Classifier class loads a YOLO model with SHA256 verification and
runs single-frame detection returning the top class name and confidence.

Usage:
    from wtvendo.classifier import Classifier, create_camera

    camera = create_camera("picamera2")
    clf = Classifier()
    frame = camera.capture()
    result = clf.classify(frame)
    if result:
        class_name, confidence = result
"""

from __future__ import annotations

import abc
import hashlib
import logging
import os
import re
from typing import Optional

import numpy as np

from wtvendo.config import CONFIDENCE_THRESHOLD, IMAGE_SIZE, MODEL_PATH

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Camera Backends
# ---------------------------------------------------------------------------


class CameraBackend(abc.ABC):
    """Abstract base class for camera capture backends."""

    @abc.abstractmethod
    def capture(self) -> np.ndarray:
        """
        Capture a single frame.

        Returns:
            BGR image as a NumPy array (H×W×3, uint8).
        """

    @abc.abstractmethod
    def release(self) -> None:
        """Release camera resources."""


class PiCamera2Backend(CameraBackend):
    """Camera backend using picamera2 for Raspberry Pi Camera Module."""

    def __init__(self) -> None:
        from picamera2 import Picamera2  # type: ignore[import-untyped]

        self._camera = Picamera2()
        self._camera.configure(
            self._camera.create_still_configuration(
                main={"size": (IMAGE_SIZE, IMAGE_SIZE), "format": "BGR888"}
            )
        )
        self._camera.start()
        logger.info("PiCamera2 backend initialized at %dx%d", IMAGE_SIZE, IMAGE_SIZE)

    def capture(self) -> np.ndarray:
        """Capture a single frame from the Pi Camera."""
        return self._camera.capture_array()  # type: ignore[no-any-return]

    def release(self) -> None:
        """Stop and close the Pi Camera."""
        self._camera.stop()
        self._camera.close()
        logger.info("PiCamera2 backend released")


class OpenCVBackend(CameraBackend):
    """Camera backend using OpenCV VideoCapture for USB webcams."""

    def __init__(self, device: int = 0) -> None:
        import cv2

        self._cap = cv2.VideoCapture(device)
        if not self._cap.isOpened():
            raise RuntimeError(f"Failed to open camera device {device}")
        logger.info("OpenCV backend initialized on device %d", device)

    def capture(self) -> np.ndarray:
        """Capture a single frame from the USB webcam."""
        import cv2

        ret, frame = self._cap.read()
        if not ret or frame is None:
            raise RuntimeError("Failed to capture frame from webcam")
        # Resize to model input size
        frame = cv2.resize(frame, (IMAGE_SIZE, IMAGE_SIZE))
        return frame  # type: ignore[no-any-return]

    def release(self) -> None:
        """Release the webcam."""
        self._cap.release()
        logger.info("OpenCV backend released")


def create_camera(backend_name: str = "picamera2") -> CameraBackend:
    """
    Factory function to create the appropriate camera backend.

    Args:
        backend_name: 'picamera2' for Pi Camera, 'opencv' for USB webcam.

    Returns:
        A CameraBackend instance.

    Raises:
        ValueError: If backend_name is not recognized.
    """
    name = backend_name.lower().strip()
    if name == "picamera2":
        return PiCamera2Backend()
    elif name == "opencv":
        return OpenCVBackend()
    else:
        raise ValueError(
            f"Unknown camera backend '{backend_name}'. Use 'picamera2' or 'opencv'."
        )


# ---------------------------------------------------------------------------
# SHA256 Verification
# ---------------------------------------------------------------------------


def _read_expected_hash(readme_path: str) -> Optional[str]:
    """
    Read the SHA256 hash from models/README.md.

    Scans for a line containing 'SHA256' followed by a 64-char hex string.

    Args:
        readme_path: Path to the README.md file.

    Returns:
        Lowercase hex digest string, or None if not found or placeholder.
    """
    if not os.path.isfile(readme_path):
        return None

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Match a 64-character hex string on a line containing SHA256
    match = re.search(r"SHA256.*?`([a-fA-F0-9]{64})`", content)
    if match:
        return match.group(1).lower()

    return None


def _compute_file_hash(file_path: str) -> str:
    """
    Compute SHA256 hash of a file.

    Args:
        file_path: Path to the file to hash.

    Returns:
        Lowercase hex digest string.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def verify_model_hash(model_path: str) -> bool:
    """
    Verify the YOLO model file against the SHA256 hash in models/README.md.

    Args:
        model_path: Path to the model .pt file.

    Returns:
        True if hash matches or no expected hash is available (placeholder).
        False if hash mismatch.
    """
    readme_path = os.path.join(os.path.dirname(model_path), "README.md")
    expected = _read_expected_hash(readme_path)

    if expected is None:
        logger.warning(
            "No SHA256 hash found in %s — skipping verification", readme_path
        )
        return True

    actual = _compute_file_hash(model_path)
    if actual == expected:
        logger.info("Model SHA256 verified: %s", actual[:16] + "...")
        return True
    else:
        logger.error(
            "Model SHA256 MISMATCH! Expected %s..., got %s...",
            expected[:16],
            actual[:16],
        )
        return False


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


class Classifier:
    """
    YOLO-based bottle classifier.

    Loads a YOLO model from disk, verifies its SHA256 hash, and provides
    single-frame classification returning the top detection's class name
    and confidence.

    Attributes:
        model_path: Filesystem path to the YOLO model weights.
        image_size: Input resolution for inference (square).
        confidence_threshold: Minimum confidence to accept a detection.
    """

    def __init__(
        self,
        model_path: str = MODEL_PATH,
        image_size: int = IMAGE_SIZE,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
    ) -> None:
        self.model_path = os.path.abspath(model_path)
        self.image_size = image_size
        self.confidence_threshold = confidence_threshold
        self._model = None

    def load(self) -> None:
        """
        Load the YOLO model from disk with SHA256 verification.

        Raises:
            FileNotFoundError: If model file does not exist.
            RuntimeError: If SHA256 hash verification fails.
        """
        if not os.path.isfile(self.model_path):
            raise FileNotFoundError(
                f"YOLO model not found at {self.model_path}. "
                "See models/README.md for download instructions."
            )

        if not verify_model_hash(self.model_path):
            raise RuntimeError(
                f"Model SHA256 verification failed for {self.model_path}"
            )

        from ultralytics import YOLO  # type: ignore[import-untyped]

        self._model = YOLO(self.model_path)
        logger.info("YOLO model loaded from %s", self.model_path)

    def classify(self, frame: np.ndarray) -> Optional[tuple[str, float]]:
        """
        Run YOLO inference on a single frame.

        Calls model.predict() with the configured image size and confidence
        threshold. Returns the top detection (highest confidence) if any
        detections are present.

        Args:
            frame: BGR image as NumPy array (H×W×3, uint8).

        Returns:
            (class_name, confidence) tuple for the top detection, or None
            if no detections meet the confidence threshold.
        """
        if self._model is None:
            raise RuntimeError("Model not loaded — call load() first")

        results = self._model.predict(
            frame,
            imgsz=self.image_size,
            conf=self.confidence_threshold,
            verbose=False,
        )

        # results is a list with one Results object per image
        if not results or len(results) == 0:
            return None

        result = results[0]

        # result.boxes contains detections; empty if nothing found
        if result.boxes is None or len(result.boxes) == 0:
            return None

        # Get the detection with highest confidence
        confidences = result.boxes.conf.cpu().numpy()
        class_ids = result.boxes.cls.cpu().numpy().astype(int)

        best_idx = int(confidences.argmax())
        best_conf = float(confidences[best_idx])
        best_cls_id = class_ids[best_idx]

        # Map class ID to name via model's names dict
        class_name = result.names.get(best_cls_id, f"unknown_{best_cls_id}")

        logger.debug(
            "Classification: '%s' (conf=%.3f, id=%d)", class_name, best_conf, best_cls_id
        )

        return (class_name, best_conf)
