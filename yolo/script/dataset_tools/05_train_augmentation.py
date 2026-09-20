import csv
import random
import shutil

from pathlib import Path
from typing import Dict
from typing import List

import cv2
import numpy as np

from PIL import Image
from PIL import ImageEnhance

from tqdm import tqdm

import sys

sys.path.append(
    str(
        Path(__file__).parent.parent
    )
)

from config import (
    DATASET_DIR,
    AUG_IMAGE_DIR,
    SPLIT_MANIFEST_CSV,
    AUGMENTATION_FACTOR,
    MAX_ROTATION_ANGLE,
    CROP_SCALE_RANGE,
    BRIGHTNESS_RANGE,
    CONTRAST_RANGE,
    NOISE_INTENSITY,
    BLUR_KERNEL_RANGE,
    RANDOM_SEED,
)

from utils.bbox_utils import (
    horizontal_flip_bboxes,
    crop_bboxes,
    rotate_bboxes_approx,
)

from utils.weather_effects import (
    add_fog,
    add_rain,
    add_night_effect,
)


MANIFEST_FIELDS = [
    "filename",
    "source_group",
    "split",
    "is_augmented",
    "parent_image",
]


def load_bboxes(
    label_path: Path
) -> List[List[float]]:

    if not label_path.exists():

        return []

    bboxes = []

    with open(
        label_path,
        "r",
        encoding="utf-8"
    ) as f:

        for line_no, line in enumerate(
            f,
            start=1
        ):

            parts = (
                line.strip().split()
            )

            if not parts:
                continue

            if len(parts) != 5:

                raise ValueError(
                    f"Malformed label "
                    f"{label_path}:"
                    f"{line_no}: "
                    f"{line.strip()}"
                )

            bboxes.append(
                [
                    int(parts[0])
                ]
                + [
                    float(x)
                    for x
                    in parts[1:]
                ]
            )

    return bboxes


def save_bboxes(
    bboxes: List[List[float]],
    save_path: Path
):

    lines = [
        (
            f"{int(b[0])} "
            f"{b[1]:.6f} "
            f"{b[2]:.6f} "
            f"{b[3]:.6f} "
            f"{b[4]:.6f}"
        )
        for b in bboxes
    ]

    save_path.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )


def apply_color_jitter(
    image: np.ndarray
) -> np.ndarray:

    pil_img = (
        Image.fromarray(
            cv2.cvtColor(
                image,
                cv2.COLOR_BGR2RGB
            )
        )
    )

    brightness = random.uniform(
        *BRIGHTNESS_RANGE
    )

    pil_img = (
        ImageEnhance
        .Brightness(
            pil_img
        )
        .enhance(
            brightness
        )
    )

    contrast = random.uniform(
        *CONTRAST_RANGE
    )

    pil_img = (
        ImageEnhance
        .Contrast(
            pil_img
        )
        .enhance(
            contrast
        )
    )

    saturation = random.uniform(
        0.8,
        1.2
    )

    pil_img = (
        ImageEnhance
        .Color(
            pil_img
        )
        .enhance(
            saturation
        )
    )

    return cv2.cvtColor(
        np.array(pil_img),
        cv2.COLOR_RGB2BGR
    )


def add_gaussian_noise(
    image: np.ndarray
) -> np.ndarray:

    noise = np.random.normal(
        0,
        NOISE_INTENSITY,
        image.shape
    ).astype(
        np.float32
    )

    noisy = (
        image.astype(
            np.float32
        )
        + noise
    )

    return np.clip(
        noisy,
        0,
        255
    ).astype(
        np.uint8
    )


def add_blur(
    image: np.ndarray
) -> np.ndarray:

    kernels = list(
        range(
            BLUR_KERNEL_RANGE[0],
            BLUR_KERNEL_RANGE[1] + 1,
            2
        )
    )

    if not kernels:

        return image

    kernel = random.choice(
        kernels
    )

    if kernel >= 3:

        return cv2.GaussianBlur(
            image,
            (
                kernel,
                kernel
            ),
            0
        )

    return image


