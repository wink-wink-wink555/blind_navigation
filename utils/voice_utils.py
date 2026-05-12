"""
语音相关工具模块

重要：整个应用只使用一个 pyttsx3 引擎实例和一个工作线程，
避免多引擎/多线程导致的 "run loop already started" 冲突。
"""
import pyttsx3
import queue
import threading
import time
from enum import Enum

# ========== 全局变量 ==========
voices_cache = None

# 统一的语音系统 - 只有一个引擎和一个工作线程
_speech_queue = queue.Queue()
_speech_lock = threading.Lock()
_speech_worker_started = False
_speech_engine = None  # 全局唯一引擎实例
_speech_stop_flag = threading.Event()  # 停止当前播放的标志
_speech_playing = threading.Event()  # 当前是否正在播放


class SpeechPriority(Enum):
    """语音优先级"""
    LOW = 0       # 低优先级（如背景提示）
    NORMAL = 1    # 普通优先级（如盲道提示）
    HIGH = 2      # 高优先级（如家属消息）
    URGENT = 3    # 紧急优先级（可打断当前播放）


def get_available_voices():
    """获取系统可用的语音列表"""
    global voices_cache
    if voices_cache is not None:
        return voices_cache

    try:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        available_voices = []

        for voice in voices:
            voice_info = {
                'id': voice.id,
                'name': voice.name,
                'gender': '女声' if 'female' in voice.id.lower() or 'Microsoft Huihui' in voice.name else '男声'
            }
            available_voices.append(voice_info)

        voices_cache = available_voices
        
        # 清理临时引擎
        try:
            engine.stop()
            del engine
        except:
            pass
            
        return available_voices
    except Exception as e:
        print(f"[语音] 获取语音列表失败: {e}")
        return []


