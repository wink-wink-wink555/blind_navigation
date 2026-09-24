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
        return {kind:'speech', text, priority, source: ['SAFETY', 'ALIGNMENT', 'ROUTE', 'FAMILY', 'ASSISTANT', 'BACKGROUND'][priority],
            event_id: `event-${++serial}`, created_at_ms: now, ttl_ms: 10000,
            resume_policy: 'discard', ...options};
    }};
}

{
    const {driver, statuses, scheduler, event} = fixture();
    scheduler.enqueue(event('家属第一句。家属第二句。', 3, {resume_policy:'continue'}));
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
    scheduler.enqueue(event('普通助手长回复。', 4));
    scheduler.enqueue(event('旧路线右转', 2, {session_id:'route-1', route_revision:1, step_id:0}));
    assert.equal(driver.calls[1].text, '旧路线右转');
    scheduler.setContext({session_id:'route-2', route_revision:2, step_index:0,
        nav_state:'NAVIGATING', context_epoch:1});
    assert.ok(driver.cancelCount >= 2);
    assert.equal(scheduler.queue.some(x => x.event.text === '旧路线右转'), false);
    setNow(50000);
    assert.equal(scheduler.enqueue(event('过期旧消息', 3, {created_at_ms: 1000})), false);
}

{
    const {driver, scheduler, event} = fixture();
    const route = {session_id:'route-1', route_revision:2, step_index:0,
        nav_state:'NAVIGATING', context_epoch:1};
    scheduler.setContext(route);
    scheduler.enqueue(event('路口请确认。', 2, {...route, step_id:0}));
    assert.equal(driver.calls.length, 1);
    scheduler.setContext({...route, nav_state:'UNCERTAIN', context_epoch:2});
    assert.equal(driver.cancelCount, 1);
    assert.equal(scheduler.enqueue(event('过时的路线指令', 2, {...route, step_id:0})), false);
    assert.equal(scheduler.setContext({...route, nav_state:'NAVIGATING', context_epoch:1}), false);
    assert.equal(scheduler.enqueue({kind:'context', route_revision:1, context_epoch:100}), false);
}

{
    const {driver, scheduler, event} = fixture();
    scheduler.enqueue(event('请停下', 0));
    scheduler.enqueue(event('助手回复', 4));
    assert.equal(driver.cancelCount, 0);
    assert.equal(driver.calls.length, 1);
    driver.calls[0].callbacks.end(false);
    assert.equal(driver.calls[1].text, '助手回复');
    scheduler.cancelAssistant();
    assert.equal(driver.cancelCount, 1);
}

// Alignment epoch invalidation: a queued steering hint belongs to the exact
// alignment state that produced it.
{
    const {driver, scheduler, event} = fixture();
    const context = {session_id:'route-1', route_revision:1, step_index:0,
        nav_state:'NAVIGATING', context_epoch:1, alignment_epoch:17};
    scheduler.setContext(context);
    const queued = event('盲道在左侧，稍向左靠。', 1,
        {session_id:'route-1', route_revision:1, alignment_epoch:17, ttl_ms:3000});
    scheduler.enqueue(event('请停下确认。', 0, {session_id:'route-1', route_revision:1}));
    scheduler.enqueue(queued); // ALIGNMENT cannot preempt SAFETY: it waits
    assert.equal(driver.calls.length, 1);
    assert.equal(driver.calls[0].text, '请停下确认。');
    // User recentered: the epoch moves on, the queued LEFT hint must die.
    scheduler.setContext({...context, alignment_epoch:18});
    assert.equal(scheduler.queue.some(x => x.event.event_id === queued.event_id), false);
    assert.equal(scheduler.enqueue(event('过期纠偏。', 1,
        {session_id:'route-1', route_revision:1, alignment_epoch:17})), false);
}

// Direction flip: an actively playing LEFT hint is interrupted the moment the
// state becomes RIGHT (new epoch), and only the RIGHT hint survives.
{
    const {driver, scheduler, event} = fixture();
    const context = {session_id:'route-1', route_revision:1, step_index:0,
        nav_state:'NAVIGATING', context_epoch:1, alignment_epoch:20};
    scheduler.setContext(context);
    scheduler.enqueue(event('盲道在左侧，稍向左靠。', 1,
        {session_id:'route-1', route_revision:1, alignment_epoch:20, ttl_ms:3000}));
    assert.equal(driver.calls[0].text, '盲道在左侧，稍向左靠。');
    scheduler.setContext({...context, alignment_epoch:21});
    assert.equal(driver.cancelCount, 1); // stale LEFT interrupted immediately
    scheduler.enqueue(event('盲道在右侧，稍向右靠。', 1,
        {session_id:'route-1', route_revision:1, alignment_epoch:21, ttl_ms:3000}));
    assert.equal(driver.calls[1].text, '盲道在右侧，稍向右靠。');
}

// Publish-order race: a fresh hint may arrive before its context event. A
// newer epoch must be accepted; only an older epoch is stale.
{
    const {driver, scheduler, event} = fixture();
    scheduler.setContext({session_id:'route-1', route_revision:1, step_index:0,
        nav_state:'NAVIGATING', context_epoch:1, alignment_epoch:30});
    assert.equal(scheduler.enqueue(event('盲道在右侧，稍向右靠。', 1,
        {session_id:'route-1', route_revision:1, alignment_epoch:31, ttl_ms:3000})), true);
    assert.equal(driver.calls[0].text, '盲道在右侧，稍向右靠。');
    scheduler.setContext({session_id:'route-1', route_revision:1, step_index:0,
        nav_state:'NAVIGATING', context_epoch:1, alignment_epoch:31});
    assert.equal(driver.cancelCount, 0); // matching epoch does not interrupt
}

// Priority contract: SAFETY > ALIGNMENT > ROUTE, and positive feedback
// (BACKGROUND) never interrupts steering.
{
    const {driver, scheduler, event} = fixture();
    const context = {session_id:'route-1', route_revision:1, step_index:0,
        nav_state:'NAVIGATING', context_epoch:1, alignment_epoch:30};
    scheduler.setContext(context);
    scheduler.enqueue(event('路线预告。', 2, {session_id:'route-1', route_revision:1}));
    scheduler.enqueue(event('稍向右靠。', 1,
        {session_id:'route-1', route_revision:1, alignment_epoch:30}));
    assert.equal(driver.cancelCount, 1); // ALIGNMENT preempts ROUTE
    assert.equal(driver.calls[1].text, '稍向右靠。');
    scheduler.enqueue(event('很好，位置已经回正。', 5,
        {session_id:'route-1', route_revision:1}));
    assert.equal(driver.cancelCount, 1); // praise must not interrupt steering
    scheduler.enqueue(event('请停下确认。', 0, {session_id:'route-1', route_revision:1}));
    assert.equal(driver.cancelCount, 2); // SAFETY interrupts ALIGNMENT
    assert.equal(driver.calls[2].text, '请停下确认。');
}

console.log('speech scheduler: preemption, resumption, route invalidation, alignment epoch and expiry passed');
