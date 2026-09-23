"""Event, routing and degraded-mode regression scenarios; no live API key needed."""

import time
import unittest

from services.baidu_navigation import BaiduWalkingProvider, MapServiceError
from services.guidance_bus import GuidanceBus
from services.navigation import NavigationManager


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


def fix(lat=31, lng=121, accuracy=5, offset_ms=0):
    return {"lat": lat, "lng": lng, "accuracy": accuracy,
            "timestamp_ms": int(time.time() * 1000) + offset_ms,
            "coord_type": "wgs84"}


class NavigationScenarios(unittest.TestCase):
    def setUp(self):
        self.bus = GuidanceBus()
        self.manager = NavigationManager(FakeProvider(), self.bus)
        self.session = self.manager.start(7, {"lat": 31.00018, "lng": 121.00018,
                                               "coord_type": "bd09ll"}, fix())

    def events(self):
        return self.bus.events_since(7)

    def test_planned_route_does_not_speak_turn_until_active(self):
        self.assertEqual(self.session["state"], "PLANNED")
        self.manager.report_visual(7, False)
        self.manager.report_visual(7, False)
        self.manager.report_visual(7, False)
        self.assertFalse(any(event["source"] == "SAFETY" and event["kind"] == "speech"
                             for event in self.events()))

    def test_right_branch_is_an_advisory_only(self):
        self.manager.activate(7)
        self.manager.update_position(7, fix(31.00013, 121, offset_ms=1000))
        advisories = [e for e in self.events() if e["source"] == "ROUTE" and "右" in e["text"]]
        self.assertEqual(len(advisories), 1)
        self.assertIn("确认", advisories[0]["text"])
        self.assertEqual(advisories[0]["step_id"], 0)

    def test_three_missing_frames_stop_and_confirm(self):
        self.manager.activate(7)
        for _ in range(3):
            self.manager.report_visual(7, False)
        self.assertEqual(self.manager.snapshot(7)["state"], "UNCERTAIN")
        alerts = [e for e in self.events() if e["source"] == "SAFETY" and e["kind"] == "speech"]
        self.assertEqual(len(alerts), 1)
        self.assertIn("停下", alerts[0]["text"])

    def test_vision_veto_and_explicit_recovery(self):
        self.manager.activate(7)
        for _ in range(3):
            self.manager.report_visual(7, False)
        self.manager.update_position(7, fix(31.00013, 121, offset_ms=1000))
        self.assertFalse(any("右" in e["text"] for e in self.events()))
        self.manager.report_visual(7, True)
        self.manager.report_visual(7, True)
        self.manager.update_position(7, fix(31.00014, 121, offset_ms=2000))
        self.assertEqual(self.manager.snapshot(7)["state"], "UNCERTAIN")
        self.manager.update_position(7, fix(31.00015, 121, offset_ms=3000))
        self.assertEqual(self.manager.snapshot(7)["state"], "NAVIGATING")

    def test_stationary_junction_does_not_advance_step(self):
        self.manager.activate(7)
        self.manager.update_position(7, fix(31.00018, 121, offset_ms=1000))
        self.manager.update_position(7, fix(31.00018, 121, offset_ms=2000))
        self.assertEqual(self.manager.snapshot(7)["step_index"], 0)
        self.manager.update_position(7, fix(31.00018, 121.00013, offset_ms=3000))
        self.manager.update_position(7, fix(31.00018, 121.00014, offset_ms=4000))
        self.assertEqual(self.manager.snapshot(7)["step_index"], 1)

    def test_no_position_callback_triggers_health_pause(self):
        self.manager.activate(7)
        with self.manager._lock:
            self.manager._sessions[7]["last_position"]["timestamp_ms"] -= 20000
        self.assertEqual(self.manager.check_health(7)["uncertain_reason"], "GPS")
        self.assertTrue(any("定位已中断" in e["text"] for e in self.events()))
        self.assertFalse(any(e["kind"] == "speech" and "右" in e["text"]
                             for e in self.events()))

    def test_off_route_requires_replan(self):
        self.manager.activate(7)
        for i in range(3):
            self.manager.update_position(7, fix(31.005, 121, offset_ms=(i + 1) * 1000))
        self.assertEqual(self.manager.snapshot(7)["uncertain_reason"], "OFF_ROUTE")
        for i in range(2):
            self.manager.update_position(7, fix(31.0001, 121, offset_ms=(i + 4) * 1000))
        self.assertEqual(self.manager.snapshot(7)["state"], "UNCERTAIN")

    def test_map_crossing_stops_for_manual_confirmation(self):
        self.manager._sessions[7]["route"]["steps"][1]["turn_type_id"] = 26
        self.manager.activate(7)
        self.manager.update_position(7, fix(31.00012, 121, offset_ms=1000))
        current = self.manager.snapshot(7)
        self.assertEqual(current["uncertain_reason"], "CROSSING")
        self.assertTrue(any("过街" in e["text"] for e in self.events()))
        self.assertFalse(any("向左转" in e["text"] for e in self.events()))

    def test_bad_gps_pauses_turn_guidance(self):
        self.manager.activate(7)
        outcome = self.manager.update_position(7, fix(31.00015, 121, accuracy=45, offset_ms=1000))
        self.assertEqual(outcome["navigation"]["state"], "UNCERTAIN")
        self.assertFalse(any("右" in e["text"] for e in self.events()))

    def test_new_route_invalidates_old_revision_and_stop_clears_session(self):
        old_revision = self.session["route_revision"]
        self.manager.replan(7, fix(offset_ms=1000))
        self.assertGreater(self.manager.snapshot(7)["route_revision"], old_revision)
        self.manager.stop(7)
        self.assertIsNone(self.manager.snapshot(7))
        self.assertIsNone(self.events()[-1]["session_id"])

    def test_out_of_order_and_stale_location_rejected(self):
        with self.assertRaises(ValueError):
            self.manager.update_position(7, fix(offset_ms=-20000))
        with self.assertRaises(ValueError):
            self.manager.update_position(7, self.session["last_position"])

    def test_destination_coordinate_system_must_be_explicit(self):
        with self.assertRaises(ValueError):
            self.manager.start(7, {"lat": 31.00018, "lng": 121.00018}, fix())
        self.assertEqual(self.manager.snapshot(7)["session_id"], self.session["session_id"])

    def test_route_provider_failure_invalidates_old_navigation(self):
        class Offline(FakeProvider):
            def plan(self, origin, destination):
                raise MapServiceError("百度步行路线不可用")
        self.manager.activate(7)
        self.manager.provider = Offline()
        with self.assertRaises(MapServiceError):
            self.manager.start(7, {"lat": 31.0002, "lng": 121.0002,
                                   "coord_type": "bd09ll"}, fix(offset_ms=1000))
        self.assertIsNone(self.manager.snapshot(7))
        self.assertGreater(self.manager.context(7)["route_revision"], self.session["route_revision"])


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


