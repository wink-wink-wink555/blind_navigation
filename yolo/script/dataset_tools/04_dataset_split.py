import csv
import json
import random
import re
import shutil

from collections import Counter
from collections import defaultdict

from pathlib import Path
from typing import Dict
from typing import List
from typing import Tuple

import yaml

from tqdm import tqdm

import sys

sys.path.append(
    str(
        Path(__file__).parent.parent
    )
)

from config import (
    CLEAN_IMAGE_DIR,
    YOLO_LABEL_DIR,
    DATASET_DIR,
    SOURCE_METADATA_CSV,
    SPLIT_MANIFEST_CSV,
    SPLIT_REPORT_JSON,
    CLASS_NAMES,
    NUM_CLASSES,
    RANDOM_SEED,
    TRAIN_RATIO,
    VAL_RATIO,
    TEST_RATIO,
    SPLIT_SEARCH_TRIALS,
)


SPLITS = (
    "train",
    "val",
    "test"
)

TARGET_RATIOS = {
    "train": TRAIN_RATIO,
    "val": VAL_RATIO,
    "test": TEST_RATIO,
}

FRAME_NAME_RE = re.compile(
    r"^(?P<source>.+)_frame_(?P<frame>\d+)$"
)


def validate_ratios() -> None:

    total = (
        TRAIN_RATIO
        + VAL_RATIO
        + TEST_RATIO
    )

    if abs(total - 1.0) > 1e-9:

        raise ValueError(
            "TRAIN_RATIO + VAL_RATIO + "
            "TEST_RATIO must equal 1.0, "
            f"got {total}"
        )

    if min(
        TRAIN_RATIO,
        VAL_RATIO,
        TEST_RATIO
    ) <= 0:

        raise ValueError(
            "All split ratios "
            "must be greater than 0."
        )


def load_source_metadata() -> Dict[str, str]:
    """
    Return:

        filename -> source_group

    If metadata.csv contains source_group,
    it has priority over source_video.

    This allows several video clips captured
    from the same route/session to be grouped
    together and assigned to the same split.
    """

    mapping: Dict[str, str] = {}

    if not SOURCE_METADATA_CSV.exists():

        print(
            "[Warning] Source metadata "
            f"not found: {SOURCE_METADATA_CSV}. "
            "Will fall back to parsing filenames."
        )

        return mapping

    with open(
        SOURCE_METADATA_CSV,
        "r",
        newline="",
        encoding="utf-8"
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            filename = (
                row.get("filename")
                or ""
            ).strip()

            source_group = (
                row.get("source_group")
                or ""
            ).strip()

            source_video = (
                row.get("source_video")
                or ""
            ).strip()

            group_id = (
                source_group
                or source_video
            )

            if filename and group_id:

                mapping[filename] = (
                    group_id
                )

    print(
        "[Metadata] Loaded source groups "
        f"for {len(mapping)} raw frames"
    )

    return mapping


def resolve_source_group(
    image_path: Path,
    metadata: Dict[str, str]
) -> Tuple[str, str]:
    """
    Resolve the independent sampling unit
    for one image.

    Priority:

    1. metadata.csv source_group
       or source_video
    2. filename pattern:
       <source>_frame_<number>
    3. standalone image:
       treat the image itself as an
       independent source group
    """

    if image_path.name in metadata:

        return (
            metadata[image_path.name],
            "metadata"
        )

    match = FRAME_NAME_RE.match(
        image_path.stem
    )

    if match:

        return (
            match.group("source"),
            "filename"
        )

    # This is appropriate for truly
    # independent photographs.
    #
    # If several images actually come from
    # the same recording/session/location,
    # they should share the same source_group
    # in metadata.csv.
    return (
        f"standalone::{image_path.stem}",
        "standalone"
    )


def load_class_ids(
    label_path: Path
) -> List[int]:

    if not label_path.exists():

        return []

    class_ids: List[int] = []

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
                    "Malformed YOLO label: "
                    f"{label_path}:"
                    f"{line_no}: "
                    f"{line.strip()}"
                )

            cls_id = int(parts[0])

            if (
                cls_id < 0
                or cls_id >= NUM_CLASSES
            ):

                raise ValueError(
                    f"Invalid class id "
                    f"{cls_id} in "
                    f"{label_path}:"
                    f"{line_no}; "
                    f"expected "
                    f"0..{NUM_CLASSES - 1}"
                )

            class_ids.append(
                cls_id
            )

    return class_ids


