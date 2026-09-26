# Blind Navigation (ARIADNE) - Your Way Out of the Labyrinth

<div align="center">

  <img src="LOGO.png" alt=" Logo" width="350"/>

English | [简体中文](README.zh-CN.md)

[![Python](https://img.shields.io/badge/Python-3.10%2F3.11-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/wink-wink-wink555/blind_navigation.svg)](https://github.com/wink-wink-wink555/blind_navigation/stargazers)

</div>

> 📹 Project Videos: [Project Showcase I](https://www.bilibili.com/video/BV1kD57zGE68), [Project Showcase II](https://openatom.tech/enterprise-ai/614b385486d53533dd74f9428aa83087/blob/master/A_%E9%A1%B9%E7%9B%AE%E6%BC%94%E7%A4%BA%E8%A7%86%E9%A2%91.mp4)

<div align="center">
  <img src="Graph.png" alt="Graph">
</div>

<details>
<summary><strong>🏆 HONORS & AWARDS</strong>  <em>(Click to expand)</em></summary>

- **Jan 2026** | **Top 10**, Intel Platform Corporate AI Solution Innovation Practice Competition (Global Finals)
- **Dec 2025** | **Top 20**, Intel Platform Corporate AI Solution Innovation Practice Competition (Preliminary Round) — *Advanced to Global Finals*
- **Aug 2025** | **Third Prize (National Level)**, Chinese Collegiate Computing Competition (CCCC)
- **May 2025** | **First Prize (Provincial Level)**, Shanghai Computer Application Competence Competition for College Students

</details>

---

## 🌟 Introduction

ARIADNE is an assistive navigation system for visually impaired users that integrates tactile-paving perception, Baidu walking routes, browser geolocation, real-time voice guidance, family interaction, and a multi-agent assistant.

The system separates macro navigation from local perception. Baidu walking routes and GPS provide route steps, turn context, and position updates; the vision pipeline detects tactile paving and estimates local alignment; `NavigationManager` combines route context and visual observations before issuing guidance. Safety alerts, route advisories, local alignment prompts, family messages, assistant replies, and background feedback share a unified browser speech channel with explicit priority and validity control.

Beyond navigation, ARIADNE provides a multi-agent natural-language interface for map questions, system settings, family communication, and companion chat, together with account management, location sharing, speech recognition, cloud/local model selection, and personalized voice settings.

### Tech Stack

- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Backend**: Flask (Python 3.10 / 3.11 recommended)
- **Vision & Navigation**:
  - YOLO - tactile-paving candidate detection
  - `PathGeometryEstimator` - near-field lateral geometry estimation
  - `NavigationManager` - route-aware navigation and alignment state control
- **AI Text Model**: server-configured cloud APIs (DeepSeek, OpenAI, DashScope/Qwen, or another OpenAI-compatible service) or a user-selected local Ollama model
- **Multi-Agent Architecture**:
  - RouterAgent - intent classification and routing
  - MapAgent (ReAct + Baidu Map MCP) - map Q&A and route lookup
  - SettingsAgent - validated natural-language settings updates
  - ChatAgent - companion chat
- **Database**: MySQL
- **Third-party Services**:
  - Baidu Map Web Service and browser JSAPI - walking routes, coordinate conversion, and map display
  - DashScope - cloud speech recognition
  - Browser Web Speech API - speech output

## 🎯 Problems Solved

1. **Real-time Assistive Navigation**: combines tactile-paving perception, browser GPS, Baidu walking routes, and route-aware local alignment
2. **Stateful Voice Guidance**: coordinates safety, route, alignment, family, assistant, and background events through one speech scheduler
3. **Multi-Agent AI Assistant**: routes natural-language requests across map Q&A, settings, family communication, and companion chat
4. **Family Interaction**: linked family accounts can receive user information, send browser voice messages, and view shared location
5. **Personalized Experience**: configurable voice speed, volume, preferred name, user mode, and AI backend
6. **Accessibility-oriented Interaction**: combines voice, navigation, visual perception, and family support in one system

## ✨ Key Features

- 🧭 **Real-time Assistive Navigation**: Baidu walking routes and GPS provide macro-level route context, while live vision supplies local tactile-paving observations and alignment cues
- 🎥 **Live Tactile-Paving Perception**: YOLO detection is combined with near-field geometry and temporal state estimation before local guidance is generated
- 🔊 **Stateful Voice Guidance**: one browser speech scheduler handles safety, route, alignment, family, assistant, and background messages with priority, TTL, interruption, and context invalidation
- 🤖 **Multi-Agent AI Assistant**:
  - 🗺️ map questions and route lookup through MapAgent + Baidu Map MCP
  - ⚙️ natural-language system and voice settings
  - 📨 family communication
  - 💬 companion chat with recent context
- 📨 **Family Voice Messages**: authorized family accounts can send browser voice messages and query playback progress
- 📍 **Location Sharing**: linked family accounts can view the user's latest shared location
- 🎙️ **Speech-to-Text**: DashScope cloud recognition or a local `/v1/audio/transcriptions` service
- 🔧 **Cloud / Local AI Backends**: server-configured cloud providers or local Ollama models
- 👤 **User System**: registration, login, password recovery, settings, and user-mode management

## 🤖 Multi-Agent Architecture

The `/chat` endpoint acts as a unified dispatch center. A user message is classified and routed to the appropriate capability while live navigation remains under the deterministic navigation pipeline.

```text
User Input
    │
    ▼
RouterAgent
    │
    ├─ map      ──► MapAgent (ReAct + Baidu Map MCP)
    │                  └─ Geocoding → Nearby search → Walking route → Natural-language reply
    │
    ├─ settings ──► SettingsAgent
    │                  └─ Parse intent → Validate → Write DB → Sync session
    │
    ├─ message  ──► Family Message Handler
    │
    └─ chat     ──► ChatAgent
```

| Agent | File | Responsibility |
|---|---|---|
| RouterAgent | `services/router_agent.py` | Intent classification and routing |
| MapAgent | `services/deepseek_ai.py` | ReAct map Q&A and walking-route lookup |
| SettingsAgent | `services/settings_agent.py` | Natural-language settings query and modification |
| ChatAgent | `routes/chat.py` | Companion chat with recent conversation context and user profile |

**Example Interactions**
- `"Set my voice speed to slow"` → SettingsAgent
- `"How do I walk from Tiananmen Square to the National Museum?"` → MapAgent
- `"Send my family a message: I've arrived"` → Family message handler
- `"What a nice day today"` → ChatAgent

## 🧭 Navigation & Guidance Architecture

### Macro route and local perception

ARIADNE separates route planning from local tactile-paving perception:

```text
Baidu Walking Route + GPS
            │
            ▼
      NavigationManager
 route steps / turns / deviation / crossings
            │
            ├────────────────────────┐
            │                        │
            ▼                        ▼
      Route Advisories          Live Camera
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
                           Local Guidance
```

Baidu routing owns macro-level route decisions. The vision pipeline provides local tactile-paving observations inside the active route context. Planned turns, crossings, vision uncertainty, paving loss, and severe deviation are represented explicitly in navigation state so guidance can switch behavior according to context.

### Tactile-path alignment

`services/vision_observer.py` obtains candidate tactile-paving detections and `services/path_alignment.py` estimates near-field lateral geometry. The estimator focuses on the lower part of the image, scores candidates using detection confidence and near-field geometry, and keeps temporal state scoped to each visual stream.

A normalized lateral offset is used to represent the paving position relative to the visual reference center:

`normalized_offset = (path_center_x - reference_center_x) / image_width`

`NavigationManager` combines recent observations with temporal consistency and hysteresis before creating a correction episode. Stable deviation may produce a concise left/right prompt; stable recentering can close the episode and trigger brief positive feedback. Near planned turns, crossings, ambiguous observations, or severe deviation, route-context and safety states take precedence over ordinary micro-corrections.

### Frame processing

The live camera uses latest-frame processing with one request in flight. Monotonic frame sequences and server-side freshness timestamps prevent stale or out-of-order observations from affecting the current guidance state. Runtime diagnostics expose geometry state, confidence, frame sequence, and latency for tuning and observability.

### Unified speech arbitration

`static/js/guidance.js` owns speech ordering, interruption, expiry, and context validity.

| Priority | Message |
|---|---|
| 0 | Safety alerts |
| 1 | Tactile-path alignment |
| 2 | Walking-route advisories |
| 3 | Authorized family voice messages |
| 4 | Assistant replies |
| 5 | Background hints, positive feedback, and voice tests |

Events can carry TTLs and navigation/alignment context versions. When the active route or alignment state changes, queued speech tied to older context is invalidated. Family voice messages use their own recovery behavior and playback receipts.

<details>
<summary><strong>Alignment Parameters</strong></summary>

| Parameter | Current value | Purpose |
|---|---:|---|
| Near-field ROI | `0.50H–0.90H` | Focus on near-field paving |
| Evaluation row | `0.70H` | Estimate near-field path center |
| Geometry minimum confidence | `0.35` | Filter weak detections |
| Centered threshold | `0.07` | Centered band |
| Correction threshold | `0.12` | Stable correction entry threshold |
| Severe threshold | `0.22` | Severe-deviation threshold |
| Alignment history | `5` frames | Recent valid lateral observations |
| Consistency window | `4` frames | Direction-consistency window |
| Required consistent frames | `3` frames | Frames required before correction |
| Recovery frames | `3` frames | Centered frames required for recovery |
| Severe frames | `3` frames | Severe frames required before escalation |
| Turn suppression distance | `12 m` | Pause local alignment near planned turns |
| Correction repeat interval | `10 s` | Repeat control within one episode |
| Positive-feedback cooldown | `20 s` | Feedback cooldown |
| Alignment speech TTL | `3 s` | Short-lived steering guidance |
| Server-observed stale-frame threshold | `1.5 s` | Freshness threshold |
| Camera scheduling | `350 ms / 700 ms` | Normal / high-latency capture delay |

The constants are grouped in `services/path_alignment.py`, `services/navigation.py`, and `static/js/navigation_ui.js`.

</details>

## 🎯 Pre-trained YOLO Model

The repository includes trained tactile-paving detection weights at `yolo/best.pt` together with training and evaluation artifacts in `yolo/`.

YOLO supplies candidate tactile-paving bounding boxes. `services/path_alignment.py` derives near-field geometry from those detections, and `services/navigation.py` combines geometry with route context and temporal state before producing guidance.

## 📋 Requirements

- Python 3.10 or 3.11 recommended for compatibility with the pinned NumPy 1.24.3 environment
- MySQL Database
- Required Python libraries (see `requirements.txt`)
- A cloud text-model key or local [Ollama](https://ollama.com/) model for assistant features
- Baidu Web Service and browser JSAPI keys, plus browser geolocation permission, for live walking-route guidance

## 🚀 Installation

<details>
<summary><strong>1. Clone Repository</strong></summary>

```bash
git clone https://github.com/wink-wink-wink555/blind_navigation.git
cd blind_navigation
```

</details>

<details>
<summary><strong>2. Create Virtual Environment (Recommended)</strong></summary>

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

</details>

<details>
<summary><strong>3. Install Dependencies</strong></summary>

```bash
pip install -r requirements.txt
```

</details>

<details>
<summary><strong>4. (Optional) Install Ollama for Local AI</strong></summary>

If you prefer running AI models locally instead of cloud APIs, install Ollama and pull a model:

```bash
# Visit https://ollama.com/ to download and install Ollama

ollama pull qwen2.5:3b
ollama list
```

Ollama runs on `http://localhost:11434` by default. You can select a local text model in AI Settings after logging in. Local speech recognition uses a separate service implementing `/v1/audio/transcriptions`.

</details>

<details>
<summary><strong>5. Database Setup</strong></summary>

```sql
CREATE DATABASE blind_navigation CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

The application will automatically create required tables on first run.

</details>

<details>
<summary><strong>6. Configuration</strong></summary>

```bash
cp config.example.py config.py  # Linux/Mac
copy config.example.py config.py  # Windows
```

Edit `config.py`:

- **`DB_CONFIG`**: MySQL host, user, password, etc.
- **`EMAIL_CONFIG`**: QQ email SMTP for verification codes and assistant-sent emails to family contacts
- **`BAIDU_MAP_CONFIG`**: `api_key` for server-side Web Service and `browser_api_key` for map JSAPI
- **`DEEPSEEK_CONFIG`**: server-side default cloud text-model settings
- **`DASHSCOPE_CONFIG`**: DashScope API key for cloud speech-to-text
- **`MODEL_WEIGHTS`**: set to `'yolo/best.pt'`

</details>

## 🏃 Running the Application

```bash
python app.py
```

Visit http://127.0.0.1:5000/

## 📖 Usage Guide

<details>
<summary><strong>Account Management</strong></summary>

Register with username, password, and email. Login and password reset are also supported.

</details>

<details>
<summary><strong>Tactile Paving Navigation</strong></summary>

- **Recorded Video**: Upload a recording to display YOLO tactile-paving detections.
- **Live Navigation**: Enable browser speech, obtain a fresh GPS fix, choose a destination, inspect the Baidu walking route, and activate navigation.
- **Live Camera Alignment**: When the live camera is enabled, the system can add local tactile-path alignment guidance to the active route.
- **Recovery Feedback**: Stable recovery after a correction can trigger brief positive feedback.
- **Turns and Crossings**: Route context and safety states take precedence over local alignment around planned turns, crossings, or uncertain visual states.
- **Manual Origin**: A manually selected origin supports route preview; live guidance uses browser geolocation.

</details>

<details>
<summary><strong>Multi-Agent AI Assistant</strong></summary>

One unified chat interface:

- **Map**: *"How do I walk from Beijing Railway Station to Tiananmen Square?"*
- **Settings**: *"Set my voice speed to slow"*
- **Family Message**: *"Send my family a message: I've arrived at school"*
- **Chat**: everyday conversation with recent context

</details>

<details>
<summary><strong>AI Settings</strong></summary>

Users can switch between server-configured cloud models and local deployments:
- **Text model**: DeepSeek / OpenAI / DashScope-Qwen / compatible cloud service / local Ollama
- **Speech-to-text**: cloud DashScope or a local OpenAI-compatible transcription endpoint

Changes take effect without restarting the server.

</details>

<details>
<summary><strong>Location Sharing</strong></summary>

Visually impaired users can share their latest browser location with linked family accounts.

</details>

<details>
<summary><strong>System Settings</strong></summary>

Customize preferred name, age group, voice speed, volume, user mode, and encouragement settings.

</details>

## 🧩 Implementation Notes

- Assistant conversations use the configured text-model backend; navigation and guidance are generated by deterministic navigation logic.
- SMTP handles verification codes and assistant-sent emails to family contacts; family-to-user browser voice messages use the speech-event channel.
- Walking routes and map rendering use Baidu Web Service and browser JSAPI keys.
- Cloud speech recognition uses DashScope; local speech recognition uses `/v1/audio/transcriptions`.
- Live navigation uses browser GPS and optionally the live camera for local tactile-path alignment.
- The current runtime keeps navigation sessions, event state, and recent positions in the Flask process.
- Local regression checks: `python -m unittest discover -s tests` and `node tests/test_guidance.js`.

## 📧 Contact

- **Email**: yfsun.jeff@gmail.com
- **GitHub**: [wink-wink-wink555](https://github.com/wink-wink-wink555)
- **LinkedIn**: [Yifei Sun](https://www.linkedin.com/in/yifei-sun-0bab66341/)
- **Bilibili**: [NO_Desire](https://space.bilibili.com/623490717)

## 🙏 Acknowledgments

Special thanks to the following members for their contributions to the tactile paving dataset collection, annotation, and project proposal:

[Chen Xingyu](https://github.com/guangxiangdebizi) · Wang Youyi · Shen Qian · Liu Yiheng · Zhang Chenshu · Zhang Kai · Sheng Sheng · Cai Yuxin

## 📁 Project Structure

The following lists the main files; `config.py` is created locally from the template.

```text
blind_navigation/
├── app.py                    # Flask application entry point
├── config.example.py         # Configuration template; copy to config.py
├── models/
│   └── database.py           # Database operations
├── routes/
│   ├── auth.py               # Authentication routes
│   ├── chat.py               # Multi-Agent /chat endpoint
│   ├── main.py               # Main page, settings, and family voice messages
│   ├── video.py              # Recorded-video detection with isolated geometry streams
│   ├── map.py                # Map-related routes
│   ├── ai_settings.py        # AI settings routes
│   └── guidance.py           # Live navigation, scoped vision, freshness, and event stream
├── services/
│   ├── ai_provider.py        # Cloud/local AI provider selection
│   ├── baidu_map_mcp.py      # Baidu Map tools for the assistant
│   ├── baidu_navigation.py   # Walking routes and coordinate conversion
│   ├── deepseek_ai.py        # MapAgent for map questions
│   ├── ollama_client.py      # Ollama client wrapper
│   ├── router_agent.py       # Intent classification
│   ├── settings_agent.py     # Settings query and modification
│   ├── speech_agent.py       # Speech recognition
│   ├── guidance_bus.py       # Per-user events and playback receipts
│   ├── location_store.py     # Recent in-process positions
│   ├── navigation.py         # Macro navigation + alignment state, episodes, and safety gating
│   ├── path_alignment.py     # Near-field lateral geometry from YOLO detection boxes
│   └── vision_observer.py    # YOLO presence, scoped geometry trackers, and frame metadata
├── static/js/
│   ├── guidance.js           # Browser speech scheduler
│   └── navigation_ui.js      # GPS, map, latest-frame camera loop, and event integration
├── tests/
│   ├── test_guidance.js      # Speech priority, interruption, TTL, and alignment epoch
│   ├── test_http_guidance.py # HTTP, stream scoping, frame metadata, and isolation boundaries
│   ├── test_navigation.py    # Macro navigation state and event scenarios
│   └── test_path_alignment.py# Geometry, stream isolation, hysteresis, correction loop, and gating
├── utils/
│   ├── decorators.py
│   ├── email_utils.py
│   └── video_utils.py
├── templates/
│   └── index.html            # Main web interface
└── yolo/
    └── best.pt               # Trained tactile-paving detection weights
```

## 📄 License

This project is licensed under the [MIT License](LICENSE). Copyright (c) 2025 wink-wink-wink555.

---

⭐ If this project helps you, please give it a star!
