"""
training/07_evaluate_model.py
在独立测试集上评估：mAP、Precision、Recall、混淆矩阵、BadCase提取
"""

import json
import cv2
import numpy as np
from pathlib import Path
from collections import defaultdict
from tqdm import tqdm

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import (DATASET_DIR, TRAINED_MODEL_DIR, BAD_CASE_DIR,
                    VISUAL_DIR, CLASS_NAMES, INFERENCE_CONF, INFERENCE_IOU)

from ultralytics import YOLO


def evaluate_test_set():
    """在测试集上执行批量评估"""
    model_path = TRAINED_MODEL_DIR / "blind_navigation_train" / "weights" / "best.pt"
    if not model_path.exists():
        print(f"[错误] 未找到模型: {model_path}")
        return

    model = YOLO(str(model_path))
    test_img_dir = DATASET_DIR / "images" / "test"

    if not test_img_dir.exists():
        print("[错误] 未找到测试集")
        return

    # 使用YOLO内置验证（最准确，自动计算mAP）
    metrics = model.val(
        data=str(DATASET_DIR / "data.yaml"),
        split="test",
        imgsz=640,
        conf=INFERENCE_CONF,
        iou=INFERENCE_IOU,
        device="0"
    )

    print("\n[测试集评估结果]")
    print(f"  mAP@0.5:     {metrics.box.map50:.4f}")
    print(f"  mAP@0.5:0.95: {metrics.box.map:.4f}")
    print(f"  Precision:   {metrics.box.mp:.4f}")
    print(f"  Recall:      {metrics.box.mr:.4f}")

    # 保存指标
    report = {
        "mAP50": float(metrics.box.map50),
        "mAP50_95": float(metrics.box.map),
        "precision": float(metrics.box.mp),
        "recall": float(metrics.box.mr),
        "class_ap50": {name: float(ap) for name, ap in zip(CLASS_NAMES, metrics.box.ap50)}
    }
    report_path = Path(model_path).parent / "test_metrics.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"  详细报告已保存: {report_path}")

    return model


def extract_bad_cases(model, max_cases=50):
    """
    提取预测错误的案例：
    - 假阳性：预测出目标但GT中没有（或IoU<0.5）
    - 假阴性：GT中有但未被检出
    - 分类错误：检出但类别错误
    """
    test_img_dir = DATASET_DIR / "images" / "test"
    test_lbl_dir = DATASET_DIR / "labels" / "test"
    BAD_CASE_DIR.mkdir(parents=True, exist_ok=True)

    bad_cases = []
    img_files = list(test_img_dir.glob("*.jpg"))

    print(f"\n[BadCase分析] 扫描 {len(img_files)} 张测试图片...")

    for img_path in tqdm(img_files[:200], desc="BadCase扫描"):  # 限制数量加速
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        h, w = img.shape[:2]

        # 读取GT
        gt_path = test_lbl_dir / (img_path.stem + ".txt")
        gt_boxes = []
        if gt_path.exists():
            with open(gt_path, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 5:
                        cls_id = int(parts[0])
                        cx, cy, bw, bh = map(float, parts[1:])
                        x1 = int((cx - bw/2) * w)
                        y1 = int((cy - bh/2) * h)
                        x2 = int((cx + bw/2) * w)
                        y2 = int((cy + bh/2) * h)
                        gt_boxes.append([cls_id, x1, y1, x2, y2])

        # 预测
        results = model(img, conf=INFERENCE_CONF, iou=INFERENCE_IOU, verbose=False)
        pred_boxes = []
        if len(results) > 0:
            boxes = results[0].boxes
            if boxes is not None:
                for box in boxes:
                    cls_id = int(box.cls)
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = float(box.conf)
                    pred_boxes.append([cls_id, x1, y1, x2, y2, conf])

        # 匹配逻辑：为每个GT找最佳预测
        matched_pred = set()
        fn_count = 0
        fp_count = 0
        cls_error = 0

        for gt in gt_boxes:
            gt_cls, gx1, gy1, gx2, gy2 = gt
            best_iou = 0
            best_idx = -1

            for idx, pred in enumerate(pred_boxes):
                if idx in matched_pred:
                    continue
                p_cls, px1, py1, px2, py2, p_conf = pred
                # 计算IoU
                inter_x1 = max(gx1, px1)
                inter_y1 = max(gy1, py1)
                inter_x2 = min(gx2, px2)
                inter_y2 = min(gy2, py2)
                if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
                    continue
                inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
                gt_area = (gx2 - gx1) * (gy2 - gy1)
                pred_area = (px2 - px1) * (py2 - py1)
                union = gt_area + pred_area - inter_area
                iou = inter_area / union if union > 0 else 0

                if iou > best_iou:
                    best_iou = iou
                    best_idx = idx

            if best_iou < 0.5:
                fn_count += 1  # 漏检
            else:
                matched_pred.add(best_idx)
                if pred_boxes[best_idx][0] != gt_cls:
                    cls_error += 1  # 分类错误

        # 未匹配的预测视为假阳性
        for idx, pred in enumerate(pred_boxes):
            if idx not in matched_pred:
                fp_count += 1

        if fn_count > 0 or fp_count > 0 or cls_error > 0:
            # 绘制对比图
            vis = img.copy()
            # GT: 绿色实线
            for gt in gt_boxes:
                c, x1, y1, x2, y2 = gt
                cv2.rectangle(vis, (x1,y1), (x2,y2), (0,255,0), 2)
                cv2.putText(vis, f"GT:{CLASS_NAMES[c]}", (x1, y1-5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)

            # Pred: 红色虚线（漏检）或蓝色实线
            for idx, pred in enumerate(pred_boxes):
                c, x1, y1, x2, y2, conf = pred
                color = (255,0,0) if idx in matched_pred else (0,0,255)
                cv2.rectangle(vis, (x1,y1), (x2,y2), color, 2)
                label = f"Pred:{CLASS_NAMES[c]} {conf:.2f}"
                cv2.putText(vis, label, (x1, y2+15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            case_type = []
            if fn_count: case_type.append(f"FN{fn_count}")
            if fp_count: case_type.append(f"FP{fp_count}")
            if cls_error: case_type.append(f"CE{cls_error}")

            save_name = f"{img_path.stem}_{'+'.join(case_type)}.jpg"
            cv2.imwrite(str(BAD_CASE_DIR / save_name), vis)
            bad_cases.append({
                "image": img_path.name,
                "fn": fn_count,
                "fp": fp_count,
                "cls_error": cls_error
            })

            if len(bad_cases) >= max_cases:
                break

    # 保存BadCase清单
    summary_path = BAD_CASE_DIR / "bad_case_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(bad_cases, f, indent=2)

    print(f"[完成] 提取 {len(bad_cases)} 个错误案例，保存至: {BAD_CASE_DIR}")


def main():
    model = evaluate_test_set()
    if model:
        extract_bad_cases(model, max_cases=50)


if __name__ == "__main__":
    main()