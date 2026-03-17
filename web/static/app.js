/**
 * app.js — Operant WebパネルのメインJS
 * WebSocket接続・メッセージ処理・i18n
 */

'use strict';

// ---------------------------------------------------------------------------
// グローバル状態
// ---------------------------------------------------------------------------
let ws = null;
let isRunning = false;
let i18n = {};
let _stepCount = 0;          // 現在タスクの思考ターン数
let _lastScreenshotData = null; // ダウンロード用

// ---------------------------------------------------------------------------
// カスタムダイアログ
// ---------------------------------------------------------------------------
let _dialogResolve = null;

function _closeDialog(result) {
  document.getElementById('customDialog').classList.remove('is-visible');
  if (_dialogResolve) {
    _dialogResolve(result);
    _dialogResolve = null;
  }
}

function showDialog({ message, confirmMode = false }) {
  const dialog    = document.getElementById('customDialog');
  const msgEl     = document.getElementById('dialogMessage');
  const okBtn     = document.getElementById('dialogOkBtn');
  const cancelBtn = document.getElementById('dialogCancelBtn');

  msgEl.textContent           = message;
  okBtn.textContent           = t('web.dialog_ok')     || 'OK';
  cancelBtn.textContent       = t('web.dialog_cancel') || 'Cancel';
  cancelBtn.style.display     = confirmMode ? '' : 'none';

  dialog.classList.add('is-visible');
  okBtn.focus();

  return new Promise(resolve => { _dialogResolve = resolve; });
}

function showAlert(message) {
  return showDialog({ message, confirmMode: false });
}

function showConfirm(message) {
  return showDialog({ message, confirmMode: true });
}

// ---------------------------------------------------------------------------
// i18n 読み込み
// ---------------------------------------------------------------------------
async function loadI18n() {
  try {
    const res = await fetch('/api/i18n');
    i18n = await res.json();
    applyI18n();
  } catch (e) {
    console.warn('Failed to load i18n', e);
  }
}

function t(key) {
  const parts = key.split('.');
  let val = i18n;
  for (const p of parts) {
    if (val && typeof val === 'object') val = val[p];
    else return key;
  }
  return typeof val === 'string' ? val : key;
}

function applyI18n() {
  document.title = t('web.panel_title') || 'Operant';
  document.querySelector('.app-title').textContent = t('web.panel_title') || 'Operant';
  document.getElementById('stopBtn').textContent = t('web.stop_button') || 'Emergency Stop';
  document.getElementById('sendBtn').textContent = t('web.send_button') || 'Send';
  document.getElementById('taskInput').placeholder = t('web.chat_placeholder') || 'Enter your task...';
  document.getElementById('noScreenshot').textContent = t('web.no_screenshot') || 'No screenshot yet';
  document.getElementById('screenshotImg').title = t('web.click_to_expand') || 'Click to expand';
  document.getElementById('chatHeaderTitle').textContent = t('web.chat_title') || 'Chat';
  document.getElementById('clearHistoryBtn').textContent = t('web.clear_history') || 'Clear';
  document.getElementById('saveChatBtn').textContent = t('web.save_chat') || 'Save';
  document.getElementById('savedChatsBtn').textContent = t('web.saved_chats') || 'Saved Chats';
  document.getElementById('savedChatsPanelTitle').textContent = t('web.saved_chats') || 'Saved Chats';
  document.getElementById('editRulesBtn').textContent = t('web.edit_rules') || 'Edit Rules';
  document.getElementById('editRulesPanelTitle').textContent = t('web.edit_rules_title') || 'Edit OPERANT.md';
  document.getElementById('saveRulesBtn').textContent = t('web.edit_rules_save') || 'Save';
  document.getElementById('editRulesTextarea').placeholder = t('web.edit_rules_placeholder') || 'Enter agent rules...';
  document.getElementById('downloadScreenshotBtn').title = t('web.download_screenshot') || 'Download screenshot';
  updateStatusBadge(isRunning);
}

// ---------------------------------------------------------------------------
// WebSocket
// ---------------------------------------------------------------------------
let _wsRetryDelay = 2000;
const _wsRetryMax = 30000;

function setWsDot(state) {
  const dot = document.getElementById('wsStatusDot');
  dot.className = `ws-dot ws-dot--${state}`;
  const labels = { connected: t('web.ws_connected') || 'Connected', disconnected: t('web.ws_disconnected') || 'Disconnected', connecting: t('web.ws_connecting') || 'Connecting...' };
  dot.title = labels[state] || state;
}

