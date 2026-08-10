<template>
  <div class="ollama-mini-chat" :class="{ 'ollama-mini-chat--compact': compact }">
    <div ref="messagesRef" class="ollama-mini-chat__messages">
      <HubMessage
        v-for="msg in messages"
        :key="msg.id"
        :message="msg"
        :module-config="moduleConfig"
      />
      <div
        v-if="showTyping"
        :key="typingAnimKey"
        class="ollama-mini-chat__typing"
        role="status"
        aria-live="polite"
      >
        <div
          class="ollama-mini-chat__typing-avatar"
          :style="{ '--typing-color': moduleConfig?.color || AI_ACCENT_CSS }"
        >
          <component :is="moduleConfig?.icon" :size="16" />
          <span class="ollama-mini-chat__typing-pulse" aria-hidden="true" />
        </div>
        <div class="ollama-mini-chat__typing-body">
          <span class="ollama-mini-chat__typing-label">{{ t('ai_assistant.generating') }}</span>
          <div class="ollama-mini-chat__typing-dots" data-ergo-motion-safe="pulse" aria-hidden="true">
            <span /><span /><span />
          </div>
        </div>
      </div>
    </div>

    <div class="ollama-mini-chat__composer">
      <div v-if="canShowSuggestions" class="ollama-mini-chat__suggestions-wrap">
        <button
          type="button"
          class="ollama-mini-chat__suggestions-toggle"
          :aria-expanded="suggestionsExpanded"
          @click="suggestionsExpanded = !suggestionsExpanded"
        >
          <ChevronDown
            :size="14"
            class="ollama-mini-chat__suggestions-chevron"
            :class="{ 'is-expanded': suggestionsExpanded }"
          />
          <span>
            {{
              suggestionsExpanded
                ? t('ai_assistant.apps.hideSuggestions')
                : t('ai_assistant.apps.showSuggestions')
            }}
          </span>
        </button>

        <div v-show="suggestionsExpanded" class="ollama-mini-chat__suggestions">
          <button
            v-for="s in moduleConfig?.suggestions"
            :key="s"
            type="button"
            class="ollama-mini-chat__suggestion"
            :disabled="loading"
            @click="sendMessage(s)"
          >
            <Zap :size="14" />
            <span>{{ s }}</span>
          </button>
        </div>
      </div>

      <div class="ollama-mini-chat__composer-row">
        <textarea
          ref="inputRef"
          v-model="chatInput"
          class="ollama-mini-chat__input"
          rows="1"
          :placeholder="moduleConfig?.settings?.placeholder"
          :disabled="loading"
          @keydown.enter.exact.prevent="sendMessage"
        />
        <button
          type="button"
          class="ollama-mini-chat__send"
          :disabled="!chatInput.trim() || loading"
          :aria-label="t('ai_assistant.apps.send')"
          @click="sendMessage"
        >
          <Send :size="18" />
        </button>
      </div>
    </div>

    <button type="button" class="ollama-mini-chat__hub-link" @click="openFullHub">
      {{ t('ai_assistant.apps.openHub') }}
    </button>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ChevronDown, Send, Zap } from 'lucide-vue-next'
import {
  BOOTSTRAP_MASK_HIDDEN_EVENT,
  isBootstrapMaskActive,
} from '@/js/bootstrapMask.js'
import { useAppI18n } from '@/i18n/useAppI18n.js'
import { logError } from '@/js/utils/logError.js'
import {
  clearMiniChatState,
  dismissOllamaMiniChat,
  isAwaitingAssistantReply,
  MINI_CHAT_MODULE,
  miniChatLoading,
  miniChatMessages,
  miniChatPending,
  miniChatSessionId,
  setMiniChatLoading,
  setMiniChatMessages,
  setMiniChatPending,
  setMiniChatSessionId,
  shouldPreferServerMessages,
  stripTrailingInterrupted,
} from '../js/ollamaMiniChatStore.js'
import { recoverPendingReply as recoverPendingReplyShared } from '../js/composables/usePendingReplyRecovery.js'
import { isPageUnloading } from '../js/streamDisconnect.js'
import { AI_ACCENT_CSS } from '../js/themeAccent.js'
import { getModuleById } from '../modules/index.js'
import { ragClient } from '../rag/js/rag-client.js'
import {
  mapApiMessages,
  nextLocalMessageId,
  resetLocalMessageIds,
  useMessageHistory,
} from '../js/composables/useAssistantStream.js'
import { useOllamaStatus } from '../js/composables/useOllamaStatus.js'
import HubMessage from './HubMessage.vue'

