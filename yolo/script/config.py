"""
config.py
全局配置中心：所有路径、超参数、阈值集中管理
"""

import os
from pathlib import Path

# ==================== 项目根目录 ====================
BASE_DIR = Path(__file__).parent.resolve()

# ==================== 数据目录 ====================
DATA_DIR = BASE_DIR / "data"
RAW_VIDEO_DIR = DATA_DIR / "raw_videos"          # 原始视频
RAW_IMAGE_DIR = DATA_DIR / "images" / "raw"       # 抽帧后原始图
CLEAN_IMAGE_DIR = DATA_DIR / "images" / "cleaned" # 清洗后图片
AUG_IMAGE_DIR = DATA_DIR / "images" / "augmented" # 增强后图片
DATASET_DIR = DATA_DIR / "dataset"                # 最终YOLO标准数据集

# 标注目录
COCO_ANNOTATION_FILE = DATA_DIR / "annotations" / "coco_export.json"  # LabelStudio导出
YOLO_LABEL_DIR = DATA_DIR / "labels" / "yolo"                         # YOLO格式标注

# ==================== 模型目录 ====================
MODEL_DIR = BASE_DIR / "models"
PRETRAINED_WEIGHTS = "yolov8s.pt"                 # 预训练权重（自动下载）
TRAINED_MODEL_DIR = MODEL_DIR / "trained"
EXPORT_MODEL_DIR = MODEL_DIR / "exported"

# ==================== 输出与日志 ====================
OUTPUT_DIR = BASE_DIR / "outputs"
REPORT_DIR = OUTPUT_DIR / "reports"
VISUAL_DIR = OUTPUT_DIR / "visualizations"
BAD_CASE_DIR = OUTPUT_DIR / "bad_cases"

# 自动创建所有目录
for d in [RAW_VIDEO_DIR, RAW_IMAGE_DIR, CLEAN_IMAGE_DIR, AUG_IMAGE_DIR,
          DATASET_DIR, YOLO_LABEL_DIR, TRAINED_MODEL_DIR, EXPORT_MODEL_DIR,
          REPORT_DIR, VISUAL_DIR, BAD_CASE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ==================== 类别定义 ====================
# 0: 行进盲道(直行)  1: 提示盲道(转弯/障碍)  2: 缘石坡道
CLASS_NAMES = ["straight_guide", "warning_guide", "curb_ramp"]
NUM_CLASSES = len(CLASS_NAMES)

# ==================== 数据采集参数 ====================
VIDEO_SAMPLE_INTERVAL = 2          # 每2秒抽一帧基础帧率
VIDEO_RESIZE_WIDTH = 1920          # 视频预处理宽度
DEDUP_HASH_THRESHOLD = 8           # 感知哈希汉明距离阈值（小于此值视为重复）

# ==================== 数据清洗参数 ====================
MIN_BLUR_THRESHOLD = 100.0         # 拉普拉斯方差阈值（低于此值视为模糊）
MAX_OVEREXPOSE_RATIO = 0.15        # 高光像素(>250)占比上限
MAX_UNDEREXPOSE_RATIO = 0.10       # 暗部像素(<20)占比上限
TARGET_IMAGE_SIZE = (640, 640)       # 训练统一尺寸

# ==================== 增强参数 ====================
AUGMENTATION_FACTOR = 3            # 每张基础图增强为3张
MAX_ROTATION_ANGLE = 10            # 最大旋转角度（度）
CROP_SCALE_RANGE = (0.7, 0.95)    # 随机裁剪保留比例
BRIGHTNESS_RANGE = (0.7, 1.3)      # 亮度系数
CONTRAST_RANGE = (0.8, 1.2)        # 对比度系数
NOISE_INTENSITY = 15               # 高斯噪声标准差
BLUR_KERNEL_RANGE = (3, 5)         # 模糊核大小

# ==================== 训练参数 ====================
TRAIN_EPOCHS = 200
TRAIN_BATCH = 16
TRAIN_IMGSZ = 640
TRAIN_LR0 = 0.01                   # 初始学习率
TRAIN_LRF = 0.01                   # 最终学习率因子
TRAIN_PATIENCE = 30                # 早停耐心值
TRAIN_DEVICE = "0"                 # GPU设备号，"cpu"表示CPU训练
FREEZE_BACKBONE_EPOCHS = 10        # 前10轮冻结骨干网络

# ==================== 推理参数 ====================
INFERENCE_CONF = 0.45              # 检测置信度阈值
INFERENCE_IOU = 0.45               # NMS IoU阈值
TRACK_MAX_LEN = 15                 # 时序跟踪队列长度（帧）
DIRECTION_THRESHOLD = 0.015        # 方向趋势斜率阈值（归一化坐标/帧）
COOLDOWN_FRAMES = 90               # 语音触发冷却帧数（约3秒@30fps）

# ==================== 语音参数 ====================
TTS_ENGINE = "pyttsx3"             # 或 "edge_tts"
TTS_RATE = 150                     # 语速
TTS_VOLUME = 0.9                   # 音量

# ==================== 数据库/API配置（与主项目对齐） ====================
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "your_password",
    "database": "blind_navigation",
    "charset": "utf8mb4"
}