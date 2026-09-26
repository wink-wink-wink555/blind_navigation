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

视障人士出行辅助系统（ARIADNE）融合实时盲道视觉感知、百度地图步行路线、浏览器定位与多 Agent 智能助手，为视障用户提供从宏观路线规划到局部盲道对齐的多层次导航辅助。实时摄像头通过 YOLO 检测候选盲道区域，近场几何层进一步估计盲道相对用户视觉参考中心的横向位置；导航状态机结合多帧观测、迟滞阈值和路线上下文，将稳定偏离转换为简洁的“稍向左靠 / 稍向右靠”微纠偏提示。当纠偏提示进入播放并且后续观测确认用户稳定回正后，系统可给出一次低优先级正反馈。

百度地图步行路线与实时 GPS 负责“沿哪条路线前进、何时预计转弯”的宏观导航，视觉模块负责当前路线上下文中的局部盲道对齐，两者职责分离。接近计划转弯、进入过街场景、视觉几何不确定、盲道丢失或偏离过大时，路线状态与安全状态优先于普通微纠偏。浏览器将安全提醒、横向纠偏、路线预告、经授权的家属语音消息、助手回复和背景反馈汇入同一语音通道，并依据优先级、有效期、导航上下文和对齐状态版本统一调度。

### 核心技术栈

- **前端**：HTML5, CSS3, JavaScript（原生）
- **后端**：Flask（建议 Python 3.10 / 3.11）
- **AI / 视觉模型**：
  - YOLO (You Only Look Once) - 候选盲道区域检测；左右纠偏方向由几何估计层与导航状态层进一步推导
  - `PathGeometryEstimator` - 基于现有 YOLO 检测框进行近场候选筛选、横向中心估计与几何置信度计算
  - `NavigationManager` Alignment State Machine - 基于连续视觉观测、迟滞阈值和导航上下文生成保守的局部对齐提示
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

1. **盲道观察、局部对齐与步行规划**：YOLO 检测候选盲道区域，近场几何估计与时间状态机进一步判断用户是否出现稳定横向偏离；百度步行路线和 GPS 独立负责宏观路径与计划转向
2. **统一语音仲裁与时效控制**：安全、横向纠偏、路线、家属、助手和背景反馈共享一个语音调度器；导航状态、路线版本、路段或对齐状态发生变化后，旧提示会依据上下文版本立即淘汰
3. **多 Agent 智能助手**：意图路由与 Agent 调度，支持地图问答、系统设置、向家属发邮件及日常闲聊
4. **家属位置查看**：关联的家属账号可查看用户共享的浏览器位置
5. **个性化体验**：自定义语音速度、音量、称呼等参数
6. **无障碍设计**：降低视障人士使用现代城市设施的门槛

## ✨ 功能亮点

- 🎥 **实时盲道观察与横向对齐**：YOLO 检测候选盲道区域，并在 50%–90% 画面高度的近场区域内评估检测框几何关系，通过归一化横向偏移、时间窗口与迟滞阈值识别稳定的左/右偏离
- 🧭 **宏观路线与微观纠偏分层**：百度步行路线和 GPS 决定路线步骤及计划转向；视觉对齐仅在正常导航、远离计划路口且不存在过街风险时提供局部微纠偏
- 🔁 **纠偏闭环反馈**：一次稳定偏离形成一个 correction episode；提示按 episode 去重与节流，用户稳定回正且纠偏语音进入播放后，系统最多给出一次低优先级正反馈
- 🛑 **保守退化机制**：严重偏离、连续盲道丢失、视觉几何冲突、摄像头中断或过街场景会进入显式不确定或安全状态，暂停微纠偏并按状态给出确认提示
- 🔊 **浏览器语音调度**：安全、横向纠偏、路线、家属、助手和背景消息共用按优先级仲裁的单一语音通道；语速和音量按用户设置播放
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

## 🧭 实时导航、盲道对齐与统一语音调度

### 宏观路线与微观对齐

实时引导由两个职责不同的层次共同组成：

```text
百度步行路线 + GPS
        │
        ▼
宏观导航 NavigationManager
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
                  近场中心 / 横向偏移 / 置信度
                               │
                               ▼
                    Alignment State Machine
                               │
             时间滤波 / 迟滞 / Episode / Gating
                               │
                               ▼
                         横向纠偏提示
```

