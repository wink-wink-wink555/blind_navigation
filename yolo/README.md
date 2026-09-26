# YOLOv8 盲道检测模型

## 📊 模型信息

这是一个经过自主收集盲道数据集并增强、完整训练的YOLOv8盲道检测模型，用于实时检测视频中的候选盲道区域（输出边界框）。模型本身只输出检测框，不预测方向：盲道相对用户的横向偏移由上层几何估计（services/path_alignment.py）、时间滤波与导航状态机共同推导。

## 💡 使用方法

在 `config.py` 中配置模型路径：

```python
MODEL_WEIGHTS = 'yolo/best.pt'
```

系统会自动加载该模型进行盲道检测。

## 📝 训练信息

本模型基于ultralytics的YOLOv8框架训练，使用了：
- 自定义收集的盲道数据集
- 团队成员人工标注的高质量标签
- 优化的训练参数

## 🙏 致谢

感谢所有参与数据收集和标注的团队成员：
- Chen Xingyu
- Wang Youyi
- Liu Yiheng
- Cai Yuxin
- Zhang Chenshu

