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
  updateStatusBadge(isRunning);
}

// ---------------------------------------------------------------------------
// WebSocket
// ---------------------------------------------------------------------------
let _wsRetryDelay = 2000;
const _wsRetryMax = 30000;

function connectWS() {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
  const url = `${protocol}://${location.host}/ws`;
  ws = new WebSocket(url);

  ws.onopen = () => {
    console.log('WebSocket connected');
    _wsRetryDelay = 2000; // 接続成功したらリトライ間隔をリセット
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
    // 認証エラー (4401) は再接続しない → ログインページへ
    if (event.code === 4401) {
      window.location.href = '/login';
      return;
    }
    console.warn(`WebSocket closed (${event.code}), reconnecting in ${_wsRetryDelay}ms...`);
    setTimeout(connectWS, _wsRetryDelay);
    _wsRetryDelay = Math.min(_wsRetryDelay * 2, _wsRetryMax); // 指数バックオフ
  };

  ws.onerror = (e) => {
    console.error('WebSocket error', e);
  };
}

function sendWS(msg) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(msg));
  }
}

// ---------------------------------------------------------------------------
// メッセージハンドラー
// ---------------------------------------------------------------------------
function handleMessage(msg) {
  switch (msg.type) {
    case 'think':
      appendChat('think', msg.content);
      break;

    case 'done':
      appendChat('done', msg.content);
      break;

    case 'screenshot':
      updateScreenshot(msg.data);
      break;

    case 'log':
      // ACTやデバッグログはチャットに表示しない（コンソールのみ）
      console.log('[LOG]', msg.content);
      break;

    case 'error':
      appendChat('error', msg.content);
      break;

    case 'status':
      isRunning = msg.running;
      updateStatusBadge(isRunning);
      updateLiveBadge(isRunning);
      updateInputState();
      break;

    default:
      console.log('[MSG]', msg);
  }
}

// ---------------------------------------------------------------------------
// チャット表示
// ---------------------------------------------------------------------------
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

  const prefixEl = document.createElement('span');
  prefixEl.className = 'chat-prefix';
  prefixEl.textContent = prefix;

  const contentEl = document.createElement('span');
  contentEl.className = 'chat-content';
  contentEl.textContent = content;

  el.appendChild(prefixEl);
  el.appendChild(contentEl);
  chatEl.appendChild(el);

  // 最新メッセージにスクロール
  chatEl.scrollTop = chatEl.scrollHeight;
}

function appendUserMessage(text) {
  appendChat('user', text);
}

// ---------------------------------------------------------------------------
// スクリーンショット更新
// ---------------------------------------------------------------------------
function updateScreenshot(base64Data) {
  const img = document.getElementById('screenshotImg');
  const noSc = document.getElementById('noScreenshot');
  const modal = document.getElementById('screenshotModal');
  const modalImg = document.getElementById('modalImg');

  const src = `data:image/webp;base64,${base64Data}`;
  img.src = src;
  img.classList.add('has-image');
  noSc.hidden = true;

  if (modal.classList.contains('is-visible')) {
    modalImg.src = src;
  }
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
  if (!confirm(t('web.confirm_clear_history') || 'Clear chat history?')) return;
  try {
    await fetch('/api/history/clear', {method: 'POST'});
    document.getElementById('chatMessages').innerHTML = '';
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
      alert(err.detail || 'Failed to save');
      return;
    }
    const data = await res.json();
    alert(`${t('web.chat_saved') || 'Chat saved'}: ${data.title}`);
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
  if (!confirm(t('web.confirm_delete_chat') || 'Delete this chat?')) return;
  try {
    await fetch(`/api/chats/${chatId}`, {method: 'DELETE'});
    await refreshSavedChatsList();
  } catch (e) {
    console.error('Failed to delete saved chat', e);
  }
}

// ---------------------------------------------------------------------------
// 緊急停止
// ---------------------------------------------------------------------------
async function emergencyStop() {
  if (!confirm(t('web.confirm_stop') || 'Emergency stop the agent?')) return;
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
  // Ctrl+Enter で送信
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

// ---------------------------------------------------------------------------
// 初期化
// ---------------------------------------------------------------------------
(async () => {
  await loadI18n();
  setupScreenshotModal();

  // 現在の実行状態を取得
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    isRunning = data.running;
    updateStatusBadge(isRunning);
    updateLiveBadge(isRunning);
    updateInputState();
  } catch (e) {}

  // チャット履歴を復元
  await loadHistory();
})();

// WebSocket接続はページの load イベント後に開始
// → ブラウザの読み込みバーが完了してから接続するのでローディング表示がハングしない
window.addEventListener('load', () => {
  connectWS();
});
