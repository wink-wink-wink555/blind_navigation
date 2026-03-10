"""
百度地图MCP（Model Context Protocol）服务类
"""
import requests
from config import BAIDU_MAP_CONFIG


class BaiduMapMCP:
    """百度地图MCP（Model Context Protocol）服务类"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.session = requests.Session()
    
    def validate_api_key(self):
        """验证API密钥是否有效"""
        try:
            # 使用一个简单的地址解析来测试API密钥
            test_params = {
                'address': '北京市',
                'output': 'json',
                'ak': self.api_key
            }
            
            response = self.session.get(BAIDU_MAP_CONFIG['web_service_url'], params=test_params)
            data = response.json()
            
            if data.get('status') == 0:
                return {
                    'valid': True,
                    'message': 'API密钥验证成功'
                }
            else:
                status_code = data.get('status')
                error_explanations = {
                    1: "服务器内部错误",
                    2: "请求参数非法", 
                    3: "权限校验失败",
                    4: "配额校验失败",
                    5: "AK不存在或者非法",
                    101: "服务禁用",
                    102: "不通过白名单或者安全码不对",
                    200: "无权限",
                    300: "配额错误",
                    301: "AK配额超限",
                    302: "天配额超限"
                }
                
                error_msg = error_explanations.get(status_code, data.get('message', '未知错误'))
                
                return {
                    'valid': False,
                    'status_code': status_code,
                    'message': f'API密钥验证失败: {error_msg}',
                    'suggestions': self._get_error_suggestions(status_code)
                }
        except Exception as e:
            return {
                'valid': False,
                'message': f'API密钥验证异常: {str(e)}',
                'suggestions': ['检查网络连接', '确认百度地图API服务可访问']
            }
    
    def _get_error_suggestions(self, status_code):
        """根据错误码提供解决建议"""
        suggestions = {
            5: [
                '1. 检查API密钥是否正确输入',
                '2. 确认在百度地图开放平台创建了应用',
                '3. 验证API密钥是否已启用相应服务'
            ],
            102: [
                '1. 在百度地图开放平台设置IP白名单',
                '2. 如果是本地测试，添加127.0.0.1到白名单',
                '3. 检查安全码设置'
            ],
            200: [
                '1. 确认应用已开通所需的API服务',
                '2. 检查服务权限配置',
                '3. 联系百度地图技术支持'
            ],
            301: [
                '1. 检查API调用配额是否超限',
                '2. 考虑升级到付费版本',
                '3. 优化API调用频率'
            ]
        }
        
        return suggestions.get(status_code, ['请查看百度地图开放平台文档或联系技术支持'])

    def geocoding(self, address, city=None):
        """地址解析：将地址转换为经纬度坐标（返回BD-09坐标系）"""
        try:
            # 如果地址中包含城市名但没有传city参数，自动提取
            if not city:
                # 常见城市列表（可扩展）
                city_keywords = ['北京', '上海', '广州', '深圳', '杭州', '南京', '苏州', '成都', '武汉', '西安', '天津', '重庆']
                for city_name in city_keywords:
                    if city_name in address:
                        city = city_name
                        break
            
            params = {
                'address': address,
                'output': 'json',
                'ak': self.api_key,
                'ret_coordtype': 'bd09ll'  # 明确指定返回百度坐标系BD-09
            }
            if city:
                params['city'] = city
            
            print(f"[MCP调试] 地址解析请求参数: {params}")
            
            response = self.session.get(BAIDU_MAP_CONFIG['web_service_url'], params=params)
            data = response.json()
            
            print(f"[MCP调试] 地址解析响应: {data}")
            
            if data.get('status') == 0:
                result = data['result']
                location = result['location']
                confidence = result.get('confidence', 0)
                precise = result.get('precise', 0)
                level = result.get('level', '')
                
                # 返回详细信息，包括置信度和精确度
                return {
                    'success': True,
                    'lat': location['lat'],
                    'lng': location['lng'],
                    'formatted_address': address,
                    'confidence': confidence,
                    'precise': precise,
                    'level': level,
                    'coordtype': 'bd09ll'  # 标注坐标系类型
                }
            else:
                status_code = data.get('status')
                error_msg = data.get('message', '未知错误')
                return {
                    'success': False,
                    'error': f"地址解析失败 (状态码: {status_code}): {error_msg}",
                    'raw_response': data
                }
        except Exception as e:
            return {
                'success': False,
                'error': f"地址解析异常: {str(e)}"
            }
    
    def reverse_geocoding(self, lat, lng, coordtype='bd09ll'):
        """
        逆地址解析：将经纬度坐标转换为地址
        
        Args:
            lat: 纬度
            lng: 经度  
            coordtype: 坐标类型，支持以下值：
                      - 'bd09ll': 百度经纬度坐标（默认）
                      - 'gcj02ll': 国测局加密经纬度坐标
                      - 'wgs84ll': GPS经纬度坐标
        """
        try:
            # 使用逆地理编码专用URL
            reverse_geocode_url = BAIDU_MAP_CONFIG['web_service_url']
            
            params = {
                'ak': self.api_key,
                'output': 'json',
                'coordtype': coordtype,  # 输入坐标类型
                'location': f"{lat},{lng}",
                'extensions_poi': '0'  # 是否召回周边POI，0-不召回，1-召回
            }
            
            print(f"[MCP调试] 逆地址解析请求参数: {params}")
            print(f"[MCP调试] 请求URL: {reverse_geocode_url}")
            
            response = self.session.get(reverse_geocode_url, params=params)
            data = response.json()
            
            print(f"[MCP调试] 逆地址解析响应: {data}")
            
            if data.get('status') == 0:
                result = data['result']
                return {
                    'success': True,
                    'formatted_address': result.get('formatted_address', ''),
                    'business': result.get('business', ''),
                    'address_components': result.get('addressComponent', {}),
                    'sematic_description': result.get('sematic_description', ''),
                    'coordtype': coordtype
                }
            else:
                status_code = data.get('status')
                error_msg = data.get('message', '未知错误')
                
                # 提供更详细的错误说明
                error_explanations = {
                    1: "服务器内部错误",
                    2: "请求参数非法（可能坐标格式错误）",
                    3: "权限校验失败",
                    4: "配额校验失败",
                    5: "AK不存在或者非法"
                }
                
                detailed_error = error_explanations.get(status_code, error_msg)
                
                return {
                    'success': False,
                    'error': f"逆地址解析失败 (状态码: {status_code}): {detailed_error}",
                    'raw_response': data
                }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': f"逆地址解析异常: {str(e)}"
            }
    
    def search_nearby_places(self, query, lat, lng, radius=1000):
        """搜索附近地点"""
        try:
            params = {
                'query': query,
                'location': f"{lat},{lng}",
                'radius': radius,
                'output': 'json',
                'ak': self.api_key
            }
            
            print(f"[MCP调试] 地点搜索请求参数: {params}")
            print(f"[MCP调试] 请求URL: {BAIDU_MAP_CONFIG['place_search_url']}")
            
            response = self.session.get(BAIDU_MAP_CONFIG['place_search_url'], params=params)
            print(f"[MCP调试] 响应状态码: {response.status_code}")
            
            data = response.json()
            print(f"[MCP调试] 响应数据: {data}")
            
            if data.get('status') == 0:
                places = []
                for place in data.get('results', []):
                    places.append({
                        'name': place['name'],
                        'address': place['address'],
                        'lat': place['location']['lat'],
                        'lng': place['location']['lng'],
                        'distance': place.get('detail_info', {}).get('distance', '未知')
                    })
                
                return {
                    'success': True,
                    'places': places,
                    'total': len(places)
                }
            else:
                # 详细错误信息处理
                status_code = data.get('status')
                error_msg = data.get('message', '未知错误')
                
                # 常见错误码解释
                error_explanations = {
                    1: "服务器内部错误",
                    2: "请求参数非法",
                    3: "权限校验失败",
                    4: "配额校验失败",
                    5: "ak不存在或者非法",
                    101: "服务禁用",
                    102: "不通过白名单或者安全码不对",
                    200: "无权限",
                    300: "配额错误",
                    301: "AK配额超限",
                    302: "天配额超限"
                }
                
                detailed_error = error_explanations.get(status_code, error_msg)
                
                return {
                    'success': False,
                    'error': f"地点搜索失败 (状态码: {status_code}): {detailed_error}",
                    'raw_response': data
                }
        except Exception as e:
            return {
                'success': False,
                'error': f"地点搜索异常: {str(e)}"
            }
    
    def calculate_route(self, origin_lat, origin_lng, dest_lat, dest_lng, mode='walking', coordtype='bd09ll'):
        """
        路线规划（仅支持步行模式 - 视障人士出行辅助系统）
        
        Args:
            origin_lat: 起点纬度
            origin_lng: 起点经度
            dest_lat: 终点纬度
            dest_lng: 终点经度
            mode: 出行方式，本系统仅支持 walking(步行)，其他参数将被忽略
            coordtype: 坐标类型，默认bd09ll（百度坐标系）
        
        Note:
            本系统专为视障人士设计，仅提供步行路线规划。
            即使传入其他mode参数（driving/transit/riding），也会强制使用walking模式。
        """
        try:
            # 强制使用步行模式（视障人士专用）
            mode = 'walking'
            url = BAIDU_MAP_CONFIG['direction_url'] + 'walking'
            
            params = {
                'origin': f"{origin_lat},{origin_lng}",
                'destination': f"{dest_lat},{dest_lng}",
                'coord_type': coordtype,  # 指定坐标系
                'output': 'json',
                'ak': self.api_key
            }
            
            print(f"[MCP调试] 路线规划请求URL: {url}")
            print(f"[MCP调试] 路线规划请求参数: {params}")
            
            response = self.session.get(url, params=params)
            data = response.json()
            
            print(f"[MCP调试] 路线规划响应: {data}")
            
            if data.get('status') == 0:
                result = data.get('result', {})
                routes = result.get('routes', [])
                
                if routes:
                    route = routes[0]
                    return {
                        'success': True,
                        'distance': route.get('distance', 0),
                        'duration': route.get('duration', 0),
                        'steps': [step.get('instruction', step.get('instructions', '')) for step in route.get('steps', [])],
                        'mode': mode,
                        'coordtype': coordtype
                    }
                else:
                    return {
                        'success': False,
                        'error': '未找到合适的路线'
                    }
            else:
                status_code = data.get('status')
                error_msg = data.get('message', '未知错误')
                
                error_explanations = {
                    1: "服务器内部错误",
                    2: "请求参数非法",
                    3: "权限校验失败（可能未开通该服务）",
                    4: "配额校验失败",
                    5: "AK不存在或者非法",
                    210: "未找到起点",
                    220: "未找到终点"
                }
                
                detailed_error = error_explanations.get(status_code, error_msg)
                
                return {
                    'success': False,
                    'error': f"路线规划失败 (状态码: {status_code}): {detailed_error}",
                    'raw_response': data
                }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': f"路线规划异常: {str(e)}"
            }

