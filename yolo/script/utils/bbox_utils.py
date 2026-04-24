"""
utils/bbox_utils.py
边界框工具函数：支持旋转、裁剪、翻转后的坐标同步计算
"""

import math
import numpy as np
from typing import List, Tuple, Optional


def yolo_to_pixels(cx: float, cy: float, w: float, h: float,
                     img_w: int, img_h: int) -> Tuple[float, float, float, float]:
    """
    YOLO格式(cx,cy,w,h, 0~1) → 像素格式(left, top, right, bottom)
    """
    px_cx = cx * img_w
    px_cy = cy * img_h
    px_w = w * img_w
    px_h = h * img_h
    left = px_cx - px_w / 2
    top = px_cy - px_h / 2
    right = px_cx + px_w / 2
    bottom = px_cy + px_h / 2
    return left, top, right, bottom


def pixels_to_yolo(left: float, top: float, right: float, bottom: float,
                   crop_w: int, crop_h: int) -> Optional[Tuple[float, float, float, float]]:
    """
    像素格式(left,top,right,bottom) → YOLO格式(cx,cy,w,h, 0~1)
    若框被完全裁剪掉，返回 None
    """
    new_w = right - left
    new_h = bottom - top
    if new_w <= 0 or new_h <= 0:
        return None
    new_cx = left + new_w / 2
    new_cy = top + new_h / 2
    # 归一化到裁剪后画布
    return (new_cx / crop_w, new_cy / crop_h,
            new_w / crop_w, new_h / crop_h)


def horizontal_flip_bboxes(bboxes: List[List[float]]) -> List[List[float]]:
    """
    水平翻转所有YOLO边界框：x_center = 1 - x_center
    bboxes: [[cls, cx, cy, w, h], ...]
    """
    flipped = []
    for bbox in bboxes:
        cls_id, cx, cy, w, h = bbox
        flipped.append([cls_id, 1.0 - cx, cy, w, h])
    return flipped


def crop_bboxes(bboxes: List[List[float]],
                x1: int, y1: int, x2: int, y2: int,
                orig_w: int, orig_h: int) -> List[List[float]]:
    """
    将YOLO边界框按裁剪区域重新计算
    裁剪区域为原图上的像素坐标 [x1, y1, x2, y2]
    """
    crop_w = x2 - x1
    crop_h = y2 - y1
    if crop_w <= 0 or crop_h <= 0:
        return []

    new_bboxes = []
    for bbox in bboxes:
        cls_id, cx, cy, w, h = bbox
        left, top, right, bottom = yolo_to_pixels(cx, cy, w, h, orig_w, orig_h)

        # 与裁剪区域求交
        new_left = max(left, x1)
        new_top = max(top, y1)
        new_right = min(right, x2)
        new_bottom = min(bottom, y2)

        result = pixels_to_yolo(new_left, new_top, new_right, new_bottom, crop_w, crop_h)
        if result is not None:
            new_cx, new_cy, new_w, new_h = result
            # 额外过滤：裁剪后太小的框（面积小于原图0.05%）视为无效
            if new_w > 0.005 and new_h > 0.005:
                new_bboxes.append([cls_id, new_cx, new_cy, new_w, new_h])
    return new_bboxes


def rotate_bboxes_approx(bboxes: List[List[float]],
                         angle_deg: float,
                         img_w: int, img_h: int) -> List[List[float]]:
    """
    近似旋转边界框（小角度适用，<=15度）。
    精确做法应旋转四个角点再求最小外接矩形，此处用简化版：
    仅旋转中心点，保持宽高，并做边界截断。
    """
    angle_rad = math.radians(angle_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    cx_img = img_w / 2
    cy_img = img_h / 2

    new_bboxes = []
    for bbox in bboxes:
        cls_id, cx, cy, w, h = bbox
        # 转到像素中心
        px_cx = cx * img_w
        px_cy = cy * img_h

        # 绕图像中心旋转
        dx = px_cx - cx_img
        dy = px_cy - cy_img
        new_px_cx = cx_img + (dx * cos_a - dy * sin_a)
        new_px_cy = cy_img + (dx * sin_a + dy * cos_a)

        # 转回归一化，并截断到[0,1]
        new_cx = np.clip(new_px_cx / img_w, 0.0, 1.0)
        new_cy = np.clip(new_px_cy / img_h, 0.0, 1.0)

        # 宽高近似不变（小角度假设），但需检查是否越界
        new_w = w * (abs(cos_a) + abs(sin_a))  # 经验补偿
        new_h = h * (abs(cos_a) + abs(sin_a))

        # 确保不越界
        new_w = min(new_w, 2 * min(new_cx, 1 - new_cx))
        new_h = min(new_h, 2 * min(new_cy, 1 - new_cy))
        if new_w > 0 and new_h > 0:
            new_bboxes.append([cls_id, new_cx, new_cy, new_w, new_h])
    return new_bboxes


def compute_iou(box1: List[float], box2: List[float]) -> float:
    """
    计算两个YOLO框的IoU
    box: [cx, cy, w, h]
    """
    def to_ltrb(b):
        cx, cy, w, h = b
        return [cx - w/2, cy - h/2, cx + w/2, cy + h/2]

    l1, t1, r1, b1 = to_ltrb(box1)
    l2, t2, r2, b2 = to_ltrb(box2)

    inter_left = max(l1, l2)
    inter_top = max(t1, t2)
    inter_right = min(r1, r2)
    inter_bottom = min(b1, b2)

    if inter_right <= inter_left or inter_bottom <= inter_top:
        return 0.0

    inter_area = (inter_right - inter_left) * (inter_bottom - inter_top)
    area1 = (r1 - l1) * (b1 - t1)
    area2 = (r2 - l2) * (b2 - t2)
    union_area = area1 + area2 - inter_area
    return inter_area / union_area if union_area > 0 else 0.0