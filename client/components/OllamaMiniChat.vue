<template>
  <div class="ollama-mini-chat" :class="{ 'ollama-mini-chat--compact': compact }">
    <div class="ollama-mini-chat__status" :class="{ 'is-online': ollamaOnline }">
      <span class="ollama-mini-chat__status-dot" aria-hidden="true" />
      <span class="ollama-mini-chat__status-text">{{ statusLabel }}</span>
    </div>

    <div ref="messagesRef" class="ollama-mini-chat__messages">
      <HubMessage
        v-for="msg in messages"
        :key="msg.id"
        :message="msg"
        :module-config="moduleConfig"
      />
      <div v-if="loading" class="ollama-mini-chat__typing">
        {{ t('ai_assistant.generating') }}
      </div>
    </div>

    <div class="ollama-mini-chat__composer">
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

    <button type="button" class="ollama-mini-chat__hub-link" @click="openFullHub">
      {{ t('ai_assistant.apps.openHub') }}
    </button>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Send } from 'lucide-vue-next'
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

defineProps({
  compact: { type: Boolean, default: false },
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
const { status: ollamaStatus, statusLabel } = useOllamaStatus({ autoPoll: true })
const ollamaOnline = computed(() => !!ollamaStatus.value.available)

const messagesRef = ref(null)
const inputRef = ref(null)
const chatInput = ref('')
const chatLoading = ref(false)
const sessionId = ref(null)
const loading = computed(() => chatLoading.value)

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

async function sendMessage() {
  const text = chatInput.value.trim()
  if (!text || chatLoading.value) return

  addUserMessage(text)
  chatInput.value = ''
  chatLoading.value = true
  scrollToBottom()

  try {
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
      null,
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

  // Компактный режим: без neural-connector и с ровной сеткой отступов
  &--compact {
    :deep(.neural-message) {
      display: flex;
      align-items: flex-start;
      gap: 0.625rem;
      padding: 0.5rem 0;
      margin: 0;

      &:hover {
        background: transparent;
      }
    }

    :deep(.message-connector) {
      display: none;
    }

    :deep(.message-avatar) {
      width: 32px;
      height: 32px;
      margin-top: 0.125rem;
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
      padding: 0.625rem 0.75rem;
      border-radius: 10px;

      &::before,
      &::after {
        display: none;
      }
    }

    :deep(.message-header) {
      gap: 0.375rem;
      margin-bottom: 0.375rem;
      flex-wrap: wrap;
    }

    :deep(.message-author) {
      font-size: 0.8125rem;
      letter-spacing: 0;
    }

    :deep(.message-time) {
      font-size: 0.75rem;
    }

    :deep(.message-content) {
      font-size: 0.875rem;
      line-height: 1.45;
    }
  }
}

.ollama-mini-chat__status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.875rem;
  border-bottom: 1px solid var(--ai-border, var(--color-border));
  font-size: 0.8125rem;
  color: var(--ai-text-secondary, var(--color-secondary-text));
  flex-shrink: 0;
}

.ollama-mini-chat__status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-danger, #dc3545);
  flex-shrink: 0;
}

.ollama-mini-chat__status.is-online .ollama-mini-chat__status-dot {
  background: var(--ai-neon-green, #22ff8d);
  box-shadow: 0 0 8px var(--ai-neon-green, #22ff8d);
}

.ollama-mini-chat__messages {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 0.75rem 0.875rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.ollama-mini-chat__typing {
  padding: 0.25rem 0;
  font-size: 0.8125rem;
  color: var(--ai-text-secondary, var(--color-secondary-text));
}

.ollama-mini-chat__composer {
  display: flex;
  gap: 0.5rem;
  align-items: flex-end;
  padding: 0.75rem 0.875rem;
  border-top: 1px solid var(--ai-border, var(--color-border));
  background: var(--ai-bg-secondary, var(--color-primary-background));
  flex-shrink: 0;
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
  color: #050508;
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
