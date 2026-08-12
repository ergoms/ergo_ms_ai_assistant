/**
 * Состояние плавающего мини-чата AI-ассистента (виджет поддержки).
 * Открытие — только из меню приложений.
 *
 * Переживание закрытия панели — module-level refs.
 * Переживание F5 — localStorage: UUID сессии + снимок сообщений + pending (не числовой pk).
 */

import { ref } from 'vue'

import { DEFAULT_CHAT_PROFILE_ID } from './chatProfiles.js'

const DEFAULT_STORAGE_KEY = 'ai_assistant.miniChat.v1'
/** Серверные сессии мини-чата — не попадают в список хаба (module=chat). */
export const MINI_CHAT_MODULE = 'mini_chat'
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

/** Активный chat-профиль мини-чата (default или id хоста). */
export const activeMiniChatProfileId = ref(DEFAULT_CHAT_PROFILE_ID)

let activeStorageKey = DEFAULT_STORAGE_KEY

function resolveStorageKey(profileId, storageKey) {
  if (storageKey) return String(storageKey)
  if (!profileId || profileId === DEFAULT_CHAT_PROFILE_ID) return DEFAULT_STORAGE_KEY
  return `ai_assistant.miniChat.${profileId}.v1`
}

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
    interrupted: Boolean(msg.interrupted),
  }))
}

function normalizeMessages(messages) {
  if (!Array.isArray(messages) || !messages.length) return null
  return messages.map((msg) => ({
    ...msg,
    streaming: false,
    interrupted: Boolean(msg.interrupted),
    timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
  }))
}

function hasUserMessages(messages) {
  return Array.isArray(messages) && messages.some((msg) => msg?.type === 'user')
}

/** Тексты replyInterrupted (ru/en/fr) — старые снимки без флага interrupted. */
const INTERRUPT_PLACEHOLDER_TEXTS = new Set([
  'Не удалось получить ответ. Отправьте сообщение ещё раз.',
  'Could not get a reply. Please send your message again.',
  'Impossible d’obtenir une réponse. Renvoyez votre message.',
])

/** Локальная заглушка после неудачного/раннего recovery — не финальный ответ. */
export function isInterruptedPlaceholder(msg) {
  if (!msg || msg.type !== 'assistant') return false
  if (msg.interrupted) return true
  return INTERRUPT_PLACEHOLDER_TEXTS.has(String(msg.content || '').trim())
}

/** Убрать хвостовые заглушки «не удалось получить ответ» перед показом typing. */
export function stripTrailingInterrupted(messages) {
  if (!Array.isArray(messages) || !messages.length) return messages || []
  const next = [...messages]
  while (next.length && isInterruptedPlaceholder(next[next.length - 1])) {
    next.pop()
  }
  return next
}

/** Последнее сообщение — от пользователя, пустой/стримящийся ответ или локальный «прервано». */
export function isAwaitingAssistantReply(messages) {
  if (!Array.isArray(messages) || !messages.length) return false
  const last = messages[messages.length - 1]
  if (!last) return false
  if (last.type === 'user') return true
  if (last.type === 'assistant') {
    // Локальная заглушка после F5 — сервер ещё может дописать настоящий ответ
    if (isInterruptedPlaceholder(last)) return true
    if (last.streaming) return true
    return !String(last.content || '').trim()
  }
  return false
}

/** Серверная история полнее локального снимка (после F5 во время/после генерации). */
export function shouldPreferServerMessages(localMessages, serverMessages) {
  if (!serverMessages?.length) return false
  if (!localMessages?.length) return true

  const localLast = localMessages[localMessages.length - 1]
  const serverLast = serverMessages[serverMessages.length - 1]
  // Локальная заглушка «прервано» — всегда уступаем реальному ответу с сервера
  if (
    isInterruptedPlaceholder(localLast)
    && serverLast?.type === 'assistant'
    && String(serverLast.content || '').trim()
    && !isInterruptedPlaceholder(serverLast)
  ) {
    return true
  }

  if (serverMessages.length > localMessages.length) return true
  if (serverMessages.length < localMessages.length) return false

  const localAwaiting = isAwaitingAssistantReply(localMessages)
  const serverAwaiting = isAwaitingAssistantReply(serverMessages)
  if (localAwaiting && !serverAwaiting) return true
  if (!localAwaiting && serverAwaiting) return false

  const localLen = String(localLast?.content || '').length
  const serverLen = String(serverLast?.content || '').length
  return serverLen > localLen
}

