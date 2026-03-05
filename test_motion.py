"""
Motion Detection Test Script - Elderly Care Monitoring System

This script tests frame-difference motion detection using the camera.
It captures live frames with CameraHandler, compares consecutive frames,
and visualizes motion contours with FPS and status overlays.

Features:
- Uses CameraHandler for video capture
- Compares previous and current frame
- Runs MotionDetector.detect() on every pair of frames
- Prints motion status in console
- Displays contour visualization in video window
- Stops after 30 seconds or when 'q' is pressed
"""

import time
import cv2

from modules.vision import CameraHandler, MotionDetector


def main() -> None:
    """Run motion detection test for 30 seconds or until user quits."""
    window_name = "Elderly Care - Motion Test"
    runtime_seconds = 30

    camera = CameraHandler(camera_id=0, width=640, height=480)
    detector = MotionDetector(threshold=25, min_area=500)

    if not camera.start():
        print("Error: Camera not found or could not be opened.")
        return

    start_time = time.time()
    fps_timer = time.time()
    fps = 0.0
    frame_count = 0

    previous_frame = camera.read_frame()
    if previous_frame is None:
        print("Error: Failed to capture initial frame.")
        camera.release()
        return

    print("Motion test started. Press 'q' to quit.")

    try:
        while True:
            current_frame = camera.read_frame()
            if current_frame is None:
                print("No motion")
                continue

            motion_detected, confidence = detector.detect(previous_frame, current_frame)

            if motion_detected:
                print("Motion detected!")
            else:
                print("No motion")

            display_frame = detector.visualize(current_frame)

            frame_count += 1
            elapsed_fps = time.time() - fps_timer
            if elapsed_fps >= 1.0:
                fps = frame_count / elapsed_fps
                frame_count = 0
                fps_timer = time.time()

            status_text = "Motion detected!" if motion_detected else "No motion"
            status_color = (0, 255, 0) if motion_detected else (0, 0, 255)

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
                f"Status: {status_text}",
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                status_color,
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                display_frame,
                f"Confidence: {confidence:.2f}",
                (10, 90),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 0),
                2,
                cv2.LINE_AA,
            )

            remaining = max(0.0, runtime_seconds - (time.time() - start_time))
            cv2.putText(
                display_frame,
                f"Time left: {remaining:.1f}s | Press 'q' to quit",
                (10, display_frame.shape[0] - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (200, 200, 200),
                1,
                cv2.LINE_AA,
            )

            cv2.imshow(window_name, display_frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            if (time.time() - start_time) >= runtime_seconds:
                break

            previous_frame = current_frame.copy()

    finally:
        camera.release()
        cv2.destroyAllWindows()
        print("Motion test ended.")


if __name__ == "__main__":
    main()
