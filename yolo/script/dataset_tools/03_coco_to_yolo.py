"""
dataset_tools/03_coco_to_yolo.py
将 LabelStudio/CVAT 导出的 COCO JSON 转换为 YOLO txt 格式
并执行标注质量校验：越界检查、空标注过滤、非法类别检查、可视化复核
"""

import json
import cv2
import numpy as np
from pathlib import Path
from collections import defaultdict
from tqdm import tqdm

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import (COCO_ANNOTATION_FILE, CLEAN_IMAGE_DIR, YOLO_LABEL_DIR,
                    VISUAL_DIR, CLASS_NAMES, NUM_CLASSES)


def coco_to_yolo_bbox(coco_bbox: list, img_w: int, img_h: int) -> tuple:
    """
    COCO bbox: [x, y, width, height]（左上角，绝对像素）
    YOLO bbox: (cx, cy, w, h)（中心点，归一化0~1）
    """
    x, y, w, h = coco_bbox
    # 边界保护
    x = max(0, x)
    y = max(0, y)
    w = min(w, img_w - x)
    h = min(h, img_h - y)

    cx = (x + w / 2) / img_w
    cy = (y + h / 2) / img_h
    nw = w / img_w
    nh = h / img_h

    # 严格截断到 [0,1]
    cx = np.clip(cx, 0.0, 1.0)
    cy = np.clip(cy, 0.0, 1.0)
    nw = np.clip(nw, 0.0, 1.0)
    nh = np.clip(nh, 0.0, 1.0)

    # 若框超出图像则修正中心点
    cx = min(max(cx, nw/2), 1 - nw/2)
    cy = min(max(cy, nh/2), 1 - nh/2)

    return cx, cy, nw, nh


