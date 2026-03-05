"""
Vision Module - Motion Detection and Video Monitoring
Handles real-time motion detection using OpenCV and background subtraction.
"""

import cv2
import numpy as np
import threading
import logging
import time
from typing import Optional, Tuple, Dict, Callable
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CameraHandler:
    """
    Low-level camera handler for video capture operations.
    
    Provides a clean interface for camera initialization, frame reading,
    and resource cleanup with context manager support.
    
    Attributes:
        camera_id: Camera device index
        width: Frame width in pixels
        height: Frame height in pixels
    """
    
    def __init__(
        self,
        camera_id: int = 0,
        width: int = 640,
        height: int = 480,
    ) -> None:
        """
        Initialize CameraHandler.
        
        Args:
            camera_id: Camera device index (default: 0)
            width: Desired frame width in pixels
            height: Desired frame height in pixels
        """
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.cap: Optional[cv2.VideoCapture] = None
        self._is_opened = False
        
        logger.debug(
            f"CameraHandler initialized: camera_id={camera_id}, "
            f"resolution={width}x{height}"
        )
    
    def __enter__(self):
        """Context manager entry - opens camera."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - releases camera."""
        self.release()
    
    def start(self) -> bool:
        """
        Open camera and configure settings.
        
        Returns:
            bool: True if camera opened successfully, False otherwise
        """
        try:
            if self._is_opened:
                logger.warning(f"Camera {self.camera_id} is already open")
                return True
            
            logger.info(f"Opening camera {self.camera_id}...")
            self.cap = cv2.VideoCapture(self.camera_id)
            
            if not self.cap.isOpened():
                logger.error(f"Failed to open camera {self.camera_id}")
                self._is_opened = False
                return False
            
            # Set resolution
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            
            # Get actual camera resolution (may differ from requested)
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            self._is_opened = True
            logger.info(
                f"Camera {self.camera_id} opened successfully "
                f"(resolution: {actual_width}x{actual_height})"
            )
            return True
            
        except Exception as e:
            logger.error(f"Error opening camera {self.camera_id}: {e}")
            self._is_opened = False
            return False
    
    def read_frame(self) -> Optional[np.ndarray]:
        """
        Read a single frame from the camera.
        
        Returns:
            numpy.ndarray: Frame if successful, None otherwise
        """
        if not self.is_opened():
            logger.error("Cannot read frame - camera not opened")
            return None
        
        try:
            ret, frame = self.cap.read()
            
            if not ret or frame is None:
                logger.warning(f"Failed to read frame from camera {self.camera_id}")
                return None
            
            return frame
            
        except Exception as e:
            logger.error(f"Error reading frame from camera {self.camera_id}: {e}")
            return None
    
    def is_opened(self) -> bool:
        """
        Check if camera is currently opened and accessible.
        
        Returns:
            bool: True if camera is opened, False otherwise
        """
        return self._is_opened and self.cap is not None and self.cap.isOpened()
    
    def release(self) -> None:
        """
        Release camera resources and cleanup.
        """
        try:
            if self.cap is not None:
                self.cap.release()
                logger.info(f"Camera {self.camera_id} released")
            
            self._is_opened = False
            self.cap = None
            
        except Exception as e:
            logger.error(f"Error releasing camera {self.camera_id}: {e}")
    
    def get_properties(self) -> Dict[str, any]:
        """
        Get current camera properties.
        
        Returns:
            Dictionary with camera properties
        """
        if not self.is_opened():
            return {
                "camera_id": self.camera_id,
                "is_opened": False,
            }
        
        try:
            return {
                "camera_id": self.camera_id,
                "is_opened": True,
                "width": int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "fps": int(self.cap.get(cv2.CAP_PROP_FPS)),
                "brightness": self.cap.get(cv2.CAP_PROP_BRIGHTNESS),
                "contrast": self.cap.get(cv2.CAP_PROP_CONTRAST),
                "saturation": self.cap.get(cv2.CAP_PROP_SATURATION),
            }
        except Exception as e:
            logger.error(f"Error getting camera properties: {e}")
            return {
                "camera_id": self.camera_id,
                "is_opened": True,
                "error": str(e),
            }


