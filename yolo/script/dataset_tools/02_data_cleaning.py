import json
import cv2
import numpy as np
from pathlib import Path
from PIL import Image
from tqdm import tqdm

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import (MAKESENSE_IMAGE_DIR, MAKESENSE_LABEL_DIR,
                    CLEAN_IMAGE_DIR, YOLO_LABEL_DIR,
                    TARGET_IMAGE_SIZE,
                    MIN_BLUR_THRESHOLD, MAX_OVEREXPOSE_RATIO, MAX_UNDEREXPOSE_RATIO,
                    REPORT_DIR, NUM_CLASSES)
from utils.bbox_utils import resize_pad_bboxes


def compute_blur_laplacian(image: np.ndarray) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def check_exposure(image: np.ndarray):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    total_pixels = gray.size
    overexpose = np.sum(gray > 250) / total_pixels
    underexpose = np.sum(gray < 20) / total_pixels
    is_ok = (overexpose <= MAX_OVEREXPOSE_RATIO) and (underexpose <= MAX_UNDEREXPOSE_RATIO)
    return is_ok, overexpose, underexpose


def load_yolo_bboxes(label_path: Path) -> list:
    if not label_path.exists():
        return []
    bboxes = []
    with open(label_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 5:
                bboxes.append([int(parts[0])] + [float(x) for x in parts[1:]])
    return bboxes


def save_yolo_bboxes(bboxes: list, save_path: Path):
    lines = []
    for b in bboxes:
        lines.append(f"{int(b[0])} {b[1]:.6f} {b[2]:.6f} {b[3]:.6f} {b[4]:.6f}")
    save_path.write_text("
".join(lines), encoding='utf-8')


def clean_and_normalize(image_path: Path, label_path: Path) -> dict:
    img = cv2.imread(str(image_path))
    if img is None:
        return {"status": "failed", "reason": "Cannot read file", "path": image_path.name}

    orig_h, orig_w = img.shape[:2]
    bboxes = load_yolo_bboxes(label_path)

    blur_score = compute_blur_laplacian(img)
    if blur_score < MIN_BLUR_THRESHOLD:
        return {
            "status": "rejected",
            "reason": "Too blurry",
            "blur_score": round(blur_score, 2),
            "path": image_path.name
        }

    exposure_ok, over_r, under_r = check_exposure(img)
    if not exposure_ok:
        return {
            "status": "rejected",
            "reason": f"Exposure abnormal(over:{over_r:.2%}, under:{under_r:.2%})",
            "blur_score": round(blur_score, 2),
            "path": image_path.name
        }

    target_w, target_h = TARGET_IMAGE_SIZE
    scale = min(target_w / orig_w, target_h / orig_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)

    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    paste_x = (target_w - new_w) // 2
    paste_y = (target_h - new_h) // 2

    new_img = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
    new_img[paste_y:paste_y+new_h, paste_x:paste_x+new_w] = resized

    new_bboxes = resize_pad_bboxes(bboxes, orig_w, orig_h, target_w, target_h)

    img_save_path = CLEAN_IMAGE_DIR / image_path.name
    cv2.imwrite(str(img_save_path), new_img, [cv2.IMWRITE_JPEG_QUALITY, 95])

    label_save_path = YOLO_LABEL_DIR / (image_path.stem + ".txt")
    if new_bboxes:
        save_yolo_bboxes(new_bboxes, label_save_path)
    else:
        label_save_path.write_text("")

    return {
        "status": "accepted",
        "blur_score": round(blur_score, 2),
        "original_size": [orig_w, orig_h],
        "normalized_size": TARGET_IMAGE_SIZE,
        "scale": round(scale, 4),
        "boxes": len(new_bboxes),
        "path": image_path.name
    }


def main():
    image_files = sorted(list(MAKESENSE_IMAGE_DIR.glob("*.jpg")) +
                           list(MAKESENSE_IMAGE_DIR.glob("*.jpeg")) +
                           list(MAKESENSE_IMAGE_DIR.glob("*.png")))

    if not image_files:
        print(f"[Error] No images found in {MAKESENSE_IMAGE_DIR}")
        print("Please place MakeSense exported images in data/makesense_export/images/")
        return

    report = {
        "total_scanned": len(image_files),
        "accepted": 0,
        "rejected": 0,
        "failed": 0,
        "details": []
    }

    print(f"[Start Cleaning] Total {len(image_files)} images from MakeSense export...")
    for img_path in tqdm(image_files, desc="Cleaning progress"):
        label_path = MAKESENSE_LABEL_DIR / (img_path.stem + ".txt")
        result = clean_and_normalize(img_path, label_path)
        report["details"].append(result)

        if result["status"] == "accepted":
            report["accepted"] += 1
        elif result["status"] == "rejected":
            report["rejected"] += 1
        else:
            report["failed"] += 1

    report_path = REPORT_DIR / "cleaning_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"
[Cleaning Done]")
    print(f"  Accepted: {report['accepted']} | Rejected: {report['rejected']} | Failed: {report['failed']}")
    print(f"  Report saved to: {report_path}")
    print(f"  Cleaned images saved to: {CLEAN_IMAGE_DIR}")
    print(f"  YOLO labels saved to: {YOLO_LABEL_DIR}")


if __name__ == "__main__":
    main()
