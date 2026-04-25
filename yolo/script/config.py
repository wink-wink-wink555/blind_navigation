import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()

DATA_DIR = BASE_DIR / "data"
RAW_VIDEO_DIR = DATA_DIR / "raw_videos"
RAW_IMAGE_DIR = DATA_DIR / "images" / "raw"
CLEAN_IMAGE_DIR = DATA_DIR / "images" / "cleaned"
AUG_IMAGE_DIR = DATA_DIR / "images" / "augmented"
DATASET_DIR = DATA_DIR / "dataset"

MAKESENSE_EXPORT_DIR = DATA_DIR / "makesense_export"
MAKESENSE_IMAGE_DIR = MAKESENSE_EXPORT_DIR / "images"
MAKESENSE_LABEL_DIR = MAKESENSE_EXPORT_DIR / "labels"
MAKESENSE_CLASSES_FILE = MAKESENSE_EXPORT_DIR / "classes.txt"

YOLO_LABEL_DIR = DATA_DIR / "labels" / "yolo"

MODEL_DIR = BASE_DIR / "models"
PRETRAINED_WEIGHTS = "yolov8s.pt"
TRAINED_MODEL_DIR = MODEL_DIR / "trained"
EXPORT_MODEL_DIR = MODEL_DIR / "exported"

OUTPUT_DIR = BASE_DIR / "outputs"
REPORT_DIR = OUTPUT_DIR / "reports"
VISUAL_DIR = OUTPUT_DIR / "visualizations"
BAD_CASE_DIR = OUTPUT_DIR / "bad_cases"

for d in [RAW_VIDEO_DIR, RAW_IMAGE_DIR, CLEAN_IMAGE_DIR, AUG_IMAGE_DIR,
          DATASET_DIR, MAKESENSE_EXPORT_DIR, MAKESENSE_IMAGE_DIR, MAKESENSE_LABEL_DIR,
          YOLO_LABEL_DIR, TRAINED_MODEL_DIR, EXPORT_MODEL_DIR,
          REPORT_DIR, VISUAL_DIR, BAD_CASE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

CLASS_NAMES = ["Tactile_Paving", "Tactile_Paving_Metro"]
NUM_CLASSES = len(CLASS_NAMES)

VIDEO_SAMPLE_INTERVAL = 2
VIDEO_RESIZE_WIDTH = 1920
DEDUP_HASH_THRESHOLD = 8

MIN_BLUR_THRESHOLD = 100.0
MAX_OVEREXPOSE_RATIO = 0.15
MAX_UNDEREXPOSE_RATIO = 0.10
TARGET_IMAGE_SIZE = (640, 640)

AUGMENTATION_FACTOR = 3
MAX_ROTATION_ANGLE = 10
CROP_SCALE_RANGE = (0.7, 0.95)
BRIGHTNESS_RANGE = (0.7, 1.3)
CONTRAST_RANGE = (0.8, 1.2)
NOISE_INTENSITY = 15
BLUR_KERNEL_RANGE = (3, 5)

TRAIN_EPOCHS = 200
TRAIN_BATCH = 16
TRAIN_IMGSZ = 640
TRAIN_LR0 = 0.01
TRAIN_LRF = 0.01
TRAIN_PATIENCE = 30
TRAIN_DEVICE = "0"
FREEZE_BACKBONE_EPOCHS = 10

INFERENCE_CONF = 0.45
INFERENCE_IOU = 0.45

TTS_ENGINE = "pyttsx3"
TTS_RATE = 150
TTS_VOLUME = 0.9

DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "your_password",
    "database": "blind_navigation",
    "charset": "utf8mb4"
}
