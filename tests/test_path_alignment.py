"""Path geometry estimator and alignment state machine regression scenarios.

Covers: near-field geometry, candidate selection, temporal stability,
hysteresis, correction episodes, positive feedback, turn-zone suppression,
crossing gating, severe deviation, visual loss and stale/out-of-order frames.
No live API key or camera is needed.
"""

import time
import unittest
from unittest.mock import patch

from services.guidance_bus import GuidanceBus
from services.navigation import (
    ALIGN_SPEECH_TTL_MS,
    ALIGNMENT_SPEECH,
    NavigationManager,
    PRAISE_SPEECH,
    SEVERE_SPEECH,
)
from services.path_alignment import PathGeometryEstimator


W, H = 480, 360  # matches the browser capture canvas


def detection(cx, y1, y2, confidence=0.85, half_width=40):
    return {"confidence": confidence, "box": [cx - half_width, y1, cx + half_width, y2]}


class PathGeometryEstimation(unittest.TestCase):
    def setUp(self):
        self.estimator = PathGeometryEstimator()

    def test_left_box_gives_negative_offset(self):
        result = self.estimator.estimate(W, H, [detection(100, 200, 320)])
        self.assertEqual(result.status, "VALID")
        self.assertLess(result.normalized_offset, 0)
        self.assertAlmostEqual(result.normalized_offset, (100 - 240) / 480, places=3)

    def test_right_box_gives_positive_offset(self):
        result = self.estimator.estimate(W, H, [detection(380, 200, 320)])
        self.assertEqual(result.status, "VALID")
        self.assertGreater(result.normalized_offset, 0)

    def test_centered_box_gives_near_zero_offset(self):
        result = self.estimator.estimate(W, H, [detection(240, 200, 320)])
        self.assertEqual(result.status, "VALID")
        self.assertAlmostEqual(result.normalized_offset, 0.0, places=3)

    def test_conflicting_candidates_are_ambiguous(self):
        result = self.estimator.estimate(W, H, [detection(70, 200, 320),
                                                detection(410, 200, 320)])
        self.assertEqual(result.status, "AMBIGUOUS")
        self.assertIsNone(result.normalized_offset)

    def test_low_confidence_detection_is_rejected(self):
        result = self.estimator.estimate(W, H, [detection(380, 200, 320, confidence=0.20)])
        self.assertEqual(result.status, "LOW_CONFIDENCE")

    def test_distant_detection_cannot_steer(self):
        # Entirely above the near-field ROI (top half of the frame).
        result = self.estimator.estimate(W, H, [detection(380, 120, 176)])
        self.assertEqual(result.status, "NO_NEAR_FIELD")

    def test_no_detection_is_no_path(self):
        self.assertEqual(self.estimator.estimate(W, H, []).status, "NO_PATH")

    def test_near_field_beats_far_high_confidence(self):
        # The most confident box is far away; the near box must be selected.
        result = self.estimator.estimate(W, H, [detection(400, 120, 176, confidence=0.95),
                                                detection(300, 240, 330, confidence=0.55)])
        self.assertEqual(result.status, "VALID")
        self.assertEqual(result.selected_detection_count, 1)
        self.assertAlmostEqual(result.path_center_x, 300, delta=25)

    def test_diagonal_strip_evaluated_at_near_field_row(self):
        # A strip receding to the upper right: the fitted centerline at the
        # near-field row stays near the close box instead of the full average.
        result = self.estimator.estimate(W, H, [detection(300, 250, 330),
                                                detection(370, 185, 240)])
        self.assertEqual(result.status, "VALID")
        self.assertLess(result.path_center_x, (300 + 370) / 2)
        self.assertGreater(result.path_center_x, 240)

    def test_custom_reference_center_shifts_offset(self):
        estimator = PathGeometryEstimator(reference_center_x=200)
        result = estimator.estimate(W, H, [detection(240, 200, 320)])
        self.assertEqual(result.status, "VALID")
        self.assertGreater(result.normalized_offset, 0)  # path right of x_ref=200

    def test_invalid_frame_size_rejected(self):
        with self.assertRaises(ValueError):
            self.estimator.estimate(0, H, [detection(240, 200, 320)])


class FakeProvider:
    def to_bd09(self, lat, lng, coord_type):
        assert coord_type == "wgs84"
        return {"lat": lat, "lng": lng}

    def plan(self, origin, destination):
        return {"origin": dict(origin), "destination": dict(destination),
                "distance": 45, "duration": 40, "coord_type": "bd09ll",
                "steps": [
                    {"id": 0, "start": {"lat": 31, "lng": 121},
                     "end": {"lat": 31.00018, "lng": 121}, "path": "", "turn_type_id": 1},
                    {"id": 1, "start": {"lat": 31.00018, "lng": 121},
                     "end": {"lat": 31.00018, "lng": 121.00018}, "path": "",
                     "turn_type_id": 3},
                ]}