class FakeHttpSession:
    def __init__(self):
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append((url, params, timeout))
        if "geoconv" in url:
            return FakeResponse({"status": 0, "result": [{"x": 121.01, "y": 31.01}]})
        return FakeResponse({"status": 0, "result": {"routes": [{"distance": 25,
            "duration": 30, "steps": [{"stepOriginLocation": {"lat": 31.01, "lng": 121.01},
            "stepDestinationLocation": {"lat": 31.02, "lng": 121.02},
            "turn_type_id": 3, "instructions": "向右转", "path": "121.01,31.01;121.02,31.02"}]}]}})


class ProviderContract(unittest.TestCase):
    def test_wgs84_is_converted_before_walking_route(self):
        http = FakeHttpSession()
        provider = BaiduWalkingProvider("test-ak", session=http)
        start = provider.to_bd09(31, 121)
        route = provider.plan(start, {"lat": 31.02, "lng": 121.02})
        self.assertEqual(http.calls[0][1]["coords"], "121.0000000,31.0000000")
        self.assertEqual(http.calls[1][1]["coord_type"], "bd09ll")
        self.assertEqual(route["steps"][0]["turn_type_id"], 3)
        self.assertEqual(route["steps"][0]["end"]["lng"], 121.02)

    def test_missing_geometry_cannot_be_used_for_live_steps(self):
        class Incomplete(FakeHttpSession):
            def get(self, url, params, timeout):
                return FakeResponse({"status": 0, "result": {"routes": [{"steps": [{}]}]}})
        with self.assertRaises(MapServiceError):
            BaiduWalkingProvider("test-ak", session=Incomplete()).plan(
                {"lat": 31, "lng": 121}, {"lat": 32, "lng": 122})


class BusContract(unittest.TestCase):
    def test_recipient_isolation_and_expiry(self):
        bus = GuidanceBus()
        one = bus.publish(1, "speech", "家属消息", priority="FAMILY", ttl_ms=300000)
        bus.publish(2, "speech", "他人的消息", priority="FAMILY", ttl_ms=300000)
        self.assertEqual([e["text"] for e in bus.events_since(1)], ["家属消息"])
        self.assertEqual([e["text"] for e in bus.events_since(2)], ["他人的消息"])
        one["created_at_ms"] = 0  # Returned events cannot mutate stored events.
        self.assertNotEqual(bus.events_since(1)[0]["created_at_ms"], 0)

    def test_only_recipient_can_ack_sender_can_check_delivery(self):
        bus = GuidanceBus()
        event = bus.publish(12, "speech", "联络信息", priority="FAMILY", sender_id=3)
        with self.assertRaises(ValueError):
            bus.acknowledge(99, event["event_id"], "FINISHED")
        self.assertEqual(bus.status(3, event["event_id"]), "QUEUED")
        bus.acknowledge(12, event["event_id"], "PLAYING")
        bus.acknowledge(12, event["event_id"], "PAUSED")
        self.assertEqual(bus.status(3, event["event_id"]), "PAUSED")
        bus.acknowledge(12, event["event_id"], "PLAYING")
        bus.acknowledge(12, event["event_id"], "FINISHED")
        self.assertEqual(bus.status(3, event["event_id"]), "FINISHED")
        self.assertEqual(bus.events_since(12), [])


if __name__ == "__main__":
    unittest.main()
