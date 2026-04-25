import cv2
import numpy as np
from typing import Tuple


def add_fog(image: np.ndarray, intensity: float = 0.4) -> np.ndarray:
    h, w = image.shape[:2]
    fog_layer = np.zeros_like(image, dtype=np.float32)
    for y in range(h):
        fog_factor = intensity * (1.0 - 0.3 * (y / h))
        fog_layer[y, :] = 255 * fog_factor

    fog_color = np.array([240, 240, 245], dtype=np.float32)
    fog_layer = fog_layer * (fog_color / 255.0)

    img_float = image.astype(np.float32)
    result = img_float * (1.0 - intensity * 0.6) + fog_layer * 0.6
    return np.clip(result, 0, 255).astype(np.uint8)


def add_rain(image: np.ndarray, num_drops: int = 800) -> np.ndarray:
    h, w = image.shape[:2]
    result = image.copy()
    for _ in range(num_drops):
        x = np.random.randint(0, w)
        y = np.random.randint(0, h - 20)
        length = np.random.randint(10, 25)
        thickness = np.random.randint(1, 2)
        angle_offset = np.random.randint(-5, 5)
        color = (200, 210, 220) if len(image.shape) == 3 else 200
        cv2.line(result, (x, y), (x + angle_offset, y + length),
                 color, thickness)
    result = cv2.convertScaleAbs(result, alpha=0.9, beta=10)
    return result


def add_night_effect(image: np.ndarray, gamma: float = 2.2) -> np.ndarray:
    inv_gamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** inv_gamma) * 255
                      for i in range(256)]).astype(np.uint8)
    dark = cv2.LUT(image, table)

    noise = np.random.normal(0, 10, dark.shape).astype(np.float32)
    result = dark.astype(np.float32) + noise
    return np.clip(result, 0, 255).astype(np.uint8)