const props = defineProps({
  compact: { type: Boolean, default: false },
  ollamaStatus: { type: Object, default: null },
})

const emit = defineEmits(['close'])
const { t } = useAppI18n()
const router = useRouter()

const moduleConfig = computed(() => getModuleById('chat'))
const {
  messages,
  setMessages,
  addUserMessage,
  appendStreamChunk,
  finishAssistantStream,
  setAssistantError,
} = useMessageHistory()
const internalOllama = useOllamaStatus({ autoPoll: props.ollamaStatus == null })
const ollamaStatus = computed(() => props.ollamaStatus ?? internalOllama.status.value)

const messagesRef = ref(null)
const inputRef = ref(null)
const chatInput = ref('')
const sessionId = ref(miniChatSessionId.value)
/** Инкремент отменяет колбэки активного стрима (очистка чата / новый запрос). */
let streamGeneration = 0
/** Remount typing после снятия app-bootstrapping — иначе CSS infinite animation может не стартовать. */
const typingAnimKey = ref(0)
const loading = computed(() => miniChatLoading.value || miniChatPending.value)
/**
 * Индикатор «генерации» — как loading в HubChatPanel.
 * Не дублируем, когда в HubMessage уже идёт текст со streaming-курсором.
 */
const showTyping = computed(() => {
  const last = messages.value.at(-1)
  const streamingWithText = Boolean(
    last?.type === 'assistant'
    && (last?.streaming || last?.isStreaming)
    && String(last?.content || '').trim(),
  )
  if (streamingWithText) return false
  if (loading.value) return true
  return Boolean(
    last?.type === 'assistant'
    && (last?.streaming || last?.isStreaming)
    && !String(last?.content || '').trim(),
  )
})
const canShowSuggestions = computed(() => (moduleConfig.value?.suggestions?.length ?? 0) > 0)
const suggestionsExpanded = ref(false)

function bumpTypingAnimation() {
  if (!showTyping.value) return
  typingAnimKey.value += 1
}

function scheduleTypingAnimRestart() {
  // Двойной rAF — как hideBootstrapMask в App.vue: после снятия маски.
  requestAnimationFrame(() => {
    requestAnimationFrame(bumpTypingAnimation)
  })
}

function onBootstrapMaskHidden() {
  scheduleTypingAnimRestart()
}

function bindBootstrapTypingRestart() {
  if (typeof window === 'undefined') return
  if (isBootstrapMaskActive()) {
    window.addEventListener(BOOTSTRAP_MASK_HIDDEN_EVENT, onBootstrapMaskHidden, { once: true })
    return
  }
  scheduleTypingAnimRestart()
}

function initWelcome() {
  resetLocalMessageIds(1)
  setMessages([{
    id: 1,
    type: 'assistant',
    content: moduleConfig.value?.settings?.welcomeMessage || t('ai_assistant.modules.chat.welcome'),
    timestamp: new Date(),
  }])
  resetLocalMessageIds(2)
}

function syncLocalMessageIds(list) {
  const numericIds = (list || [])
    .map((msg) => Number(msg.id))
    .filter((id) => Number.isFinite(id) && id > 0)
  resetLocalMessageIds(numericIds.length ? Math.max(...numericIds) + 1 : 1)
}