百度路线回答“接下来沿哪条路走、什么时候预计转弯”；YOLO 和近场几何估计回答“当前候选盲道相对用户参考中心位于哪里”。路口拓扑、路线切换与过街上下文由地图和导航状态层负责，视觉几何层专注于局部横向对齐。

### 盲道横向对齐

横向对齐流程复用现有 `yolo/best.pt` 检测器，并在检测框输出之上增加独立的几何估计层。`services/vision_observer.py` 获取候选盲道检测框，`services/path_alignment.py` 在其上执行近场横向几何估计。

几何估计优先使用画面高度约 50%–90% 的近场区域，而不是直接采用完整 bounding box 的中心。候选检测综合考虑 YOLO 置信度、与近场区域的重叠程度、靠近画面底部的程度及连续帧一致性；多个强候选在水平方向明显冲突时返回 `AMBIGUOUS`，由导航层进入对应的不确定状态处理。

几何估计的 temporal state 只属于一个连续视觉流。实时导航按用户维护独立 tracker，并在导航开始、重新规划、停止或摄像头中断时显式 reset；历史视频的每个 MJPEG reader 也拥有独立 tracker。通过这种视觉流隔离，上一帧中心位置始终只服务于当前实时摄像头或当前历史视频 reader。

系统定义归一化横向偏移：

`normalized_offset = (path_center_x - reference_center_x) / image_width`

其中正值表示候选盲道位于用户参考中心右侧，需要 `CORRECT_RIGHT`；负值表示位于左侧，需要 `CORRECT_LEFT`。当前默认参考中心为图像中心，代码保留了未来摄像头安装校准的接口。

语音决策依赖多帧时间一致性，而不是单个视觉帧。导航状态机维护最近的有效偏移，使用时间窗口和迟滞阈值形成第二层 Alignment State：

`UNKNOWN / CENTERED / CORRECT_LEFT / CORRECT_RIGHT / RECOVERING / SEVERE / NOT_VISIBLE / AMBIGUOUS / SUPPRESSED`

只有连续多帧出现方向一致的稳定偏离时才建立 correction episode 并发出一次主要纠偏提示，例如“盲道在右侧，稍向右靠。”短暂抖动和单帧异常保持静默。偏移开始改善时进入恢复阶段；连续多帧重新进入中心区域后，系统会先切换到新的 `CENTERED` alignment epoch，再根据播放回执决定是否生成低优先级正反馈。这样“很好，位置已经回正，继续保持。”与新的 CENTERED 状态属于同一个 epoch，并在同一上下文版本中保持有效。

当偏移连续达到严重阈值时，系统升级为安全提示：“与盲道位置偏差较大，请停下重新确认路径。”，普通微纠偏在对齐状态恢复前保持暂停。

### 导航上下文保护

局部横向对齐只允许在 `NAVIGATING` 状态运行，并受宏观导航状态约束。

接近下一次计划转向约 12 米以内时，对齐状态进入 `SUPPRESSED`，因为此时盲道在画面中向左或向右移动可能来自道路本身转弯，而不是用户走偏。若下一步涉及过街，则已有的过街安全流程取得优先级。定位不可靠、摄像头中断、连续未检测到盲道或导航进入其他不确定状态时，对齐层也会切换到对应的 gated state。

因此，百度路线负责宏观路线决策，视觉管线负责当前路线上下文中的局部脚下对齐。

### 实时帧处理与时效判定

浏览器采用 latest-frame processing：上一帧完成服务器推理并返回结果后，才安排下一帧，因此同时最多只有一个视觉请求在处理中，从源头控制网络与推理队列中的旧帧积压。

实时请求携带单调递增的 `frame_seq` 和浏览器采集时间。Flask 接口在收到请求时另外记录自己的 `server_received_at_ms`，`NavigationManager` 的实时 freshness 判断使用服务器侧接收/处理时间。浏览器采集时间保留用于调试展示，steering 时效统一以服务器时钟为基准。

后端通过 frame sequence 防止乱序结果回滚当前对齐状态。超过服务器侧时效阈值的视觉结果进入仅调试路径，新鲜观测进入 steering 管线。页面还提供调试状态，可查看视觉状态、几何状态、Alignment State、归一化偏移、几何置信度、候选数量、帧序号和端到端延迟。

