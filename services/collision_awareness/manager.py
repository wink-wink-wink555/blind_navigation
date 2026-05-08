from typing import List, Dict
from .tracker import LightweightTracker
from .kinematics import CollisionKinematics
from .scoring import CollisionScorer

class CollisionAwarenessManager:
    """
    Main entry point for the Collision Awareness system.
    Integrates tracking, TTC calculation, and threat scoring.
    """
    def __init__(self, ttc_threshold=3.0, alert_cooldown=5.0):
        self.tracker = LightweightTracker()
        self.kinematics = CollisionKinematics()
        self.scorer = CollisionScorer(ttc_threshold, alert_cooldown)

    def process_frame(self, detections: List[dict]) -> dict:
        """
        Processes detections for the current frame.
        Returns a summary of threats and a flag if an alert should be voiced.
        """
        # 1. Update Tracking
        tracked_detections = self.tracker.update(detections)
        
        frame_threats = []
        high_threats = []

        # 2. Analyze tracked objects
        for det in tracked_detections:
            track_id = det.get('track_id')
            if track_id and track_id in self.tracker.tracks:
                track = self.tracker.tracks[track_id]
                
                # Compute TTC
                ttc = self.kinematics.compute_ttc(track.history)
                det['ttc'] = ttc
                
                # Compute Score
                score = self.scorer.calculate_score(ttc, det['label'])
                det['threat_score'] = score
                
                if score > 70:  # Threshold for high threat
                    high_threats.append(det)
                
                frame_threats.append(det)

        # 3. Determine if alert is needed
        trigger_alert = self.scorer.should_alert(high_threats)
        
        alert_message = ""
        if trigger_alert:
            # Generate a simple alert message
            top_threat = max(high_threats, key=lambda x: x['threat_score'])
            label_map = {
                'person': '行人',
                'car': '车辆',
                'obstacle': '障碍物'
            }
            label = label_map.get(top_threat['label'].lower(), top_threat['label'])
            alert_message = f"注意，前方有{label}接近。"

        return {
            "detections": frame_threats,
            "trigger_alert": trigger_alert,
            "alert_message": alert_message
        }
