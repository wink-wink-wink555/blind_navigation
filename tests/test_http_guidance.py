"""HTTP boundary test with a fake map and camera, using Flask if available."""

from io import BytesIO
import importlib.util
import sys
import time
import types
import unittest
from unittest.mock import patch

try:
    from flask import Flask
except ImportError:
    Flask = None


@unittest.skipUnless(Flask, "Flask is not installed in this test environment")
class HttpGuidanceContract(unittest.TestCase):
    def setUp(self):
        if "config" not in sys.modules and importlib.util.find_spec("config") is None:
            config = types.ModuleType("config")
            config.BAIDU_MAP_CONFIG = {"api_key": "test-ak"}
            config.DB_CONFIG = {}
            config.EMAIL_CONFIG = {}
            config.DEFAULT_USER_SETTINGS = {"user_mode": "盲人端"}
            sys.modules["config"] = config
        from routes.guidance import guidance_bp, navigation_manager
        from routes.main import main_bp
        from services.guidance_bus import guidance_bus
        self.manager = navigation_manager
        self.bus = guidance_bus
        self.original_provider = self.manager.provider

        class FakeProvider:
            def to_bd09(self, lat, lng, coord_type):
                return {"lat": lat, "lng": lng}

            def plan(self, origin, destination):
                return {"origin": dict(origin), "destination": destination, "coord_type": "bd09ll",
                        "distance": 20, "duration": 30, "steps": [{"id": 0,
                            "start": {"lat": 31, "lng": 121},
                            "end": {"lat": 31.00018, "lng": 121},
                            "path": "", "turn_type_id": 1}]}

        self.manager.provider = FakeProvider()
        app = Flask(__name__)
        app.secret_key = "test-secret"
        app.register_blueprint(guidance_bp)
        app.register_blueprint(main_bp)
        self.a = app.test_client()
        self.b = app.test_client()
        with self.a.session_transaction() as state:
            state["user_id"] = 321
        with self.b.session_transaction() as state:
            state["user_id"] = 322

    def tearDown(self):
        self.manager.provider = self.original_provider
        self.manager.stop(321)

    @staticmethod
    def location(offset=0):
        return {"lat": 31, "lng": 121, "accuracy": 4,
                "timestamp_ms": int(time.time() * 1000) + offset,
                "coord_type": "wgs84"}

    def test_start_activate_vision_event_and_recipient_boundaries(self):
        started = self.a.post('/navigation/start', json={
            "destination": {"lat": 31.00018, "lng": 121, "coord_type": "bd09ll"},
            "position": self.location()})
        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json["navigation"]["state"], "PLANNED")
        self.assertIsNone(self.b.get('/navigation/status').json["navigation"])
        self.assertEqual(self.a.post('/navigation/activate').json["navigation"]["state"], "NAVIGATING")

        from routes.guidance import vision_observer
        with patch.object(vision_observer, "analyze", return_value={"visible": False,
                           "detections": 0, "max_confidence": 0, "branch_status": "UNKNOWN"}):
            for _ in range(3):
                response = self.a.post('/vision/frame', data={"frame": (BytesIO(b'fake'), 'f.jpg')})
                self.assertEqual(response.status_code, 200)

        warning = next(e for e in self.bus.events_since(321)
                       if e["source"] == "SAFETY" and e["kind"] == "speech")
        self.assertIsNone(self.bus.status(322, warning["event_id"]))
        forbidden = self.b.post('/guidance/ack', json={"event_id": warning["event_id"],
                             "delivery_status": "FINISHED"})
        self.assertEqual(forbidden.status_code, 400)
        stream = self.a.get('/guidance/events', buffered=False)
        first_chunk = next(stream.response)
        self.assertIn(b'event: guidance', first_chunk)
        stream.close()

    def test_sensor_error_pauses_route_and_location_is_isolated(self):
        from services.location_store import read
        started = self.a.post('/navigation/start', json={
            "destination": {"lat": 31.00018, "lng": 121, "coord_type": "bd09ll"},
            "position": self.location()})
        self.assertEqual(started.status_code, 200)
        self.a.post('/navigation/activate')
        position = self.a.post('/navigation/position', json={"position": self.location(1000)})
        self.assertEqual(position.status_code, 200)
        self.assertEqual(read(321)["coord_type"], "bd09ll")
        self.assertIsNone(read(322))
        failed = self.a.post('/vision/unavailable')
        self.assertEqual(failed.json["navigation"]["state"], "UNCERTAIN")
        self.assertEqual(self.a.get('/navigation/status').json["context"]["nav_state"], "UNCERTAIN")
        invalid = self.a.post('/navigation/start', json={
            "destination": {"lat": 31.00018, "lng": 121},
            "position": self.location(2000)})
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(self.a.get('/navigation/status').json["context"]["nav_state"], "UNCERTAIN")

    def test_frame_metadata_alignment_and_out_of_order_rejection(self):
        started = self.a.post('/navigation/start', json={
            "destination": {"lat": 31.00018, "lng": 121, "coord_type": "bd09ll"},
            "position": self.location()})
        self.assertEqual(started.status_code, 200)
        self.a.post('/navigation/activate')

        from routes.guidance import vision_observer

        def fake_analyze(frame, frame_seq=None, captured_at_ms=None):
            return {"visible": True, "detections": 1, "max_confidence": 0.9,
                    "boxes": [{"confidence": 0.9, "box": [300, 200, 380, 330]}],
                    "branch_status": "UNKNOWN",
                    "geometry": {"status": "VALID", "path_center_x": 336.0,
                                 "reference_center_x": 240, "normalized_offset": 0.2,
                                 "confidence": 0.8, "selected_detection_count": 1,
                                 "candidate_count": 1},
                    "frame_seq": frame_seq, "captured_at_ms": captured_at_ms,
                    "processed_at_ms": int(time.time() * 1000)}

        with patch.object(vision_observer, "analyze", side_effect=fake_analyze):
            for seq in (1, 2, 3):
                response = self.a.post('/vision/frame', data={
                    "frame": (BytesIO(b'fake'), 'f.jpg'), "frame_seq": str(seq),
                    "captured_at_ms": str(int(time.time() * 1000))})
                self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["alignment"]["state"], "CORRECT_RIGHT")
            self.assertEqual(response.json["observation"]["geometry"]["status"], "VALID")
            self.assertEqual(response.json["observation"]["frame_seq"], 3)
            # An out-of-order frame sequence must not change anything.
            response = self.a.post('/vision/frame', data={
                "frame": (BytesIO(b'fake'), 'f.jpg'), "frame_seq": "1",
                "captured_at_ms": str(int(time.time() * 1000))})
            self.assertEqual(response.json["alignment"]["state"], "CORRECT_RIGHT")
            # Malformed frame metadata is rejected at the boundary.
            bad = self.a.post('/vision/frame', data={
                "frame": (BytesIO(b'fake'), 'f.jpg'), "frame_seq": "abc"})
            self.assertEqual(bad.status_code, 400)

        alignment_events = [e for e in self.bus.events_since(321)
                            if e["kind"] == "speech" and e["source"] == "ALIGNMENT"]
        self.assertEqual(len(alignment_events), 1)  # one hint per episode
        self.assertLessEqual(alignment_events[0]["ttl_ms"], 4000)
        self.assertIsNotNone(alignment_events[0]["alignment_epoch"])

    def test_family_message_authorization_and_delivery_receipt(self):
        with patch('routes.main.get_user_settings', return_value=({"user_mode": "家属端"}, "ok")), \
             patch('routes.main.resolve_caregiver_recipient', return_value=322):
            result = self.a.post('/send_message', json={
                "recipient_username": "recipient", "message": "请报平安"})
        self.assertEqual(result.status_code, 200)
        event_id = result.json['event_id']
        delivered = next(e for e in self.bus.events_since(322) if e['event_id'] == event_id)
        self.assertEqual(delivered['source'], 'FAMILY')
        self.assertEqual(delivered['resume_policy'], 'continue')
        self.assertEqual(self.a.get(f'/family_message_status/{event_id}').json['delivery_status'], 'QUEUED')
        self.assertEqual(self.b.post('/guidance/ack', json={
            'event_id': event_id, 'delivery_status': 'FINISHED'}).status_code, 200)
        self.assertEqual(self.a.get(f'/family_message_status/{event_id}').json['delivery_status'], 'FINISHED')
        self.assertEqual(self.b.get(f'/family_message_status/{event_id}').json['delivery_status'], 'FINISHED')
        with patch('routes.main.get_user_settings', return_value=({"user_mode": "家属端"}, "ok")), \
             patch('routes.main.resolve_caregiver_recipient', return_value=None):
            self.assertEqual(self.a.post('/send_message', json={
                "recipient_username": "other", "message": "未授权"}).status_code, 403)


if __name__ == '__main__':
    unittest.main()
