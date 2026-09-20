import csv
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

import sys

sys.path.append(str(Path(__file__).parent.parent))

from config import (
    RAW_VIDEO_DIR,
    RAW_IMAGE_DIR,
    SOURCE_METADATA_CSV,
    VIDEO_SAMPLE_INTERVAL,
    VIDEO_RESIZE_WIDTH,
    DEDUP_HASH_THRESHOLD,
)


def p_hash(image: Image.Image) -> str:
    """
    Compute a perceptual hash for adjacent-frame deduplication.
    """
    img = image.convert("L").resize(
        (32, 32),
        Image.Resampling.LANCZOS
    )

    pixels = np.array(img, dtype=np.float32)

    dct = cv2.dct(pixels)
    dct_low = dct[:8, :8]

    avg = (
        dct_low.sum() - dct_low[0, 0]
    ) / 63.0

    bits = []

    for i in range(8):
        for j in range(8):
            if i == 0 and j == 0:
                continue

            bits.append(
                "1" if dct_low[i, j] > avg else "0"
            )

    return "".join(bits)


def hamming_distance(
    hash1: str,
    hash2: str
) -> int:

    if len(hash1) != len(hash2):
        return 999

    return sum(
        c1 != c2
        for c1, c2 in zip(hash1, hash2)
    )


def extract_frames(
    video_path: Path,
    output_dir: Path,
    meta_writer
) -> None:

    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        print(
            f"[Error] Cannot open video: {video_path}"
        )
        return

    fps = float(
        cap.get(cv2.CAP_PROP_FPS) or 0.0
    )

    total_frames = int(
        cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    )

    duration = (
        total_frames / fps
        if fps > 0
        else 0.0
    )

    # Prevent modulo-by-zero when codec metadata
    # does not report FPS correctly.
    if fps > 0:
        interval_frames = max(
            1,
            int(
                round(
                    fps * VIDEO_SAMPLE_INTERVAL
                )
            )
        )
    else:
        interval_frames = 1

    video_name = video_path.stem

    frame_idx = 0
    saved_count = 0
    skipped_count = 0

    last_hash = None

    print(
        f"\n[Processing] {video_name} | "
        f"FPS:{fps:.1f} | "
        f"TotalFrames:{total_frames} | "
        f"Duration:{duration:.1f}s"
    )

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        if frame_idx % interval_frames != 0:

            frame_idx += 1
            continue

        # Resize frame while preserving aspect ratio.
        if frame.shape[1] != VIDEO_RESIZE_WIDTH:

            ratio = (
                VIDEO_RESIZE_WIDTH
                / frame.shape[1]
            )

            new_h = max(
                1,
                int(
                    round(
                        frame.shape[0] * ratio
                    )
                )
            )

            frame = cv2.resize(
                frame,
                (
                    VIDEO_RESIZE_WIDTH,
                    new_h
                )
            )

        rgb_frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        curr_hash = p_hash(
            Image.fromarray(rgb_frame)
        )

        # Adjacent-frame perceptual deduplication.
        if last_hash is not None:

            dist = hamming_distance(
                curr_hash,
                last_hash
            )

            if dist < DEDUP_HASH_THRESHOLD:

                skipped_count += 1
                frame_idx += 1

                continue

        filename = (
            f"{video_name}_frame_"
            f"{frame_idx:06d}.jpg"
        )

        save_path = (
            output_dir / filename
        )

        ok = cv2.imwrite(
            str(save_path),
            frame,
            [
                cv2.IMWRITE_JPEG_QUALITY,
                95
            ]
        )

        if not ok:

            print(
                f"[Warning] Failed to write frame: "
                f"{save_path}"
            )

            frame_idx += 1
            continue

        # source_group represents the independent sampling
        # unit used during train/val/test splitting.
        #
        # By default, each video is treated as one group.
        # If several videos belong to the same route/session,
        # the metadata.csv file can later assign them the same
        # source_group manually.
        meta_writer.writerow([
            filename,
            video_name,
            video_name,
            frame_idx,
            time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            frame.shape[1],
            frame.shape[0],
            "day",
            "sunny",
            "outdoor",
        ])

        last_hash = curr_hash

        saved_count += 1
        frame_idx += 1

    cap.release()

    print(
        f"[Done] {video_name}: "
        f"Saved {saved_count} frames, "
        f"Skipped duplicate "
        f"{skipped_count} frames"
    )


def main() -> None:

    video_files = sorted(
        list(
            RAW_VIDEO_DIR.glob("*.mp4")
        )
        + list(
            RAW_VIDEO_DIR.glob("*.avi")
        )
        + list(
            RAW_VIDEO_DIR.glob("*.mov")
        )
        + list(
            RAW_VIDEO_DIR.glob("*.mkv")
        )
    )

    if not video_files:

        print(
            f"[Warning] No video files found "
            f"in {RAW_VIDEO_DIR}. "
            f"Please place "
            f".mp4/.avi/.mov/.mkv files there."
        )

        return

    RAW_IMAGE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    SOURCE_METADATA_CSV.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        SOURCE_METADATA_CSV,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.writer(f)

        writer.writerow([
            "filename",
            "source_video",
            "source_group",
            "frame_index",
            "extract_time",
            "width",
            "height",
            "lighting",
            "weather",
            "scene_type",
        ])

        for video_file in video_files:

            extract_frames(
                video_file,
                RAW_IMAGE_DIR,
                writer
            )

    print(
        f"\n[All Done] "
        f"All frames saved to: "
        f"{RAW_IMAGE_DIR}"
    )

    print(
        f"[Metadata] Generated: "
        f"{SOURCE_METADATA_CSV}"
    )

    print(
        "[Important] Keep metadata.csv "
        "together with the dataset. "
        "It is used to prevent frames "
        "from the same source group "
        "entering different splits."
    )


if __name__ == "__main__":
    main()
