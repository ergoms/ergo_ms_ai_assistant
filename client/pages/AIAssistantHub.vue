<template>
  <HubShell
    :module-config="currentModuleConfig"
    :active-module="activeModule"
    :ollama-online="ollamaOnline"
    :current-model="currentModel"
    :accelerated="isAIGenerating"
  >
    <template #sidebar>
      <SessionSidebar
        :loading="sessionsLoading"
        :search-query="searchQuery"
        :filter-module="filterModule"
        :sessions-by-module="sessionsByModule"
        :active-session-id="activeSessionId"
        :draft-session="draftSession"
        @update:search-query="setSearchQuery"
        @update:filter-module="setFilterModule"
        @new-chat="showChatTypeSelector = true"
        @select-session="onSelectSession"
        @delete-session="onDeleteSession"
      />
    </template>

    <template #banner-actions>
      <button
        v-if="activeModule === 'docs'"
        type="button"
        class="action-btn action-btn--primary"
        :title="t('ai_assistant.upload')"
        @click="showDocsUploader = !showDocsUploader"
      >
        <Upload :size="18" />
        <span>{{ t('ai_assistant.upload') }}</span>
      </button>
    </template>

    <ChatTypeSelector
      :show="showChatTypeSelector"
      @close="showChatTypeSelector = false"
      @select="handleChatTypeSelect"
    />

    <template v-if="activeModule === 'docs' && !currentModuleConfig?.comingSoon">
      <div class="docs-module-wrapper">
        <DocsAssistantChat
          ref="docsAssistantChatRef"
          :key="`docs-chat-${docsChatKey}`"
          :is-visible="true"
          :hide-header="true"
          :force-show-uploader="showDocsUploader"
          @session-updated="loadSessions"
        />
      </div>
    </template>

    <div v-else-if="currentModuleConfig?.comingSoon" class="coming-soon">
      <div class="coming-soon__visual">
        <div class="coming-soon__icon" :style="{ color: currentModuleConfig?.color }">
          <component :is="currentModuleConfig?.icon" :size="64" />
        </div>
        <div class="coming-soon__particles">
          <span v-for="i in 8" :key="i" class="particle"></span>
        </div>
      </div>
      <h2 class="coming-soon__title">{{ t('ai_assistant.comingSoon') }}</h2>
      <p class="coming-soon__text">
        {{ t('ai_assistant.comingSoonText', { name: currentModuleConfig?.name }) }}
      </p>
      <div class="coming-soon__features">
        <span
          v-for="s in currentModuleConfig?.suggestions"
          :key="s"
          class="feature-chip"
        >
          <Zap :size="12" />
          {{ s }}
        </span>
      </div>
    </div>

    <HubChatPanel
      v-else-if="activeModule === 'chat' || activeModule === 'code'"
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
import { computed, nextTick, onMounted, ref } from 'vue'
import { Upload, Zap } from 'lucide-vue-next'
import { useAppI18n } from '@/i18n/useAppI18n.js'
import { useToast } from '@/js/utils/toast.js'
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
import ChatTypeSelector from '../components/ChatTypeSelector.vue'
import DocsAssistantChat from '../docs/DocsAssistantChat.vue'

const { t } = useAppI18n()
const toast = useToast()