def convert_and_validate():
    if not COCO_ANNOTATION_FILE.exists():
        print(f"[错误] 未找到 COCO 标注文件: {COCO_ANNOTATION_FILE}")
        print("请从 LabelStudio 导出 COCO 格式并放置到该路径")
        return

    with open(COCO_ANNOTATION_FILE, 'r', encoding='utf-8') as f:
        coco_data = json.load(f)

    # 建立 image_id 到文件名和尺寸的映射
    image_info = {}
    for img in coco_data['images']:
        image_info[img['id']] = {
            'file_name': img['file_name'],
            'width': img['width'],
            'height': img['height']
        }

    # 建立 category_id 到 class_index 的映射
    # 假设 COCO 中的 category 顺序与 CLASS_NAMES 一致，或按 name 匹配
    cat_to_cls = {}
    for cat in coco_data['categories']:
        cat_name = cat['name']
        if cat_name in CLASS_NAMES:
            cat_to_cls[cat['id']] = CLASS_NAMES.index(cat_name)
        else:
            print(f"[警告] COCO 中存在未定义类别: {cat_name}，已跳过")

    # 按 image_id 聚合标注
    annotations_by_image = defaultdict(list)
    for ann in coco_data['annotations']:
        img_id = ann['image_id']
        annotations_by_image[img_id].append(ann)

    # 质检统计
    stats = {
        "total_images": len(image_info),
        "annotated_images": 0,
        "empty_annotations": 0,
        "total_boxes": 0,
        "rejected_boxes": 0,
        "rejection_reasons": defaultdict(int)
    }

    YOLO_LABEL_DIR.mkdir(parents=True, exist_ok=True)
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)

    # 随机选10%做可视化复核
    all_image_ids = list(image_info.keys())
    visual_sample_ids = set(np.random.choice(
        all_image_ids,
        size=max(1, int(len(all_image_ids) * 0.1)),
        replace=False
    ))

    print(f"[转换] 共 {len(all_image_ids)} 张图片，{sum(len(v) for v in annotations_by_image.values())} 个标注")

    for img_id, info in tqdm(image_info.items(), desc="转换进度"):
        img_name = info['file_name']
        img_w = info['width']
        img_h = info['height']

        # 查找对应图片（支持带后缀或不带后缀匹配）
        img_path = None
        for ext in ['.jpg', '.jpeg', '.png']:
            candidate = CLEAN_IMAGE_DIR / (Path(img_name).stem + ext)
            if candidate.exists():
                img_path = candidate
                break

        if img_path is None:
            stats["rejection_reasons"]["image_not_found"] += 1
            continue

        anns = annotations_by_image.get(img_id, [])
        if not anns:
            stats["empty_annotations"] += 1
            # 负样本也需要空txt文件
            label_path = YOLO_LABEL_DIR / (Path(img_name).stem + ".txt")
            label_path.write_text("")
            continue

        yolo_lines = []
        valid_boxes = 0

        for ann in anns:
            cat_id = ann['category_id']
            if cat_id not in cat_to_cls:
                stats["rejected_boxes"] += 1
                stats["rejection_reasons"]["unknown_category"] += 1
                continue

            cls_idx = cat_to_cls[cat_id]
            coco_bbox = ann['bbox']  # [x, y, w, h]

            # 过滤异常框
            if coco_bbox[2] <= 0 or coco_bbox[3] <= 0:
                stats["rejected_boxes"] += 1
                stats["rejection_reasons"]["zero_size_box"] += 1
                continue

            cx, cy, nw, nh = coco_to_yolo_bbox(coco_bbox, img_w, img_h)

            # 进一步校验
            if nw < 0.001 or nh < 0.001:
                stats["rejected_boxes"] += 1
                stats["rejection_reasons"]["too_small_box"] += 1
                continue
            if cls_idx < 0 or cls_idx >= NUM_CLASSES:
                stats["rejected_boxes"] += 1
                stats["rejection_reasons"]["invalid_class_id"] += 1
                continue

            yolo_lines.append(f"{cls_idx} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")
            valid_boxes += 1

        # 写入YOLO标注文件
        label_file = YOLO_LABEL_DIR / (Path(img_name).stem + ".txt")
        label_file.write_text("\n".join(yolo_lines), encoding='utf-8')

        stats["annotated_images"] += 1
        stats["total_boxes"] += valid_boxes

        # 可视化复核（10%样本）
        if img_id in visual_sample_ids and img_path:
            img_cv = cv2.imread(str(img_path))
            if img_cv is not None:
                h, w = img_cv.shape[:2]
                for line in yolo_lines:
                    parts = line.strip().split()
                    cls_idx = int(parts[0])
                    cx, cy, nw, nh = map(float, parts[1:])
                    px_cx = int(cx * w)
                    px_cy = int(cy * h)
                    px_w = int(nw * w)
                    px_h = int(nh * h)
                    x1 = int(px_cx - px_w / 2)
                    y1 = int(px_cy - px_h / 2)
                    x2 = int(px_cx + px_w / 2)
                    y2 = int(px_cy + px_h / 2)

                    color = [(0,255,0), (0,0,255), (255,0,0)][cls_idx % 3]
                    cv2.rectangle(img_cv, (x1,y1), (x2,y2), color, 2)
                    cv2.putText(img_cv, CLASS_NAMES[cls_idx], (x1, y1-5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

                vis_path = VISUAL_DIR / f"check_{img_path.name}"
                cv2.imwrite(str(vis_path), img_cv)

    # 输出质检报告
    print(f"\n[质检报告]")
    print(f"  总图片数: {stats['total_images']}")
    print(f"  有标注图片: {stats['annotated_images']}")
    print(f"  空标注(负样本): {stats['empty_annotations']}")
    print(f"  有效边界框: {stats['total_boxes']}")
    print(f"  拒绝边界框: {stats['rejected_boxes']}")
    print(f"  拒绝原因分布: {dict(stats['rejection_reasons'])}")
    print(f"  YOLO标注已保存至: {YOLO_LABEL_DIR}")
    print(f"  可视化复核样本已保存至: {VISUAL_DIR}")


if __name__ == "__main__":
    convert_and_validate()