<template>
  <HubShell
    :module-config="currentModuleConfig"
    active-module="chat"
    :accelerated="isAIGenerating"
    :model-subtitle="modelSubtitle"
  >
    <template #sidebar>
      <SessionSidebar
        :loading="sessionsLoading"
        :search-query="searchQuery"
        :sessions="chatSessions"
        :active-session-id="activeSessionId"
        :draft-session="draftSession"
        @update:search-query="setSearchQuery"
        @new-chat="handleNewChat"
        @select-session="onSelectSession"
        @delete-session="onDeleteSession"
      />
    </template>

    <HubChatPanel
      ref="chatPanelRef"
      v-model:input="chatInput"
      v-model:enable-vectorization="enableVectorization"
      :messages="messages"
      :loading="chatLoading"
      :module-config="currentModuleConfig"
      :selected-files="chatSelectedFiles"
      @send="sendChatMessage"
      @files-selected="handleChatFileSelect"
      @remove-file="removeChatFile"
    />
  </HubShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAppI18n } from '@/i18n/useAppI18n.js'
import { useToast } from '@/js/utils/toast.js'
import { UPLOAD_FEATURE_LIMITS } from '@/js/mediaUploadLimits.js'
import { logError } from '@/js/utils/logError.js'
import { confirmDelete } from '@/js/utils/confirm.js'
import { getModuleById } from '../modules/index.js'
import { ragClient } from '../rag/js/rag-client.js'
import { useAssistantSessions } from '../js/composables/useAssistantSessions.js'
import {
  mapApiMessages,
  resetLocalMessageIds,
  useMessageHistory,
} from '../js/composables/useAssistantStream.js'
import { useOllamaStatus } from '../js/composables/useOllamaStatus.js'
import HubShell from '../components/HubShell.vue'
import HubChatPanel from '../components/HubChatPanel.vue'
import SessionSidebar from '../components/session/SessionSidebar.vue'

const CHAT_MODULE = 'chat'

const { t } = useAppI18n()
const toast = useToast()

const {
  loading: sessionsLoading,
  draftSession,
  activeSessionId,
  searchQuery,
  filteredSessions,
  loadSessions,
  loadSession,
  createSession,
  deleteSession,
  selectSession,
  clearSession,
  attachSession,
  setSearchQuery,
  watchState,
} = useAssistantSessions()

const {
  messages,
  setMessages,
  addUserMessage,
  appendStreamChunk,
  finishAssistantStream,
  setAssistantError,
} = useMessageHistory()

const { status: ollamaStatus, modelSubtitle } = useOllamaStatus({ autoPoll: true })

const currentModuleConfig = computed(() => getModuleById(CHAT_MODULE))
const chatSessions = computed(() =>
  filteredSessions.value.filter((s) => (s.module || CHAT_MODULE) === CHAT_MODULE),
)
const isAIGenerating = computed(
  () => chatLoading.value || messages.value.some((msg) => msg.streaming),
)

const chatPanelRef = ref(null)
const chatInput = ref('')
const chatLoading = ref(false)
const chatSelectedFiles = ref([])
const enableVectorization = ref(false)
const currentChatSession = ref(null)

function initWelcomeChat() {
  resetLocalMessageIds(1)
  const config = getModuleById(CHAT_MODULE)
  setMessages([{
    id: 1,
    type: 'assistant',
    content: config?.settings?.welcomeMessage || t('ai_assistant.modules.chat.welcome'),
    timestamp: new Date(),
  }])
  resetLocalMessageIds(2)
}

async function onSelectSession(sessionId) {
  selectSession(sessionId, CHAT_MODULE)
  await loadChatSession(sessionId)
}

async function loadChatSession(sessionId) {
  const result = await loadSession(sessionId)
  if (!result.success) {
    toast.error(result.error || t('ai_assistant.chatLoadFail'))
    return
  }

  currentChatSession.value = { id: sessionId, module: CHAT_MODULE, ...result.session }

  resetLocalMessageIds(1)
  const mapped = mapApiMessages(result.messages)
  if (mapped.length) {
    setMessages(mapped)
    const maxId = mapped.reduce((max, msg) => Math.max(max, Number(msg.id) || 0), 0)
    resetLocalMessageIds(maxId + 1)
  } else {
    initWelcomeChat()
  }
  chatPanelRef.value?.scrollToBottom()
}

async function onDeleteSession(sessionId) {
  const ok = await confirmDelete(
    t('ai_assistant.deleteChat'),
    t('ai_assistant.deleteConfirm'),
  )
  if (!ok) return

  try {
    const result = await deleteSession(sessionId)
    if (!result.success) {
      toast.error(result.error || t('ai_assistant.chatDeleteFail'))
      return
    }

    if (currentChatSession.value?.id === sessionId || activeSessionId.value === sessionId) {
      currentChatSession.value = null
      clearSession()
      initWelcomeChat()
    }

    await loadSessions()
    toast.success(t('ai_assistant.chatDeleted'))
  } catch (error) {
    logError('Ошибка удаления чата', error)
    toast.error(t('ai_assistant.chatDeleteError'))
  }
}

