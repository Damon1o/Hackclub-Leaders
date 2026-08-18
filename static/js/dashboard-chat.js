/*
 * dashboard-chat.js — the club chat feature, split out of dashboard.js.
 *
 * Only the chat page loads this file (dashboard.js's loadChat() injects it),
 * so every other dashboard page skips ~30 KB of code it would never run.
 *
 * Everything here used to live inside dashboard.js's IIFE and is unchanged
 * apart from how it reaches the outside world:
 *   ctx.getState()  the live dashboard state object (reassigned on refresh)
 *   S               shared mutable chat state, owned by dashboard.js so its
 *                   own handlers keep seeing the active channel
 *   the rest of ctx is dashboard.js's shared helpers, destructured below.
 */
window.DashboardChat = function (ctx) {
    'use strict';

    const S = ctx.state;
    const page = ctx.page;
    const isLeader = ctx.isLeader;
    const viewerEmail = ctx.viewerEmail;
    const apiRequest = ctx.apiRequest;
    const avatarMarkup = ctx.avatarMarkup;
    const escapeHtml = ctx.escapeHtml;
    const removeSkeletons = ctx.removeSkeletons;
    const setFormError = ctx.setFormError;
    const showToast = ctx.showToast;
    const $ = ctx.$;

    const CHAT_READS_KEY = 'hcl:chatReads';
    const MESSAGE_POLL_MS = 500;
    const CHANNEL_POLL_MS = 5000;
    const READ_SYNC_MS = 2000;
    const CHAT_GROUP_MS = 5 * 60 * 1000;   // same-author messages within 5min render grouped
    const TYPING_THROTTLE_MS = 2000;       // client-side floor between POST .../typing calls
    const chatBaseTitle = document.title;  // restored when the tab regains focus

    // ── Chat (polling) ───────────────────────────────────────────────────────
    // Channels + messages. All members read/post; leaders manage channels.


    function chatReads() {
        try {
            return JSON.parse(localStorage.getItem(CHAT_READS_KEY) || '{}') || {};
        } catch (error) {
            return {};
        }
    }

    function markChannelRead(id, iso) {
        const reads = chatReads();
        reads[id] = iso || new Date().toISOString();
        try {
            localStorage.setItem(CHAT_READS_KEY, JSON.stringify(reads));
        } catch (error) {
            /* storage unavailable — non-fatal */
        }
    }

    // Debounce the server-side cursor write: a burst of incoming messages
    // while already at the bottom must not fire one request per message.
    function syncChannelRead(id, iso) {
        S.readTimers = S.readTimers || {};
        S.readPending = S.readPending || {};
        S.readPending[id] = iso || new Date().toISOString();
        if (S.readTimers[id]) return;
        S.readTimers[id] = window.setTimeout(() => {
            delete S.readTimers[id];
            apiRequest(`/api/dashboard/chat/channels/${encodeURIComponent(id)}/read`,
                { method: 'POST', body: { readAt: S.readPending[id] } })
                .catch(() => { /* the next scroll-to-bottom retries */ });
        }, READ_SYNC_MS);
    }

    const CHAT_MUTES_KEY = 'hcl:chatMutes';

    function chatMutes() {
        try {
            return JSON.parse(localStorage.getItem(CHAT_MUTES_KEY)) || [];
        } catch (error) {
            return [];
        }
    }

    function isChannelMuted(id) {
        return chatMutes().includes(id);
    }

    function channelUnread(channel) {
        if (!channel.lastMessageAt || channel.id === S.activeId) return false;
        if (isChannelMuted(channel.id)) return false;
        // The server's cursor is authoritative; the localStorage copy only
        // clears the dot optimistically while the POST is still in flight.
        if (channel.unread === false) return false;
        const seen = chatReads()[channel.id];
        return !seen || channel.lastMessageAt > seen;
    }

    function chatTime(iso) {
        if (!iso) return '';
        const date = new Date(iso);
        if (Number.isNaN(date.getTime())) return '';
        const days = Math.floor((Date.now() - date.getTime()) / 86400000);
        if (days < 1) {
            return new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(date);
        }
        const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
        if (days <= 30) return rtf.format(-days, 'day');       // "yesterday", "5 days ago"
        if (days <= 60) return rtf.format(-1, 'month');        // "last month"
        // Older than that: a real date, slash-free ("Jan 15, 2026").
        return new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short', day: 'numeric' }).format(date);
    }

    function chatFullTime(iso) {
        if (!iso) return '';
        const date = new Date(iso);
        if (Number.isNaN(date.getTime())) return '';
        return new Intl.DateTimeFormat(undefined, { dateStyle: 'full', timeStyle: 'short' }).format(date);
    }

    function renderChatTitle() {
        document.title = S.hiddenCount > 0 ? `(${S.hiddenCount}) ${chatBaseTitle}` : chatBaseTitle;
    }

    function clearChatUnreadTitle() {
        if (!S.hiddenCount) return;
        S.hiddenCount = 0;
        renderChatTitle();
    }

    function resetJumpButton() {
        S.jumpCount = 0;
        if (S.jumpBtn) S.jumpBtn.hidden = true;
    }

    function showJumpButton() {
        const btn = ensureJumpButton();
        if (!btn) return;
        btn.textContent = `↓ ${S.jumpCount} new`;
        btn.hidden = false;
    }

    function ensureJumpButton() {
        if (S.jumpBtn) return S.jumpBtn;
        const box = document.getElementById('chatMessages');
        if (!box) return null;
        const host = box.parentElement || box;
        if (window.getComputedStyle(host).position === 'static') host.style.position = 'relative';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'chat-jump-new';
        btn.hidden = true;
        btn.style.cssText = 'position:absolute;left:50%;transform:translateX(-50%);bottom:16px;'
            + 'z-index:5;padding:6px 14px;border:none;border-radius:999px;background:#ec3750;'
            + 'color:#fff;font:inherit;font-size:.82rem;font-weight:600;cursor:pointer;'
            + 'box-shadow:0 4px 12px rgba(0,0,0,.18);';
        btn.addEventListener('click', () => {
            scrollChatToBottom(true);
            resetJumpButton();
        });
        host.appendChild(btn);
        if (!S.scrollBound) {
            S.scrollBound = true;
            box.addEventListener('scroll', () => {
                if (box.scrollHeight - box.scrollTop - box.clientHeight < 40) resetJumpButton();
            });
        }
        S.jumpBtn = btn;
        return btn;
    }

    function renderChat() {
        if (page !== 'chat') return;
        removeSkeletons('chat');
        if (Array.isArray(ctx.getState().channels)) S.channels = ctx.getState().channels;
        renderChannelList();

        if (S.activeId && !S.channels.some((channel) => channel.id === S.activeId)) {
            S.activeId = null;
            closeChatThread();
        }
        if (!S.activeId && S.channels.length) {
            selectChannel(S.channels[0].id);
        }
        startChatPolling();
        bindChatVisibility();
        bindThreadPanel();
        ensureJumpButton();
        setupMentionAutocomplete();
    }

    function renderChannelList() {
        const list = document.getElementById('chatChannelList');
        const emptyBox = document.getElementById('chatChannelsEmpty');
        if (!list) return;
        if (!S.channels.length) {
            list.innerHTML = '';
            if (emptyBox) emptyBox.hidden = false;
            return;
        }
        if (emptyBox) emptyBox.hidden = true;
        list.innerHTML = S.channels.map((channel) => {
            const active = channel.id === S.activeId ? ' is-active' : '';
            const unread = channelUnread(channel)
                ? '<span class="chat-unread-dot" aria-label="Unread messages"></span>' : '';
            return `<button class="chat-channel${active}" type="button" data-channel="${escapeHtml(channel.id)}">
                <span class="chat-channel-name">#&nbsp;${escapeHtml(channel.name)}</span>${unread}
            </button>`;
        }).join('');
    }

    function selectChannel(id) {
        if (id === S.activeId) return;
        closeThreadPanel();
        S.activeId = id;
        S.lastFetch = null;
        S.lastMsgMeta = null;
        resetJumpButton();
        const channel = S.channels.find((item) => item.id === id);
        const msgs = document.getElementById('chatMessages');
        const head = document.getElementById('chatThreadHead');
        const composer = document.getElementById('chatComposer');
        const empty = document.getElementById('chatEmpty');
        if (empty) empty.hidden = true;
        if (head) head.hidden = false;
        if (msgs) { msgs.hidden = false; msgs.innerHTML = ''; }
        if (composer) composer.hidden = false;
        const nameEl = document.getElementById('chatThreadName');
        const descEl = document.getElementById('chatThreadDesc');
        if (nameEl) nameEl.textContent = '# ' + (channel?.name || '');
        if (descEl) descEl.textContent = channel?.description || '';
        const topicEl = document.getElementById('chatThreadTopic');
        if (topicEl) {
            topicEl.textContent = channel?.topic || '';
            topicEl.hidden = !channel?.topic;
        }
        renderChannelList();
        fetchMessages(id, true).then(() => {
            const mine = chatEphemerals().filter((m) => m.channelId === id);
            mine.forEach(appendEphemeral);
            if (mine.length) scrollChatToBottom();
        });
    }

    function closeChatThread() {
        closeThreadPanel();
        const msgs = document.getElementById('chatMessages');
        const head = document.getElementById('chatThreadHead');
        const composer = document.getElementById('chatComposer');
        const empty = document.getElementById('chatEmpty');
        if (head) head.hidden = true;
        if (msgs) { msgs.hidden = true; msgs.innerHTML = ''; }
        if (composer) composer.hidden = true;
        if (empty) empty.hidden = false;
        renderTypingIndicator([]);
        S.lastFetch = null;
        S.lastMsgMeta = null;
        resetJumpButton();
    }

    function scrollChatToBottom(smooth) {
        const box = document.getElementById('chatMessages');
        if (!box) return;
        const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (smooth && !reduce && typeof box.scrollTo === 'function') {
            box.scrollTo({ top: box.scrollHeight, behavior: 'smooth' });
        } else {
            box.scrollTop = box.scrollHeight;
        }
    }

    function appendMessage(message, opts) {
        opts = opts || {};
        const box = document.getElementById('chatMessages');
        if (!box) return null;
        // Skip messages already on screen (e.g. an optimistic send the poll re-fetches).
        if (message.id) {
            const existing = box.querySelector(`[data-mid="${window.CSS.escape(String(message.id))}"]`);
            if (existing) return null;
        }
        // Old or partial messages may lack a name/avatar. Heal from the club
        // roster — member records carry the freshest profile for an email.
        let authorName = message.authorName;
        let authorAvatar = message.authorAvatar;
        const rosterEntry = clubMembers().find((member) =>
            member && member.email && String(member.email).toLowerCase()
            === String(message.authorEmail || '').toLowerCase());
        if (!authorName && rosterEntry && rosterEntry.name) authorName = rosterEntry.name;
        if (!authorAvatar && rosterEntry && rosterEntry.avatar) authorAvatar = rosterEntry.avatar;
        const person = { name: authorName, avatar: authorAvatar };
        const mine = (message.authorEmail || '').toLowerCase() === viewerEmail ? ' is-mine' : '';
        const mentionsViewer = !mine && (
            (message.mentions || []).some((email) => String(email).toLowerCase() === viewerEmail)
            || Boolean(message.mentionsEveryone)
        );
        const mentioned = mentionsViewer ? ' chat-message--mentioned' : '';
        const authorKey = String(message.authorEmail || message.authorName || '').toLowerCase();
        const msgTime = new Date(message.createdAt).getTime();
        const grouped = S.lastMsgMeta
            && S.lastMsgMeta.key === authorKey
            && Number.isFinite(msgTime) && Number.isFinite(S.lastMsgMeta.time)
            && (msgTime - S.lastMsgMeta.time) >= 0
            && (msgTime - S.lastMsgMeta.time) <= CHAT_GROUP_MS;
        const row = document.createElement('div');
        row.className = 'chat-message' + mine + mentioned + (grouped ? ' chat-message--grouped' : '')
            + (message.deleted ? ' chat-message--deleted' : '')
            + (opts.pending ? ' chat-message--pending' : '');
        if (message.id) row.dataset.mid = String(message.id);
        if (opts.pending) row.style.opacity = '0.6';
        const actions = messageActionsMarkup(message, Boolean(mine));
        if (actions) row.tabIndex = -1;   // lets focus return here after edit/cancel
        const edited = message.editedAt && !message.deleted ? editedBadgeMarkup(message) : '';
        const bodyHtml = (message.deleted
            ? '<p class="chat-message-text chat-message-deleted"><em>Message deleted</em></p>'
            : `<p class="chat-message-text">${mentionBodyHtml(message)}</p>${grouped ? edited : ''}`)
            + (message.deleted ? '' : reactionsMarkup(message));
        const threadLink = message.deleted ? '' : threadAffordanceMarkup(message);
        if (grouped) {
            row.innerHTML = `
            <span class="chat-message-time chat-message-time--hover"
                title="${escapeHtml(chatFullTime(message.createdAt))}">${escapeHtml(chatTime(message.createdAt))}</span>
            <div class="chat-message-body">
                ${bodyHtml}${threadLink}
            </div>${actions}`;
        } else {
            const authorEmail = (message.authorEmail || '').toLowerCase();
            const online = (S.onlineMembers || []).includes(authorEmail) ? ' is-online' : '';
            row.innerHTML = `
            <span class="chat-avatar-presence${online}" data-presence-email="${escapeHtml(authorEmail)}">
                ${avatarMarkup(person, 'avatar-sm')}
            </span>
            <div class="chat-message-body">
                <div class="chat-message-meta">
                    <span class="chat-message-author">${escapeHtml(authorName || message.authorEmail || 'Member')}</span>
                    <span class="chat-message-time" title="${escapeHtml(chatFullTime(message.createdAt))}">${escapeHtml(chatTime(message.createdAt))}</span>
                    ${edited}
                </div>
                ${bodyHtml}${threadLink}
            </div>${actions}`;
        }
        box.appendChild(row);
        S.lastMsgMeta = { key: authorKey, time: Number.isFinite(msgTime) ? msgTime : Date.now() };
        return row;
    }

    // ── Mentions ─────────────────────────────────────────────────────────────
    // The server resolved and persisted `mentions`/`mentionsEveryone`; the
    // client only paints them (and offers the "@…" picker as a typing aid).

    function clubMembers() {
        return ctx.getState().members || [];
    }

    function mentionNames(message) {
        const byEmail = {};
        clubMembers().forEach((member) => {
            if (member && member.email && member.name) {
                byEmail[String(member.email).toLowerCase()] = member.name;
            }
        });
        const names = (message.mentions || [])
            .map((email) => byEmail[String(email).toLowerCase()])
            .filter(Boolean);
        if (message.mentionsEveryone) names.push('everyone');
        // Longest first so the alternation below prefers "@Jane Doe" over "@Jane".
        return names.sort((a, b) => b.length - a.length);
    }

    function mentionBodyHtml(message) {
        const body = message.body || '';
        const names = mentionNames(message);
        if (!names.length) return escapeHtml(body);
        const alternation = names
            .map((name) => name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
            .join('|');
        // Match on the raw body and escape each slice, so the wrapping markup
        // is never itself re-scanned by a later, shorter name.
        const pattern = new RegExp('(?<![\\w@])@(' + alternation + ')(?![\\w])', 'g');
        let html = '';
        let last = 0;
        let match;
        while ((match = pattern.exec(body)) !== null) {
            const cls = match[1] === 'everyone' ? 'mention mention--everyone' : 'mention';
            html += escapeHtml(body.slice(last, match.index))
                + `<span class="${cls}">@${escapeHtml(match[1])}</span>`;
            last = match.index + match[0].length;
        }
        return html + escapeHtml(body.slice(last));
    }

    const REACTION_EMOJI = ['👍', '❤️', '😂', '🎉'];

    function reactionsMarkup(message) {
        const reactions = message.reactions || {};
        const pills = Object.keys(reactions).map((emoji) => {
            const authors = reactions[emoji] || [];
            const mine = authors.includes(viewerEmail) ? ' is-mine' : '';
            return `<button class="chat-reaction-pill${mine}" type="button" data-react="${escapeHtml(emoji)}"
                aria-label="Toggle ${escapeHtml(emoji)} reaction">${escapeHtml(emoji)} ${authors.length}</button>`;
        }).join('');
        return `<div class="chat-reactions">${pills}</div>`;
    }

    function threadAffordanceMarkup(message) {
        const count = message.replyCount || 0;
        if (!count) return '';
        const label = count === 1 ? '1 reply' : `${count} replies`;
        return `<button class="chat-thread-open" type="button" data-open-thread="${escapeHtml(String(message.id))}">💬 ${escapeHtml(label)}</button>`;
    }

    // Edit is own-message-only (the API rejects leaders editing others'); delete
    // is available to authors and to leaders on any message. Anyone can react.
    function messageActionsMarkup(message, mine) {
        if (message.deleted) return '';
        const reactBtns = REACTION_EMOJI.map((emoji) =>
            `<button class="chat-msg-action" type="button" data-react="${emoji}" aria-label="React ${emoji}">${emoji}</button>`).join('');
        const replyBtn = message.parentId ? ''
            : `<button class="chat-msg-action" type="button" data-open-thread="${escapeHtml(String(message.id))}" aria-label="Reply in thread">Reply</button>`;
        const editBtn = mine
            ? '<button class="chat-msg-action" type="button" data-edit-msg aria-label="Edit message">Edit</button>'
            : '';
        const deleteBtn = (mine || isLeader)
            ? '<button class="chat-msg-action" type="button" data-delete-msg aria-label="Delete message">Delete</button>'
            : '';
        const reportBtn = mine
            ? ''
            : '<button class="chat-msg-action" type="button" data-report-msg aria-label="Report message">Report</button>';
        return `<span class="chat-message-actions">${reactBtns}${replyBtn}${editBtn}${deleteBtn}${reportBtn}</span>`;
    }

    function editedBadgeMarkup(message) {
        if (!message.editedAt) return '';
        return `<span class="chat-message-edited" title="${escapeHtml(chatFullTime(message.editedAt))}">(edited)</span>`;
    }

    function startInlineEdit(row) {
        if (!row || row.classList.contains('chat-message--deleted')) return;
        if (row.querySelector('.chat-edit-form')) return;
        const text = row.querySelector('.chat-message-text');
        if (!text) return;
        const editor = document.createElement('div');
        editor.className = 'chat-edit-form';
        editor.innerHTML = `
            <input class="chat-edit-input" type="text" maxlength="500" aria-label="Edit message">
            <div class="chat-edit-actions">
                <button class="btn-primary small" type="button" data-edit-save>Save</button>
                <button class="text-button" type="button" data-edit-cancel>Cancel</button>
            </div>`;
        const input = editor.querySelector('.chat-edit-input');
        input.value = text.textContent;   // textContent is the decoded body — safe to reuse
        text.hidden = true;
        text.insertAdjacentElement('afterend', editor);
        input.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                saveInlineEdit(row);
            } else if (event.key === 'Escape') {
                event.preventDefault();
                event.stopPropagation();   // cancel the edit, don't also close drawers/modals
                cancelInlineEdit(row);
            }
        });
        input.focus();
        input.setSelectionRange(input.value.length, input.value.length);
    }

    function cancelInlineEdit(row) {
        const editor = row && row.querySelector('.chat-edit-form');
        if (!editor) return;
        const text = row.querySelector('.chat-message-text');
        if (text) text.hidden = false;
        editor.remove();
        if (row.tabIndex === -1) row.focus();
    }

    async function saveInlineEdit(row) {
        const editor = row && row.querySelector('.chat-edit-form');
        if (!editor) return;
        const mid = row.dataset.mid;
        const body = (editor.querySelector('.chat-edit-input').value || '').trim();
        if (!body || !mid || !S.activeId) return;
        const saveBtn = editor.querySelector('[data-edit-save]');
        if (saveBtn) saveBtn.disabled = true;
        try {
            const response = await apiRequest(
                `/api/dashboard/chat/channels/${encodeURIComponent(S.activeId)}/messages/${encodeURIComponent(mid)}`,
                { method: 'PATCH', body: { body } });
            const updated = (response && response.message)
                || { body, editedAt: new Date().toISOString() };
            applyMessageEdit(row, updated);
        } catch (error) {
            if (saveBtn) saveBtn.disabled = false;
            showToast(error.message, 'error');
        }
    }

    function applyMessageEdit(row, message) {
        const editor = row.querySelector('.chat-edit-form');
        if (editor) editor.remove();
        const text = row.querySelector('.chat-message-text');
        if (text) {
            text.hidden = false;
            text.textContent = message.body || '';   // textContent avoids re-escaping
        }
        if (message.editedAt && !row.querySelector('.chat-message-edited')) {
            const badge = document.createElement('span');
            badge.className = 'chat-message-edited';
            badge.title = chatFullTime(message.editedAt);
            badge.textContent = '(edited)';
            const meta = row.querySelector('.chat-message-meta');
            if (meta) {
                meta.appendChild(badge);
            } else if (text) {
                text.insertAdjacentElement('afterend', badge);
            }
        }
        if (row.tabIndex === -1) row.focus();
    }

    async function deleteMessage(row) {
        const mid = row && row.dataset.mid;
        if (!mid || !S.activeId) return;
        if (!window.confirm('Delete this message?')) return;
        try {
            await apiRequest(
                `/api/dashboard/chat/channels/${encodeURIComponent(S.activeId)}/messages/${encodeURIComponent(mid)}`,
                { method: 'DELETE' });
            applyMessageDelete(row);
        } catch (error) {
            showToast(error.message, 'error');
        }
    }

    async function reportMessage(row) {
        const mid = row && row.dataset.mid;
        if (!mid || !S.activeId) return;
        const reason = window.prompt('Why are you reporting this message? (optional)');
        if (reason === null) return;
        try {
            await apiRequest(
                `/api/dashboard/chat/channels/${encodeURIComponent(S.activeId)}/messages/${encodeURIComponent(mid)}/report`,
                { method: 'POST', body: { reason: (reason || '').slice(0, 200) } });
            showToast('Report sent — club leaders and admins will review it.');
        } catch (error) {
            showToast(error.message, 'error');
        }
    }

    function applyMessageDelete(row) {
        row.classList.add('chat-message--deleted');
        const editor = row.querySelector('.chat-edit-form');
        if (editor) editor.remove();
        const text = row.querySelector('.chat-message-text');
        if (text) {
            text.hidden = false;
            text.classList.add('chat-message-deleted');
            text.innerHTML = '<em>Message deleted</em>';
        }
        const badge = row.querySelector('.chat-message-edited');
        if (badge) badge.remove();
        const actions = row.querySelector('.chat-message-actions');
        if (actions) actions.remove();
    }

    function notifyTyping() {
        if (!S.activeId) return;
        const now = Date.now();
        if (now < S.typingThrottleUntil) return;
        S.typingThrottleUntil = now + TYPING_THROTTLE_MS;
        apiRequest(`/api/dashboard/chat/channels/${encodeURIComponent(S.activeId)}/typing`,
            { method: 'POST', body: {} }).catch(() => {
                /* fire-and-forget: a dropped signal just means the peer's
                   indicator lags by up to TYPING_THROTTLE_MS */
            });
    }

    function renderTypingIndicator(typing) {
        const el = document.getElementById('chatTypingIndicator');
        if (!el) return;
        if (!typing || !typing.length) {
            el.hidden = true;
            el.innerHTML = '';
            return;
        }
        const names = typing.map((person) => person.name || person.email);
        let text;
        if (names.length === 1) {
            text = `${names[0]} is typing…`;
        } else if (names.length === 2) {
            text = `${names[0]} and ${names[1]} are typing…`;
        } else {
            text = `${names[0]} and ${names.length - 1} others are typing…`;
        }
        if (!el.querySelector('.chat-typing-text')) {
            el.innerHTML = '<span class="chat-typing-dots"><span></span><span></span><span></span></span>'
                + '<span class="chat-typing-text"></span>';
        }
        el.querySelector('.chat-typing-text').textContent = text;   // textContent — names are unescaped
        el.hidden = false;
    }

    async function fetchMessages(id, initial) {
        try {
            const query = S.lastFetch ? `?since=${encodeURIComponent(S.lastFetch)}` : '';
            const payload = await apiRequest(
                `/api/dashboard/chat/channels/${encodeURIComponent(id)}/messages${query}`);
            if (id !== S.activeId) return;   // user switched channels mid-flight
            renderTypingIndicator(payload.typing);
            const incoming = payload.messages || [];
            if (!incoming.length) return;
            const box = document.getElementById('chatMessages');
            const distance = box
                ? (box.scrollHeight - box.scrollTop - box.clientHeight) : 0;
            const nearBottom = box ? (distance < 80) : true;
            const added = incoming.map((message) => appendMessage(message)).filter(Boolean);
            S.lastFetch = incoming[incoming.length - 1].createdAt || S.lastFetch;
            // Badge the tab title with messages that landed while it was hidden.
            if (document.hidden && added.length && !isChannelMuted(id)) {
                const others = added.filter(
                    (row) => !row.classList.contains('is-mine')).length;
                if (others) {
                    S.hiddenCount += others;
                    renderChatTitle();
                }
            }
            if (initial || nearBottom) {
                scrollChatToBottom();
                resetJumpButton();
            } else if (distance > 150 && added.length) {
                S.jumpCount += added.length;
                showJumpButton();
            }
            markChannelRead(id, S.lastFetch);
            if (initial || nearBottom) syncChannelRead(id, S.lastFetch);
            const channel = S.channels.find((item) => item.id === id);
            if (channel) channel.lastMessageAt = S.lastFetch;
            renderChannelList();
        } catch (error) {
            /* keep showing what we have; the next poll retries */
        }
    }

    function applyPresence(onlineEmails) {
        const online = new Set((onlineEmails || []).map((email) => (email || '').toLowerCase()));
        document.querySelectorAll('#chatMessages .chat-avatar-presence[data-presence-email]')
            .forEach((el) => {
                el.classList.toggle('is-online', online.has(el.dataset.presenceEmail));
            });
    }

    async function refreshChannels() {
        try {
            const payload = await apiRequest('/api/dashboard/chat/channels');
            S.channels = payload.channels || S.channels;
            S.onlineMembers = payload.onlineMembers || [];
            applyPresence(S.onlineMembers);
            renderChannelList();
            if (S.activeId && !S.channels.some((channel) => channel.id === S.activeId)) {
                S.activeId = null;
                closeChatThread();
                if (S.channels.length) selectChannel(S.channels[0].id);
            }
        } catch (error) {
            /* transient — retry next tick */
        }
    }

    async function messagePoll() {
        if (document.hidden || page !== 'chat' || !S.activeId || S.messagePollBusy) return;
        S.messagePollBusy = true;
        try {
            await fetchMessages(S.activeId);
        } finally {
            S.messagePollBusy = false;
        }
    }

    async function channelPoll() {
        if (document.hidden || page !== 'chat') return;
        await refreshChannels();
        await refreshSeenBy();
    }

    async function refreshSeenBy() {
        const id = S.activeId;
        if (!id) return;
        try {
            const payload = await apiRequest(
                `/api/dashboard/chat/channels/${encodeURIComponent(id)}/reads`);
            if (id !== S.activeId) return;
            renderSeenBy(payload.reads || {});
        } catch (error) {
            /* transient — retry next tick */
        }
    }

    const SEEN_BY_MAX = 4;

    function renderSeenBy(reads) {
        const box = document.getElementById('chatMessages');
        if (!box) return;
        const existing = box.querySelector('.chat-seen-by');
        if (existing) existing.remove();
        const lastAt = S.lastFetch;
        if (!lastAt || !box.querySelector('.chat-message')) return;

        const byEmail = {};
        clubMembers().forEach((member) => {
            if (member && member.email) byEmail[String(member.email).toLowerCase()] = member;
        });
        const seen = Object.keys(reads).filter((email) => {
            const key = String(email).toLowerCase();
            return key !== viewerEmail && reads[email] >= lastAt;
        });
        if (!seen.length) return;

        const shown = seen.slice(0, SEEN_BY_MAX);
        const overflow = seen.length - shown.length;
        const row = document.createElement('div');
        row.className = 'chat-seen-by';
        row.innerHTML = '<span class="chat-seen-by-label">Seen by</span>'
            + shown.map((email) => {
                const member = byEmail[String(email).toLowerCase()] || {};
                const name = member.name || email;
                return `<span class="chat-seen-by-person" title="${escapeHtml(name)}">${avatarMarkup({ name, avatar: member.avatar }, 'avatar-sm')}</span>`;
            }).join('')
            + (overflow > 0 ? `<span class="chat-seen-by-overflow">+${overflow}</span>` : '');
        box.appendChild(row);
    }

    function startChatPolling() {
        if (S.pollTimer || page !== 'chat') return;
        S.pollTimer = window.setInterval(messagePoll, MESSAGE_POLL_MS);
        S.channelPollTimer = window.setInterval(channelPoll, CHANNEL_POLL_MS);
    }

    function stopChatPolling() {
        if (S.pollTimer) {
            window.clearInterval(S.pollTimer);
            S.pollTimer = null;
        }
        if (S.channelPollTimer) {
            window.clearInterval(S.channelPollTimer);
            S.channelPollTimer = null;
        }
    }

    // ── Thread panel ─────────────────────────────────────────────────────────
    // A side panel scoped to one parent message. It reuses appendMessage()'s
    // row renderer and runs its own poll on the same cadence as the channel.

    function threadPanel() {
        return document.getElementById('chatThreadPanel');
    }

    function openThreadPanel(parentId) {
        const panel = threadPanel();
        if (!panel) return;
        // Cancel any pending close timeout before reopening
        if (S.threadPanelCloseTimer) {
            window.clearTimeout(S.threadPanelCloseTimer);
            S.threadPanelCloseTimer = null;
        }
        S.threadParentId = parentId;
        S.threadLastFetch = null;
        S.threadLastMsgMeta = null;
        const box = panel.querySelector('.chat-thread-messages');
        if (box) box.innerHTML = '';
        panel.hidden = false;
        window.requestAnimationFrame(() => panel.classList.add('chat-thread-panel--visible'));
        loadThreadMessages(parentId);
        stopThreadPolling();
        S.threadPollTimer = window.setInterval(() => threadPoll(parentId), MESSAGE_POLL_MS);
    }

    function closeThreadPanel() {
        const panel = threadPanel();
        if (panel) {
            if (S.threadPanelCloseTimer) window.clearTimeout(S.threadPanelCloseTimer);
            panel.classList.remove('chat-thread-panel--visible');
            S.threadPanelCloseTimer = window.setTimeout(() => {
                panel.hidden = true;
                S.threadPanelCloseTimer = null;
            }, 200);
        }
        S.threadParentId = null;
        stopThreadPolling();
    }

    function stopThreadPolling() {
        if (S.threadPollTimer) {
            window.clearInterval(S.threadPollTimer);
            S.threadPollTimer = null;
        }
    }

    async function threadPoll(parentId) {
        if (document.hidden || page !== 'chat'
            || S.threadParentId !== parentId || S.threadPollBusy) return;
        S.threadPollBusy = true;
        try {
            await loadThreadMessages(parentId);
        } finally {
            S.threadPollBusy = false;
        }
    }

    async function loadThreadMessages(parentId) {
        try {
            let query = `?parentId=${encodeURIComponent(parentId)}`;
            if (S.threadLastFetch) {
                query += `&since=${encodeURIComponent(S.threadLastFetch)}`;
            }
            const payload = await apiRequest(
                `/api/dashboard/chat/channels/${encodeURIComponent(S.activeId)}/messages${query}`);
            if (S.threadParentId !== parentId) return;   // panel switched threads mid-flight
            const incoming = payload.messages || [];
            if (!incoming.length) return;
            const panel = threadPanel();
            const box = panel && panel.querySelector('.chat-thread-messages');
            if (!box) return;
            // appendMessage() renders into #chatMessages and groups against
            // S.lastMsgMeta; borrow both, then hand the rows to the panel.
            const savedMeta = S.lastMsgMeta;
            S.lastMsgMeta = S.threadLastMsgMeta || null;
            incoming.forEach((message) => {
                const row = appendMessage(message);
                if (row) box.appendChild(row);
            });
            S.threadLastMsgMeta = S.lastMsgMeta;
            S.lastMsgMeta = savedMeta;
            S.threadLastFetch = incoming[incoming.length - 1].createdAt || S.threadLastFetch;
            box.scrollTop = box.scrollHeight;
        } catch (error) {
            /* keep showing what we have; the next poll retries */
        }
    }

    async function sendThreadReply(form) {
        const input = form.querySelector('.chat-thread-reply-input');
        const body = (input.value || '').trim();
        if (!body || !S.activeId || !S.threadParentId) return;
        const submitBtn = form.querySelector('[type="submit"]');
        if (submitBtn) submitBtn.disabled = true;
        try {
            await apiRequest(
                `/api/dashboard/chat/channels/${encodeURIComponent(S.activeId)}/messages`,
                { method: 'POST', body: { body, parentId: S.threadParentId } });
            input.value = '';
        } catch (error) {
            showToast(error.message, 'error');
            if (error && error.status === 409) closeThreadPanel();
        } finally {
            if (submitBtn) submitBtn.disabled = false;
        }
    }

    function bindThreadPanel() {
        if (S.threadPanelBound) return;
        S.threadPanelBound = true;
        document.addEventListener('click', (event) => {
            const btn = event.target.closest('[data-open-thread]');
            if (btn) openThreadPanel(btn.dataset.openThread);
        });
        const panel = threadPanel();
        if (!panel) return;
        const closeBtn = panel.querySelector('[data-close-thread]');
        if (closeBtn) closeBtn.addEventListener('click', closeThreadPanel);
        const form = panel.querySelector('.chat-thread-reply-form');
        if (form) {
            form.addEventListener('submit', (event) => {
                event.preventDefault();
                sendThreadReply(form);
            });
        }
    }

    function bindChatVisibility() {
        if (S.visibilityBound) return;
        S.visibilityBound = true;
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                stopChatPolling();
            } else {
                clearChatUnreadTitle();
                if (page === 'chat') {
                    startChatPolling();
                    channelPoll();
                    messagePoll();
                }
            }
        });
        window.addEventListener('focus', clearChatUnreadTitle);
    }

    function setChatDrawer(open) {
        const sidebar = document.querySelector('.chat-sidebar');
        const backdrop = document.getElementById('chatBackdrop');
        const toggle = document.getElementById('chatDrawerToggle');
        if (!sidebar) return;
        sidebar.classList.toggle('open', open);
        if (backdrop) backdrop.hidden = !open;
        if (toggle) toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    }

    function toggleChatDrawer() {
        const sidebar = document.querySelector('.chat-sidebar');
        setChatDrawer(!(sidebar && sidebar.classList.contains('open')));
    }

    function closeChatDrawer() {
        setChatDrawer(false);
    }

    const CHAT_COMMAND_DEFS = [
        { name: 'help', usage: '/help', desc: 'List all commands' },
        { name: 'mute', usage: '/mute', desc: 'Mute or unmute this channel on this device' },
        { name: 'topic', usage: '/topic <text>', desc: 'Set the channel topic', leaders: true },
        { name: 'clear', usage: '/clear', desc: 'Delete all messages in this channel', leaders: true },
    ];

    // ── Ephemeral messages: command feedback only the viewer sees, kept per
    // device in localStorage until dismissed (capped at the newest 20). ──────
    const CHAT_EPHEMERAL_KEY = 'hcl:chatEphemeral';

    function chatEphemerals() {
        try {
            return JSON.parse(localStorage.getItem(CHAT_EPHEMERAL_KEY)) || [];
        } catch (error) {
            return [];
        }
    }

    function saveEphemerals(list) {
        localStorage.setItem(CHAT_EPHEMERAL_KEY, JSON.stringify(list.slice(-20)));
    }

    function appendEphemeral(msg) {
        const box = document.getElementById('chatMessages');
        if (!box || msg.channelId !== S.activeId) return;
        const row = document.createElement('div');
        row.className = 'chat-message chat-ephemeral';
        row.innerHTML = `
            <div class="chat-message-body">
                <p class="chat-message-text">${escapeHtml(msg.body)}</p>
                <p class="chat-ephemeral-note">Only you can see this ·
                    <button class="text-button" type="button" data-hide-eph="${escapeHtml(msg.id)}">Hide</button></p>
            </div>`;
        box.appendChild(row);
        S.lastMsgMeta = null;   // don't visually group real messages across it
    }

    function postEphemeral(text) {
        const msg = {
            id: 'eph-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7),
            channelId: S.activeId,
            body: text,
            createdAt: new Date().toISOString(),
        };
        saveEphemerals(chatEphemerals().concat(msg));
        appendEphemeral(msg);
        scrollChatToBottom();
    }

    function hideEphemeral(id, row) {
        saveEphemerals(chatEphemerals().filter((m) => m.id !== id));
        if (row) row.remove();
    }

    async function runChatCommand(text) {
        const [cmd, ...rest] = text.slice(1).split(/\s+/);
        const arg = rest.join(' ').trim();
        const def = CHAT_COMMAND_DEFS.find((c) => c.name === (cmd || '').toLowerCase());
        if (!def) {
            postEphemeral(`Unknown command /${cmd}. Try /help.`);
            return;
        }
        if (def.leaders && !isLeader) {
            postEphemeral("You don't have permission to use this command.");
            return;
        }
        const commands = {
            help() {
                postEphemeral('Commands: ' + CHAT_COMMAND_DEFS.map((c) =>
                    `${c.usage}${c.leaders ? ' (leaders)' : ''} — ${c.desc}`).join('  ·  '));
            },
            mute() {
                const mutes = chatMutes();
                const muted = mutes.includes(S.activeId);
                const next = muted
                    ? mutes.filter((id) => id !== S.activeId)
                    : mutes.concat(S.activeId);
                localStorage.setItem(CHAT_MUTES_KEY, JSON.stringify(next));
                renderChannelList();
                postEphemeral(muted ? 'Channel unmuted.' : 'Channel muted.');
            },
            async clear() {
                if (!window.confirm('Delete ALL messages in this channel?')) return;
                await apiRequest(
                    `/api/dashboard/chat/channels/${encodeURIComponent(S.activeId)}/messages`,
                    { method: 'DELETE' });
                const box = document.getElementById('chatMessages');
                if (box) box.innerHTML = '';
                S.lastMsgMeta = null;
                postEphemeral('Channel cleared.');
            },
            async topic() {
                const payload = await apiRequest(
                    `/api/dashboard/chat/channels/${encodeURIComponent(S.activeId)}`,
                    { method: 'PATCH', body: { topic: arg } });
                const local = S.channels.find((item) => item.id === S.activeId);
                if (local && payload.channel) Object.assign(local, payload.channel);
                const topicEl = document.getElementById('chatThreadTopic');
                if (topicEl) {
                    topicEl.textContent = arg;
                    topicEl.hidden = !arg;
                }
                postEphemeral(arg ? `Topic set: ${arg}` : 'Topic cleared.');
            },
        };
        try {
            await commands[def.name]();
        } catch (error) {
            postEphemeral(error.message);
        }
    }

    // ── Command autocomplete: menu above the composer while typing "/…". ─────

    function ensureCmdMenu() {
        if (S.cmdMenu) return S.cmdMenu;
        const form = document.getElementById('chatComposer');
        if (!form) return null;
        const menu = document.createElement('div');
        menu.className = 'chat-cmd-menu';
        menu.hidden = true;
        menu.addEventListener('mousedown', (event) => {
            const option = event.target.closest('[data-cmd]');
            if (!option) return;
            event.preventDefault();   // keep composer focus
            const def = CHAT_COMMAND_DEFS.find((c) => c.name === option.dataset.cmd);
            const input = form.elements.body;
            input.value = '/' + option.dataset.cmd + (def && def.usage.includes('<') ? ' ' : '');
            input.focus();
            hideCmdMenu();
        });
        form.appendChild(menu);
        S.cmdMenu = menu;
        return menu;
    }

    function hideCmdMenu() {
        if (S.cmdMenu) S.cmdMenu.hidden = true;
    }

    function updateCmdMenu(value) {
        const menu = ensureCmdMenu();
        if (!menu) return;
        if (!value.startsWith('/') || value.includes(' ')) {
            menu.hidden = true;
            return;
        }
        const term = value.slice(1).toLowerCase();
        const matches = CHAT_COMMAND_DEFS.filter((c) => c.name.startsWith(term));
        if (!matches.length) {
            menu.hidden = true;
            return;
        }
        menu.innerHTML = matches.map((c) => `
            <button class="chat-cmd-option" type="button" data-cmd="${c.name}">
                <strong>${c.usage}</strong><span>${c.desc}${c.leaders ? ' (leaders only)' : ''}</span>
            </button>`).join('');
        menu.hidden = false;
    }

    // ── Mention autocomplete: member picker above the composer on "@…". ──────

    const MENTION_MENU_MAX = 6;
    // The "@word…" the caret currently sits inside. Names contain spaces, so
    // the term runs to the caret; a term that matches nobody just closes the menu.
    const MENTION_TERM_RE = /(?:^|[^\w@])@([^@]{0,40})$/;

    function composerInput() {
        const form = document.getElementById('chatComposer');
        return form ? form.elements.body : null;
    }

    function ensureMentionMenu() {
        if (S.mentionMenu) return S.mentionMenu;
        const form = document.getElementById('chatComposer');
        if (!form) return null;
        const menu = document.createElement('div');
        menu.className = 'chat-cmd-menu chat-mention-menu';
        menu.hidden = true;
        menu.addEventListener('mousedown', (event) => {
            const option = event.target.closest('[data-mention]');
            if (!option) return;
            event.preventDefault();   // keep composer focus
            applyMention(option.dataset.mention);
        });
        form.appendChild(menu);
        S.mentionMenu = menu;
        return menu;
    }

    function hideMentionMenu() {
        if (S.mentionMenu) S.mentionMenu.hidden = true;
        S.mentionIndex = 0;
        S.mentionOptions = [];
    }

    function mentionCandidates(term) {
        const lower = term.toLowerCase();
        const names = clubMembers()
            .filter((member) => member && member.name && member.email
                && member.name.toLowerCase().startsWith(lower))
            .map((member) => member.name);
        // @everyone only notifies when a leader sends it, so only offer it to one.
        if (isLeader && 'everyone'.startsWith(lower)) names.unshift('everyone');
        return names.slice(0, MENTION_MENU_MAX);
    }

    function updateMentionMenu() {
        const input = composerInput();
        const menu = ensureMentionMenu();
        if (!input || !menu) return;
        const match = MENTION_TERM_RE.exec((input.value || '').slice(0, input.selectionStart));
        const options = match ? mentionCandidates(match[1]) : [];
        if (!options.length) {
            hideMentionMenu();
            return;
        }
        S.mentionOptions = options;
        S.mentionIndex = Math.min(S.mentionIndex || 0, options.length - 1);
        menu.innerHTML = options.map((name, index) => `
            <button class="chat-cmd-option${index === S.mentionIndex ? ' is-active' : ''}"
                type="button" data-mention="${escapeHtml(name)}">
                <strong>@${escapeHtml(name)}</strong>
            </button>`).join('');
        menu.hidden = false;
    }

    function applyMention(name) {
        const input = composerInput();
        if (!input || !name) return;
        const cursor = input.selectionStart;
        const before = (input.value || '').slice(0, cursor);
        const match = MENTION_TERM_RE.exec(before);
        if (!match) {
            hideMentionMenu();
            return;
        }
        const at = before.length - match[1].length - 1;
        // Insert the name verbatim — the server matches on the exact display name.
        const insert = '@' + name + ' ';
        input.value = before.slice(0, at) + insert + (input.value || '').slice(cursor);
        const caret = at + insert.length;
        input.focus();
        input.setSelectionRange(caret, caret);
        hideMentionMenu();
    }

    function mentionKeydown(event) {
        const options = S.mentionOptions || [];
        if (!S.mentionMenu || S.mentionMenu.hidden || !options.length) return;
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            const step = event.key === 'ArrowDown' ? 1 : -1;
            S.mentionIndex = (S.mentionIndex + step + options.length) % options.length;
            updateMentionMenu();
        } else if (event.key === 'Enter' || event.key === 'Tab') {
            event.preventDefault();
            event.stopPropagation();   // don't let Enter submit the composer
            applyMention(options[S.mentionIndex]);
        } else if (event.key === 'Escape') {
            event.stopPropagation();
            hideMentionMenu();
        }
    }

    function setupMentionAutocomplete() {
        const input = composerInput();
        if (!input || S.mentionsBound) return;
        S.mentionsBound = true;
        hideMentionMenu();
        input.addEventListener('input', updateMentionMenu);
        input.addEventListener('keydown', mentionKeydown);
        input.addEventListener('blur', () => window.setTimeout(hideMentionMenu, 150));
    }

    function prepareNewChannel() {
        const form = $('#channelForm');
        if (!form) return;
        form.reset();
        form.elements.id.value = '';
        $('#channelModalTitle').textContent = 'New channel';
        $('#deleteChannelButton').hidden = true;
        setFormError('channelFormError', '');
    }

    function prepareEditChannel(id) {
        const channel = S.channels.find((item) => item.id === id);
        const form = $('#channelForm');
        if (!channel || !form) return;
        form.elements.id.value = channel.id;
        form.elements.name.value = channel.name || '';
        form.elements.description.value = channel.description || '';
        form.elements.topic.value = channel.topic || '';
        $('#channelModalTitle').textContent = 'Edit channel';
        $('#deleteChannelButton').hidden = false;
        setFormError('channelFormError', '');
    }

    return {
            appendMessage: appendMessage,
            cancelInlineEdit: cancelInlineEdit,
            chatReads: chatReads,
            closeChatDrawer: closeChatDrawer,
            closeChatThread: closeChatThread,
            deleteMessage: deleteMessage,
            hideCmdMenu: hideCmdMenu,
            hideEphemeral: hideEphemeral,
            markChannelRead: markChannelRead,
            notifyTyping: notifyTyping,
            prepareEditChannel: prepareEditChannel,
            prepareNewChannel: prepareNewChannel,
            reactionsMarkup: reactionsMarkup,
            renderChat: renderChat,
            reportMessage: reportMessage,
            resetJumpButton: resetJumpButton,
            runChatCommand: runChatCommand,
            saveInlineEdit: saveInlineEdit,
            scrollChatToBottom: scrollChatToBottom,
            selectChannel: selectChannel,
            startInlineEdit: startInlineEdit,
            toggleChatDrawer: toggleChatDrawer,
            updateCmdMenu: updateCmdMenu,
    };
};
