"""
dataset_tools/01_video_to_frames.py
视频抽帧 + 感知哈希去重 + 元数据CSV生成
"""

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
    """
    感知哈希（pHash）：对图像内容敏感，对压缩/轻微变化鲁棒
    """
    # 缩放到32x32，转灰度
    img = image.convert('L').resize((32, 32), Image.Resampling.LANCZOS)
    pixels = np.array(img, dtype=np.float32)

    # DCT变换取低频部分
    dct = cv2.dct(pixels)
    dct_low = dct[:8, :8]

    # 计算平均值（不含直流分量）
    avg = (dct_low.sum() - dct_low[0, 0]) / 63.0
    hash_str = ''
    for i in range(8):
        for j in range(8):
            if i == 0 and j == 0:
                continue
            hash_str += '1' if dct_low[i, j] > avg else '0'
    return hash_str


def hamming_distance(hash1: str, hash2: str) -> int:
    """计算两个哈希字符串的汉明距离"""
    if len(hash1) != len(hash2):
        return 999
    return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))


def extract_frames(video_path: Path, output_dir: Path, meta_writer):
    """
    从单个视频抽帧，并进行去重
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"[错误] 无法打开视频: {video_path}")
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

    print(f"\n[处理] {video_name} | FPS:{fps:.1f} | 总帧数:{total_frames} | 时长:{duration:.1f}s")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 按间隔抽帧
        if frame_idx % interval_frames != 0:
            frame_idx += 1
            continue

        # 等比例缩放（保持清晰度用于后续标注）
        if frame.shape[1] != VIDEO_RESIZE_WIDTH:
            ratio = VIDEO_RESIZE_WIDTH / frame.shape[1]
            new_h = int(frame.shape[0] * ratio)
            frame = cv2.resize(frame, (VIDEO_RESIZE_WIDTH, new_h))

        # 感知哈希去重
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_frame)
        curr_hash = pHash(pil_img)

        if last_hash is not None:
            dist = hamming_distance(curr_hash, last_hash)
            if dist < DEDUP_HASH_THRESHOLD:
                skipped_count += 1
                frame_idx += 1
                continue

        # 保存帧
        filename = f"{video_name}_frame_{frame_idx:06d}.jpg"
        save_path = output_dir / filename
        cv2.imwrite(str(save_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])

        # 写入元数据
        meta_writer.writerow([
            filename,
            video_name,
            frame_idx,
            time.strftime("%Y-%m-%d %H:%M:%S"),
            frame.shape[1],
            frame.shape[0],
            "day",      # 可手动补充
            "sunny",    # 可手动补充
            "outdoor"   # 可手动补充
        ])

        last_hash = curr_hash
        saved_count += 1
        frame_idx += 1

    cap.release()
    print(f"[完成] {video_name}: 保存 {saved_count} 帧, 跳过重复 {skipped_count} 帧")


def main():
    import numpy as np  # 延迟导入，供pHash使用

    video_files = list(RAW_VIDEO_DIR.glob("*.mp4")) + \
                  list(RAW_VIDEO_DIR.glob("*.avi")) + \
                  list(RAW_VIDEO_DIR.glob("*.mov"))

    if not video_files:
        print(f"[警告] 在 {RAW_VIDEO_DIR} 中未找到视频文件，请放置 .mp4/.avi/.mov 文件")
        return

    # 初始化元数据CSV
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

    print(f"\n[全部完成] 所有帧已保存至: {RAW_IMAGE_DIR}")
    print(f"[元数据] 已生成: {meta_csv_path}")


if __name__ == "__main__":
    main()