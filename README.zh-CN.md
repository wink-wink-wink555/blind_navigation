# Blind Navigation (ARIADNE) - 引君出迷津

<div align="center">

<img src="LOGO.png" alt=" Logo" width="350"/>

[English](README.md) | 简体中文

[![Python](https://img.shields.io/badge/Python-3.10%2F3.11-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/wink-wink-wink555/blind_navigation.svg)](https://github.com/wink-wink-wink555/blind_navigation/stargazers)

</div>

> 📹 项目视频: [项目展示 I](https://www.bilibili.com/video/BV1kD57zGE68), [项目展示 II](https://openatom.tech/enterprise-ai/614b385486d53533dd74f9428aa83087/blob/master/A_%E9%A1%B9%E7%9B%AE%E6%BC%94%E7%A4%BA%E8%A7%86%E9%A2%91.mp4)

<details>
<summary><strong>🏆 荣誉与奖项</strong>  <em>（点击查看）</em></summary>

- **2026.1** 英特尔平台企业AI解决方案创新实践赛决赛 — 10强
- **2025.12** 英特尔平台企业AI解决方案创新实践赛 — 20强，*成功晋级决赛*
- **2025.8** 中国大学生计算机设计大赛 — 国家级三等奖
- **2025.5** 上海市大学生计算机应用能力大赛 — 省级一等奖

</details>

---

## 🌟 项目简介

视障人士出行辅助系统（ARIADNE）融合盲道视觉感知、百度地图步行路线、浏览器定位、实时语音引导、家属交互与多 Agent 智能助手，为视障用户提供一体化的导航辅助与自然语言交互能力。

系统将宏观路线与局部感知分层处理：百度步行路线和 GPS 提供路线步骤、计划转向与位置更新；视觉管线负责盲道检测与局部横向状态；`NavigationManager` 综合路线上下文和视觉观测后生成引导。安全提醒、路线预告、局部纠偏、家属语音消息、助手回复和背景反馈共享统一的浏览器语音通道，并通过优先级与上下文有效性进行调度。

除实时导航外，ARIADNE 还提供地图问答、自然语言设置、家属通信、闲聊陪伴、账户管理、位置共享、语音识别、云端/本地模型切换和个性化语音设置等功能。

### 核心技术栈

- **前端**：HTML5, CSS3, JavaScript（原生）
- **后端**：Flask（建议 Python 3.10 / 3.11）
- **视觉与导航**：
  - YOLO - 候选盲道区域检测
  - `PathGeometryEstimator` - 近场横向几何估计
  - `NavigationManager` - 路线上下文与对齐状态控制
- **文本 AI 模型**：服务器配置的云端接口（DeepSeek、OpenAI、DashScope/Qwen 或其他 OpenAI 兼容服务），或用户选择的本地 Ollama 模型
- **多 Agent 架构**：
  - RouterAgent - 意图分类与路由
  - MapAgent（ReAct + 百度地图 MCP）- 地图问答与路线查询
  - SettingsAgent - 自然语言设置查询与修改
  - ChatAgent - 闲聊陪伴
- **数据库**：MySQL
- **第三方服务**：
  - 百度地图 Web 服务与浏览器 JSAPI - 步行路线、坐标转换和地图展示
  - 阿里云百炼（DashScope）- 云端语音识别
  - 浏览器 Web Speech API - 语音输出

## 🎯 解决的问题

1. **实时辅助导航**：融合盲道视觉感知、浏览器 GPS、百度步行路线与路线上下文中的局部对齐
2. **状态化语音引导**：安全、路线、对齐、家属、助手和背景消息共享统一语音调度器
3. **多 Agent 智能助手**：在地图问答、系统设置、家属通信和闲聊之间进行自然语言意图路由
4. **家属交互**：家属账号可接收用户信息、发送浏览器语音消息并查看共享位置
5. **个性化体验**：支持语速、音量、称呼、用户模式和 AI 后端等配置
6. **无障碍交互**：将语音、导航、视觉感知和家属支持整合到同一系统

## ✨ 功能亮点

- 🧭 **实时辅助导航**：百度步行路线与 GPS 提供宏观路线上下文，实时视觉补充局部盲道观察与对齐提示
- 🎥 **实时盲道感知**：YOLO 检测与近场几何估计、时间状态结合后生成局部引导
- 🔊 **状态化语音引导**：统一调度安全、路线、对齐、家属、助手和背景消息，支持优先级、TTL、打断和上下文失效
- 🤖 **多 Agent 智能助手**：
  - 🗺️ MapAgent + 百度地图 MCP：地图问答与路线查询
  - ⚙️ SettingsAgent：自然语言设置查询与修改
  - 📨 家属通信
  - 💬 带近期上下文的闲聊陪伴
- 📨 **家属端语音消息**：经授权的家属账号可向用户浏览器发送语音消息，并查询播放进度
- 📍 **位置共享**：关联家属账号可查看用户最近共享的位置
- 🎙️ **语音识别**：支持 DashScope 云端识别或本地 `/v1/audio/transcriptions` 服务
- 🔧 **云端 / 本地 AI 后端**：支持服务器配置的云端模型与本地 Ollama
- 👤 **用户系统**：注册、登录、密码找回、用户模式与个性化设置

## 🤖 多 Agent 智能助手架构

`/chat` 作为统一调度入口，对用户自然语言请求进行分类并路由到对应能力；实时导航仍由确定性的导航管线独立负责。

```text
用户输入
    │
    ▼
RouterAgent
    │
    ├─ map      ──► MapAgent（ReAct + 百度地图 MCP）
    │                  └─ 地址解析 → 周边搜索 → 步行路线 → 自然语言回答
    │
    ├─ settings ──► SettingsAgent
    │                  └─ 理解意图 → 校验 → 写入数据库 → 同步 Session
    │
    ├─ message  ──► 家属消息处理器
    │
    └─ chat     ──► ChatAgent
```

| Agent | 文件 | 功能 |
|---|---|---|
| RouterAgent | `services/router_agent.py` | 意图分类与路由 |
| MapAgent | `services/deepseek_ai.py` | ReAct 地图问答与步行路线查询 |
| SettingsAgent | `services/settings_agent.py` | 自然语言设置查询与修改 |
| ChatAgent | `routes/chat.py` | 使用近期对话上下文和用户资料进行闲聊 |

**示例对话**
- `"帮我把语音速度调成慢"` → SettingsAgent
- `"从上海人民广场到上海博物馆怎么走？"` → MapAgent
- `"给家属说一声我已经到了"` → 家属消息处理器
- `"今天天气真好"` → ChatAgent

## 🧭 导航与语音引导架构

### 宏观路线与局部感知

ARIADNE 将路线规划与局部盲道感知分层处理：

```text
百度步行路线 + GPS
        │
        ▼
 NavigationManager
路线步骤 / 预计转向 / 偏航 / 过街
        │
        ├──────────────────────┐
        │                      │
        ▼                      ▼
路线提示                 实时摄像头
                               │
                               ▼
                         YOLO Detection
                               │
                               ▼
                    PathGeometryEstimator
                               │
                               ▼
                     Alignment State
                               │
                               ▼
                         局部引导
```

百度路线负责宏观路线决策，视觉管线在当前路线上下文中提供局部盲道观测。计划转弯、过街、视觉不确定、盲道丢失和严重偏离均作为显式导航状态参与引导决策。

### 盲道横向对齐

`services/vision_observer.py` 获取候选盲道检测结果，`services/path_alignment.py` 在检测框之上估计近场横向几何。估计器重点关注画面近场区域，并结合检测置信度、近场几何与连续帧信息进行候选选择；每个实时或历史视频流维护独立的几何状态。

系统使用归一化横向偏移表示候选盲道相对视觉参考中心的位置：

`normalized_offset = (path_center_x - reference_center_x) / image_width`

`NavigationManager` 结合最近观测、时间一致性与迟滞机制建立 correction episode。稳定偏离可触发简洁的左右纠偏提示，稳定回正后可结束本次 episode 并给出简短正反馈。接近计划转弯、过街、视觉不确定或严重偏离时，路线上下文和安全状态优先于普通微纠偏。

### 实时帧处理

实时摄像头采用 latest-frame processing，同时只保持一个视觉请求在途。单调递增的 frame sequence 与服务器侧 freshness 时间戳共同约束实时观测，使当前导航状态只接收时序有效的视觉结果。调试信息可展示几何状态、置信度、帧序号与延迟。

### 统一语音仲裁

`static/js/guidance.js` 负责浏览器语音的排序、打断、失效和上下文校验。

| 优先级 | 消息 |
|---|---|
| 0 | 安全提醒 |
| 1 | 盲道横向对齐 |
| 2 | 步行路线预告 |
| 3 | 经授权的家属端语音消息 |
| 4 | 助手回复 |
| 5 | 背景提示、正反馈与测试语音 |

事件可携带 TTL 与导航/对齐上下文版本。路线或对齐状态变化后，旧上下文中的排队语音会自动失效；家属语音消息则按照独立恢复策略与播放回执管理。

<details>
<summary><strong>横向对齐参数</strong></summary>

| 参数 | 当前值 | 作用 |
|---|---:|---|
| Near-field ROI | `0.50H–0.90H` | 聚焦近场盲道区域 |
| Evaluation row | `0.70H` | 估计近场盲道中心 |
| Geometry minimum confidence | `0.35` | 过滤低置信度检测 |
| Centered threshold | `0.07` | 居中范围 |
| Correction threshold | `0.12` | 纠偏进入阈值 |
| Severe threshold | `0.22` | 严重偏离阈值 |
| Alignment history | `5` 帧 | 最近有效横向观测 |
| Consistency window | `4` 帧 | 方向一致性窗口 |
| Required consistent frames | `3` 帧 | 触发纠偏所需一致帧数 |
| Recovery frames | `3` 帧 | 恢复确认帧数 |
| Severe frames | `3` 帧 | 严重偏离确认帧数 |
| Turn suppression distance | `12 m` | 接近计划转弯时暂停局部纠偏 |
| Correction repeat interval | `10 s` | 同一 episode 内重复控制 |
| Praise cooldown | `20 s` | 正反馈冷却时间 |
| Alignment speech TTL | `3 s` | 纠偏语音有效期 |
| Server-observed stale-frame threshold | `1.5 s` | 视觉时效阈值 |
| Camera scheduling | `350 ms / 700 ms` | 正常 / 高延迟下一帧调度间隔 |

相关常量集中在 `services/path_alignment.py`、`services/navigation.py` 和 `static/js/navigation_ui.js` 中。

</details>

## 🎯 预训练 YOLO 模型

仓库包含已训练的盲道检测权重 `yolo/best.pt`，`yolo/` 目录保留训练与评估材料。

YOLO 负责输出候选盲道 bounding boxes；`services/path_alignment.py` 在其上提取近场几何，`services/navigation.py` 再将几何观测与路线上下文和时间状态结合后生成引导。

## 📋 环境要求

- 建议 Python 3.10 或 3.11，以匹配当前固定的 NumPy 1.24.3 依赖环境
- MySQL 数据库
- 必要的 Python 库（见 `requirements.txt`）
- 使用助手功能需配置云端文本模型密钥，或运行本地 [Ollama](https://ollama.com/) 文本模型
- 使用实时步行导航需配置百度 Web 服务及浏览器 JSAPI 密钥，并允许浏览器定位

## 🚀 安装步骤

<details>
<summary><strong>1. 克隆仓库</strong></summary>

```bash
git clone https://github.com/wink-wink-wink555/blind_navigation.git
cd blind_navigation
```

</details>

<details>
<summary><strong>2. 创建并激活虚拟环境（推荐）</strong></summary>

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

</details>

<details>
<summary><strong>3. 安装依赖</strong></summary>

```bash
pip install -r requirements.txt
```

</details>

<details>
<summary><strong>4.（可选）安装 Ollama 以使用本地 AI</strong></summary>

如果希望使用本地模型而非云端 API，请安装 Ollama 并拉取模型：

```bash
# 访问 https://ollama.com/ 下载并安装 Ollama

ollama pull qwen2.5:3b
ollama list
```

Ollama 默认运行在 `http://localhost:11434`。登录后可在 AI 设置中选择本地文本模型。本地语音识别使用独立的 `/v1/audio/transcriptions` 服务。

</details>

<details>
<summary><strong>5. 配置数据库</strong></summary>

```sql
CREATE DATABASE blind_navigation CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

首次运行时应用会自动创建所需数据表。

</details>

<details>
<summary><strong>6. 配置文件</strong></summary>

```bash
cp config.example.py config.py  # Linux/Mac
copy config.example.py config.py  # Windows
```

修改 `config.py`：

- **`DB_CONFIG`**：MySQL 的 host、user、password 等
- **`EMAIL_CONFIG`**：QQ 邮箱 SMTP，用于验证码及助手向家属联系人发送邮件
- **`BAIDU_MAP_CONFIG`**：`api_key` 用于后端 Web 服务，`browser_api_key` 用于地图 JSAPI
- **`DEEPSEEK_CONFIG`**：服务器端默认云端文本模型配置
- **`DASHSCOPE_CONFIG`**：阿里云百炼 API 密钥，用于云端语音识别
- **`MODEL_WEIGHTS`**：设置为 `'yolo/best.pt'`

</details>

## 🏃 运行应用

```bash
python app.py
```

访问 http://127.0.0.1:5000/

## 📖 使用说明

<details>
<summary><strong>账户管理</strong></summary>

填写用户名、密码、邮箱并通过邮箱验证码完成注册。支持登录和密码重置。

</details>

<details>
<summary><strong>盲道导航</strong></summary>

- **历史视频检测**：上传视频后展示 YOLO 盲道检测结果。
- **实时路线导航**：启用浏览器语音并获取定位后，选择目的地、查看百度步行路线并启动导航。
- **实时摄像头对齐**：启用摄像头后，系统可在当前路线上下文中增加局部盲道对齐提示。
- **恢复反馈**：稳定纠偏并回正后可获得简短正反馈。
- **转弯与过街**：计划转弯、过街和视觉不确定状态优先于普通局部纠偏。
- **手动起点**：地图手动选点用于路线预览；实时导引使用浏览器定位。

</details>

<details>
<summary><strong>多 Agent 智能助手</strong></summary>

统一对话入口：

- **地图**：*"从北京站到天安门广场怎么走？"*
- **设置**：*"帮我把语音速度调成慢"*
- **家属消息**：*"帮我发给家属消息：我已经到学校了"*
- **闲聊**：结合近期上下文进行日常对话

</details>

<details>
<summary><strong>AI 设置</strong></summary>

用户可在 AI 设置中切换服务器配置的云端模型与本地部署：
- **文本模型**：DeepSeek / OpenAI / DashScope-Qwen / 其他兼容云端接口 / 本地 Ollama
- **语音识别**：DashScope 云端识别或本地 OpenAI 兼容音频转写接口

修改立即生效，无需重启服务。

</details>

<details>
<summary><strong>位置共享</strong></summary>

视障用户可通过浏览器定位共享最近位置，关联家属账号可在地图上查看。

</details>

<details>
<summary><strong>系统设置</strong></summary>

可自定义称呼、年龄段、语速、音量、用户模式和鼓励功能等设置。

</details>

## 🧩 实现说明

- 助手对话使用配置的文本 AI 后端；导航与引导由确定性的导航逻辑生成。
- SMTP 负责验证码及助手向家属发送邮件；家属端向用户发送浏览器语音消息使用语音事件通道。
- 步行路线与地图展示使用百度 Web 服务与浏览器 JSAPI。
- 云端语音识别使用 DashScope；本地语音识别使用 `/v1/audio/transcriptions`。
- 实时导航使用浏览器 GPS，并可进一步使用实时摄像头提供局部盲道对齐。
- 当前运行时将导航会话、事件状态和近期位置保存在 Flask 进程内。
- 本地回归检查：`python -m unittest discover -s tests` 和 `node tests/test_guidance.js`。

## 📧 联系方式

- **Email**: yfsun.jeff@gmail.com
- **GitHub**: [wink-wink-wink555](https://github.com/wink-wink-wink555)
- **LinkedIn**: [Yifei Sun](https://www.linkedin.com/in/yifei-sun-0bab66341/)
- **Bilibili**: [NO_Desire](https://space.bilibili.com/623490717)

## 🙏 特别感谢

特别感谢以下成员在盲道数据集收集、标注与项目书撰写中提供的帮助：

[Chen Xingyu](https://github.com/guangxiangdebizi) · Wang Youyi · Shen Qian · Liu Yiheng · Zhang Chenshu · Zhang Kai · Sheng Sheng · Cai Yuxin

## 📁 项目结构

以下列出主要文件；`config.py` 由配置模板在本地生成。

```text
blind_navigation/
├── app.py                    # Flask 应用入口
├── config.example.py         # 配置模板；复制为 config.py
├── models/
│   └── database.py           # 数据库操作
├── routes/
│   ├── auth.py               # 账户认证
│   ├── chat.py               # 多 Agent /chat 入口
│   ├── main.py               # 主页面、设置与家属端语音消息
│   ├── video.py              # 历史视频检测；每个播放流使用独立 geometry tracker
│   ├── map.py                # 地图相关接口
│   ├── ai_settings.py        # AI 设置接口
│   └── guidance.py           # 实时导航、视觉流隔离、freshness 与事件流
├── services/
│   ├── ai_provider.py        # 云端/本地 AI 配置
│   ├── baidu_map_mcp.py      # 助手使用的百度地图工具
│   ├── baidu_navigation.py   # 百度步行路线与坐标转换
│   ├── deepseek_ai.py        # 地图问答 MapAgent
│   ├── ollama_client.py      # Ollama 客户端
│   ├── router_agent.py       # 意图分类
│   ├── settings_agent.py     # 设置查询与修改
│   ├── speech_agent.py       # 语音识别
│   ├── guidance_bus.py       # 用户事件与播放回执
│   ├── location_store.py     # 进程内近期定位
│   ├── navigation.py         # 宏观导航 + Alignment 状态机、纠偏 Episode 与安全 Gating
│   ├── path_alignment.py     # YOLO 检测框的近场横向几何估计
│   └── vision_observer.py    # YOLO 可见性、隔离 geometry tracker 与帧元数据
├── static/js/
│   ├── guidance.js           # 浏览器语音调度器
│   └── navigation_ui.js      # 定位、地图、latest-frame 摄像头循环与事件接入
├── tests/
│   ├── test_guidance.js      # 语音优先级、打断、恢复、TTL 与 alignment epoch
│   ├── test_http_guidance.py # HTTP、视觉流隔离、帧元数据和用户边界
│   ├── test_navigation.py    # 宏观导航状态与事件回归
│   └── test_path_alignment.py# 几何估计、流隔离、迟滞、纠偏闭环与安全 gating
├── utils/
│   ├── decorators.py
│   ├── email_utils.py
│   └── video_utils.py
├── templates/
│   └── index.html            # 主页面
└── yolo/
    └── best.pt               # 盲道检测权重
```

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。Copyright (c) 2025 wink-wink-wink555。

---

⭐ 如果这个项目对您有帮助，欢迎给个 Star！
