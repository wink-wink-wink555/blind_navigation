"""Typed Baidu walking routes and explicit coordinate conversion.

The web navigation flow uses this provider as its only route source. A route
is a plan for a pedestrian, not evidence that tactile paving is present.
"""

from html import unescape
import math
import re

class MapServiceError(RuntimeError):
    pass


def validate_point(lat, lng):
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError) as exc:
        raise ValueError("经纬度必须为数字") from exc
    if not math.isfinite(lat) or not math.isfinite(lng) or not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError("经纬度超出有效范围")
    return lat, lng


def require_bd09(point):
    if not isinstance(point, dict) or point.get("coord_type") != "bd09ll":
        raise ValueError("地图选点必须声明为 BD09 经纬度")
    lat, lng = validate_point(point.get("lat"), point.get("lng"))
    return {"lat": lat, "lng": lng}


def _plain_instruction(value):
    return unescape(re.sub(r"<[^>]*>", "", value or "")).strip()


class BaiduWalkingProvider:
    def __init__(self, api_key, session=None, timeout=8):
        self.api_key = api_key
        if session is None:
            import requests
            session = requests.Session()
        self.session = session
        self.timeout = timeout

    def _get(self, url, params):
        if not self.api_key or self.api_key.startswith("your_"):
            raise MapServiceError("请先配置百度地图 Web 服务 AK")
        try:
            response = self.session.get(url, params={**params, "ak": self.api_key}, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise MapServiceError("百度地图服务暂时不可用") from exc
        if data.get("status") != 0:
            raise MapServiceError(f"百度地图服务错误：{data.get('message') or data.get('status')}")
        return data

    def to_bd09(self, lat, lng, coord_type="wgs84"):
        lat, lng = validate_point(lat, lng)
        if coord_type == "bd09ll":
            return {"lat": lat, "lng": lng}
        if coord_type != "wgs84":
            raise ValueError("不支持的输入坐标系")
        data = self._get("https://api.map.baidu.com/geoconv/v2/", {
            "coords": f"{lng:.7f},{lat:.7f}", "model": 2, "output": "json"
        })
        result = data.get("result") or []
        if not result:
            raise MapServiceError("坐标转换没有返回结果")
        bd_lat, bd_lng = validate_point(result[0].get("y"), result[0].get("x"))
        return {"lat": bd_lat, "lng": bd_lng}

    def plan(self, origin, destination):
        origin_lat, origin_lng = validate_point(origin.get("lat"), origin.get("lng"))
        dest_lat, dest_lng = validate_point(destination.get("lat"), destination.get("lng"))
        data = self._get("https://api.map.baidu.com/direction/v2/walking", {
            "origin": f"{origin_lat:.6f},{origin_lng:.6f}",
            "destination": f"{dest_lat:.6f},{dest_lng:.6f}",
            "coord_type": "bd09ll", "ret_coordtype": "bd09ll", "output": "json",
        })
        routes = (data.get("result") or {}).get("routes") or []
        if not routes:
            raise MapServiceError("未找到步行路线")
        route = routes[0]
        steps = []
        for index, raw in enumerate(route.get("steps") or []):
            start = raw.get("stepOriginLocation") or raw.get("start_location") or {}
            end = raw.get("stepDestinationLocation") or raw.get("end_location") or {}
            if not all(k in start and k in end for k in ("lat", "lng")):
                raise MapServiceError("步行路线缺少路段定位信息")
            steps.append({
                "id": index, "start": dict(zip(("lat", "lng"), validate_point(start["lat"], start["lng"]))),
                "end": dict(zip(("lat", "lng"), validate_point(end["lat"], end["lng"]))),
                "path": raw.get("path", ""),
                "distance": raw.get("distance", 0),
                "turn_type_id": raw.get("turn_type_id"),
                "instruction": _plain_instruction(raw.get("instructions") or raw.get("instruction")),
            })
        if not steps:
            raise MapServiceError("步行路线缺少路段信息")
        return {
            "origin": {"lat": origin_lat, "lng": origin_lng},
            "destination": {"lat": dest_lat, "lng": dest_lng},
            "distance": route.get("distance", 0), "duration": route.get("duration", 0),
            "steps": steps, "coord_type": "bd09ll",
        }