def build_groups(
    image_paths: List[Path],
    metadata: Dict[str, str]
):

    groups = defaultdict(
        lambda: {
            "images": [],
            "class_counts": Counter(),
            "source_resolution": Counter(),
        }
    )

    standalone_count = 0

    for image_path in image_paths:

        (
            source_group,
            resolution_method
        ) = resolve_source_group(
            image_path,
            metadata
        )

        label_path = (
            YOLO_LABEL_DIR
            / f"{image_path.stem}.txt"
        )

        class_ids = load_class_ids(
            label_path
        )

        groups[
            source_group
        ]["images"].append(
            image_path
        )

        groups[
            source_group
        ]["class_counts"].update(
            class_ids
        )

        groups[
            source_group
        ]["source_resolution"][
            resolution_method
        ] += 1

        if (
            resolution_method
            == "standalone"
        ):

            standalone_count += 1

    if standalone_count:

        print(
            f"[Warning] {standalone_count} "
            "cleaned images could not be "
            "linked to a source video. "
            "They are treated as independent "
            "standalone groups. "
            "If any of them are adjacent frames "
            "or belong to the same recording "
            "session, assign them the same "
            "source_group in metadata.csv."
        )

    return dict(groups)


def compute_group_partition_sizes(
    num_groups: int
) -> Dict[str, int]:

    if num_groups < 3:

        raise ValueError(
            "At least 3 independent source "
            "groups are required for "
            "train/val/test. "
            f"Only {num_groups} groups "
            "were found."
        )

    n_val = max(
        1,
        int(
            round(
                num_groups
                * VAL_RATIO
            )
        )
    )

    n_test = max(
        1,
        int(
            round(
                num_groups
                * TEST_RATIO
            )
        )
    )

    n_train = (
        num_groups
        - n_val
        - n_test
    )

    if n_train < 1:

        n_val = 1
        n_test = 1

        n_train = (
            num_groups - 2
        )

    return {
        "train": n_train,
        "val": n_val,
        "test": n_test,
    }


def summarize_assignment(
    assignment: Dict[
        str,
        List[str]
    ],
    groups: dict
):

    image_counts = Counter()

    class_counts = {
        split: Counter()
        for split in SPLITS
    }

    for split in SPLITS:

        for group_name in (
            assignment[split]
        ):

            group = groups[
                group_name
            ]

            image_counts[
                split
            ] += len(
                group["images"]
            )

            class_counts[
                split
            ].update(
                group["class_counts"]
            )

    return (
        image_counts,
        class_counts
    )


def assignment_score(
    assignment: Dict[
        str,
        List[str]
    ],
    groups: dict
) -> float:
    """
    Lower score is better.

    Source-group isolation is mandatory.

    Among valid group-level partitions,
    this score searches for a partition
    whose image ratio and per-class box
    distribution are close to the
    requested train/val/test ratios.
    """

    (
        image_counts,
        class_counts
    ) = summarize_assignment(
        assignment,
        groups
    )

    total_images = sum(
        image_counts.values()
    )

    image_ratio_error = 0.0

    for split in SPLITS:

        if total_images:

            actual = (
                image_counts[split]
                / total_images
            )

        else:

            actual = 0.0

        image_ratio_error += abs(
            actual
            - TARGET_RATIOS[split]
        )

    total_class_counts = Counter()

    for split in SPLITS:

        total_class_counts.update(
            class_counts[split]
        )

    class_ratio_error = 0.0
    contributing_classes = 0

    for cls_id in range(
        NUM_CLASSES
    ):

        total = (
            total_class_counts[
                cls_id
            ]
        )

        if total <= 0:

            continue

        contributing_classes += 1

        for split in SPLITS:

            actual = (
                class_counts[
                    split
                ][cls_id]
                / total
            )

            class_ratio_error += abs(
                actual
                - TARGET_RATIOS[
                    split
                ]
            )

    if contributing_classes:

        class_ratio_error /= (
            contributing_classes
        )

    # If a class is represented in at least
    # three independent source groups,
    # it is usually possible to expose that
    # class to all three splits.
    missing_class_penalty = 0.0

    for cls_id in range(
        NUM_CLASSES
    ):

        groups_with_class = sum(
            1
            for group
            in groups.values()
            if group[
                "class_counts"
            ][cls_id] > 0
        )

        if groups_with_class >= 3:

            for split in SPLITS:

                if (
                    class_counts[
                        split
                    ][cls_id]
                    == 0
                ):

                    missing_class_penalty += (
                        0.25
                    )

    return (
        image_ratio_error
        + 0.5
        * class_ratio_error
        + missing_class_penalty
    )


