"""
Vision Pipeline Test Script - Elderly Care Monitoring System

Comprehensive vision system test combining:
- CameraHandler: Camera video capture
- MotionDetector: Frame-difference motion detection
- ActivityTracker: Inactivity monitoring with state tracking

Features:
- Real-time motion detection pipeline
- Inactivity alerts with configurable threshold
- Live video overlay with FPS, motion status, inactivity timer
- Event logging with timestamps
- Thread-safe state tracking
- Graceful shutdown on 'q' or Ctrl+C

Usage:
    python test_vision_pipeline.py
"""

import time
import sys
import cv2
from datetime import datetime

from modules.vision import CameraHandler, MotionDetector, ActivityTracker


def log_event(event_type: str, message: str) -> None:
    """Log event with timestamp to console."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    event_map = {
        "motion": "🔴 MOTION",
        "no_motion": "🟢 NO MOTION",
        "alert": "🚨 ALERT",
        "resumed": "✓ RESUMED",
        "debug": "📋 DEBUG",
    }
    event_label = event_map.get(event_type, "📝 EVENT")
    print(f"[{timestamp}] {event_label}: {message}")


def on_inactivity_event(event: str) -> None:
    """Callback for inactivity tracker events."""
    if event == "inactivity_detected":
        log_event("alert", "Inactivity detected! Threshold exceeded.")
    elif event == "activity_resumed":
        log_event("resumed", "Activity resumed after inactivity.")


def main() -> None:
    """Run the complete vision pipeline test."""
    print("=" * 70)
    print("  Elderly Care - Vision Pipeline Test")
    print("=" * 70)
    print("\nInitializing components...\n")

    # Configuration
    INACTIVITY_THRESHOLD = 10  # seconds (for testing)
    WINDOW_NAME = "Elderly Care - Vision Pipeline"

    # Initialize components
    camera = CameraHandler(camera_id=0, width=640, height=480)
    if not camera.start():
        print("✗ Error: Could not initialize camera")
        return

    detector = MotionDetector(threshold=25, min_area=500)
    log_event("debug", "MotionDetector initialized")

    tracker = ActivityTracker(inactivity_threshold=INACTIVITY_THRESHOLD)
    tracker.register_callback(on_inactivity_event)
    log_event("debug", f"ActivityTracker initialized (threshold={INACTIVITY_THRESHOLD}s)")

    # FPS calculation
    fps = 0.0
    fps_timer = time.time()
    frame_count = 0

    # Get initial frame
    previous_frame = camera.read_frame()
    if previous_frame is None:
        print("✗ Error: Could not capture initial frame")
        camera.release()
        return

    print("\n" + "=" * 70)
    print("Vision pipeline running. Press 'q' to quit.")
    print("=" * 70 + "\n")

    try:
        while True:
            # Capture current frame
            current_frame = camera.read_frame()
            if current_frame is None:
                continue

            # Detect motion
            motion_detected, confidence = detector.detect(previous_frame, current_frame)

            # Log motion events
            if motion_detected:
                log_event("motion", f"Motion detected (confidence={confidence:.2f})")
            # Uncomment for verbose logging:
            # else:
            #     log_event("no_motion", "No motion")

            # Update activity tracker
            tracker.update(motion_detected)

            # Get visualization
            display_frame = detector.visualize(current_frame)

            # Calculate FPS
            frame_count += 1
            elapsed_fps = time.time() - fps_timer
            if elapsed_fps >= 1.0:
                fps = frame_count / elapsed_fps
                frame_count = 0
                fps_timer = time.time()

            # Get tracker state
            inactivity_duration = tracker.get_inactivity_duration()
            state = tracker.get_state()
            is_inactive = tracker.is_inactive()

            # Color-coded status
            motion_text = "Motion detected!" if motion_detected else "No motion"
            motion_color = (0, 255, 0) if motion_detected else (0, 0, 255)

            state_text = "INACTIVE" if is_inactive else "ACTIVE"
            state_color = (0, 0, 255) if is_inactive else (0, 255, 0)

            # Draw overlays
            cv2.putText(
                display_frame,
                f"FPS: {fps:.1f}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            cv2.putText(
                display_frame,
                f"Motion: {motion_text}",
                (10, 65),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                motion_color,
                2,
                cv2.LINE_AA,
            )

            cv2.putText(
                display_frame,
                f"State: {state_text}",
                (10, 100),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                state_color,
                2,
                cv2.LINE_AA,
            )

            cv2.putText(
                display_frame,
                f"Inactivity: {inactivity_duration:.1f}s / {INACTIVITY_THRESHOLD}s",
                (10, 135),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 0),
                2,
                cv2.LINE_AA,
            )

            cv2.putText(
                display_frame,
                f"Confidence: {confidence:.2f}",
                (10, 170),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (200, 200, 255),
                2,
                cv2.LINE_AA,
            )

            # Instructions
            cv2.putText(
                display_frame,
                "Press 'q' to quit | 'r' to reset",
                (10, display_frame.shape[0] - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (200, 200, 200),
                1,
                cv2.LINE_AA,
            )

            # Display
            cv2.imshow(WINDOW_NAME, display_frame)

            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                log_event("debug", "Quit signal received")
                break
            elif key == ord("r"):
                tracker.reset()
                log_event("debug", "ActivityTracker reset by user")

            # Update for next iteration
            previous_frame = current_frame.copy()

    except KeyboardInterrupt:
        print("\n")
        log_event("debug", "Interrupted by user (Ctrl+C)")

    finally:
        # Cleanup
        print("\nShutting down...\n")
        camera.release()
        cv2.destroyAllWindows()
        log_event("debug", "Camera released and windows closed")
        print("\n" + "=" * 70)
        print("Vision pipeline test ended.")
        print("=" * 70)


if __name__ == "__main__":
    main()
