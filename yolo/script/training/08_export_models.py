"""
training/08_export_models.py
将训练好的模型导出为 ONNX / OpenVINO / TensorRT 格式
并对比各格式的推理延迟
"""

import time
import cv2
import numpy as np
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import TRAINED_MODEL_DIR, EXPORT_MODEL_DIR, TARGET_IMAGE_SIZE

from ultralytics import YOLO


def benchmark_model(model_path: Path, name: str, iterations=100):
    """
    对单张640x640图片进行预热+测速
    """
    dummy_img = np.random.randint(0, 255, (*TARGET_IMAGE_SIZE, 3), dtype=np.uint8)

    # 预热
    for _ in range(10):
        _ = model_path(dummy_img, verbose=False)

    # 测速
    t0 = time.time()
    for _ in range(iterations):
        _ = model_path(dummy_img, verbose=False)
    elapsed = time.time() - t0

    avg_ms = (elapsed / iterations) * 1000
    print(f"  {name}: {avg_ms:.2f} ms/帧 | FPS: {1000/avg_ms:.1f}")
    return avg_ms


def main():
    pt_path = TRAINED_MODEL_DIR / "blind_navigation_train" / "weights" / "best.pt"
    if not pt_path.exists():
        print(f"[错误] 未找到模型: {pt_path}")
        return

    EXPORT_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(pt_path))

    print("[开始导出模型]")

    # 1. 导出 ONNX
    print("\n[1/3] 导出 ONNX (Opset 12)...")
    onnx_path = EXPORT_MODEL_DIR / "best.onnx"
    model.export(format="onnx", imgsz=640, half=False, simplify=True)
    # ultralytics导出后文件在训练目录，复制过来
    exported_onnx = pt_path.parent / "best.onnx"
    if exported_onnx.exists():
        exported_onnx.replace(onnx_path)
        print(f"  已保存: {onnx_path}")

    # 2. 导出 OpenVINO（Intel优化，FP16）
    print("\n[2/3] 导出 OpenVINO (FP16)...")
    try:
        model.export(format="openvino", imgsz=640, half=True)
        exported_ov = pt_path.parent / "best_openvino_model"
        if exported_ov.exists():
            import shutil
            ov_dest = EXPORT_MODEL_DIR / "best_openvino_model"
            if ov_dest.exists():
                shutil.rmtree(ov_dest)
            shutil.move(str(exported_ov), str(ov_dest))
            print(f"  已保存: {ov_dest}")
    except Exception as e:
        print(f"  [跳过] OpenVINO导出失败（可能未安装openvino-dev）: {e}")

    # 3. 导出 TensorRT（需NVIDIA GPU + TensorRT环境）
    print("\n[3/3] 导出 TensorRT (FP16)...")
    try:
        model.export(format="engine", imgsz=640, half=True, device="0")
        exported_trt = pt_path.parent / "best.engine"
        if exported_trt.exists():
            trt_dest = EXPORT_MODEL_DIR / "best.engine"
            exported_trt.replace(trt_dest)
            print(f"  已保存: {trt_dest}")
    except Exception as e:
        print(f"  [跳过] TensorRT导出失败（可能未安装tensorrt）: {e}")

    # 4. 速度基准测试
    print("\n[推理速度基准测试] 使用640x640随机图片，100次迭代")
    benchmark_model(model, "PyTorch (原始)", iterations=100)

    if onnx_path.exists():
        onnx_model = YOLO(str(onnx_path))
        benchmark_model(onnx_model, "ONNX Runtime", iterations=100)

    ov_path = EXPORT_MODEL_DIR / "best_openvino_model"
    if ov_path.exists():
        ov_model = YOLO(str(ov_path))
        benchmark_model(ov_model, "OpenVINO", iterations=100)

    trt_path = EXPORT_MODEL_DIR / "best.engine"
    if trt_path.exists():
        trt_model = YOLO(str(trt_path))
        benchmark_model(trt_model, "TensorRT", iterations=100)

    print(f"\n[全部完成] 所有导出模型保存至: {EXPORT_MODEL_DIR}")


if __name__ == "__main__":
    main()