def augment_single(
    image_path: Path,
    label_path: Path
):

    image = cv2.imread(
        str(image_path)
    )

    if image is None:

        return None

    height, width = (
        image.shape[:2]
    )

    bboxes = load_bboxes(
        label_path
    )

    # Negative samples remain negative.
    # Only photometric transforms
    # are applied.
    if not bboxes:

        image = apply_color_jitter(
            image
        )

        if random.random() < 0.5:

            image = (
                add_gaussian_noise(
                    image
                )
            )

        if random.random() < 0.3:

            image = add_blur(
                image
            )

        return (
            image,
            []
        )

    # Horizontal flip
    if random.random() < 0.5:

        image = cv2.flip(
            image,
            1
        )

        bboxes = (
            horizontal_flip_bboxes(
                bboxes
            )
        )

    # Random crop
    if random.random() < 0.7:

        scale = random.uniform(
            *CROP_SCALE_RANGE
        )

        new_width = max(
            1,
            int(
                round(
                    width
                    * scale
                )
            )
        )

        new_height = max(
            1,
            int(
                round(
                    height
                    * scale
                )
            )
        )

        x1 = random.randint(
            0,
            max(
                0,
                width - new_width
            )
        )

        y1 = random.randint(
            0,
            max(
                0,
                height - new_height
            )
        )

        x2 = (
            x1 + new_width
        )

        y2 = (
            y1 + new_height
        )

        cropped_boxes = (
            crop_bboxes(
                bboxes,
                x1,
                y1,
                x2,
                y2,
                width,
                height
            )
        )

        # Avoid generating an artificial
        # positive sample whose target
        # disappeared completely.
        if not cropped_boxes:

            return None

        image = image[
            y1:y2,
            x1:x2
        ]

        bboxes = (
            cropped_boxes
        )

        height, width = (
            image.shape[:2]
        )

    # Small rotation
    if random.random() < 0.3:

        angle = random.uniform(
            -MAX_ROTATION_ANGLE,
            MAX_ROTATION_ANGLE
        )

        matrix = (
            cv2.getRotationMatrix2D(
                (
                    width / 2,
                    height / 2
                ),
                angle,
                1.0
            )
        )

        image = cv2.warpAffine(
            image,
            matrix,
            (
                width,
                height
            ),
            borderValue=(
                114,
                114,
                114
            )
        )

        bboxes = (
            rotate_bboxes_approx(
                bboxes,
                angle,
                width,
                height
            )
        )

        bboxes = [
            b
            for b in bboxes
            if (
                0 < b[1] < 1
                and 0 < b[2] < 1
                and b[3] > 0
                and b[4] > 0
            )
        ]

        if not bboxes:

            return None

    image = apply_color_jitter(
        image
    )

    if random.random() < 0.5:

        image = (
            add_gaussian_noise(
                image
            )
        )

    if random.random() < 0.3:

        image = add_blur(
            image
        )

    # Simulate difficult outdoor
    # environmental conditions.
    weather_choice = (
        random.random()
    )

    if weather_choice < 0.07:

        image = add_fog(
            image,
            intensity=random.uniform(
                0.2,
                0.5
            )
        )

    elif weather_choice < 0.14:

        image = add_rain(
            image,
            num_drops=random.randint(
                300,
                1200
            )
        )

    elif weather_choice < 0.20:

        image = add_night_effect(
            image,
            gamma=random.uniform(
                1.8,
                2.5
            )
        )

    return (
        image,
        bboxes
    )


def load_original_manifest() -> List[dict]:

    if not SPLIT_MANIFEST_CSV.exists():

        raise FileNotFoundError(
            "Split manifest not found: "
            f"{SPLIT_MANIFEST_CSV}. "
            "Run 04_dataset_split.py first."
        )

    with open(
        SPLIT_MANIFEST_CSV,
        "r",
        newline="",
        encoding="utf-8"
    ) as f:

        rows = list(
            csv.DictReader(f)
        )

    originals = [
        row
        for row in rows
        if (
            row.get(
                "is_augmented"
            )
            or ""
        ).lower() != "true"
    ]

    return originals


def source_group_by_filename(
    original_rows: List[dict]
) -> Dict[str, str]:

    mapping = {}

    for row in original_rows:

        if (
            row.get("split")
            == "train"
        ):

            mapping[
                row["filename"]
            ] = (
                row[
                    "source_group"
                ]
            )

    return mapping


def remove_previous_augmentations(
    train_image_dir: Path,
    train_label_dir: Path
):

    # Remove synthetic samples from
    # previous runs while preserving
    # original train samples.
    for image_path in (
        train_image_dir.glob(
            "*_aug_*.jpg"
        )
    ):

        image_path.unlink(
            missing_ok=True
        )

    for label_path in (
        train_label_dir.glob(
            "*_aug_*.txt"
        )
    ):

        label_path.unlink(
            missing_ok=True
        )

    # Audit/cache directory contains
    # generated TRAIN-only samples.
    AUG_IMAGE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    for path in (
        AUG_IMAGE_DIR.iterdir()
    ):

        if (
            path.is_file()
            and path.suffix.lower()
            in {
                ".jpg",
                ".jpeg",
                ".png",
                ".txt",
            }
        ):

            path.unlink()


def write_manifest(
    original_rows: List[dict],
    augmented_rows: List[dict]
):

    with open(
        SPLIT_MANIFEST_CSV,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=MANIFEST_FIELDS
        )

        writer.writeheader()

        writer.writerows(
            original_rows
        )

        writer.writerows(
            augmented_rows
        )


