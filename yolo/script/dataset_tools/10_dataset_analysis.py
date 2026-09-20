import csv
import json

from collections import Counter
from collections import defaultdict

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import sys

sys.path.append(
    str(
        Path(__file__).parent.parent
    )
)

from config import (
    DATASET_DIR,
    CLASS_NAMES,
    VISUAL_DIR,
    SPLIT_MANIFEST_CSV,
    DATASET_INTEGRITY_REPORT,
)


SPLITS = (
    "train",
    "val",
    "test"
)


def analyze_split(
    split: str
):

    label_dir = (
        DATASET_DIR
        / "labels"
        / split
    )

    image_dir = (
        DATASET_DIR
        / "images"
        / split
    )

    if (
        not label_dir.exists()
        or not image_dir.exists()
    ):

        return None

    cls_counts = Counter()

    box_areas = {
        name: []
        for name in CLASS_NAMES
    }

    box_ratios = {
        name: []
        for name in CLASS_NAMES
    }

    for txt_file in (
        label_dir.glob("*.txt")
    ):

        with open(
            txt_file,
            "r",
            encoding="utf-8"
        ) as f:

            for line in f:

                parts = (
                    line.strip().split()
                )

                if len(parts) != 5:
                    continue

                cls_id = int(
                    parts[0]
                )

                if (
                    cls_id < 0
                    or cls_id
                    >= len(
                        CLASS_NAMES
                    )
                ):

                    continue

                width = float(
                    parts[3]
                )

                height = float(
                    parts[4]
                )

                cls_name = (
                    CLASS_NAMES[
                        cls_id
                    ]
                )

                cls_counts[
                    cls_name
                ] += 1

                box_areas[
                    cls_name
                ].append(
                    width * height
                )

                box_ratios[
                    cls_name
                ].append(
                    width / height
                    if height > 0
                    else 0
                )

    images = list(
        image_dir.glob(
            "*.jpg"
        )
    )

    original_images = [
        p
        for p in images
        if "_aug_" not in p.stem
    ]

    augmented_images = [
        p
        for p in images
        if "_aug_" in p.stem
    ]

    return {
        "cls_counts":
            cls_counts,

        "box_areas":
            box_areas,

        "box_ratios":
            box_ratios,

        "total_images":
            len(images),

        "original_images":
            len(original_images),

        "augmented_images":
            len(augmented_images),
    }


def check_dataset_integrity():

    issues = []

    source_to_splits = defaultdict(
        set
    )

    manifest_counts = Counter()

    if not SPLIT_MANIFEST_CSV.exists():

        issues.append(
            "Missing split manifest: "
            f"{SPLIT_MANIFEST_CSV}"
        )

        return {
            "passed":
                False,

            "issues":
                issues,

            "source_group_overlap":
                {},

            "manifest_counts":
                {},
        }

    with open(
        SPLIT_MANIFEST_CSV,
        "r",
        newline="",
        encoding="utf-8"
    ) as f:

        rows = list(
            csv.DictReader(f)
        )

    for row in rows:

        split = (
            row.get("split")
            or ""
        )

        source_group = (
            row.get(
                "source_group"
            )
            or ""
        )

        is_augmented = (
            (
                row.get(
                    "is_augmented"
                )
                or ""
            ).lower()
            == "true"
        )

        if split not in SPLITS:

            issues.append(
                "Invalid split "
                f"in manifest: {row}"
            )

            continue

        manifest_counts[
            (
                split,
                (
                    "aug"
                    if is_augmented
                    else "original"
                )
            )
        ] += 1

        # Leakage check should use
        # ORIGINAL independent samples.
        #
        # Augmented images inherit the
        # parent source_group and are
        # required to remain in train.
        if (
            source_group
            and not is_augmented
        ):

            source_to_splits[
                source_group
            ].add(
                split
            )

        if (
            is_augmented
            and split != "train"
        ):

            issues.append(
                "Augmented sample "
                "outside train: "
                f"{row.get('filename')} "
                f"-> {split}"
            )

    overlaps = {
        source:
            sorted(splits)

        for source, splits
        in source_to_splits.items()

        if len(splits) > 1
    }

    for (
        source,
        splits
    ) in overlaps.items():

        issues.append(
            "Source group leakage: "
            f"{source} appears in "
            f"{splits}"
        )

    # Physical file check:
    # even if manifest is correct,
    # val/test directories must contain
    # no offline augmented files.
    for split in (
        "val",
        "test"
    ):

        leaked_aug_files = sorted(
            p.name
            for p
            in (
                DATASET_DIR
                / "images"
                / split
            ).glob(
                "*_aug_*.jpg"
            )
        )

        for filename in (
            leaked_aug_files
        ):

            issues.append(
                "Augmented file "
                "physically present "
                f"in {split}: "
                f"{filename}"
            )

    report = {
        "passed":
            len(issues) == 0,

        "issues":
            issues,

        "source_group_overlap":
            overlaps,

        "num_original_source_groups":
            len(
                source_to_splits
            ),

        "manifest_counts": {
            f"{split}_{kind}":
                manifest_counts[
                    (
                        split,
                        kind
                    )
                ]

            for split in SPLITS

            for kind in (
                "original",
                "aug"
            )
        },
    }

    DATASET_INTEGRITY_REPORT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        DATASET_INTEGRITY_REPORT,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            report,
            f,
            ensure_ascii=False,
            indent=2
        )

    return report