const {
  loading: sessionsLoading,
  draftSession,
  activeSessionId,
  activeModule,
  searchQuery,
  filterModule,
  sessionsByModule,
  loadSessions,
  loadSession,
  createSession,
  deleteSession,
  selectSession,
  clearSession,
  attachSession,
  setSearchQuery,
  setFilterModule,
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

const { status: ollamaStatus, statusLabel } = useOllamaStatus({ autoPoll: true })
const ollamaOnline = computed(() => !!ollamaStatus.value.available)
const currentModel = computed(() => statusLabel.value || t('ai_assistant.modelLoading'))

const currentModuleConfig = computed(() => getModuleById(activeModule.value))
const isAIGenerating = computed(
  () => chatLoading.value || messages.value.some((msg) => msg.streaming),
)

const chatPanelRef = ref(null)
const chatInput = ref('')
const chatLoading = ref(false)
const chatSelectedFiles = ref([])
const enableVectorization = ref(false)
const currentChatSession = ref(null)

const showDocsUploader = ref(false)
const docsAssistantChatRef = ref(null)
const docsChatKey = ref(0)
const showChatTypeSelector = ref(false)

function initWelcomeChat() {
  resetLocalMessageIds(1)
  const config = getModuleById(activeModule.value) || getModuleById('chat')
  setMessages([{
    id: 1,
    type: 'assistant',
    content: config?.settings?.welcomeMessage || t('ai_assistant.modules.chat.welcome'),
    timestamp: new Date(),
  }])
  resetLocalMessageIds(2)
}

async function onSelectSession(sessionId, moduleId) {
  selectSession(sessionId, moduleId)
  await loadChatSession(sessionId, moduleId)
}

async function loadChatSession(sessionId, moduleId = null) {
  const result = await loadSession(sessionId)
  if (!result.success) {
    toast.error(result.error || t('ai_assistant.chatLoadFail'))
    return
  }

  currentChatSession.value = { id: sessionId, ...result.session }
  const sessionModule = moduleId || result.session.module || 'chat'

  if (sessionModule === 'docs') {
    docsChatKey.value++
    return
  }

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
      if (activeModule.value === 'chat' || activeModule.value === 'code') {
        initWelcomeChat()
      } else if (activeModule.value === 'docs') {
        docsChatKey.value++
      }
    }

    await loadSessions()
    toast.success(t('ai_assistant.chatDeleted'))
  } catch (error) {
    logError('Ошибка удаления чата', error)
    toast.error(t('ai_assistant.chatDeleteError'))
  }
}

async function handleChatTypeSelect(moduleId) {
  try {
    const module = getModuleById(moduleId)
    if (!module) {
      toast.error(t('ai_assistant.moduleNotFound'))
      return
    }

    const result = await createSession(moduleId)
    if (!result.success) {
      toast.error(result.error || t('ai_assistant.chatCreateFail'))
      return
    }

    currentChatSession.value = {
      id: result.session.id,
      module: moduleId,
    }
    attachSession(result.session.id, moduleId)

    if (moduleId === 'chat' || moduleId === 'code') {
      initWelcomeChat()
    } else if (moduleId === 'docs') {
      docsChatKey.value++
      nextTick(() => {
        docsAssistantChatRef.value?.resetChat?.()
      })
    }

    await loadSessions()
  } catch (error) {
    logError('Ошибка создания чата', error)
    toast.error(t('ai_assistant.chatCreateError'))
  }
}

async function sendChatMessage(text) {
  const messageText = (typeof text === 'string' ? text : chatInput.value).trim()
  if (!messageText || chatLoading.value) return

  addUserMessage(messageText)
  chatInput.value = ''
  chatLoading.value = true
  chatPanelRef.value?.scrollToBottom()

  try {
    await ragClient.sendMessageStream(
      messageText,
      (chunk) => {
        if (chatLoading.value) chatLoading.value = false
        appendStreamChunk(chunk)
        chatPanelRef.value?.scrollToBottom()
      },
      (fullResponse, metadata) => {
        finishAssistantStream(fullResponse, metadata || {})
        if (metadata?.session_id) {
          currentChatSession.value = { id: metadata.session_id }
          attachSession(metadata.session_id, activeModule.value)
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
      null,
      currentChatSession.value?.id,
      activeModule.value,
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
  ]
  const allowedExtensions = ['.pdf', '.doc', '.docx', '.txt']
  const maxSize = 10 * 1024 * 1024

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
    await loadChatSession(state.session, state.module)
    return
  }
  if (state.module !== prev?.module) {
    currentChatSession.value = null
    showDocsUploader.value = false
    if ((state.module === 'chat' || state.module === 'code') && !state.session) {
      initWelcomeChat()
    }
  }
})

onMounted(async () => {
  await loadSessions()
  if (activeSessionId.value) {
    await loadChatSession(activeSessionId.value, activeModule.value)
  } else if (activeModule.value === 'chat' || activeModule.value === 'code') {
    initWelcomeChat()
  }
})
</script>

<style lang="scss">
@import '../styles/neural-hub';
</style>