function readPersistedState(storageKey = activeStorageKey) {
  try {
    const raw = localStorage.getItem(storageKey)
    if (!raw) return { sessionId: null, messages: null, pending: false }
    const parsed = JSON.parse(raw)
    const sessionId = isUuid(parsed?.sessionId) ? String(parsed.sessionId) : null
    // Заглушку «не удалось получить ответ» не гидратируем — после F5 нужен typing, не ошибка
    let messages = normalizeMessages(parsed?.messages)
    if (messages?.length) {
      const cleaned = stripTrailingInterrupted(messages)
      messages = cleaned.length ? cleaned : null
    }
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
      localStorage.removeItem(activeStorageKey)
      return
    }
    localStorage.setItem(activeStorageKey, JSON.stringify({
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

// После F5 во время/ожидании генерации сразу открываем панель с typing.
if (hydrated.pending || isAwaitingAssistantReply(hydrated.messages)) {
  miniChatPanelMounted.value = true
  isOllamaMiniChatOpen.value = true
  miniChatLoading.value = true
  miniChatPending.value = true
}

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
  // F5 во время стрима/ожидания: pending должен пережить перезагрузку.
  // Нельзя оставлять в storage хвостовую заглушку interrupted — после F5 нужен typing.
  if (miniChatLoading.value || isAwaitingAssistantReply(miniChatMessages.value)) {
    miniChatPending.value = true
  }
  if (Array.isArray(miniChatMessages.value) && miniChatMessages.value.length) {
    const cleaned = stripTrailingInterrupted(miniChatMessages.value)
    if (cleaned.length !== miniChatMessages.value.length) {
      miniChatMessages.value = cleaned
    }
  }
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
  const next = Boolean(value)
  miniChatLoading.value = next
  // Включаем pending вместе с loading; выключаем только явно через setMiniChatPending(false)
  // (на первом SSE-chunk loading гасят отдельно, pending снимает onDone / sendMessage).
  if (next) {
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
    localStorage.removeItem(activeStorageKey)
  } catch {
    /* ignore */
  }
}

/**
 * Переключить профиль мини-чата и гидратировать его storage.
 * @param {string} profileId
 * @param {{ storageKey?: string }} [options]
 */
export function switchMiniChatProfile(profileId, options = {}) {
  const nextId = String(profileId || DEFAULT_CHAT_PROFILE_ID).trim() || DEFAULT_CHAT_PROFILE_ID
  const nextKey = resolveStorageKey(nextId, options.storageKey)
  if (nextId === activeMiniChatProfileId.value && nextKey === activeStorageKey) {
    return
  }
  // Сохранить текущий профиль перед переключением
  persist(true)
  activeMiniChatProfileId.value = nextId
  activeStorageKey = nextKey
  const hydratedProfile = readPersistedState(nextKey)
  miniChatMessages.value = hydratedProfile.messages
  miniChatSessionId.value = hydratedProfile.sessionId
  miniChatLoading.value = Boolean(hydratedProfile.pending)
  miniChatPending.value = Boolean(hydratedProfile.pending)
}

/**
 * Открыть мини-чат с указанным профилем (default или хост-модуль).
 * @param {string} [profileId]
 * @param {{ storageKey?: string }} [options]
 */
export function openMiniChat(profileId = DEFAULT_CHAT_PROFILE_ID, options = {}) {
  switchMiniChatProfile(profileId, options)
  openOllamaMiniChat()
}

/** Точка входа из меню приложений (профиль default). */
export function openOllamaMiniChatWidget() {
  openMiniChat(DEFAULT_CHAT_PROFILE_ID)
}