def find_best_group_split(
    groups: dict
) -> Dict[
    str,
    List[str]
]:

    group_names = sorted(
        groups.keys()
    )

    sizes = (
        compute_group_partition_sizes(
            len(group_names)
        )
    )

    rng = random.Random(
        RANDOM_SEED
    )

    best_assignment = None
    best_score = float("inf")

    trials = max(
        1,
        SPLIT_SEARCH_TRIALS
    )

    for _ in range(trials):

        shuffled = (
            group_names[:]
        )

        rng.shuffle(
            shuffled
        )

        train_end = (
            sizes["train"]
        )

        val_end = (
            train_end
            + sizes["val"]
        )

        assignment = {
            "train":
                shuffled[
                    :train_end
                ],
            "val":
                shuffled[
                    train_end:
                    val_end
                ],
            "test":
                shuffled[
                    val_end:
                ],
        }

        score = assignment_score(
            assignment,
            groups
        )

        if score < best_score:

            best_score = score
            best_assignment = (
                assignment
            )

    assert (
        best_assignment
        is not None
    )

    return best_assignment


def reset_dataset_split_dirs():

    for split in SPLITS:

        shutil.rmtree(
            DATASET_DIR
            / "images"
            / split,
            ignore_errors=True
        )

        shutil.rmtree(
            DATASET_DIR
            / "labels"
            / split,
            ignore_errors=True
        )

        (
            DATASET_DIR
            / "images"
            / split
        ).mkdir(
            parents=True,
            exist_ok=True
        )

        (
            DATASET_DIR
            / "labels"
            / split
        ).mkdir(
            parents=True,
            exist_ok=True
        )


def copy_originals_and_build_manifest(
    assignment: dict,
    groups: dict
) -> List[dict]:

    manifest_rows = []

    for split in SPLITS:

        image_dir = (
            DATASET_DIR
            / "images"
            / split
        )

        label_dir = (
            DATASET_DIR
            / "labels"
            / split
        )

        images_to_copy = []

        for group_name in (
            assignment[split]
        ):

            for image_path in (
                groups[
                    group_name
                ]["images"]
            ):

                images_to_copy.append(
                    (
                        group_name,
                        image_path
                    )
                )

        for (
            group_name,
            image_path
        ) in tqdm(
            images_to_copy,
            desc=(
                f"Copying "
                f"{split} originals"
            )
        ):

            dst_image = (
                image_dir
                / image_path.name
            )

            shutil.copy2(
                image_path,
                dst_image
            )

            src_label = (
                YOLO_LABEL_DIR
                / (
                    f"{image_path.stem}"
                    ".txt"
                )
            )

            dst_label = (
                label_dir
                / (
                    f"{image_path.stem}"
                    ".txt"
                )
            )

            if src_label.exists():

                shutil.copy2(
                    src_label,
                    dst_label
                )

            else:

                # No label means valid
                # negative sample.
                dst_label.write_text(
                    "",
                    encoding="utf-8"
                )

            manifest_rows.append({
                "filename":
                    image_path.name,

                "source_group":
                    group_name,

                "split":
                    split,

                "is_augmented":
                    "false",

                "parent_image":
                    "",
            })

    return manifest_rows


