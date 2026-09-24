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

ARIADNE is a web-based mobility-assistance demonstration that combines live tactile-paving observation, Baidu walking routes, browser geolocation, and a multi-agent assistant. The live camera first uses YOLO to detect candidate tactile-paving regions. On eligible straight route segments, a near-field geometry layer further estimates the paving's lateral position relative to the user's visual reference center. A temporal alignment state machine then combines multiple observations, hysteresis, and navigation context to issue conservative micro-corrections such as “move slightly left” or “move slightly right.” If a correction was actually played and subsequent observations confirm a stable return to the centered region, the system may provide one low-priority positive-feedback message.

Baidu walking routes and GPS remain responsible for macro-level navigation—where to go and when a turn is expected—while the vision subsystem is limited to local alignment under safe conditions. Near planned turns, at road crossings, when geometry is ambiguous, when paving disappears, or when lateral deviation becomes severe, normal steering hints are suppressed and the system falls back to route confirmation or safety guidance instead of guessing a walkable direction. Safety alerts, alignment corrections, route advisories, authorized family voice messages, assistant replies, and background feedback share one browser speech channel with explicit priority and validity rules.

### Tech Stack

- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Backend**: Flask (Python 3.10 / 3.11 recommended)
- **AI / Vision Models**:
  - YOLO (You Only Look Once) - candidate tactile-paving region detection; the model itself does not predict left/right steering
  - `PathGeometryEstimator` - near-field candidate filtering, lateral-center estimation, and geometry-confidence calculation from existing YOLO boxes
  - `NavigationManager` Alignment State Machine - temporal filtering, hysteresis, route-aware gating, correction episodes, and recovery feedback
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

1. **Paving Observation, Local Alignment, and Route Planning**: YOLO detects candidate paving regions; near-field geometry and a temporal state machine estimate stable lateral deviation, while Baidu walking routes and GPS independently provide macro-level route steps and planned turns
2. **Single-channel Speech Arbitration and Freshness Control**: Safety, alignment, route, family, assistant, and background events share one scheduler; obsolete prompts are invalidated when route or alignment context changes
3. **Multi-Agent AI Assistant**: Intent routing for map questions, settings changes, emails to family contacts, and companion chat
4. **Family Location View**: Linked family accounts can view shared browser location
5. **Personalized Experience**: Customizable voice speed, volume, address preferences, and more
6. **Accessibility Design**: Reduces barriers for visually impaired individuals to use modern urban facilities

## ✨ Key Features

- 🎥 **Live Paving Observation and Alignment**: YOLO detects candidate tactile-paving regions; V1 evaluates near-field box geometry, normalized lateral offset, temporal consistency, and hysteresis before producing any steering hint
- 🧭 **Separated Macro Navigation and Micro Alignment**: Baidu walking routes and GPS own route steps and planned turns; vision-based alignment is allowed only while confidently navigating away from planned turns and crossings
- 🔁 **Closed-loop Correction Episodes**: A stable deviation opens one correction episode instead of generating speech every frame. Stable recovery can produce one low-priority positive-feedback message after the correction was actually played
- 🛑 **Conservative Degradation**: Severe deviation, missing paving, ambiguous geometry, camera loss, and crossing scenarios suppress ordinary left/right nudges and fall back to stop-and-confirm behavior
- 🔊 **Browser Speech Scheduling**: One priority queue arbitrates safety, alignment, route, family, assistant, and background messages with TTLs and context-based invalidation
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

## 🧭 Live Navigation, Tactile-Path Alignment, and Speech Arbitration

### Macro navigation vs. micro alignment

Live guidance deliberately separates two responsibilities:

```text
Baidu Walking Route + GPS
            │
            ▼
   Macro Navigation State
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
                     near-field center / offset
                                    │
                                    ▼
                         Alignment State Machine
                                    │
                   temporal filtering / hysteresis
                   episode / safety gating / TTL
                                    │
                                    ▼
                           Alignment Guidance
```

