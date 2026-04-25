import shutil
import yaml
import numpy as np
from pathlib import Path
from collections import defaultdict, Counter
from tqdm import tqdm

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import (CLEAN_IMAGE_DIR, AUG_IMAGE_DIR, YOLO_LABEL_DIR,
                    DATASET_DIR, CLASS_NAMES, NUM_CLASSES, REPORT_DIR)


def load_all_bboxes(label_path: Path) -> list:
    if not label_path.exists():
        return []
    cls_ids = []
    with open(label_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if parts:
                cls_ids.append(int(parts[0]))
    return cls_ids


def stratified_split(image_paths: list, train_ratio=0.8, val_ratio=0.1, test_ratio=0.1, seed=42):
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6

    image_classes = []
    valid_images = []

    for img_path in image_paths:
        label_path = YOLO_LABEL_DIR / (img_path.stem + ".txt")
        cls_ids = load_all_bboxes(label_path)

        if not cls_ids:
            image_classes.append(-1)
            valid_images.append(img_path)
            continue

        main_cls = Counter(cls_ids).most_common(1)[0][0]
        image_classes.append(main_cls)
        valid_images.append(img_path)

    image_classes = np.array(image_classes)
    valid_images = np.array(valid_images)

    train_set, val_set, test_set = [], [], []

    np.random.seed(seed)
    for cls in range(-1, NUM_CLASSES):
        mask = image_classes == cls
        cls_images = valid_images[mask]
        if len(cls_images) == 0:
            continue

        indices = np.random.permutation(len(cls_images))
        cls_images = cls_images[indices]

        n = len(cls_images)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)

        train_set.extend(cls_images[:n_train])
        val_set.extend(cls_images[n_train:n_train + n_val])
        test_set.extend(cls_images[n_train + n_val:])

    np.random.shuffle(train_set)
    np.random.shuffle(val_set)
    np.random.shuffle(test_set)

    return train_set, val_set, test_set


def copy_to_yolo_structure(split_name: str, image_list: list):
    img_dir = DATASET_DIR / "images" / split_name
    lbl_dir = DATASET_DIR / "labels" / split_name
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)

    for img_path in tqdm(image_list, desc=f"Copying {split_name}"):
        dst_img = img_dir / img_path.name
        shutil.copy2(str(img_path), str(dst_img))

        label_name = img_path.stem + ".txt"
        src_label = AUG_IMAGE_DIR / label_name if (AUG_IMAGE_DIR / label_name).exists() else YOLO_LABEL_DIR / label_name

        dst_label = lbl_dir / label_name
        if src_label.exists():
            shutil.copy2(str(src_label), str(dst_label))
        else:
            dst_label.write_text("")


def analyze_distribution(split_name: str, image_list: list) -> dict:
    stats = Counter()
    for img_path in image_list:
        label_path = DATASET_DIR / "labels" / split_name / (img_path.stem + ".txt")
        if label_path.exists():
            cls_ids = load_all_bboxes(label_path)
            stats.update(cls_ids)
    return dict(stats)


def main():
    all_images = list(CLEAN_IMAGE_DIR.glob("*.jpg"))
    aug_images = list(AUG_IMAGE_DIR.glob("*.jpg"))
    all_images.extend(aug_images)

    if not all_images:
        print("[Error] No images found, please run previous steps first")
        return

    print(f"[Splitting Dataset] Total {len(all_images)} images (including augmented)")

    train_imgs, val_imgs, test_imgs = stratified_split(all_images, 0.8, 0.1, 0.1)

    for split in ['train', 'val', 'test']:
        shutil.rmtree(DATASET_DIR / "images" / split, ignore_errors=True)
        shutil.rmtree(DATASET_DIR / "labels" / split, ignore_errors=True)

    copy_to_yolo_structure("train", train_imgs)
    copy_to_yolo_structure("val", val_imgs)
    copy_to_yolo_structure("test", test_imgs)

    data_yaml = {
        "path": str(DATASET_DIR.resolve()),
        "train": str((DATASET_DIR / "images" / "train").relative_to(DATASET_DIR)),
        "val": str((DATASET_DIR / "images" / "val").relative_to(DATASET_DIR)),
        "test": str((DATASET_DIR / "images" / "test").relative_to(DATASET_DIR)),
        "nc": NUM_CLASSES,
        "names": CLASS_NAMES
    }

    yaml_path = DATASET_DIR / "data.yaml"
    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(data_yaml, f, allow_unicode=True, sort_keys=False)

    report = {
        "train": {"count": len(train_imgs), "distribution": analyze_distribution("train", train_imgs)},
        "val": {"count": len(val_imgs), "distribution": analyze_distribution("val", val_imgs)},
        "test": {"count": len(test_imgs), "distribution": analyze_distribution("test", test_imgs)}
    }

    report_path = REPORT_DIR / "split_distribution.json"
    import json
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n[Split Done]")
    print(f"  Train: {len(train_imgs)} | Val: {len(val_imgs)} | Test: {len(test_imgs)}")
    print(f"  data.yaml generated: {yaml_path}")
    print(f"  Distribution report: {report_path}")


if __name__ == "__main__":
    main()
