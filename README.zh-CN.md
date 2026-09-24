# Blind Navigation (ARIADNE) - 引君出迷津

<div align="center">

<img src="LOGO.png" alt=" Logo" width="350"/>

[English](README.md) | 简体中文

[![Python](https://img.shields.io/badge/Python-3.10%2F3.11-blue.svg)](https://www.python.org/downloads/)
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

视障人士出行辅助系统（ARIADNE）是结合盲道视觉观察、百度地图步行路线与多 Agent 助手的网页演示。实时摄像头报告候选盲道是否可见；路线转向预告依据百度步行路段和实时定位生成，用户仍需自行确认路口、盲道连接情况和过街条件。浏览器将安全提醒、路线预告、经授权的家属语音消息与助手回复汇入同一语音通道，按优先级和消息有效状态调度。系统还提供账户管理、位置共享和自然语言交互。

### 核心技术栈

- **前端**：HTML5, CSS3, JavaScript（原生）
- **后端**：Flask（建议 Python 3.10 / 3.11）
- **AI 模型**：
  - YOLO (You Only Look Once) - 盲道检测
  - **文本 AI 模型**：支持服务器配置的云端接口（DeepSeek、OpenAI、阿里云百炼/Qwen 或其他 OpenAI 兼容服务）与用户选择的本地 Ollama 模型；云端密钥保留在服务器端
  - 多 Agent 智能助手（意图路由、地图问答、设置管理、闲聊陪伴）
- **多 Agent 架构**：
  - RouterAgent - 意图分类路由器
  - MapAgent (ReAct + 百度地图 MCP) - 地图问答 Agent，不接管实时导航
  - SettingsAgent - 结构化提取用户意图并校验后修改设置
  - ChatAgent - 闲聊陪伴 Agent
- **数据库**：MySQL
- **第三方服务**：
  - 百度地图 Web 服务与浏览器 JSAPI - 步行路线、坐标转换和地图展示
  - 阿里云百炼（DashScope）- 云端语音识别；本地语音识别需单独配置 OpenAI 兼容的音频转写服务
  - 浏览器 Web Speech API - 单通道语音输出

## 🎯 解决的问题

1. **盲道观察与步行规划**：YOLO 报告候选盲道是否可见；百度步行路段提供需由用户核对的计划转向
2. **统一语音仲裁**：安全提醒可打断路线、家属与助手播报；导航状态改变后，过时的路线提示自动失效
3. **多 Agent 智能助手**：意图路由与 Agent 调度，支持地图问答、系统设置、向家属发邮件及日常闲聊
4. **家属位置查看**：关联的家属账号可查看用户共享的浏览器位置
5. **个性化体验**：自定义语音速度、音量、称呼等参数
6. **无障碍设计**：降低视障人士使用现代城市设施的门槛

## ✨ 功能亮点

- 🎥 **实时盲道观察**：YOLO 报告候选盲道是否可见，不判断转向安全性
- 🔊 **浏览器语音调度**：安全、路线、家属及助手消息共用按优先级仲裁的语音通道；语速和音量按用户设置播放
- 🤖 **多 Agent 智能助手**：自然语言一句话完成：
  - 🗺️ **地图问答**：位置查询、百度步行路线查询和周边搜索；实时转向预告由导航状态机负责
  - ⚙️ **语音设置**：自然语言查询或修改系统支持的语音及个人资料设置
  - 📨 **向家属发邮件**：通过助手给家属联系人发送位置或状态消息
  - 💬 **闲聊陪伴**：参考近期对话上下文生成回复
- 📨 **家属端语音消息**：经授权的家属账号可向接收者浏览器发送消息，并查询播放状态
- 👤 **用户系统**：注册、登录、密码找回
- 📍 **位置共享**：实时位置共享，方便家属了解视障人士位置
- ⚙️ **个性化设置**：语音速度、音量、性别、年龄段、称呼等均可自定义
- 🎙️ **语音识别**：阿里云百炼云端识别，或使用实现 `/v1/audio/transcriptions` 的本地服务
- 🎯 **双端模式**：盲人端与家属端两种模式
- 🔧 **灵活的文本后端**：每位用户可选择服务器配置的云端文本模型或本地 Ollama 模型，无需重启服务

## 🧭 实时导航与统一语音调度

### 单通道语音仲裁

网页通过浏览器 Web Speech API 播放语音，`static/js/guidance.js` 负责统一排序、打断、恢复和失效判断。各类消息共用以下优先级，数字越小越优先：

| 优先级 | 消息 |
|---|---|
| 0 | 安全提醒 |
| 1 | 步行路线预告 |
| 2 | 经授权的家属端语音消息 |
| 3 | 助手回复 |
| 4 | 背景提示与测试语音 |

更高优先级的消息可以打断当前播报。家属语音消息在仍有效时可从被打断的文本片段继续；路线提示和一般助手播报按各自规则失效或丢弃。事件具有有效期，并可关联导航会话、路线版本和路段：路线停止、重新规划、路段变化或进入不确定状态后，过时的转向提示不会继续播放。重复提示受到去重与节流约束。家属端可以查询消息的入队、播放和结束状态；“已入队”不代表接收者已经听到。助手替用户**向家属发送邮件**与家属端**向用户发送语音消息**是两条不同的流程。

### 配置、验证与适用边界

建议使用 Python 3.10 或 3.11。`BAIDU_MAP_CONFIG['api_key']` 用于后端百度 Web 服务，`BAIDU_MAP_CONFIG['browser_api_key']` 用于浏览器地图 JSAPI，后者应配置允许使用的域名。实时定位与摄像头通常需要 HTTPS 或 localhost、浏览器授权，以及支持 Web Speech 的浏览器；语音须在页面中启用。AI 模型用于助手对话，固定的安全提醒与路线预告不依赖 LLM。

事件队列、导航会话和最近位置保存在当前服务进程内；关闭页面、服务重启或同时打开多个接收页面时，不能保证语音持续播放或只播放一次。地图路线和盲道检测均不能验证信号灯、障碍物、过街安全及盲道实际连通性；本版本是网页演示，不能作为独立的出行辅助设备。

本地回归检查可运行 `python -m unittest discover -s tests` 和 `node tests/test_guidance.js`。这些测试使用模拟的地图与视觉输入，不等同于真实街道验收。

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
| MapAgent | `services/deepseek_ai.py` | ReAct 模式地图问答与步行路线查询，不控制实时转向预告 |
| SettingsAgent | `services/settings_agent.py` | 自然语言查询/修改系统设置，实时同步数据库与 Session |
| ChatAgent | `routes/chat.py` | 使用近期对话上下文与用户资料生成聊天回复 |

**示例对话：**
- `"帮我把语音速度调成慢"` → SettingsAgent
- `"从上海人民广场到上海博物馆怎么走？"` → MapAgent
- `"给家属说一声我在路上"` → 消息处理器
- `"今天天气真好"` → ChatAgent

</details>

## 🎯 预训练 YOLO 模型

仓库包含已训练的盲道检测权重 `yolo/best.pt`，`yolo/` 目录保留训练指标。模型输出候选盲道区域，并未训练为能够判断盲道分支连通性、过街安全或可通行方向。

## 📋 环境要求

- 建议 Python 3.10 或 3.11（依赖中固定的 NumPy 1.24.3 不支持 Python 3.12）
- MySQL 数据库
- 必要的 Python 库（见 `requirements.txt`）
- 使用助手功能需配置云端文本模型密钥，或运行本地 [Ollama](https://ollama.com/) 文本模型；固定的安全提醒与路线预告不需要 LLM
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

如果您希望使用本地模型而非云端 API，请安装 Ollama 并拉取模型：

```bash
# 访问 https://ollama.com/ 下载并安装 Ollama

ollama pull qwen2.5:3b   # 或任何您偏好的模型
ollama list              # 验证安装
```

Ollama 默认运行在 `http://localhost:11434`，登录后可在 AI 设置面板中选择本地文本模型。本地语音识别另需实现 `/v1/audio/transcriptions` 的服务；仅安装 Ollama 文本模型并不能提供音频转写。

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
- **`EMAIL_CONFIG`**：QQ 邮箱 SMTP（用于验证码及助手向家属联系人发送邮件；家属端给用户的浏览器语音消息不经 SMTP）
- **`BAIDU_MAP_CONFIG`**：`api_key` 用于后端 Web 服务，`browser_api_key` 用于地图 JSAPI；后者应设置域名白名单
- **`DEEPSEEK_CONFIG`**：服务器端默认云端文本模型配置；云端密钥不由浏览器提交
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

- **历史视频检测**：上传视频后展示盲道检测框；历史视频不会触发实时导航或语音。
- **实时路线演示**：先启用浏览器语音并获取新鲜、准确的定位，再选择目的地、查看百度步行路线并启动导航。摄像头为可选观察来源；盲道观察不可用时可暂停路线预告。路口与过街条件需由用户自行核对。
- **手动起点**：在地图上手动选点只能预览路线；实时导引需要有效的浏览器定位。

</details>

<details>
<summary><strong>多 Agent 智能助手</strong></summary>

统一对话入口，直接自然语言提问：

- **地图**：*"从北京站到天安门广场怎么走？"*
- **设置**：*"帮我把语音速度调成慢"* / *"把音量调大一点"*
- **家属消息**：*"帮我发给家属消息：我已经到学校了"*
- **闲聊**：日常对话，参考近期上下文

</details>

<details>
<summary><strong>AI 设置</strong></summary>

用户可在 AI 设置面板切换服务器配置的云端服务与本地服务。云端密钥由服务器配置；面板可选择本地接口地址与模型：
- **文本模型**：服务器配置的云端接口（DeepSeek / OpenAI / DashScope/Qwen 或其他兼容服务），或本地 Ollama 模型
- **语音识别**：云端 DashScope，或实现 OpenAI 兼容音频转写接口的本地服务

修改立即生效，无需重启服务。

</details>

<details>
<summary><strong>位置共享</strong></summary>

视障用户允许浏览器定位并保持页面打开后，关联的家属账号可以在地图上查看最近一次共享的位置；过期位置会标注为过期。

</details>

<details>
<summary><strong>系统设置</strong></summary>

可自定义性别、称呼、年龄段、语音速度、音量、用户模式（盲人端/家属端）、鼓励功能开关。点击"测试语音"预览效果后保存。

</details>

## ⚠️ 注意事项

- 助手对话需要文本 AI 后端；固定的安全提醒和步行路线预告不依赖 LLM。
- SMTP 配置用于验证码及助手向家属发邮件；经授权的家属端向用户发送浏览器语音消息使用语音事件通道。
- 步行路线与地图展示分别需要百度 Web 服务 AK 和设置了域名白名单的浏览器 JSAPI AK。
- 云端语音识别需要 DashScope API 密钥；本地语音识别需要可用的 `/v1/audio/transcriptions` 服务，仅有 Ollama 文本模型并不足够。
- 实时导航需要新鲜的浏览器定位；摄像头是可选盲道观察来源。定位与摄像头通常需要 HTTPS 或 localhost 及相应授权；浏览器语音播放时需保持支持 Web Speech 的页面打开。

## 📧 联系方式

- **Email**: yfsun.jeff@gmail.com
- **GitHub**: [wink-wink-wink555](https://github.com/wink-wink-wink555)
- **LinkedIn**: [Yifei Sun](https://www.linkedin.com/in/yifei-sun-0bab66341/)
- **Bilibili**: [NO_Desire](https://space.bilibili.com/623490717)

## 🙏 特别感谢

特别感谢以下成员在盲道数据集收集、标注与项目书撰写中提供的帮助：

[Chen Xingyu](https://github.com/guangxiangdebizi) · Wang Youyi · Shen Qian · Liu Yiheng · Zhang Chenshu · Zhang Kai · Sheng Sheng · Cai Yuxin 

## 📁 项目结构

以下列出主要文件；`config.py` 由配置模板在本地生成，不提交到仓库。

```
blind_navigation/
├── app.py                    # Flask 应用入口
├── config.example.py         # 配置模板；复制为 config.py
├── models/
│   └── database.py           # 数据库操作
├── routes/
│   ├── auth.py               # 账户认证
│   ├── chat.py               # 多 Agent /chat 入口
│   ├── main.py               # 主页面、设置与家属端语音消息
│   ├── video.py              # 历史视频检测展示
│   ├── map.py                # 地图相关接口
│   ├── ai_settings.py        # AI 设置接口
│   └── guidance.py           # 实时导航、视觉观察和事件流
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
│   ├── navigation.py         # 导航状态机
│   └── vision_observer.py    # 盲道可见性观察
├── static/js/
│   ├── guidance.js           # 浏览器语音调度器
│   └── navigation_ui.js      # 定位、地图、摄像头与事件接入
├── tests/
│   ├── test_guidance.js      # 语音调度场景
│   ├── test_http_guidance.py # HTTP 接口边界场景
│   └── test_navigation.py    # 导航状态与事件场景
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
