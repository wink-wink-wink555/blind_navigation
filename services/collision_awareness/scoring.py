import time
from typing import List, Optional

class CollisionScorer:
    def __init__(self, ttc_threshold=3.0, alert_cooldown=5.0):
        self.ttc_threshold = ttc_threshold
        self.alert_cooldown = alert_cooldown
        self.last_alert_time = 0

    def calculate_score(self, ttc: Optional[float], label: str) -> float:
        """
        Calculates a threat score from 0 to 100.
        """
        if ttc is None:
            return 0.0
            
        # Priority mapping for common obstacles
        priority_map = {
            'person': 1.2,
            'car': 1.5,
            'bus': 1.5,
            'truck': 1.5,
            'bicycle': 1.1,
            'motorcycle': 1.2,
            'dog': 1.0,
            'obstacle': 1.0
        }
        
        weight = priority_map.get(label.lower(), 1.0)
        
        # Lower TTC -> Higher score
        # Score = 100 * (threshold / ttc) * weight
        if ttc <= 0: return 100.0
        score = min(100.0, (self.ttc_threshold / ttc) * 50 * weight)
        
        return round(score, 2)

    def should_alert(self, high_threat_detections: List[dict]) -> bool:
        """
        Determines if a voice alert should be triggered based on cooldown.
        """
        if not high_threat_detections:
            return False
            
        now = time.time()
        if now - self.last_alert_time >= self.alert_cooldown:
            self.last_alert_time = now
            return True
        return False