function sanitizeChatMessages(list) {
  return (list || []).filter((msg) => {
    const text = String(msg?.content || '').trim()
    if (text) return true
    // Пустой пузырь без текста — битый снимок после обрыва SSE
    if (msg?.type === 'user') return false
    if (msg?.type === 'assistant' && !msg?.streaming && !msg?.isStreaming) return false
    return true
  })
}

function restoreSavedChat() {
  // Старые F5-заглушки не показываем — вместо них typing + recovery
  const saved = stripTrailingInterrupted(sanitizeChatMessages(miniChatMessages.value))
  if (!saved?.length) {
    return false
  }
  syncLocalMessageIds(saved)
  setMessages(saved.map((msg) => ({
    ...msg,
    streaming: false,
    interrupted: false,
    timestamp: msg.timestamp instanceof Date ? msg.timestamp : new Date(msg.timestamp || Date.now()),
  })))
  sessionId.value = miniChatSessionId.value
  setMiniChatMessages(messages.value)
  return true
}

function applyMappedMessages(mapped, persistedSessionId, sessionMeta = null) {
  const clean = sanitizeChatMessages(mapped)
  if (!clean?.length) return false
  syncLocalMessageIds(clean)
  setMessages(clean)
  const nextSessionId = sessionMeta?.id || persistedSessionId
  sessionId.value = nextSessionId
  setMiniChatSessionId(nextSessionId)
  setMiniChatMessages(clean)
  return true
}

async function fetchSessionMessages(persistedSessionId) {
  const result = await ragClient.getChatSession(persistedSessionId)
  if (!result.success) {
    if (result.status === 404) {
      sessionId.value = null
      clearMiniChatState()
    }
    return null
  }
  if (!result.messages?.length) {
    return { mapped: [], session: result.session, status: result.status }
  }
  return {
    mapped: mapApiMessages(result.messages),
    session: result.session,
    status: result.status,
  }
}

async function restoreChatFromServer(persistedSessionId, { force = false } = {}) {
  const fetched = await fetchSessionMessages(persistedSessionId)
  if (!fetched) return false
  if (!fetched.mapped.length) return false
  if (!force && !shouldPreferServerMessages(messages.value, fetched.mapped)) {
    return true
  }
  return applyMappedMessages(fetched.mapped, persistedSessionId, fetched.session)
}

function markReplyInterrupted() {
  const text = t('ai_assistant.replyInterrupted')
  const last = messages.value.at(-1)
  if (last?.type === 'assistant' && (last.interrupted || !String(last.content || '').trim())) {
    last.content = text
    last.streaming = false
    last.isStreaming = false
    last.interrupted = true
    setMiniChatMessages(messages.value)
    return
  }
  if (last?.type === 'user') {
    // Без префикса «Ошибка:» — обычная подсказка повторить отправку
    messages.value.push({
      id: nextLocalMessageId(),
      type: 'assistant',
      content: text,
      timestamp: new Date(),
      interrupted: true,
    })
    setMiniChatMessages(messages.value)
  }
}

/** После F5 до preparing sessionId может не попасть в storage — ищем свежую mini_chat сессию. */
async function resolveMiniChatSessionId() {
  const listed = await ragClient.getChatSessions(MINI_CHAT_MODULE)
  if (!listed?.success || !listed.sessions?.length) {
    return null
  }
  const localUsers = messages.value.filter((msg) => msg?.type === 'user')
  const lastUserText = String(localUsers.at(-1)?.content || '').trim()
  // API: ordering=-updated_at — сначала свежие
  const candidates = listed.sessions.slice(0, 5)

  for (const row of candidates) {
    const id = row?.id
    if (!id) continue
    const fetched = await ragClient.getChatSession(id)
    if (!fetched?.success) continue
    const mapped = mapApiMessages(fetched.messages || [])
    const serverUsers = mapped.filter((msg) => msg?.type === 'user')
    const serverLastUser = String(serverUsers.at(-1)?.content || '').trim()
    if (lastUserText && serverLastUser && lastUserText === serverLastUser) {
      applySessionId(id)
      return id
    }
  }

  // Fallback: самая свежая mini_chat
  const newest = candidates[0]?.id
  if (newest) {
    applySessionId(newest)
  }
  return newest || null
}