The Baidu route answers where the route goes and when a turn is expected. YOLO and the near-field geometry layer only estimate where candidate tactile paving lies relative to the user's visual reference center. Detection boxes are never treated as proof of junction topology, paving connectivity, or a safe direction through an intersection.

### V1 tactile-path alignment

V1 keeps the existing `yolo/best.pt` detector and does not require retraining or a segmentation model. `services/vision_observer.py` obtains candidate bounding boxes and `services/path_alignment.py` estimates their near-field lateral geometry.

The estimator prioritizes approximately the lower 50%–90% portion of the image rather than blindly using the center of a full bounding box. Candidate scoring considers YOLO confidence, near-field overlap, bottom proximity, and temporal continuity. When multiple strong candidates conflict horizontally, the result becomes `AMBIGUOUS` instead of forcing a left/right decision.

Temporal geometry state is scoped to one coherent visual stream. Live navigation uses an isolated per-user tracker that is reset on navigation start, replan, stop, and camera interruption. Each recorded-video MJPEG reader receives its own independent tracker. Therefore a historical video, another user, or another playback reader cannot change the previous-center cue used by the current live camera.

The normalized lateral offset is defined as:

`normalized_offset = (path_center_x - reference_center_x) / image_width`

A positive value means candidate paving lies to the right of the reference center and may eventually produce `CORRECT_RIGHT`; a negative value may produce `CORRECT_LEFT`. The current default reference center is the image center, while the interface leaves room for future camera-mount calibration.

A single frame never directly becomes speech. `NavigationManager` maintains a short history of valid offsets, applies a consistency window and hysteresis, and exposes a second state layer:

`UNKNOWN / CENTERED / CORRECT_LEFT / CORRECT_RIGHT / RECOVERING / SEVERE / NOT_VISIBLE / AMBIGUOUS / SUPPRESSED`

Only a stable multi-frame deviation opens a correction episode and produces one primary hint such as “the paving is on the right; move slightly right.” Short-lived noise remains silent. During improvement, the episode enters recovery. After several centered observations, the state first transitions into a new `CENTERED` alignment epoch. If the correction instruction actually entered browser playback and the feedback cooldown permits it, one low-priority positive-feedback event is then created inside that same new epoch. This ordering prevents the recovery context update from immediately invalidating the praise that it just generated.

Persistent severe deviation does not trigger increasingly aggressive nudges. It is promoted to a safety event asking the user to stop and reacquire the path.

### Route-aware safety gating

Micro-alignment is active only while the navigation state is `NAVIGATING`.

Within approximately 12 meters of a planned turn, alignment becomes `SUPPRESSED`, because sideways paving in the image may represent the path itself turning rather than user drift. If the next route step requires a road crossing, ordinary alignment guidance is prohibited and the existing crossing safety flow takes precedence. Poor GPS, camera interruption, repeated paving loss, or another uncertain navigation state also disables steering hints.

Vision therefore does not replace the Baidu route's macro-level decisions, and the map route does not directly command foot-level left/right movement.

### Latest-frame camera processing and freshness

The browser uses latest-frame processing rather than a fixed concurrent upload interval. The next capture is scheduled only after the previous inference request returns, so at most one camera frame is in flight and stale frames cannot build up in an inference queue.

Live requests carry a monotonic `frame_seq` plus browser capture time for diagnostics. The Flask endpoint records its own `server_received_at_ms` before inference, and `NavigationManager` uses server-side receive/process timestamps—not browser `Date.now()`—for freshness decisions. This avoids a client/server wall-clock difference from making every otherwise fresh frame appear stale. Browser capture time remains visible as metadata but is not compared directly with the server wall clock for steering.

Out-of-order frame sequences are prevented from rolling alignment state backward. Visual results whose server-observed age exceeds the configured limit may still be returned for diagnostics, but they cannot produce new steering speech. A small debug panel exposes vision status, geometry status, alignment state, normalized offset, geometry confidence, candidate count, frame sequence, and observed latency for tuning and demonstration.