### 单通道语音仲裁

网页通过浏览器 Web Speech API 播放语音，`static/js/guidance.js` 统一负责排序、打断、恢复和失效判断。数字越小优先级越高：

| 优先级 | 消息 |
|---|---|
| 0 | 安全提醒 |
| 1 | 盲道横向纠偏 |
| 2 | 步行路线预告 |
| 3 | 经授权的家属端语音消息 |
| 4 | 助手回复 |
| 5 | 背景提示、正反馈与测试语音 |

更高优先级事件可以打断较低优先级播放。横向纠偏提示具有约 3 秒的短 TTL，并采用 `discard` 恢复策略，使方向提示随着对齐上下文变化快速失效。

除了导航会话、路线版本和路段之外，实时纠偏事件还绑定 `alignment_epoch`。Alignment State 改变时 epoch 增加，浏览器会自动移除或中断属于旧 epoch 的纠偏事件，从而避免“用户已经回正，却又听到几秒前的左/右提示”。恢复正反馈在进入新的 CENTERED epoch 后生成，与恢复后的上下文版本保持一致。

家属语音消息按照独立恢复策略播放，并通过 `QUEUED`、`PLAYING`、`PAUSED`、`FINISHED`、`FAILED`、`CANCELLED` 等回执状态表达投递进度。助手替用户**向家属发送邮件**与家属端**向用户发送浏览器语音消息**仍是两条独立流程。

### Alignment 默认参数

以下参数是当前系统实现采用的初始工程值，并集中用于不同摄像头安装方式、行走速度与运行环境下的后续校准：

| 参数 | 当前值 | 作用 |
|---|---:|---|
| Near-field ROI | `0.50H–0.90H` | 优先关注用户即将经过的近场区域 |
| Evaluation row | `0.70H` | 估计近场盲道中心的位置 |
| Geometry minimum confidence | `0.35` | 过滤低置信度检测 |
| Centered threshold | `0.07` | `abs(offset) <= 0.07` 视为中心区域 |
| Correction threshold | `0.12` | 稳定超过该值才考虑微纠偏 |
| Severe threshold | `0.22` | 连续严重偏离时升级安全提示 |
| Alignment history | `5` 帧 | 保存最近有效横向偏移 |
| Consistency window | `4` 帧 | 判断方向一致性的时间窗口 |
| Required consistent frames | `3` 帧 | 至少 3 帧一致才建立纠偏 |
| Recovery frames | `3` 帧 | 连续回到中心后确认恢复 |
| Severe frames | `3` 帧 | 连续严重偏离后升级 |
| Turn suppression distance | `12 m` | 靠近计划转弯时暂停微纠偏 |
| Correction repeat interval | `10 s` | 同一 episode 的保守重复间隔 |
| Praise cooldown | `20 s` | 正反馈最短间隔 |
| Alignment speech TTL | `3 s` | 过时左右指令快速失效 |
| Server-observed stale-frame threshold | `1.5 s` | 服务器侧过旧视觉结果不参与 steering |
| Camera scheduling | `350 ms / 700 ms` | 正常 / 高延迟情况下的下一帧调度等待 |

这些参数集中定义在 `services/path_alignment.py`、`services/navigation.py` 和 `static/js/navigation_ui.js` 中，便于后续通过真实设备与道路数据继续校准。

### 配置、验证与实现说明

建议使用 Python 3.10 或 3.11。`BAIDU_MAP_CONFIG['api_key']` 用于后端百度 Web 服务，`BAIDU_MAP_CONFIG['browser_api_key']` 用于浏览器地图 JSAPI，后者应配置允许使用的域名。实时定位与摄像头通常需要 HTTPS 或 localhost、浏览器授权，以及支持 Web Speech 的浏览器；语音在页面中主动启用。AI 文本模型服务助手对话，安全提醒、路线预告和横向纠偏由确定性的导航逻辑生成。

横向对齐方法基于 YOLO axis-aligned bounding boxes，输出近场、相对图像参考中心的横向估计。摄像头朝向定义视觉参考系；当前默认使用图像中心，并为后续摄像头安装标定保留 reference-center 接口。路口处理、路线切换与过街行为由百度路线上下文和 `NavigationManager` 协同控制。

