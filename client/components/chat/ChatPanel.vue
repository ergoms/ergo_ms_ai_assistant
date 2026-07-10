<template>
  <AssistantChatLayout
    ref="layoutRef"
    v-model="inputText"
    :placeholder="moduleConfig?.settings?.placeholder || 'Напишите сообщение...'"
    :disabled="loading"
    :show-empty="showEmptyState"
    :typing="loading && !hasStreaming"
    show-attach
    attach-accept=".pdf,.doc,.docx,.txt"
    :attach-multiple="true"
    :files="selectedFiles"
    :suggestions="showSuggestions ? moduleConfig?.suggestions : []"
    @send="send()"
    @attach="handleFileAttach"
    @remove-file="removeFile"
    @suggestion-click="send"
  >
    <template #empty>
      <MessageSquare :size="40" class="text-muted mb-3" />
      <h3 class="h5">Начните диалог</h3>
      <p class="text-muted mb-0">
        Чат сохранится в списке после первого ответа ассистента.
      </p>
    </template>

    <template #messages>
      <AssistantChatMessage
        v-for="msg in messages"
        :key="msg.id"
        :message="msg"
        :module-config="moduleConfig"
      />
    </template>

    <template #composer-footer>
      <label v-if="selectedFiles.length" class="form-check form-check-inline mt-2 mb-0">
        <input v-model="enableVectorization" class="form-check-input" type="checkbox" />
        <span class="form-check-label">Векторизация файлов</span>
      </label>
    </template>
  </AssistantChatLayout>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { MessageSquare } from 'lucide-vue-next'
import AssistantChatLayout from './AssistantChatLayout.vue'
import AssistantChatMessage from './AssistantChatMessage.vue'
import { getModuleById } from '../../modules/index.js'
import { ragClient } from '../../rag/js/rag-client.js'
import { mapApiMessages, useMessageHistory } from '../../js/composables/useAssistantStream.js'
import { useToast } from '@/js/utils/toast.js'
import { logError } from '@/js/utils/logError.js'

const props = defineProps({
  sessionId: { type: String, default: null },
})

const emit = defineEmits(['session-created', 'draft-started'])

const toast = useToast()
const moduleConfig = computed(() => getModuleById('chat'))
const {
  messages,
  clearMessages,
  setMessages,
  addUserMessage,
  appendStreamChunk,
  finishAssistantStream,
  setAssistantError,
} = useMessageHistory()

const inputText = ref('')
const loading = ref(false)
const layoutRef = ref(null)
const selectedFiles = ref([])
const enableVectorization = ref(false)

const showEmptyState = computed(() => messages.value.length === 0 && !loading.value)
const hasStreaming = computed(() => messages.value.some((m) => m.streaming))
const showSuggestions = computed(() => messages.value.length === 0 && !loading.value)

function scrollToBottom() {
  layoutRef.value?.scrollToBottom()
}

async function loadSession(sessionId) {
  if (!sessionId) {
    clearMessages()
    return
  }
  const result = await ragClient.getChatSession(sessionId)
  if (result.success) {
    setMessages(mapApiMessages(result.messages))
    scrollToBottom()
  }
}

async function send(text) {
  const messageText = (text || inputText.value).trim()
  if (!messageText || loading.value) return

  if (!props.sessionId && messages.value.length === 0) {
    emit('draft-started', 'chat')
  }

  addUserMessage(messageText)
  inputText.value = ''
  loading.value = true
  scrollToBottom()

  let streamingStarted = false

  try {
    await ragClient.sendMessageStream(
      messageText,
      (chunk) => {
        if (!streamingStarted) {
          streamingStarted = true
          loading.value = false
        }
        appendStreamChunk(chunk)
        scrollToBottom()
      },
      (fullResponse, metadata) => {
        finishAssistantStream(fullResponse, metadata)
        if (metadata?.session_id) {
          emit('session-created', { sessionId: metadata.session_id, module: 'chat' })
        }
        loading.value = false
        selectedFiles.value = []
        scrollToBottom()
      },
      (errorMsg) => {
        setAssistantError(errorMsg)
        loading.value = false
        scrollToBottom()
      },
      null,
      props.sessionId,
      'chat',
      selectedFiles.value.length ? selectedFiles.value : null,
      enableVectorization.value,
    )
  } catch (error) {
    logError('Ошибка отправки сообщения в чат', error)
    setAssistantError(error.message)
    loading.value = false
    scrollToBottom()
  }
}

function handleFileAttach(files) {
  const allowedExtensions = ['.pdf', '.doc', '.docx', '.txt']
  const maxSize = 10 * 1024 * 1024
  const valid = []

  for (const file of files) {
    const ext = `.${file.name.split('.').pop()?.toLowerCase()}`
    if (!allowedExtensions.includes(ext)) {
      toast.error(`«${file.name}» — неподдерживаемый тип файла`)
      continue
    }
    if (file.size > maxSize) {
      toast.error(`«${file.name}» — файл слишком большой (максимум 10 МБ)`)
      continue
    }
    valid.push(file)
  }

  if (valid.length) {
    selectedFiles.value.push(...valid)
  }
}

function removeFile(index) {
  selectedFiles.value.splice(index, 1)
}

function reset() {
  clearMessages()
  inputText.value = ''
  selectedFiles.value = []
  enableVectorization.value = false
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
