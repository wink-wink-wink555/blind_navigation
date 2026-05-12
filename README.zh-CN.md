# Blind Navigation (ARIADNE) - 引君出迷津

<div align="center">

<img src="PPT/LOGO.png" alt=" Logo" width="350"/>

[English](README.md) | 简体中文

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/wink-wink-wink555/blind_navigation.svg)](https://github.com/wink-wink-wink555/blind_navigation/stargazers)

</div>

> 📹 演示视频: [V1.0.0](https://www.bilibili.com/video/BV1kD57zGE68), [V2.0.0](https://openatom.tech/enterprise-ai/614b385486d53533dd74f9428aa83087/blob/master/A_%E9%A1%B9%E7%9B%AE%E6%BC%94%E7%A4%BA%E8%A7%86%E9%A2%91.mp4)

<details>
<summary><strong>🏆 荣誉与奖项</strong>  <em>（点击查看）</em></summary>

- **2026.1** 英特尔平台企业AI解决方案创新实践赛决赛 — 10强
- **2025.12** 英特尔平台企业AI解决方案创新实践赛 — 20强，*成功晋级决赛*
- **2025.8** 中国大学生计算机设计大赛 — 国家级三等奖
- **2025.5** 上海市大学生计算机应用能力大赛 — 省级一等奖

</details>

---

## 🌟 项目简介

视障人士出行辅助系统 (ARIADNE) 是一个结合计算机视觉和人工智能的创新应用，专为视障人士设计。系统通过实时视频分析识别盲道方向变化，并通过个性化 AI 语音提示引导用户行走。同时，系统内置了一套**多 Agent 智能助手**，用户只需用自然语言说话，即可完成地图导航、系统设置修改、给家属发消息等操作，并提供位置共享功能，提高出行安全性。

### 核心技术栈

- **前端**：HTML5, CSS3, JavaScript（原生）
- **后端**：Flask (Python 3.8+)
- **AI 模型**：
  - YOLO (You Only Look Once) - 盲道检测
  - **文本 AI 模型**（灵活可配置）：支持**云端 API**（DeepSeek、OpenAI、阿里云百炼/Qwen 或任何 OpenAI 兼容接口）和**本地 Ollama** 模型，每位用户可在设置面板中独立切换
  - 多 Agent 智能助手（意图路由、地图导航、设置管理、闲聊陪伴）
- **多 Agent 架构**：
  - RouterAgent - 意图分类路由器
  - MapAgent (ReAct + 百度地图 MCP) - 地图导航 Agent
  - SettingsAgent - 设置查询/修改 Agent
  - ChatAgent - 闲聊陪伴 Agent
- **数据库**：MySQL
- **第三方服务**：
  - 百度地图 API - 位置服务和路线规划
  - 阿里云百炼（DashScope）- 语音识别（paraformer-realtime-v2），也支持本地 Ollama STT
  - Edge TTS / pyttsx3 - 语音合成

## 🎯 解决的问题

1. **盲道识别与导航**：实时视频分析识别盲道位置和方向变化，帮助视障人士安全行走
2. **实时语音反馈**：检测到方向变化时，自动提供个性化 AI 语音提示
3. **多 Agent 智能助手**：意图路由 + 多 Agent 调度，支持地图导航、系统设置修改、家属消息及日常闲聊
4. **安全监护**：位置共享让家属可远程查看视障人士位置
5. **个性化体验**：自定义语音速度、音量、称呼等参数
6. **无障碍设计**：降低视障人士使用现代城市设施的门槛

## ✨ 功能亮点

- 🎥 **实时视频分析**：YOLO 模型实时识别盲道
- 🔊 **智能语音反馈**：根据用户资料（年龄、性别、称呼、偏好）生成个性化、情境感知的语音提示
- 🤖 **多 Agent 智能助手**：自然语言一句话完成：
  - 🗺️ **地图导航**：位置查询、步行路线规划（专为视障设计）、周边搜索
  - ⚙️ **语音设置**：自然语言修改/查询任何系统设置
  - 📨 **家属消息**：一句话给家属发送位置或状态消息（邮件通知）
  - 💬 **闲聊陪伴**：带完整对话记忆的温暖陪伴
- 👤 **用户系统**：注册、登录、密码找回
- 📍 **位置共享**：实时位置共享，方便家属了解视障人士位置
- ⚙️ **个性化设置**：语音速度、音量、性别、年龄段、称呼等均可自定义
- 🎙️ **语音识别**：支持阿里云百炼云端识别或本地 Ollama，免手操作
- 🎯 **双端模式**：盲人端与家属端两种模式
- 🔧 **灵活 AI 后端**：每位用户可独立切换云端/本地 AI，无需重启服务

<details>
<summary><strong>🤖 多 Agent 智能助手架构</strong></summary>

统一的多 Agent 调度中心（`/chat` 接口），用户只需说一句话，系统自动判断意图并派发给对应 Agent。

```
用户输入
    │
    ▼
RouterAgent（意图分类器）
    │
    ├─ map      ──► MapAgent（ReAct 循环 + 百度地图 MCP）
    │                  └─ 地址解析 → 周边搜索 → 步行路线规划 → 自然语言回答
    │
    ├─ settings ──► SettingsAgent（设置查询 & 修改）
    │                  └─ 理解意图 → 校验字段值 → 写入数据库 → 同步 Session
    │
    ├─ message  ──► 消息处理器（给家属发消息）
    │
    └─ chat     ──► ChatAgent（温暖闲聊，带完整上下文）
```

| Agent | 文件 | 功能 |
|---|---|---|
| RouterAgent | `services/router_agent.py` | 意图分类，路由到对应 Agent |
| MapAgent | `services/deepseek_ai.py` | ReAct 模式地图工具调用，专为视障步行导航优化 |
| SettingsAgent | `services/settings_agent.py` | 自然语言查询/修改系统设置，实时同步数据库与 Session |
| ChatAgent | `routes/chat.py` | 带完整对话上下文的温暖陪伴式闲聊 |

**示例对话：**
- `"帮我把语音速度调成慢"` → SettingsAgent
- `"从上海人民广场到上海博物馆怎么走？"` → MapAgent
- `"给家属说一声我在路上"` → 消息处理器
- `"今天天气真好"` → ChatAgent

</details>

## 🎯 预训练 YOLO 模型

`yolo/best.pt` 为开箱即用的 YOLOv8 盲道检测模型，无需额外训练。`yolo/` 目录包含完整训练指标（混淆矩阵、PR 曲线、F1 曲线等）。

## 📋 环境要求

- Python 3.8+
- MySQL 数据库
- 必要的 Python 库（见 `requirements.txt`）
- 至少配置一种 AI 后端：云端 API 密钥（DeepSeek / OpenAI / DashScope 等）**或**本地运行的 [Ollama](https://ollama.com/) 实例

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

如果您希望使用本地模型而非云端 API，请安装 Ollama 并拉取模型：

```bash
# 访问 https://ollama.com/ 下载并安装 Ollama

ollama pull qwen2.5:3b   # 或任何您偏好的模型
ollama list              # 验证安装
```

Ollama 默认运行在 `http://localhost:11434`，登录后可在 AI 设置面板中选择模型。

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
- **`EMAIL_CONFIG`**：QQ 邮箱 SMTP（用于验证码和家属消息通知）
- **`BAIDU_MAP_CONFIG`**：百度地图 API 密钥
- **`DEEPSEEK_CONFIG`**：默认云端 AI API 密钥（用户未单独配置时使用）
- **`DASHSCOPE_CONFIG`**：阿里云百炼 API 密钥（用于云端语音识别）
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

- **视频分析**：上传视频文件，系统自动分析盲道并在检测到方向变化时播放语音提示。
- **实时导航**：点击"开始导航"，使用摄像头进行实时语音导引。

</details>

<details>
<summary><strong>多 Agent 智能助手</strong></summary>

统一对话入口，直接自然语言提问：

- **地图**：*"从北京站到天安门广场怎么走？"*
- **设置**：*"帮我把语音速度调成慢"* / *"把音量调大一点"*
- **家属消息**：*"帮我发给家属消息：我已经到学校了"*
- **闲聊**：日常对话，带完整上下文记忆

</details>

<details>
<summary><strong>AI 设置</strong></summary>

每位用户可在设置面板独立配置 AI 后端：
- **文本模型**：云端（DeepSeek / OpenAI / DashScope / 自定义 OpenAI 兼容接口）或本地（Ollama）
- **语音识别**：云端（DashScope Paraformer）或本地（Ollama）

修改立即生效，无需重启服务。

</details>

<details>
<summary><strong>位置共享</strong></summary>

视障用户在主界面开启位置共享；家属使用家属账号登录后可在地图上查看实时位置。

</details>

<details>
<summary><strong>系统设置</strong></summary>

可自定义性别、称呼、年龄段、语音速度、音量、用户模式（盲人端/家属端）、鼓励功能开关。点击"测试语音"预览效果后保存。

</details>

## ⚠️ 注意事项

- 至少需要配置一种 AI 后端（云端 API 密钥或本地 Ollama），语音提示和多 Agent 助手才能正常工作。
- 邮件配置用于验证码发送和家属消息通知。
- 地图导航需要有效的百度地图 API 密钥。
- 云端语音识别需要阿里云百炼 API 密钥；也可配置本地 Ollama STT 替代。
- 使用摄像头和位置共享功能时请确保已开启对应权限。

## 📧 联系方式

- **Email**: yfsun.jeff@gmail.com
- **GitHub**: [wink-wink-wink555](https://github.com/wink-wink-wink555)
- **LinkedIn**: [Yifei Sun](https://www.linkedin.com/in/yifei-sun-0bab66341/)
- **Bilibili**: [NO_Desire](https://space.bilibili.com/623490717)

## 🙏 特别感谢

特别感谢以下成员在盲道数据集收集、标注与项目书撰写中提供的帮助：

[Chen Xingyu](https://github.com/guangxiangdebizi) · Wang Youyi · Shen Qian · Liu Yiheng · Zhang Chenshu · Zhang Kai · Sheng Sheng · Cai Yuxin 

## 📁 项目结构

```
blind_navigation/
├── app.py                 # Flask 应用入口
├── config.py              # 配置文件
├── models/
│   └── database.py        # 数据库操作
├── routes/
│   ├── auth.py            # 认证相关路由
│   ├── chat.py            # 多 Agent 调度中心（统一 /chat 入口）
│   ├── main.py            # 主页面路由
│   ├── video.py           # 视频处理路由
│   ├── map.py             # 地图相关路由
│   └── ai_settings.py     # AI 设置路由
├── services/
│   ├── ai_provider.py     # 统一 AI 路由（云端 API ↔ Ollama）
│   ├── baidu_map_mcp.py   # 百度地图 MCP 工具集
│   ├── deepseek_ai.py     # MapAgent（ReAct 模式地图导航）
│   ├── ollama_client.py   # Ollama 客户端封装
│   ├── router_agent.py    # RouterAgent（意图分类路由器）
│   ├── settings_agent.py  # SettingsAgent（设置查询/修改）
│   └── speech_agent.py    # 语音 Agent
├── utils/
│   ├── decorators.py · email_utils.py · video_utils.py · voice_utils.py
├── templates/
│   ├── index.html · login.html · register.html · forget_password.html
└── yolo/
    └── best.pt            # 预训练模型权重（开箱即用）
```

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。Copyright (c) 2025 wink-wink-wink555。

---

⭐ 如果这个项目对您有帮助，欢迎给个 Star！
