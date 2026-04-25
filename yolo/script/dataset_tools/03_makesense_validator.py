import json
import cv2
import numpy as np
from pathlib import Path
from collections import defaultdict, Counter
from tqdm import tqdm

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import (MAKESENSE_IMAGE_DIR, MAKESENSE_LABEL_DIR, MAKESENSE_CLASSES_FILE,
                    VISUAL_DIR, CLASS_NAMES, NUM_CLASSES)


def load_yolo_bboxes(label_path: Path) -> list:
    if not label_path.exists():
        return []
    bboxes = []
    with open(label_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 5:
                try:
                    bboxes.append([int(parts[0])] + [float(x) for x in parts[1:]])
                except ValueError:
                    continue
    return bboxes


def validate_classes_txt() -> bool:
    if not MAKESENSE_CLASSES_FILE.exists():
        print(f"[Error] classes.txt not found: {MAKESENSE_CLASSES_FILE}")
        return False

    with open(MAKESENSE_CLASSES_FILE, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    if len(lines) != NUM_CLASSES:
        print(f"[Error] classes.txt has {len(lines)} classes, expected {NUM_CLASSES}")
        print(f"  Found: {lines}")
        print(f"  Expected: {CLASS_NAMES}")
        return False

    mismatches = []
    for i, (found, expected) in enumerate(zip(lines, CLASS_NAMES)):
        if found != expected:
            mismatches.append(f"  Line {i}: found '{found}', expected '{expected}'")

    if mismatches:
        print("[Error] Class name mismatches:")
        for m in mismatches:
            print(m)
        return False

    print(f"[OK] classes.txt validated: {lines}")
    return True


def validate_single(image_path: Path, label_path: Path, img_w: int, img_h: int) -> dict:
    bboxes = load_yolo_bboxes(label_path)
    issues = []

    if not bboxes and label_path.exists():
        pass

    valid_boxes = 0
    for bbox in bboxes:
        cls_id, cx, cy, w, h = bbox

        if cls_id < 0 or cls_id >= NUM_CLASSES:
            issues.append(f"Invalid class_id {cls_id} (max {NUM_CLASSES-1})")
            continue

        if not (0 <= cx <= 1 and 0 <= cy <= 1 and 0 < w <= 1 and 0 < h <= 1):
            issues.append(f"Out-of-bound coords: {bbox[1:]}")
            continue

        if w < 0.001 or h < 0.001:
            issues.append(f"Too small box: w={w:.4f}, h={h:.4f}")
            continue

        valid_boxes += 1

    return {
        "image": image_path.name,
        "boxes": len(bboxes),
        "valid_boxes": valid_boxes,
        "issues": issues,
        "has_label": label_path.exists()
    }


def draw_validation_sample(image_path: Path, label_path: Path, save_path: Path):
    img = cv2.imread(str(image_path))
    if img is None:
        return
    h, w = img.shape[:2]
    bboxes = load_yolo_bboxes(label_path)

    colors = [(0, 255, 0), (0, 0, 255)]
    for bbox in bboxes:
        cls_id = int(bbox[0])
        cx, cy, bw, bh = bbox[1], bbox[2], bbox[3], bbox[4]
        px_cx = int(cx * w)
        px_cy = int(cy * h)
        px_w = int(bw * w)
        px_h = int(bh * h)
        x1 = int(px_cx - px_w / 2)
        y1 = int(px_cy - px_h / 2)
        x2 = int(px_cx + px_w / 2)
        y2 = int(px_cy + px_h / 2)

        color = colors[cls_id % len(colors)]
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        cv2.putText(img, CLASS_NAMES[cls_id], (x1, max(y1 - 5, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    cv2.imwrite(str(save_path), img)


def main():
    if not validate_classes_txt():
        return

    image_files = sorted(list(MAKESENSE_IMAGE_DIR.glob("*.jpg")) +
                           list(MAKESENSE_IMAGE_DIR.glob("*.jpeg")) +
                           list(MAKESENSE_IMAGE_DIR.glob("*.png")))

    if not image_files:
        print(f"[Error] No images found in {MAKESENSE_IMAGE_DIR}")
        return

    stats = {
        "total_images": len(image_files),
        "missing_labels": 0,
        "valid_images": 0,
        "images_with_issues": 0,
        "total_boxes": 0,
        "valid_boxes": 0,
        "issue_breakdown": defaultdict(int)
    }

    VISUAL_DIR.mkdir(parents=True, exist_ok=True)

    sample_indices = set(np.random.choice(
        len(image_files),
        size=min(max(1, int(len(image_files) * 0.1)), 50),
        replace=False
    )) if len(image_files) > 0 else set()

    print(f"[Validating] {len(image_files)} images...")

    for idx, img_path in enumerate(tqdm(image_files, desc="Validating")):
        label_path = MAKESENSE_LABEL_DIR / (img_path.stem + ".txt")

        img = cv2.imread(str(img_path))
        if img is None:
            stats["issue_breakdown"]["unreadable_image"] += 1
            continue

        h, w = img.shape[:2]
        result = validate_single(img_path, label_path, w, h)

        if not result["has_label"]:
            stats["missing_labels"] += 1

        if result["issues"]:
            stats["images_with_issues"] += 1
            for issue in result["issues"]:
                issue_type = issue.split(":")[0].strip()
                stats["issue_breakdown"][issue_type] += 1
        else:
            stats["valid_images"] += 1

        stats["total_boxes"] += result["boxes"]
        stats["valid_boxes"] += result["valid_boxes"]

        if idx in sample_indices:
            draw_validation_sample(img_path, label_path, VISUAL_DIR / f"check_{img_path.name}")

    report = {
        "summary": {
            "total_images": stats["total_images"],
            "valid_images": stats["valid_images"],
            "missing_labels": stats["missing_labels"],
            "images_with_issues": stats["images_with_issues"],
            "total_boxes": stats["total_boxes"],
            "valid_boxes": stats["valid_boxes"]
        },
        "issue_breakdown": dict(stats["issue_breakdown"]),
        "note": "Visual samples saved to outputs/visualizations/"
    }

    report_path = Path(__file__).parent.parent / "outputs" / "reports" / "makesense_validation.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"
[Validation Report]")
    print(f"  Total images: {stats['total_images']}")
    print(f"  Valid images: {stats['valid_images']}")
    print(f"  Missing labels: {stats['missing_labels']}")
    print(f"  Images with issues: {stats['images_with_issues']}")
    print(f"  Total boxes: {stats['total_boxes']}")
    print(f"  Valid boxes: {stats['valid_boxes']}")
    print(f"  Issue breakdown: {dict(stats['issue_breakdown'])}")
    print(f"  Report saved to: {report_path}")
    print(f"  Visual checks saved to: {VISUAL_DIR}")


if __name__ == "__main__":
    main()
