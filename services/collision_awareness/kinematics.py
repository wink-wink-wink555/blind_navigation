from typing import Optional, Tuple

class CollisionKinematics:
    """
    Calculates Time-To-Collision (TTC) using bounding box expansion.
    Robust against lack of depth sensors.
    """
    def __init__(self, ema_alpha=0.3):
        self.ema_alpha = ema_alpha

    def compute_ttc(self, history) -> Optional[float]:
        """
        Calculates TTC based on height expansion.
        history: deque of (box, timestamp)
        """
        if len(history) < 3:
            return None

        # Use EMA of instantaneous TTC or just simple delta
        b1, t1 = history[-2]
        b2, t2 = history[-1]
        
        dt = t2 - t1
        if dt <= 0:
            return None

        h1 = b1[3] - b1[1]
        h2 = b2[3] - b2[1]
        
        dh = h2 - h1
        if dh <= 0:
            # Not approaching or stationary height-wise
            return None

        # Expansion-based TTC (tau)
        # TTC = current_height / (change_in_height / dt)
        expansion_rate = dh / dt
        ttc = h2 / expansion_rate
        
        return round(ttc, 2)