class AlignmentStateMachine(unittest.TestCase):
    def setUp(self):
        self.now_ms = 1_700_000_000_000
        patcher = patch("time.time", lambda: self.now_ms / 1000)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.bus = GuidanceBus()
        self.manager = NavigationManager(FakeProvider(), self.bus)
        self.seq = 0
        self.manager.start(7, {"lat": 31.00018, "lng": 121.00018, "coord_type": "bd09ll"},
                           self.fix())
        self.manager.activate(7)

    def fix(self, lat=31, lng=121, accuracy=5, offset_ms=0):
        return {"lat": lat, "lng": lng, "accuracy": accuracy,
                "timestamp_ms": self.now_ms + offset_ms, "coord_type": "wgs84"}

    def obs(self, offset=0.0, status="VALID", confidence=0.85, seq=None, captured_offset=0):
        self.seq += 1
        geometry = {"status": status,
                    "path_center_x": 240 + (offset or 0) * W if status == "VALID" else None,
                    "reference_center_x": 240,
                    "normalized_offset": offset if status == "VALID" else None,
                    "confidence": confidence,
                    "selected_detection_count": 1 if status == "VALID" else 0,
                    "candidate_count": 1}
        return {"visible": True, "detections": 1, "max_confidence": confidence,
                "boxes": [{"confidence": confidence, "box": [200, 200, 280, 330]}],
                "branch_status": "UNKNOWN", "geometry": geometry,
                "frame_seq": self.seq if seq is None else seq,
                "captured_at_ms": self.now_ms + captured_offset,
                "processed_at_ms": self.now_ms + captured_offset + 40}

    def speeches(self, source=None):
        return [e for e in self.bus.events_since(7)
                if e["kind"] == "speech" and (source is None or e["source"] == source)]

    def state(self):
        return self.manager.snapshot(7)["alignment_state"]

    def stable_deviation(self, offset=0.2, frames=4):
        for _ in range(frames):
            self.manager.report_visual(7, self.obs(offset))

    def ack_correction(self, status="PLAYING"):
        for event in self.speeches("ALIGNMENT"):
            self.bus.acknowledge(7, event["event_id"], status)

    # -- temporal stability -------------------------------------------------
    def test_single_deviating_frame_stays_silent(self):
        self.manager.report_visual(7, self.obs(0.2))
        self.assertEqual(self.speeches("ALIGNMENT"), [])
        self.assertIsNone(self.manager.snapshot(7)["alignment_episode"])

    def test_stable_deviation_opens_one_episode_with_one_hint(self):
        self.stable_deviation(0.2)
        self.assertEqual(self.state(), "CORRECT_RIGHT")
        hints = self.speeches("ALIGNMENT")
        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0]["text"], ALIGNMENT_SPEECH["CORRECT_RIGHT"])
        self.assertLessEqual(hints[0]["ttl_ms"], ALIGN_SPEECH_TTL_MS)
        self.assertEqual(hints[0]["alignment_epoch"],
                         self.manager.snapshot(7)["alignment_epoch"])
        episode = self.manager.snapshot(7)["alignment_episode"]
        self.assertEqual(episode["direction"], "CORRECT_RIGHT")
        self.assertEqual(episode["speech_event_id"], hints[0]["event_id"])

    def test_persistent_deviation_does_not_repeat_every_frame(self):
        self.stable_deviation(0.2, frames=8)
        self.assertEqual(len(self.speeches("ALIGNMENT")), 1)

    def test_repeat_hint_only_after_quiet_interval(self):
        self.stable_deviation(0.2)
        cursor = self.bus.latest_id(7)
        self.now_ms += 11000  # past the conservative repeat interval
        self.stable_deviation(0.2, frames=2)
        repeats = [e for e in self.bus.events_since(7, after=cursor)
                   if e["kind"] == "speech" and e["source"] == "ALIGNMENT"]
        self.assertEqual(len(repeats), 1)
        episode = self.manager.snapshot(7)["alignment_episode"]
        self.assertEqual(episode["speech_count"], 2)

    def test_flapping_around_threshold_never_oscillates(self):
        for offset in (0.13, 0.05, 0.13, 0.06, 0.13, 0.05):
            self.manager.report_visual(7, self.obs(offset))
        self.assertEqual(self.speeches("ALIGNMENT"), [])
        self.assertEqual(self.state(), "CENTERED")

    def test_brief_recenter_does_not_complete_episode(self):
        self.stable_deviation(0.2)
        self.manager.report_visual(7, self.obs(0.0))  # one centered frame only
        self.assertIsNotNone(self.manager.snapshot(7)["alignment_episode"])
        self.assertEqual([e for e in self.speeches("BACKGROUND") if "回正" in e["text"]], [])
        self.manager.report_visual(7, self.obs(0.2))
        self.assertEqual(self.state(), "CORRECT_RIGHT")

    def test_re_deviation_same_direction_does_not_re_speak(self):
        self.stable_deviation(0.2)
        # Brief improvement, then the same deviation returns: the same
        # episode continues and the main hint is not repeated.
        self.manager.report_visual(7, self.obs(0.05))
        self.manager.report_visual(7, self.obs(0.06))
        self.assertEqual(self.state(), "RECOVERING")
        self.stable_deviation(0.2)
        self.assertEqual(self.state(), "CORRECT_RIGHT")
        self.assertEqual(len(self.speeches("ALIGNMENT")), 1)
        self.assertEqual(self.manager.snapshot(7)["alignment_episode"]["speech_count"], 1)

    def test_severe_never_falls_back_into_immediate_nudging(self):
        self.stable_deviation(0.3, frames=4)
        self.assertEqual(self.state(), "SEVERE")
        # Offset improves but the filtered median is still in severe
        # territory: no micro-correction hint may follow the safety alert.
        self.stable_deviation(0.15, frames=2)
        # While the filtered median is still in severe territory, no
        # micro-correction hint may follow the safety alert.
        self.assertEqual(self.speeches("ALIGNMENT"), [])
        self.stable_deviation(0.15, frames=3)
        self.assertNotEqual(self.state(), "SEVERE")
        # Once the median has genuinely left severe territory, at most one
        # conservative hint for the remaining moderate deviation.
        self.assertLessEqual(len(self.speeches("ALIGNMENT")), 1)

    # -- correction episode and positive feedback ---------------------------
    def test_recovery_after_played_correction_gives_one_praise(self):
        self.stable_deviation(0.2)
        self.ack_correction()
        for _ in range(3):
            self.manager.report_visual(7, self.obs(0.0))
        self.assertEqual(self.state(), "CENTERED")
        self.assertIsNone(self.manager.snapshot(7)["alignment_episode"])
        praises = [e for e in self.speeches("BACKGROUND") if "回正" in e["text"]]
        self.assertEqual(len(praises), 1)
        self.assertEqual(praises[0]["text"], PRAISE_SPEECH)

    def test_praise_requires_actually_played_correction(self):
        self.stable_deviation(0.2)
        # No playback receipt: the correction never reached the user's ears.
        for _ in range(3):
            self.manager.report_visual(7, self.obs(0.0))
        self.assertEqual(self.state(), "CENTERED")
        self.assertEqual([e for e in self.speeches("BACKGROUND") if "回正" in e["text"]], [])

    def test_praise_needs_an_episode_and_respects_cooldown(self):
        # No episode at all: staying centered never earns praise.
        for _ in range(4):
            self.manager.report_visual(7, self.obs(0.0))
        self.assertEqual([e for e in self.speeches("BACKGROUND") if "回正" in e["text"]], [])
        # First episode completes with praise.
        self.stable_deviation(0.2)
        self.ack_correction()
        for _ in range(3):
            self.manager.report_visual(7, self.obs(0.0))
        self.assertEqual(len([e for e in self.speeches("BACKGROUND") if "回正" in e["text"]]), 1)
        # A second episode inside the cooldown is guided but not praised.
        self.stable_deviation(0.2)
        self.ack_correction()
        cursor = self.bus.latest_id(7)
        for _ in range(3):
            self.manager.report_visual(7, self.obs(0.0))
        recent = self.bus.events_since(7, after=cursor)
        self.assertEqual([e for e in recent if e["kind"] == "speech" and "回正" in e["text"]], [])
        # After the cooldown, a completed correction is praised once again.
        self.now_ms += 21000
        self.stable_deviation(0.2)
        self.ack_correction()
        cursor = self.bus.latest_id(7)
        for _ in range(3):
            self.manager.report_visual(7, self.obs(0.0))
        recent = self.bus.events_since(7, after=cursor)
        praises = [e for e in recent if e["kind"] == "speech" and "回正" in e["text"]]
        self.assertEqual(len(praises), 1)

    def test_direction_flip_closes_old_episode_without_praise(self):
        self.stable_deviation(0.2)
        self.ack_correction()
        self.stable_deviation(-0.2)
        self.assertEqual(self.state(), "CORRECT_LEFT")
        texts = [e["text"] for e in self.speeches("ALIGNMENT")]
        self.assertEqual(texts, [ALIGNMENT_SPEECH["CORRECT_RIGHT"],
                                 ALIGNMENT_SPEECH["CORRECT_LEFT"]])
        self.assertEqual([e for e in self.speeches("BACKGROUND") if "回正" in e["text"]], [])

    # -- navigation gating ----------------------------------------------------
    def test_alignment_requires_navigating_state(self):
        self.manager.stop(7)
        self.manager.start(7, {"lat": 31.00018, "lng": 121.00018, "coord_type": "bd09ll"},
                           self.fix(offset_ms=1000))
        self.stable_deviation(0.2)  # still PLANNED
        self.assertEqual(self.speeches("ALIGNMENT"), [])
        self.assertEqual(self.state(), "UNKNOWN")

    def test_turn_zone_suppresses_steering_but_keeps_route_advisory(self):
        # Move close to the end of step 0; the next step turns right.
        self.manager.update_position(7, self.fix(31.00010, 121, offset_ms=1000))
        self.assertTrue(any("右转" in e["text"] for e in self.speeches("ROUTE")))
        self.stable_deviation(0.2)
        self.assertEqual(self.speeches("ALIGNMENT"), [])
        self.assertEqual(self.state(), "SUPPRESSED")
        # Far from the junction again, steering resumes.
        self.manager.replan(7, self.fix(31, 121, offset_ms=2000))
        self.manager.activate(7)
        self.stable_deviation(0.2)
        self.assertEqual(len(self.speeches("ALIGNMENT")), 1)

    def test_crossing_forbids_steering_but_keeps_safety(self):
        self.manager._sessions[7]["route"]["steps"][1]["turn_type_id"] = 26
        self.manager.update_position(7, self.fix(31.00012, 121, offset_ms=1000))
        self.assertEqual(self.manager.snapshot(7)["uncertain_reason"], "CROSSING")
        self.stable_deviation(0.2)
        self.assertEqual(self.speeches("ALIGNMENT"), [])
        self.assertTrue(any("过街" in e["text"] for e in self.speeches("SAFETY")))

    def test_severe_deviation_escalates_to_safety(self):
        self.stable_deviation(0.3, frames=4)
        self.assertEqual(self.state(), "SEVERE")
        self.assertEqual(self.speeches("ALIGNMENT"), [])
        safety = [e for e in self.speeches("SAFETY") if "偏差较大" in e["text"]]
        self.assertEqual(len(safety), 1)
        self.assertEqual(safety[0]["text"], SEVERE_SPEECH)

    def test_ambiguous_geometry_never_guesses(self):
        for _ in range(4):
            self.manager.report_visual(7, self.obs(status="AMBIGUOUS"))
        self.assertEqual(self.state(), "AMBIGUOUS")
        self.assertEqual(self.speeches("ALIGNMENT"), [])

    def test_visual_loss_keeps_original_safety_behavior(self):
        for _ in range(3):
            self.manager.report_visual(7, False)
        snapshot = self.manager.snapshot(7)
        self.assertEqual(snapshot["state"], "UNCERTAIN")
        self.assertEqual(snapshot["vision_status"], "NOT_VISIBLE")
        self.assertTrue(any("未识别到盲道" in e["text"] for e in self.speeches("SAFETY")))
        self.assertEqual(self.speeches("ALIGNMENT"), [])

    # -- frame freshness ------------------------------------------------------
    def test_out_of_order_frame_never_rolls_state_back(self):
        self.stable_deviation(0.2)
        before = self.manager.snapshot(7)
        stale = self.obs(-0.3, seq=1)  # older sequence with opposite direction
        self.manager.report_visual(7, stale)
        after = self.manager.snapshot(7)
        self.assertEqual(after["alignment_state"], before["alignment_state"])
        self.assertEqual(after["alignment_history"], before["alignment_history"])

    def test_stale_capture_never_steers(self):
        for _ in range(4):
            self.manager.report_visual(7, self.obs(0.3, captured_offset=-5000))
        self.assertEqual(self.speeches("ALIGNMENT"), [])
        self.assertNotIn(self.state(), ("CORRECT_LEFT", "CORRECT_RIGHT", "SEVERE"))

    def test_legacy_bool_observations_keep_working(self):
        self.manager.report_visual(7, True)
        self.assertEqual(self.manager.snapshot(7)["vision_status"], "VISIBLE")
        self.assertEqual(self.state(), "UNKNOWN")

    def test_alignment_epoch_invalidates_on_state_change(self):
        self.stable_deviation(0.2)
        epoch_correct = self.manager.snapshot(7)["alignment_epoch"]
        for _ in range(3):
            self.manager.report_visual(7, self.obs(0.0))
        self.assertGreater(self.manager.snapshot(7)["alignment_epoch"], epoch_correct)
        contexts = [e for e in self.bus.events_since(7) if e["kind"] == "context"]
        self.assertTrue(any("alignment_epoch" in e for e in contexts))


if __name__ == "__main__":
    unittest.main()
