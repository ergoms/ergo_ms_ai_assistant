/**
 * Состояние плавающего мини-чата AI-ассистента (виджет поддержки).
 * Открытие — только из меню приложений.
 *
 * Переживание закрытия панели — module-level refs.
 * Переживание F5 — localStorage: UUID сессии + снимок сообщений + pending (не числовой pk).
 */

import { ref } from 'vue'

const STORAGE_KEY = 'ai_assistant.miniChat.v1'
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

function isUuid(value) {
  return Boolean(value && UUID_RE.test(String(value)))
}

function serializeMessages(messages) {
  if (!Array.isArray(messages) || !messages.length) return []
  return messages.map((msg) => ({
    id: msg.id,
    type: msg.type,
    content: msg.content || '',
    timestamp: msg.timestamp instanceof Date
      ? msg.timestamp.toISOString()
      : (msg.timestamp || null),
    processing_time_ms: msg.processing_time_ms || null,
    skill_name: msg.skill_name || null,
    skill_call: msg.skill_call || null,
    chart_config: msg.chart_config || null,
    attachments: msg.attachments || [],
    metadata: msg.metadata || {},
    streaming: false,
  }))
}

function normalizeMessages(messages) {
  if (!Array.isArray(messages) || !messages.length) return null
  return messages.map((msg) => ({
    ...msg,
    streaming: false,
    timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
  }))
}

function hasUserMessages(messages) {
  return Array.isArray(messages) && messages.some((msg) => msg?.type === 'user')
}

/** Последнее сообщение — от пользователя или пустой/стримящийся ответ ассистента. */
export function isAwaitingAssistantReply(messages) {
  if (!Array.isArray(messages) || !messages.length) return false
  const last = messages[messages.length - 1]
  if (!last) return false
  if (last.type === 'user') return true
  if (last.type === 'assistant') {
    if (last.streaming) return true
    return !String(last.content || '').trim()
  }
  return false
}

/** Серверная история полнее локального снимка (после F5 во время/после генерации). */
export function shouldPreferServerMessages(localMessages, serverMessages) {
  if (!serverMessages?.length) return false
  if (!localMessages?.length) return true
  if (serverMessages.length > localMessages.length) return true
  if (serverMessages.length < localMessages.length) return false

  const localAwaiting = isAwaitingAssistantReply(localMessages)
  const serverAwaiting = isAwaitingAssistantReply(serverMessages)
  if (localAwaiting && !serverAwaiting) return true
  if (!localAwaiting && serverAwaiting) return false

  const localLast = localMessages[localMessages.length - 1]
  const serverLast = serverMessages[serverMessages.length - 1]
  const localLen = String(localLast?.content || '').length
  const serverLen = String(serverLast?.content || '').length
  return serverLen > localLen
}

function readPersistedState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { sessionId: null, messages: null, pending: false }
    const parsed = JSON.parse(raw)
    const sessionId = isUuid(parsed?.sessionId) ? String(parsed.sessionId) : null
    const messages = normalizeMessages(parsed?.messages)
    const pending = Boolean(parsed?.pending) || isAwaitingAssistantReply(messages)
    return { sessionId, messages, pending }
  } catch {
    return { sessionId: null, messages: null, pending: false }
  }
}

function writePersistedState(sessionId, messages, pending) {
  try {
    const nextSessionId = isUuid(sessionId) ? String(sessionId) : null
    const nextMessages = serializeMessages(messages)
    const nextPending = Boolean(pending)
    if (!nextSessionId && !hasUserMessages(nextMessages) && !nextPending) {
      localStorage.removeItem(STORAGE_KEY)
      return
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      sessionId: nextSessionId,
      messages: nextMessages,
      pending: nextPending,
      savedAt: Date.now(),
    }))
  } catch {
    /* private mode / quota */
  }
}

const hydrated = readPersistedState()

try {
  const legacy = sessionStorage.getItem('ai_assistant.miniChatSessionId')
  if (legacy && isUuid(legacy) && !hydrated.sessionId) {
    hydrated.sessionId = String(legacy)
    writePersistedState(hydrated.sessionId, hydrated.messages, hydrated.pending)
  }
  sessionStorage.removeItem('ai_assistant.miniChatSessionId')
} catch {
  /* ignore */
}

export const isOllamaMiniChatOpen = ref(false)
/** После первого открытия панель остаётся в DOM (v-show), чтобы стрим/анимация не сбрасывались. */
export const miniChatPanelMounted = ref(false)
/** Позиция после перетаскивания: { left, top } в px или null (дефолт у меню). */
export const miniChatDragPosition = ref(null)
/** Сообщения текущего мини-чата (null — ещё не инициализировали welcome). */
export const miniChatMessages = ref(hydrated.messages)
/** server session_id (UUID) для продолжения диалога после закрытия / F5. */
export const miniChatSessionId = ref(hydrated.sessionId)
/** Идёт генерация ответа — переживает закрытие панели. */
export const miniChatLoading = ref(false)
/**
 * Ожидаем ответ ассистента (в т.ч. после F5): показываем «генерацию» и дотягиваем с сервера.
 * Гидрация: true, если прервали стрим обновлением страницы.
 */
export const miniChatPending = ref(hydrated.pending)

let persistTimer = null

function persist(immediate = false) {
  const flush = () => {
    persistTimer = null
    writePersistedState(
      miniChatSessionId.value,
      miniChatMessages.value,
      miniChatPending.value || miniChatLoading.value,
    )
  }
  if (immediate) {
    if (persistTimer) {
      clearTimeout(persistTimer)
      persistTimer = null
    }
    flush()
    return
  }
  if (persistTimer) clearTimeout(persistTimer)
  persistTimer = setTimeout(flush, 150)
}

function onPageHide() {
  persist(true)
}

if (typeof window !== 'undefined') {
  window.addEventListener('pagehide', onPageHide)
  window.addEventListener('beforeunload', onPageHide)
}

export function openOllamaMiniChat() {
  miniChatPanelMounted.value = true
  isOllamaMiniChatOpen.value = true
}

export function setMiniChatLoading(value) {
  miniChatLoading.value = Boolean(value)
  if (value) {
    miniChatPending.value = true
  }
  persist(true)
}

export function setMiniChatPending(value) {
  miniChatPending.value = Boolean(value)
  persist(true)
}

export function closeOllamaMiniChat() {
  isOllamaMiniChatOpen.value = false
  persist(true)
}

export function dismissOllamaMiniChat() {
  isOllamaMiniChatOpen.value = false
  persist(true)
}

export function setMiniChatDragPosition(position) {
  miniChatDragPosition.value = position
}

export function setMiniChatMessages(messages) {
  miniChatMessages.value = messages
  persist(false)
}

export function setMiniChatSessionId(sessionId) {
  miniChatSessionId.value = isUuid(sessionId) ? String(sessionId) : null
  persist(true)
}

export function clearMiniChatState() {
  miniChatMessages.value = null
  miniChatSessionId.value = null
  miniChatLoading.value = false
  miniChatPending.value = false
  if (persistTimer) {
    clearTimeout(persistTimer)
    persistTimer = null
  }
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* ignore */
  }
}

/** Точка входа из меню приложений. */
export function openOllamaMiniChatWidget() {
  openOllamaMiniChat()
}