### One speech channel

`static/js/guidance.js` owns ordering, interruption, expiry, and context validity for browser Web Speech. Lower numbers mean higher priority:

| Priority | Message |
|---|---|
| 0 | Safety alerts |
| 1 | Tactile-path alignment corrections |
| 2 | Walking-route advisories |
| 3 | Authorized family voice messages |
| 4 | Assistant replies |
| 5 | Background hints, positive feedback, and voice tests |

Alignment corrections use a short TTL of roughly three seconds and a discard-on-interruption policy. A left/right instruction that is no longer valid must not be played several seconds later.

In addition to navigation session, route revision, and route step, alignment speech is associated with an `alignment_epoch`. When Alignment State changes, the epoch advances. The browser drops or interrupts steering events belonging to an older epoch, preventing stale instructions from surviving a recentering event or a direction reversal. Positive recovery feedback is emitted only after entering the new `CENTERED` epoch, so it remains valid under the same rule.

Authorized family voice messages retain their own recovery behavior and playback receipts. A queued event is not proof that the recipient heard it. Assistant-sent **email to a family contact** and family-to-user **browser voice messaging** remain separate flows.

### Default alignment parameters

These values are engineering defaults for the current web demonstration, not field-validated mobility-device safety thresholds:

| Parameter | Current value | Purpose |
|---|---:|---|
| Near-field ROI | `0.50H–0.90H` | Focus on paving the user is about to approach |
| Evaluation row | `0.70H` | Evaluate near-field path center |
| Geometry minimum confidence | `0.35` | Reject weak detections |
| Centered threshold | `0.07` | Treat `abs(offset) <= 0.07` as centered |
| Correction threshold | `0.12` | Require stable deviation beyond this value |
| Severe threshold | `0.22` | Escalate persistent large deviation |
| Alignment history | `5` frames | Recent valid lateral observations |
| Consistency window | `4` frames | Direction-consistency window |
| Required consistent frames | `3` frames | Frames needed before correction |
| Recovery frames | `3` frames | Centered observations required for recovery |
| Severe frames | `3` frames | Severe observations required before escalation |
| Turn suppression distance | `12 m` | Disable steering near planned turns |
| Correction repeat interval | `10 s` | Conservative repeat within one episode |
| Positive-feedback cooldown | `20 s` | Minimum interval between feedback |
| Alignment speech TTL | `3 s` | Rapidly expire obsolete steering |
| Server-observed stale-frame threshold | `1.5 s` | Prevent old server-side visual results from steering |
| Camera scheduling | `350 ms / 700 ms` | Normal / high-latency next-frame delay |

The relevant constants are grouped in `services/path_alignment.py`, `services/navigation.py`, and `static/js/navigation_ui.js` so they can be recalibrated after hardware and field testing.

### Setup, verification, and limitations

Python 3.10 or 3.11 is recommended. `BAIDU_MAP_CONFIG['api_key']` is the server-side Baidu Web Service key, while `BAIDU_MAP_CONFIG['browser_api_key']` is the browser JSAPI key and should use an appropriate domain allowlist. Live GPS and camera access generally require HTTPS or localhost plus browser permission. Speech requires Web Speech support and explicit activation on the page. AI text models serve assistant conversations; deterministic safety, route, and alignment guidance does not require an LLM.

V1 still operates on axis-aligned YOLO bounding boxes rather than pixel-level tactile-paving segmentation. It can provide only a conservative near-field lateral estimate. It cannot certify actual paving connectivity, traffic-signal state, obstacle clearance, crossing safety, or a traversable branch, and it does not claim centimeter-level physical lateral distance. Camera mounting and large hand-held rotations can also affect the visual reference frame; real deployment would require calibration and field evaluation.

