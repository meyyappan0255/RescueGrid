# junction_unit/ai_detector.py
# ─────────────────────────────────────────────────────────────
# RescueGrid — AI Ambulance Detector (Raspberry Pi / Edge)
#
# Uses YOLOv8n (nano) for real-time ambulance detection on
# the Pi camera feed.  Falls back to colour-based siren
# detection if the model is unavailable.
# ─────────────────────────────────────────────────────────────

import cv2
import numpy as np
import logging
import time
from pathlib import Path

logger = logging.getLogger("ai_detector")

# Path to the YOLOv8n model weights
# Download: yolo export model=yolov8n.pt format=onnx
MODEL_PATH = Path(__file__).parent / "models" / "yolov8n_ambulance.onnx"

# COCO class IDs that correspond to emergency / large vehicles
# 2=car, 5=bus, 7=truck — we look for "ambulance" custom class (0 if retrained)
AMBULANCE_CLASS_IDS = {0, 2, 5, 7}   # Update after fine-tuning
CONFIDENCE_THRESHOLD = 0.55

class AmbulanceDetector:
    def __init__(self, camera_index: int = 0, use_pi_camera: bool = True):
        self._model_loaded = False
        self._net = None
        self._output_layers = []
        self._use_pi_camera = use_pi_camera
        self._cap = None
        self._load_model()
        self._open_camera(camera_index)

    # ── Model loading ────────────────────────────────────────

    def _load_model(self):
        if not MODEL_PATH.exists():
            logger.warning(f"ONNX model not found at {MODEL_PATH}. "
                           "Falling back to colour-based detection.")
            return
        try:
            self._net = cv2.dnn.readNetFromONNX(str(MODEL_PATH))
            self._net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self._net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            self._model_loaded = True
            logger.info("YOLOv8 ONNX model loaded ✓")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")

    def _open_camera(self, index: int):
        if self._use_pi_camera:
            # Use libcamera / picamera2 on Pi
            try:
                from picamera2 import Picamera2  # type: ignore
                self._picam = Picamera2()
                config = self._picam.create_preview_configuration(
                    main={"size": (640, 480), "format": "RGB888"}
                )
                self._picam.configure(config)
                self._picam.start()
                logger.info("Pi Camera opened ✓")
                return
            except ImportError:
                logger.warning("picamera2 not available — falling back to OpenCV")
        self._cap = cv2.VideoCapture(index)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        logger.info(f"OpenCV camera {index} opened ✓")

    # ── Public API ───────────────────────────────────────────

    def grab_frame(self) -> np.ndarray | None:
        """Capture one frame from the camera."""
        if hasattr(self, "_picam"):
            return self._picam.capture_array()
        if self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            return frame if ret else None
        return None

    def detect(self, frame: np.ndarray) -> dict:
        """
        Run detection on a frame.
        Returns:
          {
            "ambulance_detected": bool,
            "confidence": float,
            "bbox": [x, y, w, h] or None,
            "method": "yolo" | "colour"
          }
        """
        if self._model_loaded:
            return self._yolo_detect(frame)
        return self._colour_detect(frame)

    def run_continuous(self, callback, interval: float = 0.5):
        """
        Continuously capture frames and call callback(result).
        Run this in a background thread.
        """
        while True:
            frame = self.grab_frame()
            if frame is not None:
                result = self.detect(frame)
                callback(result, frame)
            time.sleep(interval)

    def release(self):
        if self._cap:
            self._cap.release()
        if hasattr(self, "_picam"):
            self._picam.stop()

    # ── YOLOv8 detection ─────────────────────────────────────

    def _yolo_detect(self, frame: np.ndarray) -> dict:
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            frame, 1/255.0, (640, 640), swapRB=True, crop=False
        )
        self._net.setInput(blob)
        outputs = self._net.forward(self._net.getUnconnectedOutLayersNames())

        best_conf = 0.0
        best_bbox = None

        # Parse YOLOv8 output format [batch, 84, 8400]
        preds = outputs[0]
        if preds.ndim == 3:
            preds = preds[0]          # [84, 8400]
        preds = preds.T               # [8400, 84]

        for row in preds:
            x, y, bw, bh = row[:4]
            class_scores = row[4:]
            class_id = int(np.argmax(class_scores))
            confidence = float(class_scores[class_id])

            if confidence < CONFIDENCE_THRESHOLD:
                continue
            if class_id not in AMBULANCE_CLASS_IDS:
                continue
            if confidence > best_conf:
                best_conf = confidence
                # Convert from normalised to pixel coords
                x1 = int((x - bw / 2) * w / 640)
                y1 = int((y - bh / 2) * h / 640)
                best_bbox = [x1, y1, int(bw * w / 640), int(bh * h / 640)]

        return {
            "ambulance_detected": best_conf >= CONFIDENCE_THRESHOLD,
            "confidence": round(best_conf, 3),
            "bbox": best_bbox,
            "method": "yolo",
        }

    # ── Colour-based fallback ────────────────────────────────

    def _colour_detect(self, frame: np.ndarray) -> dict:
        """
        Detect ambulance by flashing red/blue siren lights.
        Looks for high-saturation red or blue regions.
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)

        # Red siren range
        red1 = cv2.inRange(hsv, (0, 150, 150),   (10, 255, 255))
        red2 = cv2.inRange(hsv, (170, 150, 150),  (180, 255, 255))
        red  = cv2.bitwise_or(red1, red2)

        # Blue siren range
        blue = cv2.inRange(hsv, (100, 150, 150), (140, 255, 255))

        red_pct  = np.count_nonzero(red)  / red.size
        blue_pct = np.count_nonzero(blue) / blue.size

        detected   = red_pct > 0.02 or blue_pct > 0.02
        confidence = min(1.0, (red_pct + blue_pct) * 20)

        return {
            "ambulance_detected": detected,
            "confidence": round(confidence, 3),
            "bbox": None,
            "method": "colour",
        }
