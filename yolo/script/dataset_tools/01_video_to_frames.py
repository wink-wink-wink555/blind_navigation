import os
import csv
import cv2
import hashlib
import time
from pathlib import Path
from PIL import Image

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import (RAW_VIDEO_DIR, RAW_IMAGE_DIR, VIDEO_SAMPLE_INTERVAL,
                    VIDEO_RESIZE_WIDTH, DEDUP_HASH_THRESHOLD)


def pHash(image: Image.Image) -> str:
    img = image.convert('L').resize((32, 32), Image.Resampling.LANCZOS)
    pixels = np.array(img, dtype=np.float32)
    dct = cv2.dct(pixels)
    dct_low = dct[:8, :8]
    avg = (dct_low.sum() - dct_low[0, 0]) / 63.0
    hash_str = ''
    for i in range(8):
        for j in range(8):
            if i == 0 and j == 0:
                continue
            hash_str += '1' if dct_low[i, j] > avg else '0'
    return hash_str


def hamming_distance(hash1: str, hash2: str) -> int:
    if len(hash1) != len(hash2):
        return 999
    return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))


def extract_frames(video_path: Path, output_dir: Path, meta_writer):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"[Error] Cannot open video: {video_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    interval_frames = int(fps * VIDEO_SAMPLE_INTERVAL)

    video_name = video_path.stem
    frame_idx = 0
    saved_count = 0
    skipped_count = 0
    last_hash = None

    print(f"\n[Processing] {video_name} | FPS:{fps:.1f} | TotalFrames:{total_frames} | Duration:{duration:.1f}s")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % interval_frames != 0:
            frame_idx += 1
            continue

        if frame.shape[1] != VIDEO_RESIZE_WIDTH:
            ratio = VIDEO_RESIZE_WIDTH / frame.shape[1]
            new_h = int(frame.shape[0] * ratio)
            frame = cv2.resize(frame, (VIDEO_RESIZE_WIDTH, new_h))

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_frame)
        curr_hash = pHash(pil_img)

        if last_hash is not None:
            dist = hamming_distance(curr_hash, last_hash)
            if dist < DEDUP_HASH_THRESHOLD:
                skipped_count += 1
                frame_idx += 1
                continue

        filename = f"{video_name}_frame_{frame_idx:06d}.jpg"
        save_path = output_dir / filename
        cv2.imwrite(str(save_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])

        meta_writer.writerow([
            filename,
            video_name,
            frame_idx,
            time.strftime("%Y-%m-%d %H:%M:%S"),
            frame.shape[1],
            frame.shape[0],
            "day",
            "sunny",
            "outdoor"
        ])

        last_hash = curr_hash
        saved_count += 1
        frame_idx += 1

    cap.release()
    print(f"[Done] {video_name}: Saved {saved_count} frames, Skipped duplicate {skipped_count} frames")


def main():
    import numpy as np

    video_files = list(RAW_VIDEO_DIR.glob("*.mp4")) + \
                  list(RAW_VIDEO_DIR.glob("*.avi")) + \
                  list(RAW_VIDEO_DIR.glob("*.mov"))

    if not video_files:
        print(f"[Warning] No video files found in {RAW_VIDEO_DIR}, please place .mp4/.avi/.mov files")
        return

    meta_csv_path = RAW_IMAGE_DIR.parent / "metadata.csv"
    RAW_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    with open(meta_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            "filename", "source_video", "frame_index", "extract_time",
            "width", "height", "lighting", "weather", "scene_type"
        ])

        for vfile in video_files:
            extract_frames(vfile, RAW_IMAGE_DIR, writer)

    print(f"\n[All Done] All frames saved to: {RAW_IMAGE_DIR}")
    print(f"[Metadata] Generated: {meta_csv_path}")


if __name__ == "__main__":
    main()
