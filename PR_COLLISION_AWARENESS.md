# Pull Request: Collision Awareness System Integration

## 1. Project Context
*   **Target Project**: ARIADNE (Flask-based Blind Navigation Platform)
*   **Source Project**: [Visiona AI](https://github.com/paavansirivardhan123/Visiona)
*   **Contributor**: Paavan Sirivardhan
*   **Contribution**: Modularly integrated a real-time **Collision Awareness** subsystem to enhance user safety beyond simple path following.

## 2. The Problem
The original ARIADNE platform focused primarily on **Tactile Path (Blind Track) Navigation**. While effective for staying on the path, it lacked awareness of:
*   **Static Obstacles**: Objects (chairs, poles, signs) blocking the path.
*   **Dynamic Threats**: Approaching pedestrians or vehicles.
*   **Depth Estimation**: Standard cameras don't provide depth, making it hard to judge if an object is 1m or 5m away.

## 3. The Solution
We integrated a vision-based perception engine that calculates **Time-to-Collision (TTC)** using **Bounding Box Expansion** logic.

### Key Components added to `services/collision_awareness/`:
1.  **`tracker.py`**: A pure NumPy IoU-based tracker. It maintains object IDs across frames, which is critical for calculating velocity and reducing "alert jitter."
2.  **`kinematics.py`**: Calculates TTC based on the rate of change of an object's height. 
    *   *Formula*: `TTC = height / (delta_height / delta_time)`.
    *   *Advantage*: This works on monocular cameras without needing heavy depth estimation models (like MiDaS), keeping CPU overhead extremely low (~0.05ms/frame).
3.  **`scoring.py`**: Maps TTC and object labels (from YOLO) to a 0-100 danger score. It includes a configurable 5-second alert cooldown to prevent "spamming" the user with audio.
4.  **`manager.py`**: The orchestrator that connects the video stream detections to the tracking and scoring modules.

## 4. Integration Details
*   **`routes/video.py`**: Injected the `CollisionAwarenessManager` into the `generate_frames` loop. High-priority alerts are sent to the user via the existing `voice_utils.speak()` utility with `SpeechPriority.URGENT`.
*   **`app.py`**:
    *   Fixed a critical **PyTorch 2.6+** compatibility issue (`WeightsUnpickler error`) using a `torch.load` patch.
    *   Updated `ultralytics` to **v8.4.x** to ensure compatibility with modern YOLOv8 weights.
    *   **Note**: Temporarily enabled "Guest Mode" for testing (bypassing login).
*   **`config.py`**: Added `COLLISION_AWARENESS_CONFIG` for modular control (enable/disable, thresholds, cooldowns).

## 5. How to Work with the Changes
1.  **Dependencies**: Ensure you have run `pip install -r requirements.txt` (requires `ultralytics>=8.4.0`).
2.  **Configuration**: In `config.py`, set `"enable": True` under `COLLISION_AWARENESS_CONFIG`.
3.  **Testing**:
    *   Run `python app.py`.
    *   Visit `http://127.0.0.1:5000`.
    *   Upload a video of a street.
    *   The system will automatically detect paths and alert you to nearby obstacles.

## 6. Verification Status
*   **`verify_integration.py`**: All 5 steps (Import, Persistence, Kinematics, Alert Logic, Performance) passed successfully.
*   **Overhead**: Total processing overhead is less than **0.1ms per frame**, ensuring no lag in the video stream.
