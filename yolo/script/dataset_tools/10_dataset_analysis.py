"""
dataset_tools/10_dataset_analysis.py
数据集分布可视化：类别分布、边界框大小分布、宽高比分布
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from collections import Counter

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import (DATASET_DIR, CLASS_NAMES, VISUAL_DIR)


def analyze_split(split: str):
    """分析某个split的标注分布"""
    label_dir = DATASET_DIR / "labels" / split
    if not label_dir.exists():
        return None

    cls_counts = Counter()
    box_areas = {name: [] for name in CLASS_NAMES}
    box_ratios = {name: [] for name in CLASS_NAMES}

    for txt_file in label_dir.glob("*.txt"):
        with open(txt_file, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) != 5:
                    continue
                cls_id = int(parts[0])
                w, h = float(parts[3]), float(parts[4])
                cls_name = CLASS_NAMES[cls_id]

                cls_counts[cls_name] += 1
                box_areas[cls_name].append(w * h)  # 归一化面积
                box_ratios[cls_name].append(w / h if h > 0 else 0)

    return {
        "cls_counts": cls_counts,
        "box_areas": box_areas,
        "box_ratios": box_ratios,
        "total_images": len(list((DATASET_DIR / "images" / split).glob("*.jpg")))
    }


def plot_distribution(train_data, val_data, test_data):
    """绘制分布对比图"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 1. 类别分布
    ax = axes[0, 0]
    x = np.arange(len(CLASS_NAMES))
    width = 0.25
    for i, (data, name, color) in enumerate([
        (train_data, 'Train', '#3498db'),
        (val_data, 'Val', '#2ecc71'),
        (test_data, 'Test', '#e74c3c')
    ]):
        counts = [data["cls_counts"].get(c, 0) for c in CLASS_NAMES]
        ax.bar(x + (i-1)*width, counts, width, label=name, color=color, alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(CLASS_NAMES, rotation=15, ha='right')
    ax.set_ylabel("Box Count")
    ax.set_title("Class Distribution Across Splits")
    ax.legend()

    # 2. 边界框面积分布（训练集）
    ax = axes[0, 1]
    for cls_name in CLASS_NAMES:
        areas = train_data["box_areas"][cls_name]
        if areas:
            ax.hist(areas, bins=30, alpha=0.5, label=cls_name, range=(0, 0.1))
    ax.set_xlabel("Normalized Box Area")
    ax.set_ylabel("Frequency")
    ax.set_title("Training Set Bounding Box Area Distribution")
    ax.legend()

    # 3. 宽高比分布（训练集）
    ax = axes[1, 0]
    for cls_name in CLASS_NAMES:
        ratios = [r for r in train_data["box_ratios"][cls_name] if 0 < r < 5]
        if ratios:
            ax.hist(ratios, bins=30, alpha=0.5, label=cls_name, range=(0, 3))
    ax.set_xlabel("Width / Height Ratio")
    ax.set_ylabel("Frequency")
    ax.set_title("Training Set Aspect Ratio Distribution")
    ax.legend()

    # 4. 样本数量汇总
    ax = axes[1, 1]
    splits = ['Train', 'Val', 'Test']
    totals = [train_data["total_images"], val_data["total_images"], test_data["total_images"]]
    colors = ['#3498db', '#2ecc71', '#e74c3c']
    bars = ax.bar(splits, totals, color=colors, alpha=0.8, edgecolor='black')
    ax.set_ylabel("Image Count")
    ax.set_title("Total Images per Split")
    for bar, total in zip(bars, totals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                str(total), ha='center', va='bottom', fontsize=11)

    plt.tight_layout()
    save_path = VISUAL_DIR / "dataset_analysis.png"
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"[图表已保存] {save_path}")
    plt.close()


def main():
    print("[分析数据集分布]...")
    train_data = analyze_split("train")
    val_data = analyze_split("val")
    test_data = analyze_split("test")

    if train_data is None:
        print("[错误] 未找到数据集，请先运行 05_dataset_split.py")
        return

    plot_distribution(train_data, val_data, test_data)

    # 输出文字摘要
    print("\n[数据集统计摘要]")
    for split, data in [("Train", train_data), ("Val", val_data), ("Test", test_data)]:
        print(f"\n{split}: {data['total_images']} 张图片")
        for cls in CLASS_NAMES:
            count = data['cls_counts'].get(cls, 0)
            avg_area = np.mean(data['box_areas'][cls]) if data['box_areas'][cls] else 0
            print(f"  {cls}: {count} 个框, 平均面积(归一化): {avg_area:.4f}")


if __name__ == "__main__":
    main()