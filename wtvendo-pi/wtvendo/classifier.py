"""
YOLO bottle classifier module for WTVendo.

Provides camera abstraction and YOLO inference for classifying bottle types.
Supports picamera2 (Pi Camera) and OpenCV (USB webcam) backends via a factory
function. The Classifier class loads a YOLO NCNN model directory and runs
single-frame detection using the ncnn Python bindings directly — no PyTorch
required.

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
import logging
import os
from typing import Optional

import numpy as np

from wtvendo.config import CAMERA_DEVICE_NAME, CONFIDENCE_THRESHOLD, IMAGE_SIZE, MODEL_PATH

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


def _find_camera_by_name(name: str) -> list[int]:
    """
    Find V4L2 video capture devices whose name contains the given substring.

    Only returns devices that support VIDEO_CAPTURE (filters out metadata nodes
    that would flash the camera LED when opened).

    Returns a list of device indices sorted ascending, or empty list.
    Non-Linux platforms return an empty list (falls through to index scan).
    """
    import glob as _glob
    import sys

    if sys.platform != "linux":
        return []

    matches: list[int] = []
    for path in sorted(_glob.glob("/sys/class/video4linux/video*/name")):
        try:
            dev_name = open(path, "r").read().strip()
        except OSError:
            continue
        if name.lower() not in dev_name.lower():
            continue

        idx_str = path.split("/")[-2].replace("video", "")
        try:
            idx = int(idx_str)
        except ValueError:
            continue

        # Check this is a capture device, not a metadata node.
        # Metadata nodes lack the "capture" capability in uevent.
        uevent_path = path.replace("/name", "/device/video4linux/video" + idx_str + "/uevent")
        try:
            uevent = open(uevent_path, "r").read()
        except OSError:
            uevent = ""

        # Also accept if uevent check is inconclusive — we'll verify with OpenCV
        if "CAPTURE" not in uevent.upper() and uevent:
            logger.debug("Skipping video%d — not a capture device", idx)
            continue

        logger.info("V4L2 device video%d matches '%s' (name='%s')", idx, name, dev_name)
        matches.append(idx)

    if not matches:
        logger.info("No V4L2 device matching '%s' found", name)
    return matches


class OpenCVBackend(CameraBackend):
    """Camera backend using OpenCV VideoCapture for USB webcams."""

    def __init__(self, device: Optional[int] = 0) -> None:
        import cv2

        if device is not None:
            self._cap = cv2.VideoCapture(device)
            if not self._cap.isOpened():
                raise RuntimeError(f"Failed to open camera device {device}")
            self._warmup()
            logger.info("OpenCV backend initialized on device %d", device)
            return

        # Try to find camera by name (e.g. "A4Tech") first
        for idx in _find_camera_by_name(CAMERA_DEVICE_NAME):
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    self._cap = cap
                    self._warmup()
                    logger.info(
                        "OpenCV backend found '%s' camera on device %d",
                        CAMERA_DEVICE_NAME, idx,
                    )
                    return
            cap.release()

        # Fallback: scan devices 0–9 for any working camera
        for idx in range(10):
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    self._cap = cap
                    self._warmup()
                    logger.info("OpenCV backend found working camera on device %d", idx)
                    return
            cap.release()

        raise RuntimeError("No working camera found on devices 0–9")

    def _warmup(self) -> None:
        """Read a few frames so the camera stabilizes (auto-exposure, etc.)."""
        for _ in range(5):
            self._cap.read()

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
# Classifier
# ---------------------------------------------------------------------------


class Classifier:
    """
    YOLO-based bottle classifier using ncnn inference directly.

    Loads a YOLO NCNN model directory and provides single-frame classification
    returning the top detection's class name and confidence.

    Attributes:
        model_path: Filesystem path to the YOLO NCNN model directory.
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
        self._net = None
        self._names: dict[int, str] = {}

    def load(self) -> None:
        """
        Load the YOLO NCNN model from disk.

        Raises:
            FileNotFoundError: If model directory does not exist.
        """
        import ncnn
        import yaml

        if not os.path.isdir(self.model_path):
            raise FileNotFoundError(
                f"YOLO NCNN model directory not found at {self.model_path}. "
                "See models/README.md for setup instructions."
            )

        param = os.path.join(self.model_path, "model.ncnn.param")
        weights = os.path.join(self.model_path, "model.ncnn.bin")
        meta = os.path.join(self.model_path, "metadata.yaml")

        with open(meta) as f:
            metadata = yaml.safe_load(f)
        self._names = {int(k): v for k, v in metadata["names"].items()}

        net = ncnn.Net()
        net.opt.use_vulkan_compute = False
        net.load_param(param)
        net.load_model(weights)
        self._net = net

        logger.info(
            "YOLO NCNN model loaded from %s (%d classes)", self.model_path, len(self._names)
        )

    def classify(self, frame: np.ndarray) -> Optional[tuple[str, float]]:
        """
        Run YOLO inference on a single frame.

        Args:
            frame: BGR image as NumPy array (H×W×3, uint8).

        Returns:
            (class_name, confidence) tuple for the top detection, or None
            if no detections meet the confidence threshold.
        """
        import ncnn

        if self._net is None:
            raise RuntimeError("Model not loaded — call load() first")

        h, w = frame.shape[:2]
        mat_in = ncnn.Mat.from_pixels_resize(
            np.ascontiguousarray(frame),
            ncnn.Mat.PixelType.PIXEL_BGR2RGB,
            w, h,
            self.image_size, self.image_size,
        )
        mat_in.substract_mean_normalize([0.0, 0.0, 0.0], [1 / 255.0, 1 / 255.0, 1 / 255.0])

        with self._net.create_extractor() as ex:
            ex.input("in0", mat_in)
            _, mat_out = ex.extract("out0")

        return self._decode(np.array(mat_out))

    def _decode(self, output: np.ndarray) -> Optional[tuple[str, float]]:
        """
        Decode raw NCNN output to (class_name, confidence).

        Ultralytics NCNN export shape: (4+num_classes, num_anchors).
        Rows 0-3 are bbox (cx,cy,w,h); rows 4+ are per-class scores.
        """
        preds = output.T  # (num_anchors, 4+num_classes)
        class_scores = preds[:, 4:]
        confidences = class_scores.max(axis=1)
        class_ids = class_scores.argmax(axis=1)

        mask = confidences >= self.confidence_threshold
        if not mask.any():
            return None

        best = int(confidences[mask].argmax())
        cls_id = int(class_ids[mask][best])
        conf = float(confidences[mask][best])

        class_name = self._names.get(cls_id, f"unknown_{cls_id}")
        logger.debug("Classification: '%s' (conf=%.3f, id=%d)", class_name, conf, cls_id)
        return class_name, conf