function connectWS() {
  setWsDot('connecting');
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
  const url = `${protocol}://${location.host}/ws`;
  ws = new WebSocket(url);

  ws.onopen = () => {
    console.log('WebSocket connected');
    setWsDot('connected');
    _wsRetryDelay = 2000;
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleMessage(msg);
    } catch (e) {
      console.error('Failed to parse WS message', e);
    }
  };

  ws.onclose = (event) => {
    setWsDot('disconnected');
    if (event.code === 4401) {
      window.location.href = '/login';
      return;
    }
    console.warn(`WebSocket closed (${event.code}), reconnecting in ${_wsRetryDelay}ms...`);
    setTimeout(connectWS, _wsRetryDelay);
    _wsRetryDelay = Math.min(_wsRetryDelay * 2, _wsRetryMax);
  };

  ws.onerror = (e) => {
    setWsDot('disconnected');
    console.error('WebSocket error', e);
  };
}

function sendWS(msg) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(msg));
  }
}

// ---------------------------------------------------------------------------
// 生成中インジケーター
// ---------------------------------------------------------------------------
let _thinkingEl = null;

function showThinkingIndicator() {
  if (_thinkingEl) return;
  const chatEl = document.getElementById('chatMessages');
  _thinkingEl = document.createElement('div');
  _thinkingEl.className = 'chat-msg chat-msg--thinking';
  _thinkingEl.innerHTML = `
    <span class="thinking-label">${t('web.generating') || 'Generating...'}</span>
    <span class="thinking-dots"><span></span><span></span><span></span></span>
  `;
  chatEl.appendChild(_thinkingEl);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function hideThinkingIndicator() {
  if (_thinkingEl) {
    _thinkingEl.remove();
    _thinkingEl = null;
  }
}

// ---------------------------------------------------------------------------
// ステップカウンター
// ---------------------------------------------------------------------------
function resetStepCounter() {
  _stepCount = 0;
  const el = document.getElementById('stepCounter');
  el.hidden = true;
}

function incrementStep() {
  _stepCount++;
  const el = document.getElementById('stepCounter');
  const label = t('web.step_count') || 'Step';
  el.textContent = `${label} ${_stepCount}`;
  el.hidden = false;
}

// ---------------------------------------------------------------------------
// メッセージハンドラー
// ---------------------------------------------------------------------------
function handleMessage(msg) {
  switch (msg.type) {
    case 'think':
      hideThinkingIndicator();
      incrementStep();
      appendChat('think', msg.content);
      if (isRunning) showThinkingIndicator();
      break;

    case 'done':
      hideThinkingIndicator();
      appendChat('done', msg.content);
      break;

    case 'screenshot':
      updateScreenshot(msg.data);
      break;

    case 'log':
      // アクションログをチャットに薄く表示
      appendLog(msg.content);
      break;

    case 'error':
      hideThinkingIndicator();
      appendChat('error', msg.content);
      break;

    case 'status':
      isRunning = msg.running;
      updateStatusBadge(isRunning);
      updateLiveBadge(isRunning);
      updateInputState();
      if (isRunning) {
        showThinkingIndicator();
      } else {
        hideThinkingIndicator();
        resetStepCounter();
      }
      break;

    default:
      console.log('[MSG]', msg);
  }
}

// ---------------------------------------------------------------------------
// チャット表示
// ---------------------------------------------------------------------------
function _formatTimestamp() {
  const now = new Date();
  return `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;
}

function appendChat(type, content) {
  const chatEl = document.getElementById('chatMessages');
  const el = document.createElement('div');
  el.classList.add('chat-msg', `chat-msg--${type}`);

  let prefix = '';
  switch (type) {
    case 'think': prefix = t('web.think_prefix') || 'Thinking: '; break;
    case 'done':  prefix = t('web.done_prefix')  || 'Done: ';    break;
    case 'user':  prefix = t('web.user_prefix')  || 'You: ';     break;
    case 'error': prefix = t('web.error_prefix') || 'Error: ';   break;
  }

  // メインボディ
  const body = document.createElement('div');
  body.className = 'chat-msg-body';

  const prefixEl = document.createElement('span');
  prefixEl.className = 'chat-prefix';
  prefixEl.textContent = prefix;

  const contentEl = document.createElement('span');
  contentEl.className = 'chat-content';
  contentEl.textContent = content;

  body.appendChild(prefixEl);
  body.appendChild(contentEl);

  // メタ行（タイムスタンプ + コピーボタン）
  const meta = document.createElement('div');
  meta.className = 'chat-msg-meta';

  const ts = document.createElement('span');
  ts.className = 'chat-timestamp';
  ts.textContent = _formatTimestamp();

  const copyBtn = document.createElement('button');
  copyBtn.className = 'chat-copy-btn';
  copyBtn.title = t('web.copy') || 'Copy';
  copyBtn.textContent = t('web.copy') || 'Copy';
  copyBtn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(content);
      copyBtn.textContent = t('web.copied') || 'Copied!';
      setTimeout(() => { copyBtn.textContent = t('web.copy') || 'Copy'; }, 1500);
    } catch (e) {}
  });

  meta.appendChild(ts);
  meta.appendChild(copyBtn);

  el.appendChild(body);
  el.appendChild(meta);
  chatEl.appendChild(el);

  // 最新メッセージにスクロール
  chatEl.scrollTop = chatEl.scrollHeight;
}

function appendLog(content) {
  // アクションログは小さく・薄く表示（折りたたみ可）
  const chatEl = document.getElementById('chatMessages');
  const el = document.createElement('div');
  el.className = 'chat-msg chat-msg--log';

  const icon = document.createElement('span');
  icon.className = 'log-icon';
  icon.textContent = '▶';

  const text = document.createElement('span');
  text.className = 'log-content';
  text.textContent = content;

  const ts = document.createElement('span');
  ts.className = 'log-timestamp';
  ts.textContent = _formatTimestamp();

  el.appendChild(icon);
  el.appendChild(text);
  el.appendChild(ts);
  chatEl.appendChild(el);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function appendUserMessage(text) {
  appendChat('user', text);
}

// ---------------------------------------------------------------------------
// スクリーンショット更新
// ---------------------------------------------------------------------------
function updateScreenshot(base64Data) {
  _lastScreenshotData = base64Data;
  const img = document.getElementById('screenshotImg');
  const noSc = document.getElementById('noScreenshot');
  const modal = document.getElementById('screenshotModal');
  const modalImg = document.getElementById('modalImg');
  const toolbar = document.getElementById('screenshotToolbar');
  const ts = document.getElementById('screenshotTimestamp');

  const src = `data:image/webp;base64,${base64Data}`;
  img.src = src;
  img.classList.add('has-image');
  noSc.hidden = true;
  toolbar.hidden = false;

  // タイムスタンプ更新
  const now = new Date();
  ts.textContent = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;

  if (modal.classList.contains('is-visible')) {
    modalImg.src = src;
  }
}

// ---------------------------------------------------------------------------
// スクリーンショットダウンロード
// ---------------------------------------------------------------------------
function downloadScreenshot() {
  if (!_lastScreenshotData) return;
  const a = document.createElement('a');
  a.href = `data:image/webp;base64,${_lastScreenshotData}`;
  const now = new Date();
  const ts = `${now.getFullYear()}${String(now.getMonth()+1).padStart(2,'0')}${String(now.getDate()).padStart(2,'0')}_${String(now.getHours()).padStart(2,'0')}${String(now.getMinutes()).padStart(2,'0')}${String(now.getSeconds()).padStart(2,'0')}`;
  a.download = `operant_${ts}.webp`;
  a.click();
}

// ---------------------------------------------------------------------------
// ステータス・バッジ
// ---------------------------------------------------------------------------
function updateStatusBadge(running) {
  const badge = document.getElementById('statusBadge');
  if (running) {
    badge.textContent = t('web.status_running') || 'Running';
    badge.className = 'status-badge status-running';
  } else {
    badge.textContent = t('web.status_idle') || 'Idle';
    badge.className = 'status-badge status-idle';
  }
}

function updateLiveBadge(running) {
  document.getElementById('liveBadge').hidden = !running;
}

function updateInputState() {
  const sendBtn = document.getElementById('sendBtn');
  const taskInput = document.getElementById('taskInput');
  sendBtn.disabled = isRunning;
  taskInput.disabled = isRunning;
}

// ---------------------------------------------------------------------------
// タスク送信
// ---------------------------------------------------------------------------
function sendTask() {
  const input = document.getElementById('taskInput');
  const text = input.value.trim();
  if (!text || isRunning) return;

  resetStepCounter();
  appendUserMessage(text);
  sendWS({type: 'task', content: text});
  input.value = '';
}

// ---------------------------------------------------------------------------
// チャット履歴
// ---------------------------------------------------------------------------
async function loadHistory() {
  try {
    const res = await fetch('/api/history');
    if (!res.ok) return;
    const history = await res.json();
    for (const msg of history) {
      appendChat(msg.type, msg.content);
    }
  } catch (e) {
    console.warn('Failed to load chat history', e);
  }
}

async function clearHistory() {
  if (!await showConfirm(t('web.confirm_clear_history') || 'Clear chat history?')) return;
  try {
    await fetch('/api/history/clear', {method: 'POST'});
    document.getElementById('chatMessages').innerHTML = '';
    resetStepCounter();
  } catch (e) {
    console.error('Failed to clear history', e);
  }
}

// ---------------------------------------------------------------------------
// 保存チャット
// ---------------------------------------------------------------------------
async function saveCurrentChat() {
  try {
    const res = await fetch('/api/chats', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({}),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      await showAlert(err.detail || 'Failed to save');
      return;
    }
    const data = await res.json();
    await showAlert(`${t('web.chat_saved') || 'Chat saved'}: ${data.title}`);
  } catch (e) {
    console.error('Failed to save chat', e);
  }
}

async function openSavedChats() {
  const modal = document.getElementById('savedChatsModal');
  modal.classList.add('is-visible');
  await refreshSavedChatsList();
}

function closeSavedChats() {
  document.getElementById('savedChatsModal').classList.remove('is-visible');
}

async function refreshSavedChatsList() {
  const listEl = document.getElementById('savedChatsList');
  listEl.innerHTML = '';
  try {
    const res = await fetch('/api/chats');
    if (!res.ok) return;
    const chats = await res.json();
    if (chats.length === 0) {
      const empty = document.createElement('p');
      empty.className = 'saved-chats-empty';
      empty.textContent = t('web.no_saved_chats') || 'No saved chats';
      listEl.appendChild(empty);
      return;
    }
    for (const chat of chats) {
      const item = document.createElement('div');
      item.className = 'saved-chat-item';

      const info = document.createElement('div');
      info.className = 'saved-chat-info';

      const titleEl = document.createElement('div');
      titleEl.className = 'saved-chat-title';
      titleEl.textContent = chat.title;

      const meta = document.createElement('div');
      meta.className = 'saved-chat-meta';
      const dateStr = new Date(chat.created_at).toLocaleString();
      const countSuffix = t('web.messages_count') || ' messages';
      meta.textContent = `${dateStr} · ${chat.message_count}${countSuffix}`;

      info.appendChild(titleEl);
      info.appendChild(meta);

      const actions = document.createElement('div');
      actions.className = 'saved-chat-actions';

      const loadBtn = document.createElement('button');
      loadBtn.textContent = t('web.load_chat') || 'Load';
      loadBtn.className = 'saved-chat-load-btn';
      loadBtn.onclick = () => loadSavedChat(chat.id);

      const delBtn = document.createElement('button');
      delBtn.textContent = t('web.delete_chat') || 'Delete';
      delBtn.className = 'saved-chat-delete-btn';
      delBtn.onclick = () => deleteSavedChat(chat.id);

      actions.appendChild(loadBtn);
      actions.appendChild(delBtn);

      item.appendChild(info);
      item.appendChild(actions);
      listEl.appendChild(item);
    }
  } catch (e) {
    console.warn('Failed to load saved chats', e);
  }
}

async function loadSavedChat(chatId) {
  try {
    const res = await fetch(`/api/chats/${chatId}`);
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById('chatMessages').innerHTML = '';
    for (const msg of (data.messages || [])) {
      appendChat(msg.type, msg.content);
    }
    closeSavedChats();
  } catch (e) {
    console.error('Failed to load saved chat', e);
  }
}

async function deleteSavedChat(chatId) {
  if (!await showConfirm(t('web.confirm_delete_chat') || 'Delete this chat?')) return;
  try {
    await fetch(`/api/chats/${chatId}`, {method: 'DELETE'});
    await refreshSavedChatsList();
  } catch (e) {
    console.error('Failed to delete saved chat', e);
  }
}

// ---------------------------------------------------------------------------
// OPERANT.md 編集
// ---------------------------------------------------------------------------
async function openEditRules() {
  const modal = document.getElementById('editRulesModal');
  modal.classList.add('is-visible');
  try {
    const res = await fetch('/api/operant');
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById('editRulesTextarea').value = data.content || '';
  } catch (e) {
    console.error('Failed to load OPERANT.md', e);
  }
}

function closeEditRules() {
  document.getElementById('editRulesModal').classList.remove('is-visible');
}

async function saveRules() {
  const content = document.getElementById('editRulesTextarea').value;
  try {
    const res = await fetch('/api/operant', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({content}),
    });
    if (!res.ok) {
      await showAlert('Failed to save OPERANT.md');
      return;
    }
    await showAlert(t('web.edit_rules_saved') || 'OPERANT.md saved');
    closeEditRules();
  } catch (e) {
    console.error('Failed to save OPERANT.md', e);
  }
}

// ---------------------------------------------------------------------------
// 緊急停止
// ---------------------------------------------------------------------------
async function emergencyStop() {
  if (!await showConfirm(t('web.confirm_stop') || 'Emergency stop the agent?')) return;
  sendWS({type: 'stop'});
  try {
    await fetch('/api/stop', {method: 'POST'});
  } catch (e) {}
}

// ---------------------------------------------------------------------------
// ログアウト
// ---------------------------------------------------------------------------
async function logout() {
  await fetch('/api/logout', {method: 'POST'}).catch(() => {});
  window.location.href = '/login';
}

// ---------------------------------------------------------------------------
// スクリーンショット拡大
// ---------------------------------------------------------------------------
function setupScreenshotModal() {
  const img = document.getElementById('screenshotImg');
  const modal = document.getElementById('screenshotModal');
  const modalImg = document.getElementById('modalImg');
  const backdrop = document.getElementById('modalBackdrop');

  img.addEventListener('click', () => {
    if (!img.src || !img.classList.contains('has-image')) return;
    modalImg.src = img.src;
    modal.classList.add('is-visible');
  });

  backdrop.addEventListener('click', () => {
    modal.classList.remove('is-visible');
  });

  modalImg.addEventListener('click', () => {
    modal.classList.remove('is-visible');
  });
}

// ---------------------------------------------------------------------------
// イベントリスナー登録
// ---------------------------------------------------------------------------
document.getElementById('sendBtn').addEventListener('click', sendTask);

document.getElementById('taskInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    sendTask();
  }
});

document.getElementById('stopBtn').addEventListener('click', emergencyStop);
document.getElementById('logoutBtn').addEventListener('click', logout);
document.getElementById('clearHistoryBtn').addEventListener('click', clearHistory);
document.getElementById('saveChatBtn').addEventListener('click', saveCurrentChat);
document.getElementById('savedChatsBtn').addEventListener('click', openSavedChats);
document.getElementById('closeSavedChatsBtn').addEventListener('click', closeSavedChats);
document.getElementById('savedChatsBackdrop').addEventListener('click', closeSavedChats);
document.getElementById('editRulesBtn').addEventListener('click', openEditRules);
document.getElementById('closeEditRulesBtn').addEventListener('click', closeEditRules);
document.getElementById('editRulesBackdrop').addEventListener('click', closeEditRules);
document.getElementById('saveRulesBtn').addEventListener('click', saveRules);
document.getElementById('downloadScreenshotBtn').addEventListener('click', downloadScreenshot);

// ダイアログ
document.getElementById('dialogOkBtn').addEventListener('click',     () => _closeDialog(true));
document.getElementById('dialogCancelBtn').addEventListener('click', () => _closeDialog(false));
document.getElementById('dialogBackdrop').addEventListener('click',  () => _closeDialog(false));
document.addEventListener('keydown', (e) => {
  if (!document.getElementById('customDialog').classList.contains('is-visible')) return;
  if (e.key === 'Enter')  { e.preventDefault(); _closeDialog(true);  }
  if (e.key === 'Escape') { e.preventDefault(); _closeDialog(false); }
});

// ---------------------------------------------------------------------------
// 初期化
// ---------------------------------------------------------------------------
(async () => {
  await loadI18n();
  setupScreenshotModal();

  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    isRunning = data.running;
    updateStatusBadge(isRunning);
    updateLiveBadge(isRunning);
    updateInputState();
    if (isRunning) showThinkingIndicator();
  } catch (e) {}

  await loadHistory();
})();

window.addEventListener('load', () => {
  connectWS();
});
