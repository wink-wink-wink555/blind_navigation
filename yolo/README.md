# YOLOv8 盲道检测模型

## 📊 模型信息

这是一个经过自主收集盲道数据集并增强、完整训练的YOLOv8盲道检测模型，用于实时识别视频中的盲道及其方向变化。

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
- 优化的训练参数（见 `args.yaml`）

## 🙏 致谢

感谢所有参与数据收集和标注的团队成员：
- Chen Xingyu
- Wang Youyi
- Liu Yiheng
- Cai Yuxin
- Zhang Chenshu