async function recoverPendingReply(persistedSessionId) {
  const ok = await recoverPendingReplyShared({
    sessionId: persistedSessionId,
    getLocalMessages: () => messages.value,
    applyMessages: (mapped) => {
      const sid = miniChatSessionId.value || persistedSessionId
      applyMappedMessages(mapped, sid)
    },
    setPending: (pending) => {
      setMiniChatPending(pending)
      setMiniChatLoading(pending)
    },
    resolveSessionId: resolveMiniChatSessionId,
    onInterrupted: markReplyInterrupted,
  })
  scrollToBottom()
  scheduleTypingAnimRestart()
  return ok
}

function applySessionId(nextSessionId) {
  if (!nextSessionId) return
  sessionId.value = nextSessionId
  setMiniChatSessionId(nextSessionId)
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

function clearChat() {
  streamGeneration += 1
  chatInput.value = ''
  sessionId.value = null
  setMiniChatLoading(false)
  setMiniChatPending(false)
  clearMiniChatState()
  initWelcome()
  scrollToBottom()
  nextTick(() => inputRef.value?.focus())
}

async function sendMessage(prefilled) {
  const text = (typeof prefilled === 'string' ? prefilled : chatInput.value).trim()
  if (!text || miniChatLoading.value || miniChatPending.value) return

  const requestId = ++streamGeneration
  addUserMessage(text)
  chatInput.value = ''
  // Как на hub: typing сразу от loading, пузырь — с первого SSE-chunk
  setMiniChatLoading(true)
  scheduleTypingAnimRestart()
  scrollToBottom()

  try {
    const ollamaConfig = ollamaStatus.value.model
      ? { model: ollamaStatus.value.model }
      : null

    const streamResult = await ragClient.sendMessageStream(
      text,
      (chunk) => {
        if (requestId !== streamGeneration) return
        // Первый токен: гасим только loading (typing → курсор). pending держим до done —
        // иначе после F5 индикатор и recovery пропадают.
        if (miniChatLoading.value) {
          miniChatLoading.value = false
        }
        appendStreamChunk(chunk)
        scrollToBottom()
      },
      (fullResponse, metadata) => {
        if (requestId !== streamGeneration) return
        finishAssistantStream(fullResponse, metadata || {})
        applySessionId(metadata?.session_id)
        setMiniChatPending(false)
        setMiniChatLoading(false)
        scrollToBottom()
      },
      (errorMsg) => {
        if (requestId !== streamGeneration) return
        setAssistantError(errorMsg)
        setMiniChatPending(false)
        setMiniChatLoading(false)
        scrollToBottom()
      },
      ollamaConfig,
      sessionId.value,
      // Не module=chat: иначе сессии мини-чата засоряют список хаба
      MINI_CHAT_MODULE,
      null,
      false,
      (preparingSessionId) => {
        if (requestId !== streamGeneration) return
        applySessionId(preparingSessionId)
      },
    )
    // Обрыв SSE: fetch часто abort'ится ДО pagehide — нельзя писать «не удалось» здесь,
    // иначе после F5 в localStorage уже ошибка вместо pending+typing.
    if (streamResult?.disconnected && requestId === streamGeneration) {
      setMiniChatPending(true)
      setMiniChatLoading(true)
      if (isPageUnloading()) {
        return
      }
      scheduleTypingAnimRestart()
      await recoverPendingReply(sessionId.value || null)
    }
  } catch (error) {
    if (requestId !== streamGeneration) return
    logError('Ошибка мини-чата Ollama', error)
    setAssistantError(error.message || t('ai_assistant.chatCreateFail'))
    setMiniChatPending(false)
    setMiniChatLoading(false)
  }
}

defineExpose({ clearChat })

async function openFullHub() {
  dismissOllamaMiniChat()
  emit('close')
  // Хаб — отдельный список чатов; сессию мини-чата туда не тащим
  await router.push({ name: 'AIAssistantHub', query: { module: 'chat' } })
}

watch(messages, (value) => {
  setMiniChatMessages(value)
}, { deep: true })

watch(sessionId, (value) => {
  // Не затираем persistence при временном null — только явный clearMiniChatState
  if (value) {
    setMiniChatSessionId(value)
  }
})

watch(showTyping, (visible) => {
  if (visible) {
    scheduleTypingAnimRestart()
    scrollToBottom()
  }
})

onMounted(async () => {
  bindBootstrapTypingRestart()
  // История мини-чата живёт в localStorage; сервер — только для LLM/recovery, не список хаба
  const hadLocalSnapshot = restoreSavedChat()
  if (!hadLocalSnapshot) {
    const persistedSessionId = miniChatSessionId.value
    if (persistedSessionId) {
      try {
        const restored = await restoreChatFromServer(persistedSessionId, { force: true })
        if (!restored) {
          initWelcome()
        }
      } catch (error) {
        logError('Ошибка восстановления мини-чата', error)
        initWelcome()
      }
    } else {
      initWelcome()
    }
  }

  // Ещё раз снять заглушку, если успела попасть в messages
  const withoutInterrupted = stripTrailingInterrupted(messages.value)
  if (withoutInterrupted.length !== messages.value.length) {
    setMessages(withoutInterrupted)
    setMiniChatMessages(withoutInterrupted)
  }

  const last = messages.value.at(-1)
  const stuckEmpty = Boolean(
    last
    && !String(last.content || '').trim()
    && !(last.streaming || last.isStreaming),
  )
  const awaiting = isAwaitingAssistantReply(messages.value)

  // Пустой битый пузырь — сброс; при ожидании ответа loading не трогаем
  if (stuckEmpty && !awaiting) {
    setMiniChatPending(false)
    setMiniChatLoading(false)
  } else if (!hadLocalSnapshot && !messages.value.length) {
    setMiniChatPending(false)
    setMiniChatLoading(false)
  }

  scrollToBottom()
  nextTick(() => inputRef.value?.focus())

  const activeSessionId = miniChatSessionId.value || sessionId.value
  const needsRecovery = Boolean(
    miniChatPending.value || miniChatLoading.value || awaiting,
  )

  if (needsRecovery) {
    // Пока идёт recovery — только typing, без текста ошибки
    setMiniChatPending(true)
    setMiniChatLoading(true)
    scheduleTypingAnimRestart()
    await recoverPendingReply(activeSessionId)
    return
  }

  if (!activeSessionId && (miniChatPending.value || miniChatLoading.value) && !awaiting) {
    setMiniChatPending(false)
    setMiniChatLoading(false)
  }
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener(BOOTSTRAP_MASK_HIDDEN_EVENT, onBootstrapMaskHidden)
  }
})
</script>