async function handleNewChat() {
  try {
    const result = await createSession(CHAT_MODULE)
    if (!result.success) {
      toast.error(result.error || t('ai_assistant.chatCreateFail'))
      return
    }

    currentChatSession.value = {
      id: result.session.id,
      module: CHAT_MODULE,
    }
    attachSession(result.session.id, CHAT_MODULE)
    initWelcomeChat()
    await loadSessions()
  } catch (error) {
    logError('Ошибка создания чата', error)
    toast.error(t('ai_assistant.chatCreateError'))
  }
}

function resolveChatSessionId() {
  return currentChatSession.value?.id || activeSessionId.value || null
}

async function sendChatMessage(text) {
  const messageText = (typeof text === 'string' ? text : chatInput.value).trim()
  if (!messageText || chatLoading.value) return

  const pendingFiles = [...chatSelectedFiles.value]
  const localAttachments = pendingFiles
    .filter((file) => file.type?.startsWith('image/') || /\.(png|jpe?g|webp|gif)$/i.test(file.name))
    .map((file) => ({
      kind: 'image',
      name: file.name,
      preview_url: URL.createObjectURL(file),
    }))
  addUserMessage(messageText, { attachments: localAttachments })
  chatInput.value = ''
  chatLoading.value = true
  chatPanelRef.value?.scrollToBottom()

  try {
    const ollamaConfig = ollamaStatus.value.model
      ? { model: ollamaStatus.value.model }
      : null
    const sessionId = resolveChatSessionId()

    await ragClient.sendMessageStream(
      messageText,
      (chunk) => {
        if (chatLoading.value) chatLoading.value = false
        appendStreamChunk(chunk)
        chatPanelRef.value?.scrollToBottom()
      },
      (fullResponse, metadata) => {
        finishAssistantStream(fullResponse, metadata || {})
        const nextSessionId = metadata?.session_id || sessionId
        if (nextSessionId) {
          currentChatSession.value = {
            ...(currentChatSession.value || {}),
            id: nextSessionId,
            module: CHAT_MODULE,
          }
          attachSession(nextSessionId, CHAT_MODULE)
          loadSessions()
        }
        chatLoading.value = false
        chatSelectedFiles.value = []
        chatPanelRef.value?.clearFileInput()
        chatPanelRef.value?.scrollToBottom()
      },
      (errorMsg) => {
        setAssistantError(errorMsg)
        chatLoading.value = false
        chatPanelRef.value?.scrollToBottom()
      },
      ollamaConfig,
      sessionId,
      CHAT_MODULE,
      chatSelectedFiles.value.length > 0 ? chatSelectedFiles.value : null,
      enableVectorization.value,
    )
  } catch (error) {
    setAssistantError(error.message)
    chatLoading.value = false
    chatPanelRef.value?.scrollToBottom()
  }
}

function handleChatFileSelect(event) {
  const files = Array.from(event.target.files || [])
  if (files.length === 0) return

  const allowedTypes = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain',
    'text/markdown',
    'text/csv',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'image/png',
    'image/jpeg',
    'image/webp',
    'image/gif',
  ]
  const allowedExtensions = [
    '.pdf', '.doc', '.docx', '.txt', '.md', '.csv', '.xlsx', '.xls',
    '.png', '.jpg', '.jpeg', '.webp', '.gif',
  ]
  const maxSize = UPLOAD_FEATURE_LIMITS.aiAssistantChat

  const validFiles = []
  const errors = []

  files.forEach((file) => {
    const fileExtension = `.${file.name.split('.').pop().toLowerCase()}`
    if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(fileExtension)) {
      errors.push(t('ai_assistant.fileUnsupported', { name: file.name }))
      return
    }
    if (file.size > maxSize) {
      errors.push(t('ai_assistant.fileTooLarge', { name: file.name }))
      return
    }
    if (chatSelectedFiles.value.some((f) => f.name === file.name && f.size === file.size)) {
      errors.push(t('ai_assistant.fileAlreadyAdded', { name: file.name }))
      return
    }
    validFiles.push(file)
  })

  if (errors.length > 0) {
    toast.error(errors.join('\n'))
  }
  if (validFiles.length > 0) {
    chatSelectedFiles.value.push(...validFiles)
    toast.success(t('ai_assistant.filesUploaded', {
      count: validFiles.length,
      names: validFiles.map((f) => f.name).join(', '),
    }))
  }
  chatPanelRef.value?.clearFileInput()
}

function removeChatFile(index) {
  if (index >= 0 && index < chatSelectedFiles.value.length) {
    chatSelectedFiles.value.splice(index, 1)
  }
}

watchState(async (state, prev) => {
  if (state.session && state.session !== prev?.session) {
    await loadChatSession(state.session)
    return
  }
  if (!state.session && state.session !== prev?.session) {
    currentChatSession.value = null
    initWelcomeChat()
  }
})

onMounted(async () => {
  await loadSessions()
  if (activeSessionId.value) {
    await loadChatSession(activeSessionId.value)
  } else {
    initWelcomeChat()
  }
})
</script>

<style lang="scss">
@import '../styles/neural-hub';
</style>
