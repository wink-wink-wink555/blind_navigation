"""
utils/weather_effects.py
模拟恶劣天气对图像的影响：雾、雨、夜间低光
"""

import cv2
import numpy as np
from typing import Tuple


def add_fog(image: np.ndarray, intensity: float = 0.4) -> np.ndarray:
    """
    添加雾化效果（大气散射简化模型）
    intensity: 0.0~1.0，雾的浓度
    """
    h, w = image.shape[:2]
    # 生成雾层（亮度从下到上递减，模拟地面雾）
    fog_layer = np.zeros_like(image, dtype=np.float32)
    for y in range(h):
        # 越靠近下方雾越浓（地面附近）
        fog_factor = intensity * (1.0 - 0.3 * (y / h))
        fog_layer[y, :] = 255 * fog_factor

    # 雾色偏白或偏灰
    fog_color = np.array([240, 240, 245], dtype=np.float32)
    fog_layer = fog_layer * (fog_color / 255.0)

    # 混合：I = I_orig * (1-fog) + fog_color * fog
    img_float = image.astype(np.float32)
    result = img_float * (1.0 - intensity * 0.6) + fog_layer * 0.6
    return np.clip(result, 0, 255).astype(np.uint8)


def add_rain(image: np.ndarray, num_drops: int = 800) -> np.ndarray:
    """
    添加雨滴效果
    """
    h, w = image.shape[:2]
    result = image.copy()
    for _ in range(num_drops):
        # 随机起点
        x = np.random.randint(0, w)
        y = np.random.randint(0, h - 20)
        length = np.random.randint(10, 25)
        thickness = np.random.randint(1, 2)
        # 雨滴倾斜角度
        angle_offset = np.random.randint(-5, 5)
        # 亮度：雨滴偏白
        color = (200, 210, 220) if len(image.shape) == 3 else 200
        cv2.line(result, (x, y), (x + angle_offset, y + length),
                 color, thickness)
    # 轻微降低对比度模拟雨天阴沉
    result = cv2.convertScaleAbs(result, alpha=0.9, beta=10)
    return result


def add_night_effect(image: np.ndarray, gamma: float = 2.2) -> np.ndarray:
    """
    模拟夜间低光效果：伽马校正 + 噪声
    """
    # 伽马校正压暗
    inv_gamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** inv_gamma) * 255
                      for i in range(256)]).astype(np.uint8)
    dark = cv2.LUT(image, table)

    # 添加高斯噪声
    noise = np.random.normal(0, 10, dark.shape).astype(np.float32)
    result = dark.astype(np.float32) + noise
    return np.clip(result, 0, 255).astype(np.uint8)