def plot_distribution(
    train_data,
    val_data,
    test_data
):

    fig, axes = plt.subplots(
        2,
        2,
        figsize=(
            14,
            10
        )
    )

    ax = axes[
        0,
        0
    ]

    x = np.arange(
        len(CLASS_NAMES)
    )

    width = 0.25

    for i, (
        data,
        name,
        color
    ) in enumerate([
        (
            train_data,
            "Train",
            "#3498db"
        ),
        (
            val_data,
            "Val",
            "#2ecc71"
        ),
        (
            test_data,
            "Test",
            "#e74c3c"
        ),
    ]):

        counts = [
            data[
                "cls_counts"
            ].get(
                c,
                0
            )
            for c
            in CLASS_NAMES
        ]

        ax.bar(
            x
            + (
                i - 1
            )
            * width,
            counts,
            width,
            label=name,
            color=color,
            alpha=0.8
        )

    ax.set_xticks(
        x
    )

    ax.set_xticklabels(
        CLASS_NAMES,
        rotation=15,
        ha="right"
    )

    ax.set_ylabel(
        "Box Count"
    )

    ax.set_title(
        "Class Distribution "
        "Across Splits"
    )

    ax.legend()

    ax = axes[
        0,
        1
    ]

    for cls_name in (
        CLASS_NAMES
    ):

        areas = (
            train_data[
                "box_areas"
            ][cls_name]
        )

        if areas:

            ax.hist(
                areas,
                bins=30,
                alpha=0.5,
                label=cls_name,
                range=(
                    0,
                    0.1
                )
            )

    ax.set_xlabel(
        "Normalized Box Area"
    )

    ax.set_ylabel(
        "Frequency"
    )

    ax.set_title(
        "Training Set Bounding "
        "Box Area Distribution"
    )

    ax.legend()

    ax = axes[
        1,
        0
    ]

    for cls_name in (
        CLASS_NAMES
    ):

        ratios = [
            r
            for r
            in train_data[
                "box_ratios"
            ][cls_name]
            if 0 < r < 5
        ]

        if ratios:

            ax.hist(
                ratios,
                bins=30,
                alpha=0.5,
                label=cls_name,
                range=(
                    0,
                    3
                )
            )

    ax.set_xlabel(
        "Width / Height Ratio"
    )

    ax.set_ylabel(
        "Frequency"
    )

    ax.set_title(
        "Training Set "
        "Aspect Ratio Distribution"
    )

    ax.legend()

    ax = axes[
        1,
        1
    ]

    split_names = [
        "Train",
        "Val",
        "Test"
    ]

    totals = [
        train_data[
            "total_images"
        ],

        val_data[
            "total_images"
        ],

        test_data[
            "total_images"
        ],
    ]

    colors = [
        "#3498db",
        "#2ecc71",
        "#e74c3c"
    ]

    bars = ax.bar(
        split_names,
        totals,
        color=colors,
        alpha=0.8,
        edgecolor="black"
    )

    ax.set_ylabel(
        "Image Count"
    )

    ax.set_title(
        "Total Images per Split"
    )

    for (
        bar,
        total
    ) in zip(
        bars,
        totals
    ):

        ax.text(
            bar.get_x()
            + (
                bar.get_width()
                / 2
            ),
            bar.get_height()
            + 1,
            str(total),
            ha="center",
            va="bottom",
            fontsize=11
        )

    plt.tight_layout()

    save_path = (
        VISUAL_DIR
        / "dataset_analysis.png"
    )

    plt.savefig(
        save_path,
        dpi=300,
        bbox_inches="tight"
    )

    print(
        "[Chart saved] "
        f"{save_path}"
    )

    plt.close()


def main():

    print(
        "[Checking dataset integrity]..."
    )

    integrity = (
        check_dataset_integrity()
    )

    if integrity["passed"]:

        print(
            "[Integrity] PASS: "
            "no source-group overlap "
            "and no augmented "
            "val/test samples."
        )

    else:

        print(
            "[Integrity] FAIL"
        )

        for issue in (
            integrity["issues"]
        ):

            print(
                f"  - {issue}"
            )

        print(
            "  Detailed report: "
            f"{DATASET_INTEGRITY_REPORT}"
        )

        return

    print(
        "\n"
        "[Analyzing dataset "
        "distribution]..."
    )

    train_data = (
        analyze_split(
            "train"
        )
    )

    val_data = (
        analyze_split(
            "val"
        )
    )

    test_data = (
        analyze_split(
            "test"
        )
    )

    if (
        train_data is None
        or val_data is None
        or test_data is None
    ):

        print(
            "[Error] Dataset "
            "is incomplete. "
            "Run 04_dataset_split.py "
            "and "
            "05_train_augmentation.py "
            "first."
        )

        return

    plot_distribution(
        train_data,
        val_data,
        test_data
    )

    print(
        "\n"
        "[Dataset Statistics Summary]"
    )

    for (
        split,
        data
    ) in [
        (
            "Train",
            train_data
        ),
        (
            "Val",
            val_data
        ),
        (
            "Test",
            test_data
        ),
    ]:

        print(
            f"\n{split}: "
            f"{data['total_images']} "
            "images "
            "("
            f"original="
            f"{data['original_images']}, "
            f"augmented="
            f"{data['augmented_images']}"
            ")"
        )

        for cls_name in (
            CLASS_NAMES
        ):

            count = (
                data[
                    "cls_counts"
                ].get(
                    cls_name,
                    0
                )
            )

            if (
                data[
                    "box_areas"
                ][cls_name]
            ):

                avg_area = float(
                    np.mean(
                        data[
                            "box_areas"
                        ][cls_name]
                    )
                )

            else:

                avg_area = 0.0

            print(
                f"  {cls_name}: "
                f"{count} boxes, "
                "average normalized "
                "area: "
                f"{avg_area:.4f}"
            )

    print(
        "\n"
        "[Integrity report] "
        f"{DATASET_INTEGRITY_REPORT}"
    )


if __name__ == "__main__":
    main()
