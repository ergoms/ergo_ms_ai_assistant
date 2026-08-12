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
      :allow-files="allowFiles"
      :allow-vectorization="allowVectorization"
      @send="sendChatMessage"
      @files-selected="handleChatFileSelect"
      @remove-file="removeChatFile"
    />
  </HubShell>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAppI18n } from '@/i18n/useAppI18n.js'
import { useToast } from '@/js/utils/toast.js'
import { UPLOAD_FEATURE_LIMITS } from '@/js/mediaUploadLimits.js'
import { logError } from '@/js/utils/logError.js'
import { confirmDelete } from '@/js/utils/confirm.js'
import {
  DEFAULT_CHAT_PROFILE_ID,
  getChatProfile,
  profileToModuleConfig,
} from '../js/chatProfiles.js'
import { createChatTransport } from '../js/chatTransport.js'
import { useAssistantSessions } from '../js/composables/useAssistantSessions.js'
import {
  mapApiMessages,
  nextLocalMessageId,
  resetLocalMessageIds,
  useMessageHistory,
} from '../js/composables/useAssistantStream.js'
import {
  isAwaitingAssistantReply,
  recoverPendingReply,
} from '../js/composables/usePendingReplyRecovery.js'
import { isPageUnloading } from '../js/streamDisconnect.js'
import { useOllamaStatus } from '../js/composables/useOllamaStatus.js'
import HubShell from '../components/HubShell.vue'
import HubChatPanel from '../components/HubChatPanel.vue'
import SessionSidebar from '../components/session/SessionSidebar.vue'

const { t } = useAppI18n()
const toast = useToast()
const route = useRoute()

const activeProfile = ref(null)
const transport = ref(null)

const chatModuleKey = computed(
  () => activeProfile.value?.sessionModule || 'chat',
)
const allowFiles = computed(() => activeProfile.value?.features?.files !== false
  && !activeProfile.value?.external)
const allowVectorization = computed(
  () => activeProfile.value?.features?.vectorization !== false
    && !activeProfile.value?.external,
)

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

const currentModuleConfig = computed(() => {
  if (activeProfile.value) return profileToModuleConfig(activeProfile.value)
  return null
})
const chatSessions = computed(() =>
  filteredSessions.value.filter(
    (s) => (s.module || 'chat') === chatModuleKey.value,
  ),
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

async function ensureProfileFromRoute() {
  const profileParam = String(route.query.profile || '').trim()
  const profileId = profileParam || DEFAULT_CHAT_PROFILE_ID
  const profile = await getChatProfile(profileId)
  activeProfile.value = profile
  transport.value = createChatTransport(profile)
  return profile
}

function initWelcomeChat() {
  resetLocalMessageIds(1)
  const config = currentModuleConfig.value
  setMessages([{
    id: 1,
    type: 'assistant',
    content: config?.settings?.welcomeMessage || t('ai_assistant.modules.chat.welcome'),
    timestamp: new Date(),
  }])
  resetLocalMessageIds(2)
}

async function onSelectSession(sessionId) {
  selectSession(sessionId, chatModuleKey.value)
  await loadChatSession(sessionId)
}

async function maybeRecoverPendingReply(sessionId) {
  if (!sessionId || !isAwaitingAssistantReply(messages.value)) {
    return
  }
  await recoverPendingReply({
    sessionId,
    getLocalMessages: () => messages.value,
    applyMessages: (mapped) => {
      setMessages(mapped)
      const maxId = mapped.reduce((max, msg) => Math.max(max, Number(msg.id) || 0), 0)
      resetLocalMessageIds(maxId + 1)
    },
    setPending: (pending) => {
      chatLoading.value = pending
    },
    onInterrupted: () => {
      // Без префикса «Ошибка:» — короткая подсказка повторить
      messages.value.push({
        id: nextLocalMessageId(),
        type: 'assistant',
        content: t('ai_assistant.replyInterrupted'),
        timestamp: new Date(),
        interrupted: true,
      })
    },
  })
  chatPanelRef.value?.scrollToBottom()
}

async function loadChatSession(sessionId) {
  const result = await loadSession(sessionId)
  if (!result.success) {
    toast.error(result.error || t('ai_assistant.chatLoadFail'))
    return
  }

  currentChatSession.value = { id: sessionId, module: chatModuleKey.value, ...result.session }

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
  await maybeRecoverPendingReply(sessionId)
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

    await loadSessions(chatModuleKey.value)
    toast.success(t('ai_assistant.chatDeleted'))
  } catch (error) {
    logError('Ошибка удаления чата', error)
    toast.error(t('ai_assistant.chatDeleteError'))
  }
}

async function handleNewChat() {
  try {
    const result = await createSession(chatModuleKey.value)
    if (!result.success) {
      toast.error(result.error || t('ai_assistant.chatCreateFail'))
      return
    }

    currentChatSession.value = {
      id: result.session.id,
      module: chatModuleKey.value,
    }
    attachSession(result.session.id, chatModuleKey.value)
    initWelcomeChat()
    await loadSessions(chatModuleKey.value)
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

    const streamResult = await transport.value.sendMessageStream(
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
            module: chatModuleKey.value,
          }
          attachSession(nextSessionId, chatModuleKey.value)
          loadSessions(chatModuleKey.value)
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
      chatModuleKey.value,
      allowFiles.value && chatSelectedFiles.value.length > 0
        ? chatSelectedFiles.value
        : null,
      allowVectorization.value && enableVectorization.value,
    )
    if (streamResult?.disconnected) {
      if (isPageUnloading()) {
        chatLoading.value = true
        return
      }
      const activeId = currentChatSession.value?.id || sessionId
      if (activeId) {
        chatLoading.value = true
        await maybeRecoverPendingReply(activeId)
      } else {
        messages.value.push({
          id: nextLocalMessageId(),
          type: 'assistant',
          content: t('ai_assistant.replyInterrupted'),
          timestamp: new Date(),
        })
        chatLoading.value = false
      }
      chatPanelRef.value?.scrollToBottom()
    }
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

watch(
  () => route.query.profile,
  async () => {
    await ensureProfileFromRoute()
    currentChatSession.value = null
    clearSession()
    initWelcomeChat()
    await loadSessions(chatModuleKey.value)
  },
)

onMounted(async () => {
  await ensureProfileFromRoute()
  await loadSessions(chatModuleKey.value)
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
