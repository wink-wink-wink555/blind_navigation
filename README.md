# Blind Navigation (ARIADNE) - Your Way Out of the Labyrinth

<div align="center">
  
  <img src="LOGO.png" alt=" Logo" width="350"/>
  
English | [简体中文](README.zh-CN.md)

[![Python](https://img.shields.io/badge/Python-3.10%2F3.11-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/wink-wink-wink555/blind_navigation.svg)](https://github.com/wink-wink-wink555/blind_navigation/stargazers)

</div>

> 📹 Demo Video: [V1.0.0](https://www.bilibili.com/video/BV1kD57zGE68), [V2.0.0](https://openatom.tech/enterprise-ai/614b385486d53533dd74f9428aa83087/blob/master/A_%E9%A1%B9%E7%9B%AE%E6%BC%94%E7%A4%BA%E8%A7%86%E9%A2%91.mp4)

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

ARIADNE is a web demonstration that combines tactile-paving observations, Baidu walking routes, and a multi-agent assistant. The live camera reports whether candidate paving is visible; turn advisories come from walking-route steps and current location. Users must still verify intersections, paving connections, and road crossings themselves. In the browser, one speech scheduler arbitrates safety alerts, route advisories, authorized family voice messages, and assistant replies according to priority and validity. The application also includes account management, location sharing, and natural-language interaction.

### Tech Stack

- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Backend**: Flask (Python 3.10 / 3.11 recommended)
- **AI Models**:
  - YOLO (You Only Look Once) - Tactile paving detection
  - **AI Text Model**: server-configured cloud APIs (DeepSeek, OpenAI, DashScope/Qwen, or another OpenAI-compatible service) or a user-selected local Ollama model; cloud credentials remain on the server
  - Multi-Agent assistant for intent routing, map questions, settings management, and companion chat
- **Multi-Agent Architecture**:
  - RouterAgent - Intent classification & routing
  - MapAgent (ReAct loop + Baidu Map MCP) - Map question answering; separate from live guidance
  - SettingsAgent - Validated settings updates from structured natural-language extraction
  - ChatAgent - Companion chat agent
- **Database**: MySQL
- **Third-party Services**:
  - Baidu Map Web Service and browser JSAPI - walking routes, coordinate conversion, and map display
  - DashScope (Alibaba Cloud) - cloud speech recognition; local transcription requires an OpenAI-compatible audio endpoint
  - Browser Web Speech API - single-channel speech output

## 🎯 Problems Solved

1. **Paving Observations and Route Planning**: YOLO reports candidate paving visibility; Baidu walking steps supply planned turns for users to verify
2. **Single-channel Speech Arbitration**: Time-sensitive safety alerts can interrupt route, family, and assistant audio; invalid route prompts expire
3. **Multi-Agent AI Assistant**: Intent routing for map questions, settings changes, emails to family contacts, and companion chat
4. **Family Location View**: Linked family accounts can view shared browser location
5. **Personalized Experience**: Customizable voice speed, volume, address preferences, and more
6. **Accessibility Design**: Reduces barriers for visually impaired individuals to use modern urban facilities

## ✨ Key Features

- 🎥 **Live Paving Observations**: YOLO reports candidate paving visibility; it does not infer safe turns
- 🔊 **Browser Speech Scheduling**: One priority queue for safety, route, family, and assistant messages; browser speech speed and volume follow user settings
- 🤖 **Multi-Agent AI Assistant**: Speak naturally to:
  - 🗺️ **Map Questions**: Location queries, Baidu walking-route lookup, and nearby place search; live turn advisories use the navigation state machine
  - ⚙️ **Voice Settings**: Query or modify supported voice and profile settings via natural language
  - 📨 **Emails to Family**: Ask the assistant to send a location or status message to a family contact by email
  - 💬 **Companion Chat**: Conversational assistant using recent chat context
- 📨 **Family Voice Messages**: Authorized family accounts can queue speech in the recipient's browser and query its playback status
- 👤 **User System**: Registration, login, and password recovery
- 📍 **Location Sharing**: Real-time location sharing for family members
- ⚙️ **Personalized Settings**: Voice speed, volume, gender, age group, address preferences, etc.
- 🎙️ **Speech-to-Text**: DashScope cloud recognition or a local service implementing `/v1/audio/transcriptions`
- 🎯 **Dual Mode**: Visually impaired user mode and family member mode
- 🔧 **Flexible Text Backend**: Users can select a server-configured cloud service or a local Ollama text model without restarting the server

## 🧭 Live Navigation and Speech Arbitration (Current Web Demo)

### Route planning and visual observations

After a destination is selected, the application obtains walking steps from Baidu Map Web Services. It converts browser GPS coordinates from WGS84 to BD09 for route matching. Live turn advisories require a recent, sufficiently accurate position, route confirmation, and explicit navigation activation. A manually selected origin supports route preview only; it cannot start live spoken guidance.

The optional live camera uses YOLO to observe candidate tactile paving. Detection boxes indicate visibility; they cannot establish whether a branch is connected or safe, and they do not choose left or right turns. Repeatedly missing paving observations, an interrupted camera feed, inaccurate GPS, or route deviation suspend route advisories and trigger a request to stop and verify the surroundings. A crossing indicated by the route is not automatically certified as safe. Uploaded recordings display detection results only and do not produce live navigation speech. The assistant's MapAgent answers map questions; it does not control the live turn state machine.

### One speech channel

The web page speaks through the browser Web Speech API. `static/js/guidance.js` owns ordering, interruption, resumption, and validity checks. Lower numbers have higher priority:

| Priority | Message |
|---|---|
| 0 | Safety alerts |
| 1 | Walking-route advisories |
| 2 | Authorized family voice messages |
| 3 | Assistant replies |
| 4 | Background hints and voice tests |

A higher-priority message may interrupt playback. A family voice message can resume from its interrupted text segment while it remains valid; route advisories and assistant speech follow their own expiry and discard rules. Events have a time-to-live and can be tied to a navigation session, route revision, and step. Stopping or replanning a route, moving to another step, or entering an uncertain state invalidates obsolete turn advisories. Deduplication and throttling limit repeated prompts. The family interface can query queued and playback status; a queued message is not proof that the recipient heard it. The assistant **sending an email to a family contact** and a family user **sending a voice message to the recipient's browser** are separate flows.

### Setup, verification, and limitations

Python 3.10 or 3.11 is recommended. `BAIDU_MAP_CONFIG['api_key']` is the server-side Baidu Web Service key; `BAIDU_MAP_CONFIG['browser_api_key']` is the browser JSAPI key and should have an appropriate domain allowlist. Live GPS and camera access generally require HTTPS or localhost and browser permissions. Speech requires a browser supporting Web Speech and must be enabled on the page. An AI backend serves assistant conversations; fixed safety alerts and route advisories do not require an LLM.

The event log, navigation sessions, and recent positions are held in the current server process. Closing the page, restarting the server, or opening multiple receiving pages does not guarantee continuous or exactly-once playback. Neither a walking route nor a paving detection certifies traffic signals, obstacles, crossing safety, or actual paving connectivity. This version is a web demonstration, not an independent mobility aid.

For local regression checks, run `python -m unittest discover -s tests` and `node tests/test_guidance.js`. These tests use simulated map and camera inputs; they do not constitute validation on real streets.

<details>
<summary><strong>🤖 Multi-Agent Architecture</strong></summary>

The system features a unified multi-agent dispatch center (`/chat` endpoint). A single user message is automatically classified and routed to the appropriate agent.

```
User Input
    │
    ▼
RouterAgent (Intent Classifier)
    │
    ├─ map      ──► MapAgent (ReAct loop + Baidu Map MCP)
    │                  └─ Geocoding → Nearby search → Walking route → Natural language reply
    │
    ├─ settings ──► SettingsAgent (Query & Modify settings)
    │                  └─ Parse intent → Validate values → Write to DB → Sync Session
    │
    ├─ message  ──► Message Handler (Send message to family)
    │
    └─ chat     ──► ChatAgent (Warm companion chat with full context)
```

| Agent | File | Responsibility |
|---|---|---|
| RouterAgent | `services/router_agent.py` | Classify intent and route to the correct agent |
| MapAgent | `services/deepseek_ai.py` | ReAct map Q&A and walking-route lookup; does not drive live turn advisories |
| SettingsAgent | `services/settings_agent.py` | Natural language settings query and modification, synced to DB and Session |
| ChatAgent | `routes/chat.py` | Companion chat with recent conversation context and user profile |

**Example Interactions:**
- `"Set my voice speed to slow"` → SettingsAgent
- `"How do I walk from Tiananmen Square to the National Museum?"` → MapAgent
- `"Send my family a message: I've arrived"` → Message handler
- `"What a nice day today"` → ChatAgent

</details>

## 🎯 Pre-trained YOLO Model

The repository includes trained tactile-paving detection weights at `yolo/best.pt` and training metrics in `yolo/`. The model reports candidate paving regions; it was not trained to certify connected branches, crossings, or safe walking directions.

## 📋 Requirements

- Python 3.10 or 3.11 recommended (the pinned NumPy 1.24.3 does not support Python 3.12)
- MySQL Database
- Required Python libraries (see `requirements.txt`)
- A cloud text-model key or local [Ollama](https://ollama.com/) model for assistant features; fixed safety and route speech does not require an LLM
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

ollama pull qwen2.5:3b   # or any other model you prefer
ollama list              # verify installation
```

Ollama runs on `http://localhost:11434` by default. You can select a local text model in AI Settings after logging in. Local speech recognition additionally requires a service implementing `/v1/audio/transcriptions`; a text-only Ollama model is insufficient.

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
- **`EMAIL_CONFIG`**: QQ email SMTP (for verification codes and assistant-sent emails to family contacts; browser family voice messages do not use SMTP)
- **`BAIDU_MAP_CONFIG`**: `api_key` for the server-side Web Service and `browser_api_key` for the map JSAPI (restrict the latter to allowed domains)
- **`DEEPSEEK_CONFIG`**: Server-side default cloud text-model settings; cloud credentials are not submitted by the browser
- **`DASHSCOPE_CONFIG`**: DashScope API key (for cloud speech-to-text)
- **`MODEL_WEIGHTS`**: Set to `'yolo/best.pt'`

</details>

## 🏃 Running the Application

```bash
python app.py
```

Visit http://127.0.0.1:5000/

## 📖 Usage Guide

<details>
<summary><strong>Account Management</strong></summary>

Register with username, password, and email (email verification code required). Login and password reset are also supported.

</details>

<details>
<summary><strong>Tactile Paving Navigation</strong></summary>

- **Recorded Video**: Upload a video to display tactile-paving detection boxes. A recording cannot trigger live navigation or speech.
- **Live Route Demo**: Enable browser speech and grant accurate, recent GPS access; choose a destination, inspect the Baidu walking route, and activate navigation. The optional camera can pause route advisories if paving becomes unavailable. Verify actual junctions and crossings yourself.
- **Manual Origin**: Selecting a starting point on the map previews a route only. Live guidance requires an accurate browser GPS fix.

</details>

<details>
<summary><strong>Multi-Agent AI Assistant</strong></summary>

One unified chat interface — just speak naturally:

- **Map**: *"How do I walk from Beijing Railway Station to Tiananmen Square?"*
- **Settings**: *"Set my voice speed to slow"* / *"Turn the volume up a bit"*
- **Family Message**: *"Send my family a message: I've arrived at school"*
- **Chat**: Any everyday conversation

</details>

<details>
<summary><strong>AI Settings</strong></summary>

Users can switch between a server-configured cloud deployment and a local deployment in AI Settings. Cloud credentials are configured on the server; the panel lets users select local endpoints and models:
- **Text model**: use the server-configured cloud provider (DeepSeek, OpenAI, DashScope/Qwen, or a compatible service) or a local Ollama model
- **Speech-to-text**: choose cloud DashScope or a local service implementing the OpenAI-compatible audio-transcription endpoint

Changes take effect immediately without restarting the server.

</details>

<details>
<summary><strong>Location Sharing</strong></summary>

Visually impaired users can enable browser geolocation and leave the page open to share their most recent position. Authorized family accounts can view it on the map; stale positions are reported as stale.

</details>

<details>
<summary><strong>System Settings</strong></summary>

Customize gender, preferred name, age group, voice speed, volume, user mode (visually impaired / family), and encouragement toggle. Use "Test Voice" to preview before saving.

</details>

## ⚠️ Notes

- An AI text backend is needed for assistant conversations; fixed safety alerts and walking-route advisories do not require an LLM.
- SMTP configuration is needed for verification codes and assistant-sent emails to family; authorized family-to-user browser voice messages use the speech event channel.
- Set separate Baidu Web Service and domain-restricted browser JSAPI keys for walking routes and map display.
- DashScope requires an API key for cloud speech recognition. Local STT requires a working `/v1/audio/transcriptions` service; a text-only Ollama model does not provide this endpoint.
- Live guidance requires fresh browser GPS; the camera is optional for paving observations. GPS/camera generally require HTTPS or localhost and the relevant permissions. Keep a supported browser page open for Web Speech playback.

## 📧 Contact

- **Email**: yfsun.jeff@gmail.com
- **GitHub**: [wink-wink-wink555](https://github.com/wink-wink-wink555)
- **LinkedIn**: [Yifei Sun](https://www.linkedin.com/in/yifei-sun-0bab66341/)
- **Bilibili**: [NO_Desire](https://space.bilibili.com/623490717)

## 🙏 Acknowledgments

Special thanks to the following members for their contributions to the tactile paving dataset collection, annotation, and project proposal:

[Chen Xingyu](https://github.com/guangxiangdebizi) · Wang Youyi · Shen Qian · Liu Yiheng · Zhang Chenshu · Zhang Kai · Sheng Sheng · Cai Yuxin 

## 📁 Project Structure

The following lists the main files; `config.py` is created locally from the template and is not committed.

```
blind_navigation/
├── app.py                    # Flask application entry point
├── config.example.py         # Configuration template; copy to config.py
├── models/
│   └── database.py           # Database operations
├── routes/
│   ├── auth.py               # Authentication routes
│   ├── chat.py               # Multi-Agent /chat endpoint
│   ├── main.py               # Main page, settings, and family voice messages
│   ├── video.py              # Recorded-video detection display
│   ├── map.py                # Map-related routes
│   ├── ai_settings.py        # AI settings routes
│   └── guidance.py           # Live navigation, vision, and event stream
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
│   ├── navigation.py         # Navigation state machine
│   └── vision_observer.py    # Paving visibility observations
├── static/js/
│   ├── guidance.js           # Browser speech scheduler
│   └── navigation_ui.js      # GPS, map, camera, and event integration
├── tests/
│   ├── test_guidance.js      # Scheduler scenarios
│   ├── test_http_guidance.py # HTTP boundary scenarios
│   └── test_navigation.py    # Navigation state and event scenarios
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