The event log, navigation sessions, and recent positions live in the current server process. Closing the page, restarting the service, or using multiple receiving pages does not provide continuous or exactly-once speech delivery. This repository remains a web engineering demonstration and research prototype; it is not a replacement for a cane, guide dog, or certified mobility aid.

For local regression checks, run `python -m unittest discover -s tests` and `node tests/test_guidance.js`. The test suite includes simulated near-field geometry, visual-stream isolation, temporal consistency, hysteresis, correction episodes, recovery feedback, turn suppression, crossing gating, severe deviation, out-of-order/server-stale frames, client/server clock skew, and alignment-epoch invalidation. Simulation is not equivalent to validation on real streets.

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

The repository includes trained tactile-paving detection weights at `yolo/best.pt` together with training and evaluation artifacts in `yolo/`. The detector itself still predicts candidate tactile-paving bounding boxes; it was not trained with explicit left/right steering classes and does not certify branch topology, crossing safety, or walkable direction.

V1 alignment is built above the detector rather than inside it. `services/path_alignment.py` estimates near-field center and normalized lateral offset from the existing boxes, while `services/navigation.py` combines multiple observations, hysteresis, route context, and speech-event validity before deciding whether any correction should be issued.

## 📋 Requirements

- Python 3.10 or 3.11 recommended (the pinned NumPy 1.24.3 does not support Python 3.12)
- MySQL Database
- Required Python libraries (see `requirements.txt`)
- A cloud text-model key or local [Ollama](https://ollama.com/) model for assistant features; fixed safety, route, and alignment speech does not require an LLM
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

- **Recorded Video**: Upload a recording to display YOLO tactile-paving detection boxes. Recorded-video processing is isolated from live geometry state and does not trigger live route or alignment speech.
- **Live Route Demo**: Enable browser speech, obtain a fresh and accurate GPS fix, choose a destination, inspect the Baidu walking route, and activate navigation. With the live camera enabled, eligible straight segments additionally use near-field visual geometry to detect stable lateral drift and may issue a small left/right correction.
- **Recovery Feedback**: If a correction actually enters playback and later visual observations confirm stable recentering, one low-priority positive-feedback message may be emitted in the new centered alignment epoch. Remaining centered does not generate repeated praise.
- **Turns and Crossings**: Micro-alignment is suppressed near planned turns. Crossings, ambiguous geometry, severe deviation, and paving loss use conservative route or safety behavior instead. Users must still verify actual junctions, paving connectivity, and crossing conditions.
- **Manual Origin**: A manually selected map origin supports route preview only. Live guidance requires a valid browser GPS fix.

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

- An AI text backend is required for assistant conversations; deterministic safety alerts, walking-route advisories, and tactile-path alignment do not require an LLM.
- SMTP is used for verification codes and assistant-sent emails to family contacts. Authorized family-to-user browser voice messages use the separate speech-event channel.
- Walking routes and map rendering require separate Baidu Web Service and domain-restricted browser JSAPI keys.
- DashScope requires an API key for cloud speech recognition. Local STT requires a working `/v1/audio/transcriptions` endpoint; a text-only Ollama model does not provide audio transcription.
- Live route guidance requires a fresh browser GPS fix. Tactile-path alignment additionally requires the live camera.
- V1 alignment is derived from YOLO bounding boxes rather than semantic segmentation or 3-D localization. It estimates image-relative direction and normalized lateral offset; it does not claim a physical deviation in centimeters.
- Camera orientation directly affects the visual reference center. The current implementation defaults to the image center and leaves camera-mount calibration for future hardware deployment.
- Browser capture timestamps are diagnostic only; real-time steering freshness is checked with timestamps generated by the server to avoid client/server clock-skew errors.
- Intersections, tactile-paving branches, road crossings, traffic signals, temporary obstacles, and true traversability are not certified by the current detector. In uncertain cases the system deliberately suppresses steering and falls back to confirmation or safety guidance.
- This repository remains a web demonstration and engineering research prototype. It is not a replacement for a cane, guide dog, or certified mobility aid.

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
