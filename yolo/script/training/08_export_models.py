import time
import cv2
import numpy as np
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import TRAINED_MODEL_DIR, EXPORT_MODEL_DIR, TARGET_IMAGE_SIZE

from ultralytics import YOLO


def benchmark_model(model_path, name: str, iterations=100):
    dummy_img = np.random.randint(0, 255, (*TARGET_IMAGE_SIZE, 3), dtype=np.uint8)

    for _ in range(10):
        _ = model_path(dummy_img, verbose=False)

    t0 = time.time()
    for _ in range(iterations):
        _ = model_path(dummy_img, verbose=False)
    elapsed = time.time() - t0

    avg_ms = (elapsed / iterations) * 1000
    print(f"  {name}: {avg_ms:.2f} ms/frame | FPS: {1000/avg_ms:.1f}")
    return avg_ms


def main():
    pt_path = TRAINED_MODEL_DIR / "blind_navigation_train" / "weights" / "best.pt"
    if not pt_path.exists():
        print(f"[Error] Model not found: {pt_path}")
        return

    EXPORT_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(pt_path))

    print("[Start Exporting Models]")

    print("
[1/3] Exporting ONNX (Opset 12)...")
    onnx_path = EXPORT_MODEL_DIR / "best.onnx"
    model.export(format="onnx", imgsz=640, half=False, simplify=True)
    exported_onnx = pt_path.parent / "best.onnx"
    if exported_onnx.exists():
        exported_onnx.replace(onnx_path)
        print(f"  Saved: {onnx_path}")

    print("
[2/3] Exporting OpenVINO (FP16)...")
    try:
        model.export(format="openvino", imgsz=640, half=True)
        exported_ov = pt_path.parent / "best_openvino_model"
        if exported_ov.exists():
            import shutil
            ov_dest = EXPORT_MODEL_DIR / "best_openvino_model"
            if ov_dest.exists():
                shutil.rmtree(ov_dest)
            shutil.move(str(exported_ov), str(ov_dest))
            print(f"  Saved: {ov_dest}")
    except Exception as e:
        print(f"  [Skipped] OpenVINO export failed (openvino-dev may not be installed): {e}")

    print("
[3/3] Exporting TensorRT (FP16)...")
    try:
        model.export(format="engine", imgsz=640, half=True, device="0")
        exported_trt = pt_path.parent / "best.engine"
        if exported_trt.exists():
            trt_dest = EXPORT_MODEL_DIR / "best.engine"
            exported_trt.replace(trt_dest)
            print(f"  Saved: {trt_dest}")
    except Exception as e:
        print(f"  [Skipped] TensorRT export failed (tensorrt may not be installed): {e}")

    print("
[Inference Speed Benchmark] Using 640x640 random image, 100 iterations")
    benchmark_model(model, "PyTorch (Original)", iterations=100)

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

    print(f"
[All Done] All exported models saved to: {EXPORT_MODEL_DIR}")


if __name__ == "__main__":
    main()
