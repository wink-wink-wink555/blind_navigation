/* Browser audio owner: priority, expiry, route invalidation and interruption.
 * A server event is only a request to speak. Playback is acknowledged locally.
 */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    else root.Guidance = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    function sentences(text) {
        const pieces = String(text || '').match(/[^。！？.!?；;]+[。！？.!?；;]?/g) || [];
        const chunks = [];
        for (const piece of pieces) {
            const cleaned = piece.trim();
            for (let i = 0; i < cleaned.length; i += 70) chunks.push(cleaned.slice(i, i + 70));
        }
        return chunks;
    }

    class SpeechScheduler {
        constructor({driver, now = () => Date.now(), onStatus = () => {}, limit = 64}) {
            this.driver = driver;
            this.now = now;
            this.onStatus = onStatus;
            this.limit = limit;
            this.enabled = false;
            this.context = {session_id: null, route_revision: 0, step_index: null,
                nav_state: null, context_epoch: 0, alignment_epoch: null};
            this.queue = [];
            this.active = null;
            this.sequence = 0;
            this.token = 0;
            this.seen = new Set();
            this.expiryTimer = null;
        }

        enable() {
            this.enabled = true;
            if (this.driver.unlock) this.driver.unlock();
            this._pump();
        }

        setContext(context) {
            const revision = context && context.route_revision != null ? context.route_revision : 0;
            const epoch = context && context.context_epoch != null ? context.context_epoch : 0;
            if (revision < this.context.route_revision ||
                (revision === this.context.route_revision && epoch < this.context.context_epoch)) return false;
            this.context = {
                session_id: context && context.session_id || null,
                route_revision: revision,
                step_index: context && context.step_index != null ? context.step_index : null,
                nav_state: context && context.nav_state || null,
                context_epoch: epoch,
                alignment_epoch: context && context.alignment_epoch != null ?
                    context.alignment_epoch : this.context.alignment_epoch
            };
            this.queue = this.queue.filter(entry => this._valid(entry));
            if (this.active && !this._valid(this.active)) {
                this._interrupt(false);
                this._pump();
            }
            return true;
        }

        _valid(entry) {
            const event = entry.event;
            const expiry = event.created_at_ms + event.ttl_ms;
            if (this.now() >= expiry) return false;
            if (event.session_id && (event.session_id !== this.context.session_id ||
                event.route_revision !== this.context.route_revision)) return false;
            if (event.step_id != null && event.step_id !== this.context.step_index) return false;
            // A steering hint belongs to the alignment epoch that produced it.
            // Events arrive in publish order, so a fresh hint may legitimately
            // precede its context update; only an epoch OLDER than the current
            // context proves the hint is stale and must never play.
            if (event.alignment_epoch != null && this.context.alignment_epoch != null &&
                event.alignment_epoch < this.context.alignment_epoch) return false;
            if (event.source === 'ROUTE' && event.session_id &&
                this.context.nav_state !== 'NAVIGATING' &&
                !(this.context.nav_state === 'ARRIVAL_UNCONFIRMED' &&
                  event.dedupe_key === 'arrival')) return false;
            return true;
        }

        enqueue(event) {
            if (event.kind === 'context') {
                return this.setContext({...event, step_index: event.step_id});
            }
            if (event.kind === 'cancel_assistant') {
                this.cancelAssistant();
                return true;
            }
            if (event.kind !== 'speech' || typeof event.text !== 'string' ||
                !Number.isInteger(event.priority) || event.priority < 0 || event.priority > 5 ||
                !Number.isFinite(event.created_at_ms) || !Number.isFinite(event.ttl_ms)) return false;
            if (event.event_id && this.seen.has(event.event_id)) return false;
            if (event.event_id) {
                this.seen.add(event.event_id);
                if (this.seen.size > 512) this.seen.delete(this.seen.values().next().value);
            }
            const entry = {event, chunks: sentences(event.text), index: 0, order: ++this.sequence};
            if (!entry.chunks.length || !this._valid(entry)) return false;
            if (event.dedupe_key) {
                const same = item => item.event.dedupe_key === event.dedupe_key &&
                    item.event.session_id === event.session_id;
                this.queue = this.queue.filter(item => !same(item));
                if (this.active && same(this.active)) return false;
            }
            if (this.active && event.priority < this.active.event.priority) this._interrupt(true);
            this.queue.push(entry);
            this.queue.sort((a, b) => a.event.priority - b.event.priority || a.order - b.order);
            if (this.queue.length > this.limit) this.queue.splice(this.limit);
            this._pump();
            return true;
        }

        _interrupt(mayResume) {
            const old = this.active;
            if (!old) return;
            this.token += 1; // Ignore a late onend/onerror from the canceled utterance.
            this._clearExpiry();
            this.active = null;
            this.driver.cancel();
            const resume = mayResume && this._valid(old) &&
                (old.event.resume_policy === 'continue' || old.event.resume_policy === 'restart');
            if (resume) {
                if (old.event.resume_policy === 'restart') old.index = 0;
                old.order = ++this.sequence;
                this.queue.push(old);
            }
            this.onStatus(resume ? 'paused' : 'interrupted', old.event);
        }

        _pump() {
            if (!this.enabled || this.active) return;
            this.queue = this.queue.filter(entry => this._valid(entry));
            this.queue.sort((a, b) => a.event.priority - b.event.priority || a.order - b.order);
            this.active = this.queue.shift() || null;
            if (!this.active) {
                this.onStatus('idle', null);
                return;
            }
            this._nextChunk();
        }

        _nextChunk() {
            const entry = this.active;
            if (!entry) return;
            if (!this._valid(entry) || entry.index >= entry.chunks.length) {
                this.active = null;
                this._clearExpiry();
                this.onStatus(this._valid(entry) ? 'finished' : 'expired', entry.event);
                this._pump();
                return;
            }
            const token = ++this.token;
            this._clearExpiry();
            this.expiryTimer = setTimeout(() => {
                if (this.token === token && this.active === entry) {
                    this._interrupt(false);
                    this.onStatus('expired', entry.event);
                    this._pump();
                }
            }, Math.max(0, entry.event.created_at_ms + entry.event.ttl_ms - this.now()));
            if (this.expiryTimer && this.expiryTimer.unref) this.expiryTimer.unref();
            try {
                this.driver.speak(entry.chunks[entry.index], entry.event, {
                start: () => {
                    if (this.token === token && this.active === entry) this.onStatus('playing', entry.event);
                },
                end: (error) => {
                    if (this.token !== token || this.active !== entry) return;
                    this._clearExpiry();
                    if (error) {
                        this.active = null;
                        this.onStatus('error', entry.event);
                        this._pump();
                        return;
                    }
                    entry.index += 1;
                    this._nextChunk();
                }
                });
            } catch (error) {
                if (this.token === token && this.active === entry) {
                    this._clearExpiry();
                    this.active = null;
                    this.onStatus('error', entry.event);
                    this._pump();
                }
            }
        }

        _clearExpiry() {
            if (this.expiryTimer) clearTimeout(this.expiryTimer);
            this.expiryTimer = null;
        }

        cancelAssistant() {
            this.queue = this.queue.filter(entry => entry.event.source !== 'ASSISTANT' &&
                entry.event.source !== 'BACKGROUND');
            if (this.active && (this.active.event.source === 'ASSISTANT' ||
                this.active.event.source === 'BACKGROUND')) this._interrupt(false);
            this._pump();
        }

        cancelAll() {
            this.queue = [];
            this._interrupt(false);
            this._pump();
        }
    }

    class BrowserSpeechDriver {
        constructor(synth, utterance, getSettings) {
            this.synth = synth;
            this.Utterance = utterance;
            this.getSettings = getSettings;
        }

        unlock() {
            if (this.synth && this.synth.paused) this.synth.resume();
        }

        speak(text, event, callbacks) {
            if (!this.synth || !this.Utterance) {
                callbacks.end(true);
                return;
            }
            const utterance = new this.Utterance(text);
            const settings = this.getSettings() || {};
            utterance.lang = 'zh-CN';
            utterance.rate = {'慢': 0.8, '中等': 1, '快': 1.2}[settings.voice_speed] || 1;
            utterance.volume = {'低': 0.5, '中等': 0.8, '高': 1}[settings.voice_volume] || 0.8;
            const voice = this.synth.getVoices().find(v => v.lang && v.lang.toLowerCase().startsWith('zh'));
            if (voice) utterance.voice = voice;
            utterance.onstart = callbacks.start;
            utterance.onend = () => callbacks.end(false);
            utterance.onerror = () => callbacks.end(true);
            this.synth.speak(utterance);
        }

        cancel() {
            if (this.synth) this.synth.cancel();
        }
    }

    return {SpeechScheduler, BrowserSpeechDriver, sentences};
});
