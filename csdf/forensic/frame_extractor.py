import cv2, os
from PIL import Image

def extract_frames(video_path, out_dir, max_frames=30, every_nth=1):
    """
    Extract frames from video_path into out_dir.
    - max_frames: limit number of frames to extract (0 or None => all)
    - every_nth: extract every nth frame to reduce count
    Returns list of file paths extracted.
    """
    os.makedirs(out_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    extracted = []
    idx = 0
    saved = 0
    success, frame = cap.read()
    while success:
        if idx % every_nth == 0:
            if max_frames and saved >= max_frames:
                break
            fname = f"{os.path.splitext(os.path.basename(video_path))[0]}_frame_{saved:04d}.jpg"
            out_path = os.path.join(out_dir, fname)
            # Convert BGR -> RGB and save with PIL for consistent ELA handling later
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            Image.fromarray(img).save(out_path, quality=95)
            extracted.append(out_path)
            saved += 1
        idx += 1
        success, frame = cap.read()
    cap.release()
    return extracted