def main():

    # Full reproducibility for
    # offline augmentation.
    random.seed(
        RANDOM_SEED
    )

    np.random.seed(
        RANDOM_SEED
    )

    train_image_dir = (
        DATASET_DIR
        / "images"
        / "train"
    )

    train_label_dir = (
        DATASET_DIR
        / "labels"
        / "train"
    )

    if (
        not train_image_dir.exists()
        or not train_label_dir.exists()
    ):

        print(
            "[Error] Training split "
            "does not exist. "
            "Run 04_dataset_split.py first."
        )

        return

    original_rows = (
        load_original_manifest()
    )

    train_source_groups = (
        source_group_by_filename(
            original_rows
        )
    )

    remove_previous_augmentations(
        train_image_dir,
        train_label_dir
    )

    # IMPORTANT:
    # only ORIGINAL TRAIN images
    # participate in offline augmentation.
    train_images = sorted(
        image_path
        for image_path
        in train_image_dir.glob(
            "*.jpg"
        )
        if (
            "_aug_"
            not in image_path.stem
        )
    )

    if not train_images:

        print(
            "[Error] No original "
            "training images found."
        )

        return

    print(
        "[Train-only Augmentation] "
        f"{len(train_images)} "
        "original train images, "
        f"up to "
        f"{AUGMENTATION_FACTOR} "
        "augmentations each"
    )

    generated_rows = []

    total_generated = 0
    total_skipped = 0

    for image_path in tqdm(
        train_images,
        desc="Augmenting train only"
    ):

        if (
            image_path.name
            not in train_source_groups
        ):

            raise RuntimeError(
                f"Training image "
                f"'{image_path.name}' "
                "is missing from "
                "split_manifest.csv. "
                "Re-run "
                "04_dataset_split.py "
                "before augmentation."
            )

        label_path = (
            train_label_dir
            / (
                f"{image_path.stem}"
                ".txt"
            )
        )

        source_group = (
            train_source_groups[
                image_path.name
            ]
        )

        for aug_index in range(
            AUGMENTATION_FACTOR
        ):

            result = augment_single(
                image_path,
                label_path
            )

            if result is None:

                total_skipped += 1

                continue

            (
                aug_image,
                aug_bboxes
            ) = result

            aug_name = (
                f"{image_path.stem}"
                f"_aug_"
                f"{aug_index:02d}"
                ".jpg"
            )

            aug_label_name = (
                f"{Path(aug_name).stem}"
                ".txt"
            )

            audit_image_path = (
                AUG_IMAGE_DIR
                / aug_name
            )

            audit_label_path = (
                AUG_IMAGE_DIR
                / aug_label_name
            )

            ok = cv2.imwrite(
                str(
                    audit_image_path
                ),
                aug_image,
                [
                    cv2.IMWRITE_JPEG_QUALITY,
                    92
                ]
            )

            if not ok:

                total_skipped += 1

                continue

            save_bboxes(
                aug_bboxes,
                audit_label_path
            )

            # Synthetic data is copied
            # into TRAIN ONLY.
            shutil.copy2(
                audit_image_path,
                train_image_dir
                / aug_name
            )

            shutil.copy2(
                audit_label_path,
                train_label_dir
                / aug_label_name
            )

            generated_rows.append({
                "filename":
                    aug_name,

                "source_group":
                    source_group,

                "split":
                    "train",

                "is_augmented":
                    "true",

                "parent_image":
                    image_path.name,
            })

            total_generated += 1

    write_manifest(
        original_rows,
        generated_rows
    )

    # Hard leakage guard.
    val_aug = list(
        (
            DATASET_DIR
            / "images"
            / "val"
        ).glob(
            "*_aug_*.jpg"
        )
    )

    test_aug = list(
        (
            DATASET_DIR
            / "images"
            / "test"
        ).glob(
            "*_aug_*.jpg"
        )
    )

    if val_aug or test_aug:

        raise RuntimeError(
            "Leakage guard failed: "
            "augmented samples were found "
            "in validation/test. "
            "Re-run 04_dataset_split.py "
            "to rebuild clean splits."
        )

    print(
        "\n"
        "[Augmentation Done]"
    )

    print(
        "  Original train images: "
        f"{len(train_images)}"
    )

    print(
        "  Generated train-only "
        "samples: "
        f"{total_generated}"
    )

    print(
        "  Skipped augmentation "
        "attempts: "
        f"{total_skipped}"
    )

    print(
        f"  Audit copies: "
        f"{AUG_IMAGE_DIR}"
    )

    print(
        f"  Manifest updated: "
        f"{SPLIT_MANIFEST_CSV}"
    )

    print(
        "[Leakage Check] PASS: "
        "validation/test contain "
        "no offline augmented samples."
    )


if __name__ == "__main__":
    main()