事件队列、导航会话和最近位置保存在当前服务进程内，对应当前单进程 Flask 部署模型。本地回归检查可运行 `python -m unittest discover -s tests` 和 `node tests/test_guidance.js`。测试覆盖近场几何、视觉流隔离、时间连续性、迟滞、correction episode、恢复正反馈、路口抑制、过街 gating、严重偏离、乱序/服务器侧过期帧、客户端/服务器时钟偏差以及语音 epoch 失效。

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

仓库包含已训练的盲道检测权重 `yolo/best.pt`，`yolo/` 目录保留训练与评估材料。检测器输出候选盲道 bounding boxes，路线拓扑与导航上下文由地图和状态机层负责。

横向对齐能力建立在检测框之上的独立几何估计与状态控制层：`services/path_alignment.py` 从近场候选区域估计盲道中心和归一化横向偏移，`services/navigation.py` 再结合连续帧、迟滞阈值、路线状态和语音生命周期决定是否给出纠偏。因此，“横向纠偏”属于上层感知与状态控制能力，而不是 YOLO 模型新增的方向类别。

## 📋 环境要求

- 建议 Python 3.10 或 3.11，以匹配当前固定的 NumPy 1.24.3 依赖环境
- MySQL 数据库
- 必要的 Python 库（见 `requirements.txt`）
- 使用助手功能需配置云端文本模型密钥，或运行本地 [Ollama](https://ollama.com/) 文本模型；固定的安全提醒、路线预告和横向纠偏不需要 LLM
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

Ollama 默认运行在 `http://localhost:11434`，登录后可在 AI 设置面板中选择本地文本模型。本地语音识别使用独立的 `/v1/audio/transcriptions` 服务，Ollama 负责本地文本模型后端。

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

- **历史视频检测**：上传视频后展示 YOLO 候选盲道检测框；历史视频使用与实时导航完全隔离的 geometry tracker，负责独立的视觉检测与几何观察。
- **实时路线导航**：先启用浏览器语音并获取新鲜、准确的定位，再选择目的地、查看百度步行路线并启动导航。启用实时摄像头后，系统在满足安全条件的直线路段内估计近场盲道横向偏移；时间状态确认稳定偏离后会提示“稍向左靠 / 稍向右靠”。
- **恢复反馈**：一次纠偏提示进入实际播放后，如果后续连续视觉观测确认用户重新回到中心区域，系统先进入新的 CENTERED epoch，再可播放一次低优先级正反馈；反馈以 correction episode 为单位并受 cooldown 控制，使播报保持简洁。
- **路口与过街**：接近计划转弯和过街场景时，路线上下文与安全状态优先于普通横向纠偏；视觉不确定、严重偏离或盲道丢失也进入对应的安全状态处理。
- **手动起点**：在地图上手动选点用于路线预览；实时导引使用新鲜的浏览器定位。

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

## 🧩 实现说明

- 助手对话使用配置的文本 AI 后端；安全提醒、百度路线预告和盲道横向纠偏由确定性的导航逻辑生成。
- SMTP 负责验证码与助手向家属发送邮件；经授权的家属端向用户发送浏览器语音消息使用独立的语音事件通道。
- 步行路线与地图展示分别使用百度 Web 服务 AK 和设置域名白名单的浏览器 JSAPI AK。
- 云端语音识别使用 DashScope；本地语音识别使用独立的 `/v1/audio/transcriptions` 服务，Ollama 负责本地文本模型后端。
- 实时路线导航使用新鲜的浏览器 GPS；盲道横向对齐进一步使用实时摄像头。定位与摄像头通常需要 HTTPS 或 localhost 及对应浏览器授权。
- 横向对齐基于 YOLO bounding boxes，在检测器之上结合近场几何估计、时间滤波与路线状态，输出相对图像参考中心的方向和归一化横向偏移。
- 摄像头朝向定义视觉参考中心。当前默认以图像中心作为参考，并保留 reference-center 接口用于摄像头安装标定。
- 浏览器采集时间保留用于调试；实时 steering freshness 以服务器生成的时间戳为基准。
- 计划转弯、过街、视觉几何不确定、盲道丢失和严重偏离均通过显式的路线状态与安全状态进入语音调度。

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
