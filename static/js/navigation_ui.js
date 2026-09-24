/* Web demonstration wiring. Only guidance.js may call speechSynthesis. */
(function () {
    'use strict';

    const textPanel = document.getElementById('speechText');
    const modePanel = document.getElementById('guidanceMode');
    const camera = document.getElementById('liveCamera');
    const cameraStatus = document.getElementById('liveVisionStatus');
    const visionDebug = document.getElementById('visionDebug');
    // Camera sampling: one frame in flight at most; the next capture is
    // scheduled only after the previous response arrives (~2-3 FPS typical).
    const CAMERA_BASE_INTERVAL_MS = 350;
    const CAMERA_SLOW_INTERVAL_MS = 700;
    const CAMERA_SLOW_LATENCY_MS = 800;
    let cameraFrameSeq = 0;
    let latestFix = null;
    let watchId = null;
    let cameraStream = null;
    let cameraTimer = null;
    let cameraRequestRunning = false;
    let locationRequestRunning = false;
    let lastPositionSentAt = 0;
    let lastAddressLookupAt = 0;
    let lastPositionWarningAt = 0;
    let lastCameraWarningAt = 0;
    let navigation = null;
    let routeDrawRequest = 0;
    let stream = null;
    const lastFamilyStorageKey = `lastFamilyMessageId:${document.body.dataset.userId}`;
    let lastFamilyMessageId = sessionStorage.getItem(lastFamilyStorageKey);

    const driver = new Guidance.BrowserSpeechDriver(
        window.speechSynthesis, window.SpeechSynthesisUtterance,
        () => ({
            voice_speed: document.getElementById('settingVoiceSpeed')?.value || '中等',
            voice_volume: document.getElementById('settingVoiceVolume')?.value || '中等'
        })
    );
    const scheduler = new Guidance.SpeechScheduler({driver, onStatus(status, event) {
        if (event && event.event_id && !event.event_id.startsWith('local-')) {
            const mapped = {playing: 'PLAYING', paused: 'PAUSED',
                interrupted: 'CANCELLED', finished: 'FINISHED', error: 'FAILED',
                expired: 'CANCELLED'}[status];
            if (mapped) api('/guidance/ack', {event_id: event.event_id,
                delivery_status: mapped}).catch(console.warn);
        }
        if (status === 'playing' && event) {
            textPanel.textContent = event.text;
            updateVoiceStatus('播放中');
        } else if (status === 'error') {
            updateVoiceStatus('语音不可用');
        } else if (status === 'idle') {
            updateVoiceStatus('就绪');
        }
        updateSendBtnState(scheduler.active?.event.source === 'ASSISTANT');
    }});
    window.guidanceScheduler = scheduler;

    function applyNavigation(value, serverContext=null) {
        const context = serverContext || (value ? {
            session_id: value.session_id, route_revision: value.route_revision,
            step_index: value.step_index, nav_state: value.state,
            context_epoch: value.context_epoch, alignment_epoch: value.alignment_epoch
        } : null);
        if (context && !scheduler.setContext(context)) return false;
        const previous = navigation;
        navigation = value;
        if (value) {
            modePanel.textContent = `导航状态：${value.state}；当前位置仅供辅助参考。`;
        } else {
            modePanel.textContent = '网页演示：请保持此页面处于前台。';
            if (previous && typeof map !== 'undefined' && map && routePolyline) {
                routeDrawRequest++;
                map.removeOverlay(routePolyline);
                routePolyline = null;
                document.getElementById('destinationInfoPanel').style.display = 'none';
            }
        }
        return true;
    }

    function submitLocal(text, priority, source, ttlMs, key) {
        scheduler.enqueue({kind: 'speech', text, priority, source,
            event_id: `local-${Date.now()}-${Math.random()}`,
            created_at_ms: Date.now(), ttl_ms: ttlMs,
            dedupe_key: key || null, resume_policy: 'discard'});
    }

    async function api(url, payload) {
        const response = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload || {})});
        const result = await response.json();
        if (!response.ok || result.status !== 'success') throw new Error(result.message || `请求失败 (${response.status})`);
        return result;
    }

    function navigationError(error) {
        console.error('[导航]', error);
        showMessage(error.message || String(error));
    }

    function onLocation(position) {
        latestFix = {lat: position.coords.latitude, lng: position.coords.longitude,
            accuracy: position.coords.accuracy, timestamp_ms: position.timestamp,
            coord_type: 'wgs84'};
        window.navigationDemoManualOrigin = false;
        if (locationRequestRunning || Date.now() - lastPositionSentAt < 3000) return;
        locationRequestRunning = true;
        lastPositionSentAt = Date.now();
        api('/navigation/position', {position: latestFix}).then(result => {
            const point = result.position;
            currentPosition = {lat: point.lat, lng: point.lng};
            if (typeof BMap !== 'undefined' && typeof map !== 'undefined' && map) {
                const bdPoint = new BMap.Point(point.lng, point.lat);
                updateMapPosition(bdPoint);
                if (Date.now() - lastAddressLookupAt >= 10000) {
                    lastAddressLookupAt = Date.now();
                    getAddressFromPoint(bdPoint);
                }
            }
            updateLocationStatus(`定位误差约 ${Math.ceil(point.accuracy)} 米`);
            if (result.navigation) applyNavigation(result.navigation);
        }).catch(error => {
            console.error('[定位]', error);
            updateLocationStatus('定位服务暂不可用');
            if (navigation && navigation.state === 'NAVIGATING' &&
                Date.now() - lastPositionWarningAt > 12000) {
                lastPositionWarningAt = Date.now();
                submitLocal('定位服务不可用，请停下确认当前位置。', 0, 'SAFETY', 6000);
            }
        }).finally(() => { locationRequestRunning = false; });
    }

    window.locateMe = function () {
        if (!navigator.geolocation || !window.isSecureContext) {
            showMessage('浏览器持续定位需要 HTTPS 或 localhost，并允许定位权限。');
            return;
        }
        if (watchId !== null) return;
        updateLocationStatus('正在定位');
        watchId = navigator.geolocation.watchPosition(onLocation,
            error => {
                updateLocationStatus('定位失败');
                console.error(error);
                if (navigation && navigation.state === 'NAVIGATING')
                    submitLocal('定位已中断，请停下确认当前位置。', 0, 'SAFETY', 6000);
            },
            {enableHighAccuracy: true, timeout: 10000, maximumAge: 0});
    };

    function freshPosition() {
        return latestFix && Date.now() - latestFix.timestamp_ms < 12000 &&
            latestFix.accuracy > 0 && latestFix.accuracy <= 25 && !window.navigationDemoManualOrigin;
    }

    function drawRoute(route, attempt=0, requestId=null) {
        if (requestId === null) requestId = ++routeDrawRequest;
        if (requestId !== routeDrawRequest) return;
        if (typeof map === 'undefined' || !map || typeof BMap === 'undefined') {
            if (attempt < 20) setTimeout(() => drawRoute(route, attempt + 1, requestId), 250);
            else modePanel.textContent = '地图未能载入，请检查浏览器地图 AK 和网络。';
            return;
        }
        if (routePolyline) map.removeOverlay(routePolyline);
        const points = [];
        for (const step of route.steps) {
            points.push(new BMap.Point(step.start.lng, step.start.lat));
            const path = String(step.path || '').split(';');
            for (const pair of path) {
                const [lng, lat] = pair.split(',').map(Number);
                if (Number.isFinite(lng) && Number.isFinite(lat) && lng && lat)
                    points.push(new BMap.Point(lng, lat));
            }
            points.push(new BMap.Point(step.end.lng, step.end.lat));
        }
        if (points.length < 2) points.push(new BMap.Point(route.origin.lng, route.origin.lat),
            new BMap.Point(route.destination.lng, route.destination.lat));
        routePolyline = new BMap.Polyline(points, {strokeColor: '#3388ff', strokeWeight: 6,
            strokeOpacity: 0.8});
        map.addOverlay(routePolyline);
        map.setViewport(points);
        document.getElementById('destinationInfoPanel').style.display = 'block';
        document.getElementById('destinationName').textContent =
            `${destinationAddress || '目的地'}（步行约 ${Math.round(route.distance)} 米）`;
    }

    window.planRoute = async function () {
        if (!destinationPoint) return showMessage('请先设置目的地');
        if (!currentPosition && !freshPosition()) return showMessage('请先定位或手动选择起点');
        try {
            const destination = {lat: destinationPoint.lat, lng: destinationPoint.lng,
                coord_type: 'bd09ll'};
            if (freshPosition()) {
                const result = await api('/navigation/start', {destination, position: latestFix});
                if (applyNavigation(result.navigation)) drawRoute(result.navigation.route);
            } else {
                if (navigation) return showMessage('请先停止当前路线，再预览手动起点的路线。');
                const result = await api('/navigation/preview', {origin: {...currentPosition,
                    coord_type: 'bd09ll'}, destination});
                drawRoute(result.route);
                modePanel.textContent = '手动起点仅能预览路线。开始实时导航前请获取新定位。';
            }
        } catch (error) { navigationError(error); }
    };

    window.startNavigation = async function () {
        if (!destinationPoint) return showMessage('请先设置目的地');
        window.enableGuidanceVoice();
        window.locateMe();
        if (!freshPosition()) return showMessage('正在获取准确定位；请定位完成后再次点击开始导航。');
        try {
            if (!navigation || navigation.state !== 'PLANNED' ||
                navigation.route.destination.lat !== destinationPoint.lat ||
                navigation.route.destination.lng !== destinationPoint.lng) {
                const result = await api('/navigation/start', {destination: {
                    lat: destinationPoint.lat, lng: destinationPoint.lng,
                    coord_type: 'bd09ll'}, position: latestFix});
                if (applyNavigation(result.navigation)) drawRoute(result.navigation.route);
            }
            const result = await api('/navigation/activate');
            applyNavigation(result.navigation);
        } catch (error) { navigationError(error); }
    };

    window.stopNavigation = async function () {
        try {
            const result = await api('/navigation/stop');
            applyNavigation(null, result.context);
            routeDrawRequest++;
            if (routePolyline) { map.removeOverlay(routePolyline); routePolyline = null; }
            document.getElementById('destinationInfoPanel').style.display = 'none';
            window.stopLiveCamera();
        } catch (error) { navigationError(error); }
    };

    window.replanNavigation = async function () {
        if (!freshPosition()) return showMessage('重新规划需要新鲜、准确的定位。');
        try {
            const result = await api('/navigation/replan', {position: latestFix});
            if (applyNavigation(result.navigation)) drawRoute(result.navigation.route);
            modePanel.textContent = '路线已更新，请确认目的地后点击开始导航。';
        } catch (error) { navigationError(error); }
    };

    window.enableGuidanceVoice = function () {
        if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) {
            showMessage('当前浏览器不支持本机语音；请使用支持 Web Speech 的浏览器。');
            return;
        }
        scheduler.enable();
        document.getElementById('enableGuidanceVoice').textContent = '本机语音已启用';
    };

    window.playHintVoice = async function (text) {
        window.enableGuidanceVoice();
        submitLocal(text, 5, 'BACKGROUND', 7000, 'thinking');
    };
    window.playAiSpeech = async function (text, intent) {
        window.enableGuidanceVoice();
        if (intent === 'map' && navigation && navigation.state !== 'PLANNED') {
            text = '地图问答已显示在屏幕上。当前路线请以导航状态提示为准。';
        }
        submitLocal(text, 4, 'ASSISTANT', 45000, 'assistant_reply');
    };
    window.stopAiSpeech = async function () { scheduler.cancelAssistant(); };
    window.testVoice = async function () {
        window.enableGuidanceVoice();
        submitLocal('这是一条本机语音测试。', 5, 'BACKGROUND', 10000, 'test_voice');
    };

    window.sendMessage = async function () {
        const input = document.getElementById('familyMessage');
        const recipient = document.getElementById('recipientUsername');
        if (!input.value.trim() || !recipient.value.trim()) return showMessage('请填写接收者用户名和消息');
        try {
            const result = await api('/send_message', {message: input.value.trim(),
                recipient_username: recipient.value.trim()});
            input.value = '';
            lastFamilyMessageId = result.event_id;
            sessionStorage.setItem(lastFamilyStorageKey, lastFamilyMessageId);
            document.getElementById('familyMessageStatus').textContent = result.message;
        } catch (error) { navigationError(error); }
    };

    window.checkFamilyMessageStatus = async function () {
        if (!lastFamilyMessageId) return showMessage('目前没有可查询的家属消息');
        try {
            const response = await fetch(`/family_message_status/${encodeURIComponent(lastFamilyMessageId)}`);
            const result = await response.json();
            if (!response.ok) throw new Error(result.message);
            const labels = {QUEUED: '已入队，未确认播报', PLAYING: '接收端开始播报',
                PAUSED: '被更高优先级提示打断，待恢复', FINISHED: '接收端报告播报完成',
                FAILED: '接收端播报失败',
                CANCELLED: '播报已取消', EXPIRED: '消息已过期'};
            document.getElementById('familyMessageStatus').textContent = labels[result.delivery_status] || result.delivery_status;
        } catch (error) { navigationError(error); }
    };

    window.stopLiveCamera = function () {
        if (cameraStream && navigation && navigation.state === 'NAVIGATING')
            api('/vision/unavailable').catch(console.warn);
        if (cameraTimer) clearTimeout(cameraTimer);
        cameraTimer = null;
        if (cameraStream) cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
        camera.srcObject = null;
        camera.style.display = 'none';
        if (visionDebug) visionDebug.style.display = 'none';
        cameraStatus.textContent = '实时摄像头已关闭。';
        document.getElementById('liveCameraButton').textContent = '启用实时摄像头观察';
    };

    function updateVisionDebug(result, latencyMs) {
        if (!visionDebug) return;
        const observation = result.observation || {};
        const geometry = observation.geometry || {};
        const alignment = result.alignment || {};
        const offset = alignment.offset != null ? Number(alignment.offset).toFixed(3) : '—';
        const confidence = geometry.confidence != null ? Number(geometry.confidence).toFixed(2) : '—';
        visionDebug.style.display = 'block';
        visionDebug.textContent =
            `Vision: ${result.vision_status || '—'} | Geometry: ${geometry.status || '—'} | ` +
            `Alignment: ${alignment.state || '—'} (epoch ${alignment.epoch != null ? alignment.epoch : '—'}) | ` +
            `Offset: ${offset} | Confidence: ${confidence} | ` +
            `Candidates: ${geometry.candidate_count != null ? geometry.candidate_count : 0} | ` +
            `Frame: ${observation.frame_seq != null ? observation.frame_seq : '—'} | ` +
            `Latency: ${latencyMs != null ? latencyMs + ' ms' : '—'}`;
    }

    async function sendCameraFrame() {
        if (cameraRequestRunning || !cameraStream || camera.readyState < 2) return null;
        cameraRequestRunning = true;
        const frameSeq = ++cameraFrameSeq;
        const capturedAtMs = Date.now();
        const startedAtMs = capturedAtMs;
        try {
            const canvas = document.createElement('canvas');
            canvas.width = 480;
            canvas.height = 360;
            canvas.getContext('2d').drawImage(camera, 0, 0, canvas.width, canvas.height);
            const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.7));
            if (!blob) throw new Error('无法编码摄像头图像');
            const form = new FormData();
            form.append('frame', blob, 'camera.jpg');
            form.append('frame_seq', String(frameSeq));
            form.append('captured_at_ms', String(capturedAtMs));
            const response = await fetch('/vision/frame', {method: 'POST', body: form});
            const result = await response.json();
            if (!response.ok || result.status !== 'success') throw new Error(result.message);
            const latency = Date.now() - startedAtMs;
            cameraStatus.textContent = result.observation.visible ?
                `检测到盲道候选区域（${result.observation.detections}）；尚不能验证路口分支。` :
                '本帧未检测到盲道；连续未检测到时会发出停下确认提示。';
            updateVisionDebug(result, latency);
            return latency;
        } catch (error) {
            cameraStatus.textContent = `观察失败：${error.message}`;
            if (Date.now() - lastCameraWarningAt > 12000) {
                lastCameraWarningAt = Date.now();
                api('/vision/unavailable').catch(console.warn);
            }
            return null;
        }
        finally { cameraRequestRunning = false; }
    }

    async function cameraLoop() {
        // Latest-frame processing: the next capture is only scheduled after
        // the previous inference finished, so at most one frame is ever in
        // flight and stale frames can never pile up behind a slow network.
        if (!cameraStream) return;
        const latency = await sendCameraFrame();
        if (!cameraStream) return;
        let delay = CAMERA_BASE_INTERVAL_MS;
        if (latency == null || latency > CAMERA_SLOW_LATENCY_MS) delay = CAMERA_SLOW_INTERVAL_MS;
        cameraTimer = setTimeout(cameraLoop, delay);
    }

    window.toggleLiveCamera = async function () {
        if (cameraStream) return window.stopLiveCamera();
        try {
            cameraStream = await navigator.mediaDevices.getUserMedia({video: {
                facingMode: {ideal: 'environment'}, width: {ideal: 640}}, audio: false});
            camera.srcObject = cameraStream;
            camera.style.display = 'block';
            await camera.play();
            document.getElementById('liveCameraButton').textContent = '关闭实时摄像头';
            cameraStatus.textContent = '摄像头已连接，正在观察盲道。';
            cameraLoop();
        } catch (error) {
            window.stopLiveCamera();
            if (navigation && navigation.state === 'NAVIGATING')
                api('/vision/unavailable').catch(console.warn);
            showMessage(`无法启用摄像头：${error.message}`);
        }
    };

    fetch('/navigation/status').then(r => r.json()).then(result => {
        if (result.status === 'success') {
            if (applyNavigation(result.navigation, result.context) && result.navigation)
                drawRoute(result.navigation.route);
        }
    }).catch(console.error);

    stream = new EventSource('/guidance/events');
    stream.onopen = () => { if (navigation) applyNavigation(navigation); };
    stream.addEventListener('guidance', message => {
        try {
            const event = JSON.parse(message.data);
            if (event.kind === 'context' && scheduler.enqueue(event)) {
                fetch('/navigation/status').then(r => r.json()).then(result => {
                    if (result.status === 'success') applyNavigation(result.navigation, result.context);
                }).catch(console.error);
            } else if (event.kind !== 'context') scheduler.enqueue(event);
        }
        catch (error) { console.error('[引导事件]', error); }
    });
    stream.onerror = () => { if (modePanel) modePanel.textContent = '事件连接中断，浏览器正在尝试重连。'; };

    const healthTimer = setInterval(() => {
        if (!navigation || navigation.state === 'PLANNED') return;
        fetch('/navigation/status').then(r => r.json()).then(result => {
            if (result.status === 'success') applyNavigation(result.navigation, result.context);
        }).catch(console.warn);
    }, 3000);

    window.addEventListener('beforeunload', () => {
        clearInterval(healthTimer);
        if (stream) stream.close();
        if (watchId !== null) navigator.geolocation.clearWatch(watchId);
        window.stopLiveCamera();
        scheduler.cancelAll();
    });
})();
