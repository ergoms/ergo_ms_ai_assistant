<template>
  <AssistantChatLayout
    ref="layoutRef"
    v-model="inputMessage"
    :placeholder="selectedDocument ? 'Задайте вопрос к документу...' : 'Задайте вопрос по базе знаний...'"
    :disabled="isTyping"
    :show-empty="showSelectorEmpty"
    :typing="isTyping && !hasStreamingContent"
    :show-composer="Boolean(selectedDocument || messages.length)"
    @send="sendMessage"
  >
    <template #toolbar>
      <div class="docs-panel__toolbar">
        <button type="button" class="btn btn-sm btn-primary" @click="showUploader = true">
          <Upload :size="16" class="me-1" />
          Загрузить документ
        </button>
        <button
          v-if="selectedDocument"
          type="button"
          class="btn btn-sm btn-outline-secondary"
          @click="clearDocument"
        >
          Сбросить документ
        </button>
      </div>
      <div v-if="selectedDocument" class="docs-panel__doc-banner">
        <FileText :size="14" />
        <span class="docs-panel__doc-title">{{ selectedDocument.title }}</span>
        <span
          class="badge"
          :class="selectedDocument.is_indexed ? 'bg-success' : 'bg-warning'"
        >
          {{ selectedDocument.is_indexed ? 'Индексирован' : 'Не индексирован' }}
        </span>
      </div>
    </template>

    <template #empty>
      <DocumentSelector @document-selected="onDocumentSelected" />
    </template>

    <template #messages>
      <p v-if="!showSelectorEmpty && showEmptyState" class="text-muted text-center mb-0">
        Задайте вопрос к документу — чат сохранится после первого ответа.
      </p>
      <template v-else-if="messages.length">
        <AssistantChatMessage
          v-for="message in messages"
          :key="message.id"
          :message="normalizedMessage(message)"
          :module-config="moduleConfig"
        />
      </template>
    </template>
  </AssistantChatLayout>

  <ModalCenter
    standalone
    modal-id="docsUploadModal"
    title="Загрузка документа"
    :visible="showUploader"
    size="lg"
    @close="showUploader = false"
  >
    <DocumentUploader
      @document-uploaded="handleDocumentUploaded"
      @document-created="handleDocumentCreated"
    />
  </ModalCenter>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Upload, FileText } from 'lucide-vue-next'
import ModalCenter from '@/components/ModalCenter.vue'
import AssistantChatLayout from '../components/chat/AssistantChatLayout.vue'
import AssistantChatMessage from '../components/chat/AssistantChatMessage.vue'
import DocumentSelector from './DocumentSelector.vue'
import DocumentUploader from './DocumentUploader.vue'
import { docsClient } from './js/docs-client.js'
import { ragClient } from '../rag/js/rag-client.js'
import { mapApiMessages, nextLocalMessageId } from '../js/composables/useAssistantStream.js'
import { getModuleById } from '../modules/index.js'
import { logError } from '@/js/utils/logError.js'

const props = defineProps({
  sessionId: { type: String, default: null },
})

const emit = defineEmits(['session-created', 'draft-started'])

const moduleConfig = computed(() => getModuleById('docs'))
const messages = ref([])
const inputMessage = ref('')
const isTyping = ref(false)
const selectedDocument = ref(null)
const showUploader = ref(false)
const layoutRef = ref(null)
const ollamaChecked = ref(false)
let streamingMessageId = null

const showSelectorEmpty = computed(() => !selectedDocument.value && messages.value.length === 0)
const showEmptyState = computed(() => messages.value.length === 0 && !isTyping.value)
const hasStreamingContent = computed(() => messages.value.some((m) => m.isStreaming || m.streaming))

function normalizedMessage(message) {
  return {
    ...message,
    streaming: Boolean(message.streaming || message.isStreaming),
  }
}

function scrollToBottom() {
  layoutRef.value?.scrollToBottom()
}

function clearDocument() {
  selectedDocument.value = null
}

function onDocumentSelected(document) {
  selectedDocument.value = document
}