class MotionDetector:
    """Frame-difference based motion detector."""

    def __init__(self, threshold: int = 25, min_area: int = 500) -> None:
        """
        Initialize motion detector.

        Args:
            threshold: Pixel intensity threshold used after frame differencing
            min_area: Minimum contour area to classify as motion
        """
        self.threshold = threshold
        self.min_area = min_area
        self._last_contours = []
        self._last_max_area = 0.0

    def detect(self, frame1: np.ndarray, frame2: np.ndarray) -> Tuple[bool, float]:
        """
        Detect motion by comparing two consecutive frames.

        Uses grayscale conversion, Gaussian blur, absolute difference,
        thresholding, dilation, and contour detection.

        Args:
            frame1: Previous frame
            frame2: Current frame

        Returns:
            Tuple[bool, float]: (motion_detected, confidence)
        """
        try:
            gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)

            blur1 = cv2.GaussianBlur(gray1, (5, 5), 0)
            blur2 = cv2.GaussianBlur(gray2, (5, 5), 0)

            diff = cv2.absdiff(blur1, blur2)
            _, thresh = cv2.threshold(diff, self.threshold, 255, cv2.THRESH_BINARY)
            dilated = cv2.dilate(thresh, None, iterations=2)

            contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            valid_contours = []
            max_area = 0.0
            for contour in contours:
                area = cv2.contourArea(contour)
                if area >= self.min_area:
                    valid_contours.append(contour)
                    if area > max_area:
                        max_area = area

            self._last_contours = valid_contours
            self._last_max_area = max_area

            motion_detected = len(valid_contours) > 0
            confidence = min(1.0, max_area / float(self.min_area * 10)) if motion_detected else 0.0
            return motion_detected, confidence

        except Exception as e:
            logger.error(f"Error detecting motion: {e}")
            self._last_contours = []
            self._last_max_area = 0.0
            return False, 0.0

    def visualize(self, frame: np.ndarray) -> np.ndarray:
        """
        Draw detected contours on the given frame for debugging.

        Args:
            frame: Frame to draw contours on

        Returns:
            Frame with contour overlays
        """
        output = frame.copy()
        for contour in self._last_contours:
            x, y, w, h = cv2.boundingRect(contour)
            cv2.rectangle(output, (x, y), (x + w, y + h), (0, 255, 0), 2)
        return output


class ActivityTracker:
    """
    Tracks motion activity and detects inactivity periods.

    Thread-safe activity tracking with state management and callbacks.
    
    Attributes:
        inactivity_threshold: Threshold in seconds before alerting
    """

    def __init__(self, inactivity_threshold: int = 30) -> None:
        """
        Initialize ActivityTracker.

        Args:
            inactivity_threshold: Seconds of no motion before considered inactive
        """
        self.inactivity_threshold = inactivity_threshold
        self.last_motion_time: float = time.time()
        self.state = "ACTIVE"
        self._callback: Optional[Callable[[str], None]] = None
        self._lock = threading.Lock()
        self._alert_sent = False

        logger.info(
            f"ActivityTracker initialized (threshold={inactivity_threshold}s)"
        )

    def update(self, motion_detected: bool) -> None:
        """
        Update tracker with motion detection result.

        Called every frame. Updates timestamp if motion detected,
        checks for inactivity threshold breach.

        Args:
            motion_detected: Whether motion was detected in current frame
        """
        with self._lock:
            if motion_detected:
                self.last_motion_time = time.time()
                old_state = self.state
                self.state = "ACTIVE"
                self._alert_sent = False

                if old_state != "ACTIVE":
                    logger.info("Activity resumed - state: ACTIVE")
                    if self._callback:
                        self._callback("activity_resumed")
            else:
                # Check if we've exceeded threshold
                duration = time.time() - self.last_motion_time
                if duration > self.inactivity_threshold and self.state == "ACTIVE":
                    self.state = "INACTIVE"
                    logger.warning(f"Inactivity threshold exceeded: {duration:.1f}s")
                    if self._callback and not self._alert_sent:
                        self._callback("inactivity_detected")
                        self._alert_sent = True

    def get_inactivity_duration(self) -> float:
        """
        Get duration of current inactivity in seconds.

        Returns:
            Seconds since last motion detected
        """
        with self._lock:
            return time.time() - self.last_motion_time

    def is_inactive(self) -> bool:
        """
        Check if inactivity threshold has been exceeded.

        Returns:
            True if inactive for longer than threshold
        """
        with self._lock:
            return self.state == "INACTIVE"

    def register_callback(self, callback: Callable[[str], None]) -> None:
        """
        Register callback for state change events.

        Callback receives event type:
        - "inactivity_detected": Inactivity threshold exceeded
        - "activity_resumed": Motion detected after inactivity

        Args:
            callback: Function to call on state change
        """
        with self._lock:
            self._callback = callback
            logger.info("Inactivity callback registered")

    def reset(self) -> None:
        """Reset activity tracker and clear alerts."""
        with self._lock:
            self.last_motion_time = time.time()
            self.state = "ACTIVE"
            self._alert_sent = False
            logger.info("ActivityTracker reset")

    def get_state(self) -> str:
        """Get current state."""
        with self._lock:
            return self.state
