import random
import cv2
import numpy as np
from pathlib import Path
from PIL import Image, ImageEnhance
from tqdm import tqdm

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import (CLEAN_IMAGE_DIR, YOLO_LABEL_DIR, AUG_IMAGE_DIR,
                    AUGMENTATION_FACTOR, MAX_ROTATION_ANGLE, CROP_SCALE_RANGE,
                    BRIGHTNESS_RANGE, CONTRAST_RANGE, NOISE_INTENSITY,
                    BLUR_KERNEL_RANGE, CLASS_NAMES)
from utils.bbox_utils import (horizontal_flip_bboxes, crop_bboxes,
                               rotate_bboxes_approx)
from utils.weather_effects import add_fog, add_rain, add_night_effect


def load_bboxes(label_path: Path) -> list:
    if not label_path.exists():
        return []
    bboxes = []
    with open(label_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 5:
                bboxes.append([int(parts[0])] + [float(x) for x in parts[1:]])
    return bboxes


def save_bboxes(bboxes: list, save_path: Path):
    lines = []
    for b in bboxes:
        lines.append(f"{int(b[0])} {b[1]:.6f} {b[2]:.6f} {b[3]:.6f} {b[4]:.6f}")
    save_path.write_text("\n".join(lines), encoding='utf-8')


def apply_color_jitter(image: np.ndarray) -> np.ndarray:
    pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

    factor = random.uniform(*BRIGHTNESS_RANGE)
    pil_img = ImageEnhance.Brightness(pil_img).enhance(factor)

    factor = random.uniform(*CONTRAST_RANGE)
    pil_img = ImageEnhance.Contrast(pil_img).enhance(factor)

    factor = random.uniform(0.8, 1.2)
    pil_img = ImageEnhance.Color(pil_img).enhance(factor)

    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def add_gaussian_noise(image: np.ndarray) -> np.ndarray:
    noise = np.random.normal(0, NOISE_INTENSITY, image.shape).astype(np.float32)
    noisy = image.astype(np.float32) + noise
    return np.clip(noisy, 0, 255).astype(np.uint8)


def add_blur(image: np.ndarray) -> np.ndarray:
    k = random.choice(range(BLUR_KERNEL_RANGE[0], BLUR_KERNEL_RANGE[1]+1, 2))
    if k >= 3:
        return cv2.GaussianBlur(image, (k, k), 0)
    return image


def augment_single(image_path: Path, label_path: Path, aug_index: int):
    img = cv2.imread(str(image_path))
    if img is None:
        return None
    h, w = img.shape[:2]
    bboxes = load_bboxes(label_path)

    if not bboxes:
        img = apply_color_jitter(img)
        img = add_gaussian_noise(img)
        return img, []

    if random.random() < 0.5:
        img = cv2.flip(img, 1)
        bboxes = horizontal_flip_bboxes(bboxes)

    if random.random() < 0.7:
        scale = random.uniform(*CROP_SCALE_RANGE)
        new_w = int(w * scale)
        new_h = int(h * scale)
        x1 = random.randint(0, w - new_w)
        y1 = random.randint(0, h - new_h)
        x2 = x1 + new_w
        y2 = y1 + new_h

        img = img[y1:y2, x1:x2]
        bboxes = crop_bboxes(bboxes, x1, y1, x2, y2, w, h)
        if not bboxes:
            return None
        h, w = img.shape[:2]

    if random.random() < 0.3:
        angle = random.uniform(-MAX_ROTATION_ANGLE, MAX_ROTATION_ANGLE)
        M = cv2.getRotationMatrix2D((w/2, h/2), angle, 1.0)
        img = cv2.warpAffine(img, M, (w, h), borderValue=(114, 114, 114))
        bboxes = rotate_bboxes_approx(bboxes, angle, w, h)
        bboxes = [b for b in bboxes if 0 < b[1] < 1 and 0 < b[2] < 1 and b[3] > 0 and b[4] > 0]

    img = apply_color_jitter(img)

    if random.random() < 0.5:
        img = add_gaussian_noise(img)

    if random.random() < 0.3:
        img = add_blur(img)

    weather_choice = random.random()
    if weather_choice < 0.07:
        img = add_fog(img, intensity=random.uniform(0.2, 0.5))
    elif weather_choice < 0.14:
        img = add_rain(img, num_drops=random.randint(300, 1200))
    elif weather_choice < 0.20:
        img = add_night_effect(img, gamma=random.uniform(1.8, 2.5))

    return img, bboxes


def main():
    image_files = sorted(list(CLEAN_IMAGE_DIR.glob("*.jpg")))
    if not image_files:
        print(f"[Error] No images in {CLEAN_IMAGE_DIR}")
        return

    print(f"[Start Augmentation] Total {len(image_files)} base images, augmenting to {AUGMENTATION_FACTOR} each...")

    total_generated = 0
    for img_path in tqdm(image_files, desc="Augmentation progress"):
        stem = img_path.stem
        label_path = YOLO_LABEL_DIR / (stem + ".txt")

        for i in range(AUGMENTATION_FACTOR):
            result = augment_single(img_path, label_path, i)
            if result is None:
                continue
            aug_img, aug_bboxes = result

            aug_name = f"{stem}_aug_{i:02d}.jpg"
            aug_img_path = AUG_IMAGE_DIR / aug_name
            cv2.imwrite(str(aug_img_path), aug_img, [cv2.IMWRITE_JPEG_QUALITY, 92])

            aug_label_path = AUG_IMAGE_DIR / f"{stem}_aug_{i:02d}.txt"
            save_bboxes(aug_bboxes, aug_label_path)
            total_generated += 1

    print(f"\n[Augmentation Done] Generated {total_generated} augmented samples")
    print(f"  Saved to: {AUG_IMAGE_DIR}")


if __name__ == "__main__":
    main()
