import cv2
import time
import os
import sys

sys.path.insert(0, os.path.abspath("backend"))
sys.path.insert(0, os.path.abspath("."))

from app.services.video_service import VideoCaptureService
from app.services.model_service import get_model

def run():
    cap = VideoCaptureService(camera_index=0)
    if not cap.start():
        print("Failed to open camera")
        return
    model = get_model()
    print("Testing 10 frames with conf=0.10...")
    for i in range(10):
        ret, frame = cap.read_frame()
        if not ret or frame is None:
            time.sleep(0.05)
            continue
        res = model.predict(frame, conf=0.10, verbose=False)[0]
        names = res.names
        dets = [f"{names[int(b.cls[0])]}:{float(b.conf[0]):.2f}" for b in res.boxes]
        print(f"Frame {i}: {dets}")
        time.sleep(0.1)
    cap.release()

if __name__ == "__main__":
    run()

