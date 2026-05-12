# Blind Navigation (ARIADNE) - Your Way Out of the Labyrinth

<div align="center">
  
  <img src="PPT/LOGO.png" alt=" Logo" width="350"/>
  
English | [简体中文](README.zh-CN.md)

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/wink-wink-wink555/blind_navigation.svg)](https://github.com/wink-wink-wink555/blind_navigation/stargazers)

</div>

> 📹 Demo Video: [V1.0.0](https://www.bilibili.com/video/BV1kD57zGE68), [V2.0.0](https://openatom.tech/enterprise-ai/614b385486d53533dd74f9428aa83087/blob/master/A_%E9%A1%B9%E7%9B%AE%E6%BC%94%E7%A4%BA%E8%A7%86%E9%A2%91.mp4)

<div align="center">
  <img src="PPT/Graph.png" alt="Graph">
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

Travel Assistance System for the Visually Impaired (ARIADNE) is an AI-powered navigation system designed for visually impaired individuals. It combines computer vision and AI to identify tactile paving through real-time video analysis and provides intelligent voice guidance. The system also features a built-in **Multi-Agent AI Assistant** — users can speak naturally to complete map navigation, adjust system settings, send messages to family members, and more. Additional features include real-time location sharing to enhance travel safety and independence.

### Tech Stack

- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Backend**: Flask (Python 3.8+)
- **AI Models**:
  - YOLO (You Only Look Once) - Tactile paving detection
  - **AI Text Model** (flexible): supports both **cloud APIs** (DeepSeek, OpenAI, DashScope/Qwen, or any OpenAI-compatible endpoint) and **local Ollama** models — configurable per user in the settings panel
  - Multi-Agent assistant for intent routing, map navigation, settings management, and companion chat
- **Multi-Agent Architecture**:
  - RouterAgent - Intent classification & routing
  - MapAgent (ReAct loop + Baidu Map MCP) - Map navigation agent
  - SettingsAgent - Settings query & modification (Text-to-SQL) agent
  - ChatAgent - Companion chat agent
- **Database**: MySQL
- **Third-party Services**:
  - Baidu Map API - Location services and route planning
  - DashScope (Alibaba Cloud) - Speech-to-text recognition (paraformer-realtime-v2), also supports local Ollama STT
  - Edge TTS / pyttsx3 - Text-to-speech synthesis

## 🎯 Problems Solved

1. **Tactile Paving Recognition & Navigation**: Real-time video analysis to identify tactile paving position and direction changes
2. **Real-time Voice Feedback**: Automatically provides personalized AI voice prompts when direction changes are detected
3. **Multi-Agent AI Assistant**: Unified intent routing + multi-agent dispatch for map navigation, settings modification, family messaging, and companion chat
4. **Safety Monitoring**: Location sharing so family members can remotely view the user's location
5. **Personalized Experience**: Customizable voice speed, volume, address preferences, and more
6. **Accessibility Design**: Reduces barriers for visually impaired individuals to use modern urban facilities

## ✨ Key Features

- 🎥 **Real-time Video Analysis**: YOLO-based real-time tactile paving detection
- 🔊 **Intelligent Voice Feedback**: Personalized, context-aware voice prompts based on user profile (age, gender, name, preferences), powered by the configured AI model
- 🤖 **Multi-Agent AI Assistant**: Speak naturally to:
  - 🗺️ **Map Navigation**: Location queries, walking route planning (optimized for the visually impaired), nearby place search
  - ⚙️ **Voice Settings**: Query or modify any system setting via natural language
  - 📨 **Family Messaging**: Send location or status messages to family members via email in one sentence
  - 💬 **Companion Chat**: Warm conversational companion with full conversation memory
- 👤 **User System**: Registration, login, and password recovery
- 📍 **Location Sharing**: Real-time location sharing for family members
- ⚙️ **Personalized Settings**: Voice speed, volume, gender, age group, address preferences, etc.
- 🎙️ **Speech-to-Text**: Real-time speech recognition (DashScope cloud or local Ollama), enabling hands-free voice input
- 🎯 **Dual Mode**: Visually impaired user mode and family member mode
- 🔧 **Flexible AI Backend**: Switch between cloud APIs and local Ollama models per user without restarting the server

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
| MapAgent | `services/deepseek_ai.py` | ReAct-loop map tools, walking navigation optimized for the visually impaired |
| SettingsAgent | `services/settings_agent.py` | Natural language settings query and modification, synced to DB and Session |
| ChatAgent | `routes/chat.py` | Companion chat with full conversation context and user profile |

**Example Interactions:**
- `"Set my voice speed to slow"` → SettingsAgent
- `"How do I walk from Tiananmen Square to the National Museum?"` → MapAgent
- `"Send my family a message: I've arrived"` → Message handler
- `"What a nice day today"` → ChatAgent

</details>

## 🎯 Pre-trained YOLO Model

The `yolo/best.pt` model is fully trained and ready to use — no additional training needed. The `yolo/` folder contains comprehensive training metrics including confusion matrices, Precision-Recall curves, F1 curves, and results visualization.

## 📋 Requirements

- Python 3.8+
- MySQL Database
- Required Python libraries (see `requirements.txt`)
- At least one AI backend configured: a cloud API key (DeepSeek / OpenAI / DashScope / etc.) **or** a locally running [Ollama](https://ollama.com/) instance

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

Ollama runs on `http://localhost:11434` by default. You can select the model in the AI Settings panel after logging in.

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
- **`EMAIL_CONFIG`**: QQ email SMTP (for verification codes and family notifications)
- **`BAIDU_MAP_CONFIG`**: Baidu Map API key
- **`DEEPSEEK_CONFIG`**: Default cloud AI API key (used if no per-user setting is configured)
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

- **Video Analysis**: Upload a video file; the system analyzes tactile paving and plays voice prompts when direction changes are detected.
- **Real-time Navigation**: Click "Start Navigation" to use the camera for real-time guidance.

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

Each user can independently configure their AI backend from the settings panel:
- **Text model**: choose cloud (DeepSeek / OpenAI / DashScope / custom OpenAI-compatible) or local (Ollama)
- **Speech-to-text**: choose cloud (DashScope Paraformer) or local (Ollama)

Changes take effect immediately without restarting the server.

</details>

<details>
<summary><strong>Location Sharing</strong></summary>

Visually impaired users can share real-time location with family members. Family members log in and view the location on the map.

</details>

<details>
<summary><strong>System Settings</strong></summary>

Customize gender, preferred name, age group, voice speed, volume, user mode (visually impaired / family), and encouragement toggle. Use "Test Voice" to preview before saving.

</details>

## ⚠️ Notes

- At least one AI backend must be configured (cloud API key or local Ollama) for voice prompts and the Multi-Agent assistant to function.
- Email configuration is required for verification codes and family notifications.
- Baidu Map API key is required for map navigation.
- DashScope API key is required for cloud speech-to-text; alternatively, configure a local Ollama STT model.
- Camera and GPS permissions must be enabled for navigation and location sharing.

## 📧 Contact

- **Email**: yfsun.jeff@gmail.com
- **GitHub**: [wink-wink-wink555](https://github.com/wink-wink-wink555)
- **LinkedIn**: [Yifei Sun](https://www.linkedin.com/in/yifei-sun-0bab66341/)
- **Bilibili**: [NO_Desire](https://space.bilibili.com/623490717)

## 🙏 Acknowledgments

Special thanks to the following members for their contributions to the tactile paving dataset collection, annotation, and project proposal:

[Chen Xingyu](https://github.com/guangxiangdebizi) · Wang Youyi · Shen Qian · Liu Yiheng · Zhang Chenshu · Zhang Kai · Sheng Sheng · Cai Yuxin 

## 📁 Project Structure

```
blind_navigation/
├── app.py                 # Flask application entry point
├── config.py              # Configuration file
├── models/
│   └── database.py        # Database operations
├── routes/
│   ├── auth.py            # Authentication routes
│   ├── chat.py            # Multi-Agent dispatch center (unified /chat endpoint)
│   ├── main.py            # Main page routes
│   ├── video.py           # Video processing routes
│   ├── map.py             # Map-related routes
│   └── ai_settings.py     # AI settings routes
├── services/
│   ├── ai_provider.py     # Unified AI routing (cloud APIs ↔ Ollama)
│   ├── baidu_map_mcp.py   # Baidu Map MCP tool set
│   ├── deepseek_ai.py     # MapAgent (ReAct-mode map navigation)
│   ├── ollama_client.py   # Ollama client wrapper
│   ├── router_agent.py    # RouterAgent (intent classifier & router)
│   ├── settings_agent.py  # SettingsAgent (settings query & modification)
│   └── speech_agent.py    # Speech agent
├── utils/
│   ├── decorators.py · email_utils.py · video_utils.py · voice_utils.py
├── templates/
│   ├── index.html · login.html · register.html · forget_password.html
└── yolo/
    └── best.pt            # Pre-trained model weights (ready to use)
```

## 📄 License

This project is licensed under the [MIT License](LICENSE). Copyright (c) 2025 wink-wink-wink555.

---

⭐ If this project helps you, please give it a star!