def write_manifest(
    rows: List[dict]
):

    SPLIT_MANIFEST_CSV.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    fieldnames = [
        "filename",
        "source_group",
        "split",
        "is_augmented",
        "parent_image",
    ]

    with open(
        SPLIT_MANIFEST_CSV,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(rows)


def write_data_yaml() -> Path:

    data_yaml = {
        "path":
            str(
                DATASET_DIR.resolve()
            ),

        "train":
            "images/train",

        "val":
            "images/val",

        "test":
            "images/test",

        "nc":
            NUM_CLASSES,

        "names":
            CLASS_NAMES,
    }

    yaml_path = (
        DATASET_DIR
        / "data.yaml"
    )

    with open(
        yaml_path,
        "w",
        encoding="utf-8"
    ) as f:

        yaml.safe_dump(
            data_yaml,
            f,
            allow_unicode=True,
            sort_keys=False
        )

    return yaml_path


def write_split_report(
    assignment: dict,
    groups: dict
):

    (
        image_counts,
        class_counts
    ) = summarize_assignment(
        assignment,
        groups
    )

    total_images = sum(
        image_counts.values()
    )

    report = {
        "strategy":
            "grouped_by_source_group_before_augmentation",

        "seed":
            RANDOM_SEED,

        "search_trials":
            SPLIT_SEARCH_TRIALS,

        "target_ratios":
            TARGET_RATIOS,

        "num_source_groups":
            len(groups),

        "splits": {},
    }

    for split in SPLITS:

        report[
            "splits"
        ][split] = {

            "original_image_count":
                image_counts[
                    split
                ],

            "actual_image_ratio":
                round(
                    image_counts[
                        split
                    ]
                    / total_images,
                    6
                ),

            "source_group_count":
                len(
                    assignment[
                        split
                    ]
                ),

            "source_groups":
                sorted(
                    assignment[
                        split
                    ]
                ),

            "box_distribution": {
                CLASS_NAMES[
                    cls_id
                ]:
                    class_counts[
                        split
                    ][cls_id]

                for cls_id
                in range(
                    NUM_CLASSES
                )
            },
        }

    SPLIT_REPORT_JSON.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        SPLIT_REPORT_JSON,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            report,
            f,
            ensure_ascii=False,
            indent=2
        )


def assert_no_source_leakage(
    assignment: dict
):

    seen = {}

    for split in SPLITS:

        for group_name in (
            assignment[split]
        ):

            if group_name in seen:

                raise RuntimeError(
                    "Source leakage detected: "
                    f"group '{group_name}' "
                    "appears in both "
                    f"{seen[group_name]} "
                    f"and {split}."
                )

            seen[
                group_name
            ] = split


def main():

    validate_ratios()

    image_paths = sorted(
        CLEAN_IMAGE_DIR.glob(
            "*.jpg"
        )
    )

    if not image_paths:

        print(
            "[Error] No cleaned images "
            f"found in {CLEAN_IMAGE_DIR}"
        )

        print(
            "Please run the cleaning step "
            "before dataset splitting."
        )

        return

    metadata = (
        load_source_metadata()
    )

    groups = build_groups(
        image_paths,
        metadata
    )

    print(
        "[Group Split] "
        f"{len(image_paths)} cleaned images "
        f"in {len(groups)} independent "
        "source groups"
    )

    assignment = (
        find_best_group_split(
            groups
        )
    )

    assert_no_source_leakage(
        assignment
    )

    reset_dataset_split_dirs()

    manifest_rows = (
        copy_originals_and_build_manifest(
            assignment,
            groups
        )
    )

    write_manifest(
        manifest_rows
    )

    yaml_path = (
        write_data_yaml()
    )

    write_split_report(
        assignment,
        groups
    )

    (
        image_counts,
        _
    ) = summarize_assignment(
        assignment,
        groups
    )

    total = sum(
        image_counts.values()
    )

    print(
        "\n"
        "[Split Done - "
        "ORIGINAL samples only]"
    )

    for split in SPLITS:

        ratio = (
            image_counts[
                split
            ]
            / total
            if total
            else 0.0
        )

        print(
            f"  {split:5s}: "
            f"{image_counts[split]:4d} "
            "images | "
            f"{len(assignment[split]):3d} "
            "source groups | "
            f"ratio={ratio:.3f}"
        )

    print(
        f"  data.yaml: "
        f"{yaml_path}"
    )

    print(
        f"  manifest:  "
        f"{SPLIT_MANIFEST_CSV}"
    )

    print(
        f"  report:    "
        f"{SPLIT_REPORT_JSON}"
    )

    print(
        "\n"
        "[Leakage Check] PASS: "
        "no source group appears "
        "in multiple splits."
    )

    print(
        "[Next] Run "
        "05_train_augmentation.py. "
        "It will augment TRAIN only."
    )


if __name__ == "__main__":
    main()