def _init_engine():
    """
    初始化 pyttsx3 引擎并设置中文语音
    
    Returns:
        tuple: (engine, selected_voice_id) 或 (None, None) 如果失败
    """
    try:
        engine = pyttsx3.init()
        
        # 设置中文语音
        voices = engine.getProperty('voices')
        selected_voice = None
        for voice in voices:
            voice_name = voice.name.lower()
            if "chinese" in voice_name or "huihui" in voice_name or "china" in voice_name or "中文" in voice_name:
                selected_voice = voice.id
                print(f"[语音系统] 找到中文语音: {voice.name}")
                break
        
        if not selected_voice and len(voices) > 0:
            selected_voice = voices[0].id
            print(f"[语音系统] 使用默认语音: {voices[0].name}")
        
        if selected_voice:
            engine.setProperty('voice', selected_voice)
        
        return engine, selected_voice
        
    except Exception as e:
        print(f"[语音系统] 引擎初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def _unified_speech_worker():
    """
    统一的语音播放工作线程
    整个应用只有这一个线程处理所有语音任务
    """
    global _speech_engine, _speech_stop_flag, _speech_playing
    
    print("[语音系统] ========== 工作线程启动 ==========")
    
    # 创建引擎实例
    engine, selected_voice = _init_engine()
    if engine is None:
        print("[语音系统] 无法启动，引擎初始化失败")
        return
    
    _speech_engine = engine
    print("[语音系统] 引擎初始化成功")
    
    # 标记引擎是否需要重新初始化（在被 stop() 后需要）
    need_reinit = False
    
    while True:
        try:
            # 从队列获取任务
            try:
                task = _speech_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            
            if task is None:
                print("[语音系统] 收到退出信号")
                break
            
            text, user_settings, priority, task_id = task
            print(f"[语音系统] 收到任务 [{task_id}]: '{text[:40]}...' (优先级: {priority.name})")
            
            # 如果引擎需要重新初始化（上次被 stop() 中断后）
            if need_reinit:
                print(f"[语音系统] 🔄 重新初始化引擎...")
                try:
                    # 清理旧引擎
                    if engine:
                        try:
                            del engine
                        except:
                            pass
                    
                    # 创建新引擎
                    engine, selected_voice = _init_engine()
                    if engine is None:
                        print(f"[语音系统] ✗ 重新初始化失败，跳过任务 [{task_id}]")
                        _speech_playing.clear()
                        _speech_queue.task_done()
                        continue
                    
                    _speech_engine = engine
                    need_reinit = False
                    print(f"[语音系统] ✓ 引擎重新初始化成功")
                    
                except Exception as reinit_error:
                    print(f"[语音系统] ✗ 重新初始化异常: {reinit_error}")
                    _speech_playing.clear()
                    _speech_queue.task_done()
                    continue
            
            # 重置标志
            _speech_stop_flag.clear()
            _speech_playing.set()
            
            # 标记本次播放是否被中断
            was_interrupted = False
            
            try:
                # 设置语音速度
                speed_map = {"慢": 150, "中等": 200, "快": 250}
                engine.setProperty('rate', speed_map.get(user_settings.get("voice_speed", "中等"), 200))
                
                # 设置音量
                volume_map = {"低": 0.5, "中等": 0.8, "高": 1.0}
                engine.setProperty('volume', volume_map.get(user_settings.get("voice_volume", "中等"), 0.8))
                
                # 检查是否在播放前就被取消
                if _speech_stop_flag.is_set():
                    print(f"[语音系统] 任务 [{task_id}] 播放前被取消")
                    was_interrupted = True
                    continue
                
                # 播放语音
                print(f"[语音系统] 开始播放 [{task_id}]...")
                engine.say(text)
                engine.runAndWait()
                
                if _speech_stop_flag.is_set():
                    print(f"[语音系统] ✗ 任务 [{task_id}] 被中断")
                    was_interrupted = True
                else:
                    print(f"[语音系统] ✓ 任务 [{task_id}] 播放完成")
                    
            except RuntimeError as e:
                error_msg = str(e)
                print(f"[语音系统] 运行时错误 [{task_id}]: {error_msg}")
                was_interrupted = True
                        
            except Exception as e:
                print(f"[语音系统] 播放错误 [{task_id}]: {e}")
                import traceback
                traceback.print_exc()
                was_interrupted = True
                
            finally:
                _speech_playing.clear()
                
                # 关键：如果播放被中断，标记需要重新初始化引擎
                # 因为 engine.stop() 会导致引擎进入异常状态
                if was_interrupted:
                    need_reinit = True
                    print(f"[语音系统] ⚠️ 引擎已标记为需要重新初始化")
                
                try:
                    _speech_queue.task_done()
                except ValueError:
                    pass
                    
        except Exception as e:
            print(f"[语音系统] 工作线程异常: {e}")
            import traceback
            traceback.print_exc()
            _speech_playing.clear()
            need_reinit = True  # 出现异常也标记重新初始化
    
    # 清理
    print("[语音系统] ========== 工作线程退出 ==========")
    _speech_engine = None
    if engine:
        try:
            engine.stop()
            del engine
        except:
            pass


def _ensure_worker_started():
    """确保语音工作线程已启动"""
    global _speech_worker_started
    
    with _speech_lock:
        if not _speech_worker_started:
            worker = threading.Thread(target=_unified_speech_worker, daemon=True)
            worker.start()
            _speech_worker_started = True
            # 等待引擎初始化
            time.sleep(0.5)
            print("[语音系统] 工作线程已启动")


def _generate_task_id():
    """生成唯一任务ID"""
    return f"{int(time.time() * 1000) % 100000}"


# ========== 统一的对外接口 ==========

def speak(text, user_settings, priority=SpeechPriority.NORMAL):
    """
    播放语音（统一接口）
    
    用于：盲道提示、家属消息等
    
    Args:
        text: 要播放的文本
        user_settings: 用户设置字典，包含 voice_speed 和 voice_volume
        priority: 语音优先级
    
    Returns:
        str: 任务ID
    """
    _ensure_worker_started()
    
    task_id = _generate_task_id()
    print(f"[语音] 添加任务 [{task_id}]: '{text[:30]}...'")
    
    _speech_queue.put((text, user_settings, priority, task_id))
    return task_id


def ai_speak(text, user_settings):
    """
    AI助手语音播放（可中止）
    
    用于：AI地图助手回复
    
    Args:
        text: 要播放的文本
        user_settings: 用户设置字典
    
    Returns:
        bool: 是否成功添加到队列
    """
    _ensure_worker_started()
    
    # 如果正在播放，先停止
    if _speech_playing.is_set():
        print("[AI语音] 当前有语音在播放，先停止")
        stop_ai_speak()
        time.sleep(0.3)
    
    # 清空队列中的旧任务
    cleared = 0
    while not _speech_queue.empty():
        try:
            _speech_queue.get_nowait()
            _speech_queue.task_done()
            cleared += 1
        except queue.Empty:
            break
    
    if cleared > 0:
        print(f"[AI语音] 已清空 {cleared} 个待处理任务")
    
    task_id = _generate_task_id()
    print(f"[AI语音] 添加任务 [{task_id}]: '{text[:50]}...'")
    
    _speech_queue.put((text, user_settings, SpeechPriority.URGENT, task_id))
    _speech_playing.set()
    return True


def stop_ai_speak():
    """
    停止当前语音播放
    
    Returns:
        bool: 是否成功停止
    """
    global _speech_stop_flag, _speech_engine, _speech_playing
    
    print("[语音] 收到停止请求")
    
    # 设置停止标志
    _speech_stop_flag.set()
    
    # 尝试停止引擎
    if _speech_engine:
        try:
            _speech_engine.stop()
            print("[语音] 引擎已停止")
        except Exception as e:
            print(f"[语音] 停止引擎时出错: {e}")
    
    # 清除播放状态
    _speech_playing.clear()
    
    return True


def stop_speech():
    """停止语音播放（别名，兼容旧代码）"""
    return stop_ai_speak()


def is_ai_speaking():
    """
    检查是否正在播放语音
    
    Returns:
        bool: 是否正在播放
    """
    return _speech_playing.is_set()


def is_speaking():
    """检查是否正在播放（别名）"""
    return is_ai_speaking()


def get_prompt_template(user_settings):
    """
    根据用户设置生成AI提示模板
    
    Args:
        user_settings: 用户设置字典
        
    Returns:
        str: AI提示模板
    """
    gender_term = ""
    age_term = ""

    if user_settings["gender"] == "男":
        gender_term = "先生"
    elif user_settings["gender"] == "女":
        gender_term = "女士"

    if user_settings["age"] == "老年":
        age_term = "年长的"
    elif user_settings["age"] == "青年":
        age_term = "年轻的"

    prompt = f'''
你是一个服务于盲人行走的语音导航小助手。
你的用户是{age_term}{user_settings["name"]}{gender_term}。

重要要求：
1. 在回复时，你必须明确称呼用户的名字"{user_settings["name"]}{gender_term}"，例如："{user_settings["name"]}{gender_term}，盲道向右转了"。
2. 你必须说清楚盲道转向方位（左？右？），确保盲人知道要往哪个方向走。
3. 你的语气要温柔、亲切且充满元气。
4. 回复要简短明了，便于盲人快速理解。
5. 注意：盲人因为看不见路面情况，所以需要你清晰准确的语音行走提示。
'''

    # 如果开启了鼓励功能，在提示词中添加相关要求
    if user_settings["encourage"] == "开":
        prompt += f'''
6. 请在引导方向的同时，适当给予用户温暖的鼓励和正面的肯定，例如称赞{user_settings["name"]}{gender_term}走得好、进步明显，或者鼓励{user_settings["name"]}{gender_term}继续保持自信等。
'''

    return prompt


def build_static_turn_text(direction, user_settings):
    """
    生成关闭鼓励功能时的硬编码盲道转向播报文本。

    直接使用确定性模板，不走 LLM，保证响应即时、文本稳定可预期：
        "{称呼}，前方盲道向{左|右}，请缓慢{左|右}转。"

    Args:
        direction: 'left' 或 'right'
        user_settings: 用户设置字典（需包含 name、gender）

    Returns:
        str: 播报文本
    """
    gender_term = ""
    if user_settings.get("gender") == "男":
        gender_term = "先生"
    elif user_settings.get("gender") == "女":
        gender_term = "女士"

    name = (user_settings.get("name") or "").strip()
    direction_word = "左" if direction == "left" else "右"

    # 没有姓名时直接省略称呼，避免出现"先生，前方..."这种孤立的称谓
    if name:
        return f"{name}{gender_term}，前方盲道向{direction_word}，请缓慢{direction_word}转。"
    return f"前方盲道向{direction_word}，请缓慢{direction_word}转。"
