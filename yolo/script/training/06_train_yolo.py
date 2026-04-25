import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from ultralytics import YOLO
from config import (DATASET_DIR, TRAINED_MODEL_DIR, PRETRAINED_WEIGHTS,
                    TRAIN_EPOCHS, TRAIN_BATCH, TRAIN_IMGSZ,
                    TRAIN_LR0, TRAIN_LRF, TRAIN_PATIENCE,
                    TRAIN_DEVICE, FREEZE_BACKBONE_EPOCHS)


def main():
    data_yaml = DATASET_DIR / "data.yaml"
    if not data_yaml.exists():
        print(f"[Error] {data_yaml} not found, please run dataset_tools/05_dataset_split.py first")
        return

    print(f"[Loading model] Using pretrained weights: {PRETRAINED_WEIGHTS}")
    model = YOLO(PRETRAINED_WEIGHTS)

    print(f"[Start Training] Dataset: {data_yaml}")
    print(f"  Epochs: {TRAIN_EPOCHS} | Batch: {TRAIN_BATCH} | ImageSize: {TRAIN_IMGSZ}")
    print(f"  Device: {TRAIN_DEVICE} | FreezeEpochs: {FREEZE_BACKBONE_EPOCHS}")

    results = model.train(
        data=str(data_yaml),
        epochs=TRAIN_EPOCHS,
        batch=TRAIN_BATCH,
        imgsz=TRAIN_IMGSZ,
        lr0=TRAIN_LR0,
        lrf=TRAIN_LRF,
        patience=TRAIN_PATIENCE,
        device=TRAIN_DEVICE,
        freeze=FREEZE_BACKBONE_EPOCHS,
        optimizer="SGD",
        cos_lr=True,
        warmup_epochs=3,
        augment=True,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=5.0,
        translate=0.1,
        scale=0.5,
        shear=2.0,
        flipud=0.0,
        fliplr=0.5,
        mosaic=1.0,
        mixup=0.1,
        copy_paste=0.1,
        name="blind_navigation_train",
        project=str(TRAINED_MODEL_DIR),
        exist_ok=True,
        verbose=True,
        seed=42
    )

    best_path = TRAINED_MODEL_DIR / "blind_navigation_train" / "weights" / "best.pt"
    print(f"\n[Training Done] Best model: {best_path}")
    print(f"  Val mAP50: {results.results_dict.get('metrics/mAP50(B)', 'N/A')}")
    print(f"  Val mAP50-95: {results.results_dict.get('metrics/mAP50-95(B)', 'N/A')}")


if __name__ == "__main__":
    main()
