const assert = require('node:assert/strict');
const {SpeechScheduler} = require('../static/js/guidance.js');

function fixture() {
    let now = 1000;
    const statuses = [];
    const driver = {
        calls: [], cancelCount: 0,
        speak(text, event, callbacks) {
            this.calls.push({text, event, callbacks});
            callbacks.start();
        },
        cancel() { this.cancelCount++; }
    };
    const scheduler = new SpeechScheduler({driver, now: () => now,
        onStatus: (status, e) => statuses.push([status, e?.event_id])});
    scheduler.enable();
    let serial = 0;
    return {driver, statuses, scheduler, setNow: value => {now = value;}, event(text, priority, options={}) {
        return {kind:'speech', text, priority, source: ['SAFETY', 'ROUTE', 'FAMILY', 'ASSISTANT', 'BACKGROUND'][priority],
            event_id: `event-${++serial}`, created_at_ms: now, ttl_ms: 10000,
            resume_policy: 'discard', ...options};
    }};
}

{
    const {driver, statuses, scheduler, event} = fixture();
    scheduler.enqueue(event('家属第一句。家属第二句。', 2, {resume_policy:'continue'}));
    const canceled = driver.calls[0].callbacks;
    scheduler.enqueue(event('未识别到盲道，请停下。', 0));
    assert.equal(driver.cancelCount, 1);
    assert.ok(statuses.some(([s]) => s === 'paused'));
    assert.equal(driver.calls[1].text, '未识别到盲道，请停下。');
    canceled.end(false); // Late callback from the canceled family utterance.
    assert.equal(driver.calls.length, 2);
    driver.calls[1].callbacks.end(false);
    assert.equal(driver.calls[2].text, '家属第一句。');
    driver.calls[2].callbacks.end(false);
    assert.equal(driver.calls[3].text, '家属第二句。');
}

{
    const {driver, scheduler, event, setNow} = fixture();
    scheduler.setContext({session_id:'route-1', route_revision: 1, step_index: 0,
        nav_state:'NAVIGATING', context_epoch: 1});
    scheduler.enqueue(event('普通助手长回复。', 3));
    scheduler.enqueue(event('旧路线右转', 1, {session_id:'route-1', route_revision:1, step_id:0}));
    assert.equal(driver.calls[1].text, '旧路线右转');
    scheduler.setContext({session_id:'route-2', route_revision:2, step_index:0,
        nav_state:'NAVIGATING', context_epoch:1});
    assert.ok(driver.cancelCount >= 2);
    assert.equal(scheduler.queue.some(x => x.event.text === '旧路线右转'), false);
    setNow(50000);
    assert.equal(scheduler.enqueue(event('过期旧消息', 2, {created_at_ms: 1000})), false);
}

{
    const {driver, scheduler, event} = fixture();
    const route = {session_id:'route-1', route_revision:2, step_index:0,
        nav_state:'NAVIGATING', context_epoch:1};
    scheduler.setContext(route);
    scheduler.enqueue(event('路口请确认。', 1, {...route, step_id:0}));
    assert.equal(driver.calls.length, 1);
    scheduler.setContext({...route, nav_state:'UNCERTAIN', context_epoch:2});
    assert.equal(driver.cancelCount, 1);
    assert.equal(scheduler.enqueue(event('过时的路线指令', 1, {...route, step_id:0})), false);
    assert.equal(scheduler.setContext({...route, nav_state:'NAVIGATING', context_epoch:1}), false);
    assert.equal(scheduler.enqueue({kind:'context', route_revision:1, context_epoch:100}), false);
}

{
    const {driver, scheduler, event} = fixture();
    scheduler.enqueue(event('请停下', 0));
    scheduler.enqueue(event('助手回复', 3));
    assert.equal(driver.cancelCount, 0);
    assert.equal(driver.calls.length, 1);
    driver.calls[0].callbacks.end(false);
    assert.equal(driver.calls[1].text, '助手回复');
    scheduler.cancelAssistant();
    assert.equal(driver.cancelCount, 1);
}

console.log('speech scheduler: preemption, resumption, route invalidation and expiry passed');