async function loadSession(sessionId) {
  messages.value = []
  selectedDocument.value = null
  ollamaChecked.value = false

  if (!sessionId) return

  const result = await ragClient.getChatSession(sessionId)
  if (!result.success) return

  messages.value = mapApiMessages(result.messages).map((msg) => ({
    ...msg,
    isStreaming: false,
  }))

  const docId = result.session?.metadata?.document_id
  if (docId) {
    const docResult = await docsClient.getDocument(docId)
    if (docResult.success) {
      selectedDocument.value = docResult.document
    }
  }

  scrollToBottom()
}

function reset() {
  messages.value = []
  inputMessage.value = ''
  selectedDocument.value = null
  ollamaChecked.value = false
  streamingMessageId = null
  isTyping.value = false
}

function handleDocumentUploaded(document) {
  showUploader.value = false
  selectedDocument.value = document
}

function handleDocumentCreated(document) {
  showUploader.value = false
  selectedDocument.value = document
}

async function sendMessage() {
  if (!inputMessage.value.trim() || isTyping.value) return

  if (!props.sessionId && messages.value.length === 0) {
    emit('draft-started', 'docs')
  }

  const messageText = inputMessage.value.trim()
  messages.value.push({
    id: nextLocalMessageId(),
    type: 'user',
    content: messageText,
    timestamp: new Date(),
  })
  inputMessage.value = ''
  isTyping.value = true
  scrollToBottom()

  if (!ollamaChecked.value) {
    const status = await docsClient.checkOllamaStatus(true)
    ollamaChecked.value = true

    if (!status.available) {
      isTyping.value = false
      messages.value.push({
        id: nextLocalMessageId(),
        type: 'assistant',
        content:
          `**Ollama недоступен**\n\n${status.message || 'Сервис не отвечает'}\n\n` +
          'Запустите Ollama: `ergoms ollama_framework:start-ollama`',
        timestamp: new Date(),
      })
      scrollToBottom()
      return
    }

    if (!status.embeddings) {
      messages.value.push({
        id: nextLocalMessageId(),
        type: 'assistant',
        content: 'Сервис embeddings недоступен. Ответы могут не использовать базу знаний.',
        timestamp: new Date(),
      })
    }
  }

  streamingMessageId = nextLocalMessageId()
  messages.value.push({
    id: streamingMessageId,
    type: 'assistant',
    content: '',
    timestamp: new Date(),
    isStreaming: true,
  })
  scrollToBottom()

  try {
    await docsClient.sendMessageStream(
      messageText,
      (chunk) => {
        const msg = messages.value.find((m) => m.id === streamingMessageId)
        if (msg) {
          msg.content += chunk
          scrollToBottom()
        }
      },
      (fullResponse, metadata) => {
        const msg = messages.value.find((m) => m.id === streamingMessageId)
        if (msg) {
          msg.content = fullResponse
          msg.isStreaming = false
        }
        isTyping.value = false
        streamingMessageId = null
        if (metadata?.session_id) {
          emit('session-created', { sessionId: metadata.session_id, module: 'docs' })
        }
        scrollToBottom()
      },
      (errorMsg) => {
        const msg = messages.value.find((m) => m.id === streamingMessageId)
        if (msg) {
          msg.content = `**Ошибка:** ${errorMsg}`
          msg.isStreaming = false
        }
        isTyping.value = false
        streamingMessageId = null
        scrollToBottom()
      },
      props.sessionId,
      selectedDocument.value?.id || null,
    )
  } catch (error) {
    logError('Ошибка отправки сообщения docs', error)
    const msg = messages.value.find((m) => m.id === streamingMessageId)
    if (msg) {
      msg.content = `**Ошибка:** ${error.message || 'Не удалось отправить сообщение'}`
      msg.isStreaming = false
    }
    isTyping.value = false
    streamingMessageId = null
    scrollToBottom()
  }
}

watch(
  () => props.sessionId,
  (id) => {
    if (id) {
      loadSession(id)
    } else {
      reset()
    }
  },
  { immediate: true },
)

defineExpose({ reset, loadSession })
</script>

<style lang="scss" scoped>
.docs-panel__toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.docs-panel__doc-banner {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.625rem;
  padding: 0.375rem 0.625rem;
  border-radius: 0.375rem;
  background: var(--bs-tertiary-bg, #f8f9fa);
  font-size: 0.875rem;
}

.docs-panel__doc-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