<style scoped lang="scss">
.ollama-mini-chat {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: var(--ai-bg-primary, var(--color-background));
  color: var(--ai-text-primary, var(--color-primary-text));

  // Компактный режим: без neural-connector, разделение вопрос/ответ
  &--compact {
    :deep(.neural-message) {
      display: flex;
      align-items: flex-start;
      gap: 0.5rem;
      padding: 0.35rem 0;
      margin: 0;
      max-width: 92%;

      &:hover {
        background: transparent;
      }
    }

    :deep(.neural-message--assistant) {
      align-self: flex-start;
    }

    :deep(.neural-message--user) {
      flex-direction: row-reverse;
      align-self: flex-end;
      margin-left: auto;

      .message-body {
        background: color-mix(in srgb, var(--ai-accent, #d0322d) 14%, var(--ai-bg-secondary, #18181a));
        border: 1px solid color-mix(in srgb, var(--ai-accent, #d0322d) 28%, transparent);
      }

      .message-time {
        text-align: right;
      }
    }

    :deep(.message-connector) {
      display: none;
    }

    :deep(.message-avatar) {
      width: 28px;
      height: 28px;
      margin-top: 0.125rem;
      flex-shrink: 0;
    }

    :deep(.avatar-core) {
      inset: 2px;
      border-radius: 8px;
    }

    :deep(.avatar-ring) {
      border-radius: 10px;
      border-width: 1.5px;
    }

    :deep(.message-body) {
      flex: 1 1 auto;
      min-width: 0;
      max-width: none;
      padding: 0.5rem 0.75rem;
      border-radius: 12px;
      border: 1px solid var(--ai-border, var(--color-border));
      background: var(--ai-bg-elevated, var(--color-hover-background));

      &::before,
      &::after {
        display: none;
      }
    }

    :deep(.message-header) {
      gap: 0.375rem;
      margin-bottom: 0.25rem;
      flex-wrap: wrap;
    }

    :deep(.message-author) {
      font-size: 0.8125rem;
      letter-spacing: 0;
    }

    :deep(.message-time),
    :deep(.message-meta-sep) {
      font-size: 0.6875rem;
      color: var(--ai-text-secondary, var(--color-secondary-text));
    }

    :deep(.message-processing-time) {
      font-size: 0.6875rem;
      color: var(--ai-accent, var(--color-accent));
      background: color-mix(in srgb, var(--ai-accent, var(--color-accent)) 12%, transparent);
      border-color: color-mix(in srgb, var(--ai-accent, var(--color-accent)) 28%, transparent);
    }

    :deep(.message-content) {
      font-size: 0.875rem;
      line-height: 1.45;
    }
  }
}

.ollama-mini-chat__messages {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 0.75rem 0.875rem;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.ollama-mini-chat__typing {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.35rem 0;
}

.ollama-mini-chat__typing-avatar {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border-radius: 8px;
  color: #fff;
  background: linear-gradient(
    135deg,
    var(--typing-color, var(--ai-accent, #d0322d)),
    color-mix(in srgb, var(--typing-color, var(--ai-accent, #d0322d)) 55%, #000)
  );
}

.ollama-mini-chat__typing-pulse {
  position: absolute;
  inset: -4px;
  border: 1px solid color-mix(in srgb, var(--typing-color, var(--ai-accent, #d0322d)) 55%, transparent);
  border-radius: 10px;
  animation: ollama-typing-pulse 1.8s ease-out infinite;

  @media (prefers-reduced-motion: reduce) {
    animation: none;
    opacity: 0.35;
  }
}

html[data-ergo-motion='reduce'] .ollama-mini-chat__typing-pulse {
  animation: none;
  opacity: 0.35;
}

.ollama-mini-chat__typing-body {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 0;
  padding: 0.35rem 0;
}

.ollama-mini-chat__typing-label {
  font-size: 0.8125rem;
  line-height: 1.2;
  color: var(--ai-text-secondary, var(--color-secondary-text));
}

.ollama-mini-chat__typing-dots {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 14px;

  span {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--ai-accent, var(--color-accent));
    animation: ollama-typing-bounce 1.2s ease-in-out infinite;

    &:nth-child(2) {
      animation-delay: 0.15s;
    }

    &:nth-child(3) {
      animation-delay: 0.3s;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    span {
      animation: none;
      opacity: 0.55;
    }
  }
}

/* Не глушим bounce у span правилом animation:none — иначе перекрывает
   data-ergo-motion-safe="pulse" на контейнере. При reduce контейнер пульсирует. */
html[data-ergo-motion='reduce'] .ollama-mini-chat__typing-dots span {
  opacity: 0.55;
}

@keyframes ollama-typing-pulse {
  0% {
    transform: scale(0.85);
    opacity: 0.75;
  }

  100% {
    transform: scale(1.25);
    opacity: 0;
  }
}

@keyframes ollama-typing-bounce {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.35;
  }

  30% {
    transform: translateY(-4px);
    opacity: 1;
  }
}

.ollama-mini-chat__composer {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.75rem 0.875rem;
  border-top: 1px solid var(--ai-border, var(--color-border));
  background: var(--ai-bg-secondary, var(--color-primary-background));
  flex-shrink: 0;
}

.ollama-mini-chat__composer-row {
  display: flex;
  gap: 0.5rem;
  align-items: flex-end;
  width: 100%;
}

.ollama-mini-chat__suggestions-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  width: 100%;
}

.ollama-mini-chat__suggestions-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  width: 100%;
  margin: 0;
  padding: 0.375rem 0.5rem;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: color-mix(
    in srgb,
    var(--ai-text-primary, var(--color-primary-text, #c9cccf)) 78%,
    transparent
  );
  font-size: 0.8125rem;
  font-weight: 500;
  line-height: 1.2;
  text-align: left;
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease;

  &:hover {
    color: var(--ai-accent, var(--color-accent));
    background: color-mix(in srgb, var(--ai-accent, #d0322d) 6%, transparent);
  }
}

.ollama-mini-chat__suggestions-chevron {
  flex-shrink: 0;
  transition: transform 0.2s ease;

  &.is-expanded {
    transform: rotate(180deg);
  }
}

.ollama-mini-chat__suggestions {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  width: 100%;
}

.ollama-mini-chat__suggestion {
  display: inline-flex;
  align-items: flex-start;
  gap: 0.4rem;
  width: 100%;
  margin: 0;
  padding: 0.5rem 0.625rem;
  background: var(--ai-bg-tertiary, var(--color-secondary-background));
  border: 1px solid var(--ai-border, var(--color-border));
  border-radius: 10px;
  font-size: 0.8125rem;
  line-height: 1.3;
  color: var(--ai-text-primary, var(--color-primary-text));
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease, background 0.15s ease;

  svg {
    flex-shrink: 0;
    margin-top: 0.1rem;
    color: var(--ai-accent, var(--color-accent));
  }

  span {
    min-width: 0;
  }

  &:hover:not(:disabled) {
    background: color-mix(in srgb, var(--ai-accent, #d0322d) 8%, var(--ai-bg-tertiary, #222));
    border-color: color-mix(in srgb, var(--ai-accent, #d0322d) 40%, var(--ai-border, #333));
    color: var(--ai-text-primary, var(--color-primary-text));
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.ollama-mini-chat__input {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 40px;
  max-height: 96px;
  resize: none;
  border: 1px solid var(--ai-border, var(--color-border));
  border-radius: 10px;
  padding: 0.5rem 0.75rem;
  background: var(--ai-bg-tertiary, var(--color-secondary-background));
  color: var(--ai-text-primary, var(--color-primary-text));
  font: inherit;
  font-size: 0.875rem;
  line-height: 1.4;

  &::placeholder {
    color: color-mix(
      in srgb,
      var(--ai-text-primary, var(--color-primary-text, #c9cccf)) 52%,
      transparent
    );
    opacity: 1;
  }

  &:focus {
    outline: none;
    border-color: var(--ai-accent, var(--color-accent));
  }

  &:disabled {
    opacity: 0.6;
  }
}

.ollama-mini-chat__send {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 10px;
  background: var(--ai-accent, var(--color-accent));
  color: #fff;
  cursor: pointer;
  flex-shrink: 0;

  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  &:not(:disabled):hover {
    filter: brightness(1.08);
  }
}

.ollama-mini-chat__hub-link {
  border: none;
  border-top: 1px solid var(--ai-border, var(--color-border));
  background: transparent;
  color: var(--ai-accent, var(--color-accent));
  padding: 0.625rem 0.875rem;
  font-size: 0.8125rem;
  font-weight: 500;
  text-align: center;
  cursor: pointer;
  flex-shrink: 0;

  &:hover {
    background: var(--ai-bg-elevated, var(--color-hover-background));
  }
}
</style>
