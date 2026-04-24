"""
dataset_tools/02_data_cleaning.py
清晰度检测 + 曝光检测 + 尺寸标准化 + 清洗报告生成
"""

import json
import cv2
import numpy as np
from pathlib import Path
from PIL import Image
from tqdm import tqdm

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import (RAW_IMAGE_DIR, CLEAN_IMAGE_DIR, TARGET_IMAGE_SIZE,
                    MIN_BLUR_THRESHOLD, MAX_OVEREXPOSE_RATIO, MAX_UNDEREXPOSE_RATIO,
                    REPORT_DIR)


def compute_blur_laplacian(image: np.ndarray) -> float:
    """
    使用拉普拉斯算子方差评估清晰度。值越大越清晰。
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def check_exposure(image: np.ndarray) -> Tuple[bool, float, float]:
    """
    检查过曝/欠曝比例
    返回: (是否合格, 过曝比例, 欠曝比例)
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    total_pixels = gray.size

    overexpose = np.sum(gray > 250) / total_pixels
    underexpose = np.sum(gray < 20) / total_pixels

    is_ok = (overexpose <= MAX_OVEREXPOSE_RATIO) and (underexpose <= MAX_UNDEREXPOSE_RATIO)
    return is_ok, overexpose, underexpose


def clean_image(image_path: Path) -> dict:
    """
    对单张图片执行清洗流程
    """
    img = cv2.imread(str(image_path))
    if img is None:
        return {"status": "failed", "reason": "无法读取文件", "path": str(image_path)}

    # 1. 清晰度检测
    blur_score = compute_blur_laplacian(img)
    if blur_score < MIN_BLUR_THRESHOLD:
        return {
            "status": "rejected",
            "reason": "过于模糊",
            "blur_score": round(blur_score, 2),
            "path": image_path.name
        }

    # 2. 曝光检测
    exposure_ok, over_r, under_r = check_exposure(img)
    if not exposure_ok:
        return {
            "status": "rejected",
            "reason": f"曝光异常(过曝:{over_r:.2%}, 欠曝:{under_r:.2%})",
            "blur_score": round(blur_score, 2),
            "path": image_path.name
        }

    # 3. 尺寸标准化（保持宽高比，短边填充至640x640）
    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    orig_w, orig_h = pil_img.size
    target_w, target_h = TARGET_IMAGE_SIZE

    # 等比例缩放
    scale = min(target_w / orig_w, target_h / orig_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)

    resized = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # 创建640x640画布，居中填充
    new_img = Image.new('RGB', TARGET_IMAGE_SIZE, (114, 114, 114))  # 灰色填充（YOLO常用）
    paste_x = (target_w - new_w) // 2
    paste_y = (target_h - new_h) // 2
    new_img.paste(resized, (paste_x, paste_y))

    # 保存
    save_path = CLEAN_IMAGE_DIR / image_path.name
    new_img.save(save_path, quality=95)

    return {
        "status": "accepted",
        "blur_score": round(blur_score, 2),
        "original_size": [orig_w, orig_h],
        "padded_size": TARGET_IMAGE_SIZE,
        "scale": round(scale, 4),
        "path": image_path.name
    }


def main():
    image_files = sorted(list(RAW_IMAGE_DIR.glob("*.jpg")) + list(RAW_IMAGE_DIR.glob("*.png")))
    if not image_files:
        print(f"[错误] {RAW_IMAGE_DIR} 中没有图片，请先运行 01_video_to_frames.py")
        return

    report = {
        "total_scanned": len(image_files),
        "accepted": 0,
        "rejected": 0,
        "failed": 0,
        "details": []
    }

    print(f"[开始清洗] 共 {len(image_files)} 张图片...")
    for img_path in tqdm(image_files, desc="清洗进度"):
        result = clean_image(img_path)
        report["details"].append(result)

        if result["status"] == "accepted":
            report["accepted"] += 1
        elif result["status"] == "rejected":
            report["rejected"] += 1
        else:
            report["failed"] += 1

    # 保存报告
    report_path = REPORT_DIR / "cleaning_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n[清洗完成]")
    print(f"  通过: {report['accepted']} | 拒绝: {report['rejected']} | 失败: {report['failed']}")
    print(f"  报告保存至: {report_path}")
    print(f"  清洗后图片保存至: {CLEAN_IMAGE_DIR}")


if __name__ == "__main__":
    from typing import Tuple
    main()