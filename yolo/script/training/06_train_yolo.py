"""
training/06_train_yolo.py
YOLOv8 训练脚本：支持迁移学习、冻结骨干、余弦退火、早停、断点续训
"""

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
        print(f"[错误] 未找到 {data_yaml}，请先运行 dataset_tools/05_dataset_split.py")
        return

    # 加载预训练模型（自动下载 yolov8s.pt 到当前目录）
    print(f"[加载模型] 使用预训练权重: {PRETRAINED_WEIGHTS}")
    model = YOLO(PRETRAINED_WEIGHTS)

    # 训练参数
    print(f"[开始训练] 数据集: {data_yaml}")
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
        freeze=FREEZE_BACKBONE_EPOCHS,  # 前N轮冻结骨干
        optimizer="SGD",                # YOLOv8默认，也可改为 "AdamW"
        cos_lr=True,                    # 余弦退火
        warmup_epochs=3,                # Warm-up轮数
        augment=True,                   # 启用内置在线增强（Mosaic, MixUp等）
        hsv_h=0.015,                    # HSV色调增强幅度
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=5.0,                    # 在线旋转角度（度）
        translate=0.1,
        scale=0.5,
        shear=2.0,
        flipud=0.0,                     # 上下翻转概率（盲道场景关闭）
        fliplr=0.5,                     # 左右翻转概率
        mosaic=1.0,                     # Mosaic增强概率
        mixup=0.1,                      # MixUp增强概率
        copy_paste=0.1,                 # 复制粘贴增强
        name="blind_navigation_train",
        project=str(TRAINED_MODEL_DIR),
        exist_ok=True,
        verbose=True,
        seed=42
    )

    # 输出最佳模型路径
    best_path = TRAINED_MODEL_DIR / "blind_navigation_train" / "weights" / "best.pt"
    print(f"\n[训练完成] 最优模型: {best_path}")
    print(f"  验证集 mAP50: {results.results_dict.get('metrics/mAP50(B)', 'N/A')}")
    print(f"  验证集 mAP50-95: {results.results_dict.get('metrics/mAP50-95(B)', 'N/A')}")


if __name__ == "__main__":
    main()