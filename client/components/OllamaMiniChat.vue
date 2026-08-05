<template>
  <div class="ollama-mini-chat" :class="{ 'ollama-mini-chat--compact': compact }">
    <div ref="messagesRef" class="ollama-mini-chat__messages">
      <HubMessage
        v-for="msg in messages"
        :key="msg.id"
        :message="msg"
        :module-config="moduleConfig"
      />
      <div v-if="isThinking" class="ollama-mini-chat__typing" role="status" aria-live="polite">
        <div
          class="ollama-mini-chat__typing-avatar"
          :style="{ '--typing-color': moduleConfig?.color || 'var(--ai-accent, #d0322d)' }"
        >
          <component :is="moduleConfig?.icon" :size="16" />
          <span class="ollama-mini-chat__typing-pulse" aria-hidden="true" />
        </div>
        <div class="ollama-mini-chat__typing-body">
          <span class="ollama-mini-chat__typing-label">{{ t('ai_assistant.generating') }}</span>
          <div class="ollama-mini-chat__typing-dots" aria-hidden="true">
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
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ChevronDown, Send, Zap } from 'lucide-vue-next'
import { useAppI18n } from '@/i18n/useAppI18n.js'
import { logError } from '@/js/utils/logError.js'
import { dismissOllamaMiniChat } from '../js/ollamaMiniChatStore.js'
import { getModuleById } from '../modules/index.js'
import { ragClient } from '../rag/js/rag-client.js'
import {
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
const chatLoading = ref(false)
const sessionId = ref(null)
const loading = computed(() => chatLoading.value)
const isThinking = computed(() => {
  if (chatLoading.value) {
    return true
  }
  const last = messages.value.at(-1)
  return Boolean(last?.type === 'assistant' && last?.streaming && !last?.content?.trim())
})
const canShowSuggestions = computed(() => (moduleConfig.value?.suggestions?.length ?? 0) > 0)
const suggestionsExpanded = ref(false)

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

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

async function sendMessage(prefilled) {
  const text = (typeof prefilled === 'string' ? prefilled : chatInput.value).trim()
  if (!text || chatLoading.value) return

  addUserMessage(text)
  chatInput.value = ''
  chatLoading.value = true
  scrollToBottom()

  try {
    const ollamaConfig = ollamaStatus.value.model
      ? { model: ollamaStatus.value.model }
      : null

    await ragClient.sendMessageStream(
      text,
      (chunk) => {
        if (chatLoading.value) chatLoading.value = false
        appendStreamChunk(chunk)
        scrollToBottom()
      },
      (fullResponse, metadata) => {
        finishAssistantStream(fullResponse, metadata || {})
        if (metadata?.session_id) {
          sessionId.value = metadata.session_id
        }
        chatLoading.value = false
        scrollToBottom()
      },
      (errorMsg) => {
        setAssistantError(errorMsg)
        chatLoading.value = false
        scrollToBottom()
      },
      ollamaConfig,
      sessionId.value,
      'chat',
      null,
      false,
    )
  } catch (error) {
    logError('Ошибка мини-чата Ollama', error)
    setAssistantError(error.message || t('ai_assistant.chatCreateFail'))
    chatLoading.value = false
  }
}

async function openFullHub() {
  dismissOllamaMiniChat()
  emit('close')
  await router.push({ name: 'AIAssistantHub', query: { module: 'chat' } })
}

onMounted(() => {
  initWelcome()
  nextTick(() => inputRef.value?.focus())
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

    :deep(.message-time) {
      font-size: 0.6875rem;
      color: var(--ai-text-secondary, var(--color-secondary-text));
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

html[data-ergo-motion='reduce'] .ollama-mini-chat__typing-dots span {
  animation: none;
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
  color: var(--ai-text-secondary, var(--color-secondary-text));
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
  color: var(--ai-text-secondary, var(--color-secondary-text));
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
  color: inherit;
  font: inherit;
  font-size: 0.875rem;
  line-height: 1.4;

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
