"""
Test Camera Script - Elderly Care Monitoring System

This script tests camera functionality by displaying a live video feed
with FPS counter. Used for verifying camera access and performance
before running the main monitoring system.

Usage:
    python test_camera.py

Controls:
    - Press 'q' to quit
    - Camera feed shown in window "Elderly Care - Camera Test"

Requirements:
    - OpenCV (cv2)
    - Working camera device
"""

import cv2
import time
import sys


def test_camera(camera_id: int = 0, width: int = 640, height: int = 480) -> None:
    """
    Test camera by displaying live video feed with FPS counter.
    
    Args:
        camera_id: Camera device index (default: 0)
        width: Frame width in pixels
        height: Frame height in pixels
    """
    print("=" * 60)
    print("  Elderly Care System - Camera Test")
    print("=" * 60)
    print(f"\nAttempting to open camera {camera_id}...")
    
    # Initialize camera
    cap = cv2.VideoCapture(camera_id)
    
    if not cap.isOpened():
        print(f"\n✗ ERROR: Could not open camera {camera_id}")
        print("  Possible causes:")
        print("  - Camera not connected")
        print("  - Camera in use by another application")
        print("  - Insufficient permissions")
        print("  - Invalid camera index")
        sys.exit(1)
    
    # Set camera properties
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    
    # Get actual resolution (camera may not support requested resolution)
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print(f"✓ Camera opened successfully")
    print(f"  Resolution: {actual_width}x{actual_height}")
    print(f"\nDisplaying live feed...")
    print("  Press 'q' to quit\n")
    
    # Window name
    window_name = "Elderly Care - Camera Test"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    
    # FPS calculation variables
    fps_time = time.time()
    fps = 0
    frame_count = 0
    
    try:
        while True:
            # Read frame
            ret, frame = cap.read()
            
            if not ret:
                print("\n✗ ERROR: Failed to read frame from camera")
                break
            
            # Calculate FPS
            frame_count += 1
            current_time = time.time()
            elapsed = current_time - fps_time
            
            if elapsed >= 1.0:
                fps = frame_count / elapsed
                frame_count = 0
                fps_time = current_time
            
            # Draw FPS on frame
            fps_text = f"FPS: {fps:.1f}"
            cv2.putText(
                frame,
                fps_text,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 0),
                2,
                cv2.LINE_AA
            )
            
            # Draw camera info
            info_text = f"Camera {camera_id} | {actual_width}x{actual_height}"
            cv2.putText(
                frame,
                info_text,
                (10, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                1,
                cv2.LINE_AA
            )
            
            # Draw instructions
            instruction_text = "Press 'q' to quit"
            cv2.putText(
                frame,
                instruction_text,
                (10, actual_height - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                1,
                cv2.LINE_AA
            )
            
            # Display frame
            cv2.imshow(window_name, frame)
            
            # Check for 'q' key press
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("\n✓ Camera test completed successfully")
                break
    
    except KeyboardInterrupt:
        print("\n\n✓ Camera test interrupted by user")
    
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
    
    finally:
        # Cleanup
        print("\nCleaning up...")
        cap.release()
        cv2.destroyAllWindows()
        print("✓ Camera released")
        print("✓ Windows destroyed")
        print("\n" + "=" * 60)


def main():
    """Main entry point for camera test script."""
    try:
        test_camera(camera_id=0, width=640, height=480)
    except Exception as e:
        print(f"\n✗ FATAL ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
