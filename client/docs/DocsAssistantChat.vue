<template>
  <div 
    v-if="isVisible" 
    class="assistant-chat assistant-chat--visible"
    :class="{ 'drag-over': isDragging }"
    :style="{ '--module-color': moduleColor }"
    @dragover.prevent="handleDragOver"
    @dragleave.prevent="handleDragLeave"
    @drop.prevent="handleDrop"
  >
    <div v-if="!hideHeader" class="assistant-chat__header">
      <div class="assistant-chat__title">
        <FileText :size="20" class="me-2" />
        <span>{{ t('ai_assistant.docs.header.title') }}</span>
      </div>
      <div class="assistant-chat__controls">
        <button 
          class="control-btn btn-primary" 
          @click="showUploader = !showUploader"
          :title="t('ai_assistant.docs.header.uploadTooltip')"
        >
          <Upload :size="18" />
          <span class="ms-1">{{ t('ai_assistant.upload') }}</span>
        </button>
        <router-link 
          to="/ai-assistant" 
          class="control-btn" 
          :title="t('ai_assistant.docs.header.openHub')"
        >
          <ExternalLink :size="18" />
        </router-link>
      </div>
    </div>
    
    <!-- Кнопка загрузки в компактном виде, если header скрыт -->
    <div v-if="hideHeader && !showUploader && !selectedDocument && !showMessages" class="assistant-chat__compact-upload">
      <button 
        class="btn btn-primary btn-lg w-100"
        @click="showUploader = !showUploader"
      >
        <Upload :size="20" class="me-2" />
        {{ t('ai_assistant.docs.compactUpload') }}
      </button>
    </div>

    <!-- Модальное окно загрузки документов -->
    <teleport to="body">
      <div v-if="showUploader" class="upload-modal-overlay" @click.self="showUploader = false">
        <div class="upload-modal">
          <div class="upload-modal__header">
            <div class="upload-modal__title">
              <Upload :size="24" class="me-2" />
              <h5 class="mb-0">{{ t('ai_assistant.docs.uploadModalTitle') }}</h5>
            </div>
            <button class="upload-modal__close" @click="showUploader = false" :title="t('common.close')">
              <X :size="20" />
            </button>
          </div>
          <div class="upload-modal__body">
            <DocumentUploader
              @document-uploaded="handleDocumentUploaded"
              @document-created="handleDocumentCreated"
            />
          </div>
        </div>
      </div>
    </teleport>

    <!-- Выбор документа -->
    <div v-if="!selectedDocument && !showMessages" class="assistant-chat__document-selector">
      <DocumentSelector ref="documentSelector" @document-selected="onDocumentSelected" />
    </div>

    <!-- Информация о выбранном документе -->
    <div v-if="selectedDocument" class="assistant-chat__selected-info">
      <div class="selected-info-item">
        <FileText :size="14" />
        <span>{{ selectedDocument.title }}</span>
        <span v-if="selectedDocument.file_type" class="badge bg-secondary ms-2">
          {{ selectedDocument.file_type.toUpperCase() }}
        </span>
        <span v-if="selectedDocument.is_indexed" class="badge bg-success ms-2">
          {{ t('ai_assistant.docs.selectedInfo.indexed') }}
        </span>
        <span v-else class="badge bg-warning ms-2">
          {{ t('ai_assistant.docs.selectedInfo.notIndexed') }}
        </span>
      </div>
      <div class="selected-info-actions">
        <button class="btn btn-sm btn-outline-secondary" @click="showDocumentSelector = true; selectedDocument = null">
          {{ t('ai_assistant.docs.selectedInfo.changeDocument') }}
        </button>
        <button class="btn btn-sm btn-outline-secondary" @click="selectedDocument = null">
          {{ t('ai_assistant.docs.selectedInfo.removeFilter') }}
        </button>
      </div>
    </div>

    <!-- Кнопка выбора документа, если не выбран -->
    <div v-if="!selectedDocument && showMessages" class="assistant-chat__document-selector-toggle">
      <div class="document-actions">
        <button class="btn btn-sm btn-primary" @click="showUploader = !showUploader">
          <Upload :size="14" class="me-1" />
          {{ t('ai_assistant.docs.compactUpload') }}
        </button>
        <button class="btn btn-sm btn-outline-primary" @click="showDocumentSelector = !showDocumentSelector">
          <FileText :size="14" class="me-1" />
          {{ showDocumentSelector ? t('ai_assistant.docs.toggle.hideList') : t('ai_assistant.docs.toggle.selectDocument') }}
        </button>
      </div>
    </div>

    <!-- Список документов в свернутом виде -->
    <div v-if="showDocumentSelector && !selectedDocument" class="assistant-chat__document-selector-collapsed">
      <DocumentSelector ref="documentSelector" @document-selected="onDocumentSelected" />
    </div>

    <!-- Сообщения -->
    <div v-if="showMessages || messages.length > 1" ref="messagesContainer" class="assistant-chat__messages">
      <AssistantMessage 
        v-for="message in messages" 
        :key="message.id" 
        :message="message"
        :class="{ 'streaming': message.isStreaming }"
      />
      <AssistantTyping v-if="isTyping && !hasStreamingContent" />
    </div>

    <!-- Ввод -->
    <div class="assistant-chat__input">
      <div class="input-wrapper">
        <div class="input-group">
          <button
            class="btn btn-outline-primary"
            @click="showUploader = !showUploader"
            :title="t('ai_assistant.docs.compactUpload')"
            :disabled="isTyping"
          >
            <Upload :size="18" />
          </button>
          <input
            v-model="inputMessage"
            type="text"
            class="form-control"
            :placeholder="selectedDocument ? t('ai_assistant.docs.placeholderDocument') : t('ai_assistant.docs.placeholderKnowledgeBase')"
            @keypress.enter="sendMessage"
            :disabled="isTyping"
          />
          <button
            class="btn btn-danger"
            @click="sendMessage"
            :disabled="!inputMessage.trim() || isTyping"
          >
            <Send :size="18" />
          </button>
        </div>
        <div v-if="showUploader" class="upload-hint mt-2">
          <small class="text-muted">
            {{ t('ai_assistant.docs.uploadHint') }}
          </small>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch, computed, onMounted } from 'vue'
import { Send, FileText, ExternalLink, Upload, X } from 'lucide-vue-next'
import { useAppI18n } from '@/i18n/useAppI18n.js'
import { logError } from '@/js/utils/logError.js'
import AssistantMessage from '../base/AssistantMessage.vue'
import AssistantTyping from '../base/AssistantTyping.vue'
import DocumentSelector from './DocumentSelector.vue'
import DocumentUploader from './DocumentUploader.vue'
import { docsClient } from './js/docs-client.js'
import { ragClient } from '../rag/js/rag-client.js'
import { getModuleById } from '../modules/index.js'

const { t } = useAppI18n()

const props = defineProps({
  isVisible: {
    type: Boolean,
    default: false,
  },
  hideHeader: {
    type: Boolean,
    default: false,
  },
  forceShowUploader: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['session-updated'])

// Метод для сброса чата (вызывается из родительского компонента)
const resetChat = () => {
  // Сбрасываем текущую сессию
  currentSessionId = null
  historyLoaded = false
  
  // Сбрасываем выбранный документ
  selectedDocument.value = null
  showDocumentSelector.value = false
  
  // Сбрасываем сообщения на приветственное
  messageIdCounter = 1
  messages.value = [{
    id: messageIdCounter++,
    type: 'assistant',
    content: t('ai_assistant.docs.welcomeMessage'),
    timestamp: new Date(),
  }]
  
  // Сбрасываем состояние
  showMessages.value = false
  inputMessage.value = ''
  isTyping.value = false
  streamingMessageId = null
  showUploader.value = false
  
  // Прокручиваем в начало
  nextTick(() => {
    scrollToBottom()
  })
}

// Экспортируем метод для использования в родительском компоненте
defineExpose({
  resetChat
})

const messagesContainer = ref(null)
const documentSelector = ref(null)
const inputMessage = ref('')
const isTyping = ref(false)
const selectedDocument = ref(null)
const ollamaChecked = ref(false)
const showDocumentSelector = ref(false)
const showMessages = ref(false)
const showUploader = ref(false)
const isDragging = ref(false)

let messageIdCounter = 1
let streamingMessageId = null
let currentSessionId = null
let historyLoaded = false

const messages = ref([
  {
    id: messageIdCounter++,
    type: 'assistant',
    content: t('ai_assistant.docs.welcomeMessage'),
    timestamp: new Date(),
  },
])

const hasStreamingContent = computed(() => {
  return messages.value.some(m => m.isStreaming)
})

const moduleColor = computed(() => {
  const module = getModuleById('docs')
  return module?.color || '#8b5cf6'
})

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

const onDocumentSelected = (document) => {
  if (!document) {
    selectedDocument.value = null
    showDocumentSelector.value = false
    addAssistantMessage(t('ai_assistant.docs.documentCancelled'))
    showMessages.value = true
    return
  }

  selectedDocument.value = document
  showDocumentSelector.value = false
  showMessages.value = true
  
  if (document.is_indexed) {
    const chunksInfo = document.chunks_count > 0
      ? ` (${t('ai_assistant.docs.chunksCount', document.chunks_count)})`
      : ''

    addAssistantMessage(
      t('ai_assistant.docs.selectedIndexed', { title: document.title, chunksInfo })
    )
  } else {
    addAssistantMessage(
      t('ai_assistant.docs.selectedNotIndexed', { title: document.title })
    )
  }
}

const _changeDocument = () => {
  selectedDocument.value = null
  showDocumentSelector.value = true
  showMessages.value = true
}

const handleDocumentUploaded = (document) => {
  showUploader.value = false
  showMessages.value = true
  
  // Обновляем список документов, если селектор открыт
  if (documentSelector.value && typeof documentSelector.value.loadDocuments === 'function') {
    documentSelector.value.loadDocuments()
  }
  
  if (document.is_indexed) {
    // Автоматически выбираем документ, если он был индексирован
    selectedDocument.value = document
    addAssistantMessage(
      t('ai_assistant.docs.uploadedIndexed', {
        title: document.title,
        chunks: t('ai_assistant.docs.chunksCount', document.chunks_count),
      })
    )
  } else {
    addAssistantMessage(
      t('ai_assistant.docs.uploadedNotIndexed', { title: document.title })
    )
  }
}

const handleDocumentCreated = (document) => {
  showUploader.value = false
  showMessages.value = true
  
  // Обновляем список документов, если селектор открыт
  if (documentSelector.value && typeof documentSelector.value.loadDocuments === 'function') {
    documentSelector.value.loadDocuments()
  }
  
  if (document.is_indexed) {
    // Автоматически выбираем документ, если он был индексирован
    selectedDocument.value = document
    addAssistantMessage(
      t('ai_assistant.docs.createdIndexed', {
        title: document.title,
        chunks: t('ai_assistant.docs.chunksCount', document.chunks_count),
      })
    )
  } else {
    addAssistantMessage(
      t('ai_assistant.docs.createdNotIndexed', { title: document.title })
    )
  }
}

const addAssistantMessage = (content) => {
  const message = {
    id: messageIdCounter++,
    type: 'assistant',
    content: content,
    timestamp: new Date(),
  }
  messages.value.push(message)
  scrollToBottom()
}

const sendMessage = async () => {
  if (!inputMessage.value.trim() || isTyping.value) {
    return
  }

  // Показываем область сообщений после первого сообщения
  if (!showMessages.value) {
    showMessages.value = true
  }

  const messageText = inputMessage.value.trim()
  
  const userMessage = {
    id: messageIdCounter++,
    type: 'user',
    content: messageText,
    timestamp: new Date(),
  }
  messages.value.push(userMessage)
  inputMessage.value = ''
  scrollToBottom()

  isTyping.value = true

  // Проверяем Ollama перед отправкой
  if (!ollamaChecked.value) {
    const status = await docsClient.checkOllamaStatus()
    ollamaChecked.value = true
    
    if (!status.available) {
      isTyping.value = false
      addAssistantMessage(
        `${t('ai_assistant.docs.ollamaErrorTitle')}\n\n` +
        `${status.message || t('ai_assistant.ollama.unavailable')}\n\n` +
        t('ai_assistant.docs.ollamaErrorSteps')
      )
      return
    }

    if (!status.embeddings) {
      addAssistantMessage(t('ai_assistant.docs.embeddingsUnavailable'))
    }
  }

  // Создаем сообщение для streaming
  streamingMessageId = messageIdCounter++
  const streamingMessage = {
    id: streamingMessageId,
    type: 'assistant',
    content: '',
    timestamp: new Date(),
    isStreaming: true,
  }
  messages.value.push(streamingMessage)
  scrollToBottom()

  try {
    await docsClient.sendMessageStream(
      messageText,
      // onChunk
      (chunk) => {
        const msg = messages.value.find(m => m.id === streamingMessageId)
        if (msg) {
          msg.content += chunk
          scrollToBottom()
        }
      },
      // onDone
      async (fullResponse, metadata) => {
        const msg = messages.value.find(m => m.id === streamingMessageId)
        if (msg) {
          msg.content = fullResponse
          msg.isStreaming = false
        }
        isTyping.value = false
        streamingMessageId = null
        
        if (metadata?.session_id) {
          currentSessionId = metadata.session_id
          // Уведомляем родительский компонент об обновлении сессии
          // Это обновит список сессий в боковой панели
          emit('session-updated', metadata.session_id)
        }
        
        scrollToBottom()
      },
      // onError
      (errorMsg) => {
        let errorMessage = errorMsg || t('ai_assistant.docs.unknownError')
        
        if (errorMessage.includes('Ollama') || errorMessage.includes('ollama')) {
          errorMessage = `${t('ai_assistant.docs.ollamaErrorTitle')}\n\n` +
            `${errorMessage}\n\n` +
            t('ai_assistant.docs.ollamaErrorSteps')
        }
        
        const msg = messages.value.find(m => m.id === streamingMessageId)
        if (msg) {
          msg.content = t('ai_assistant.docs.errorPrefix', { message: errorMessage })
          msg.isStreaming = false
        }
        isTyping.value = false
        streamingMessageId = null
        scrollToBottom()
      },
      currentSessionId,
      selectedDocument.value?.id || null
    )
  } catch (error) {
    logError('Ошибка отправки сообщения:', error)
    const msg = messages.value.find(m => m.id === streamingMessageId)
    if (msg) {
      msg.content = t('ai_assistant.docs.errorPrefix', {
        message: error.message || t('ai_assistant.rag.api.sendMessageFailed'),
      })
      msg.isStreaming = false
    }
    isTyping.value = false
    streamingMessageId = null
    scrollToBottom()
  }
}

const handleDragOver = (event) => {
  isDragging.value = true
  event.dataTransfer.dropEffect = 'copy'
}

const handleDragLeave = (event) => {
  // Проверяем, что мы действительно покинули элемент, а не его дочерние элементы
  if (!event.currentTarget.contains(event.relatedTarget)) {
    isDragging.value = false
  }
}

const handleDrop = async (event) => {
  isDragging.value = false
  
  const files = Array.from(event.dataTransfer.files)
  const validFiles = files.filter(file => {
    const ext = file.name.split('.').pop()?.toLowerCase()
    return ['pdf', 'docx', 'txt'].includes(ext || '')
  })
  
  if (validFiles.length === 0) {
    addAssistantMessage(t('ai_assistant.docs.unsupportedFileTypes'))
    return
  }
  
  // Открываем панель загрузки
  showUploader.value = true
  
  // Ждем, пока компонент отобразится, затем устанавливаем файл
  await nextTick()
  
  // Можно добавить автоматическое заполнение формы, но пока просто открываем панель
  addAssistantMessage(t('ai_assistant.docs.fileDetected', { name: validFiles[0].name }))
}

watch(() => props.forceShowUploader, (newVal) => {
  if (newVal) {
    showUploader.value = true
  }
})

// Загрузка истории чата
const loadChatHistory = async () => {
  if (historyLoaded) return
  
  try {
    // Загружаем последнюю сессию для модуля docs
    const sessionsResult = await ragClient.getChatSessions('docs')
    if (sessionsResult.success && sessionsResult.sessions && sessionsResult.sessions.length > 0) {
      // Берем последнюю сессию (самую свежую)
      const latestSession = sessionsResult.sessions.sort((a, b) => 
        new Date(b.updated_at) - new Date(a.updated_at)
      )[0]
      
      // Загружаем сообщения из сессии
      const sessionResult = await ragClient.getChatSession(latestSession.id)
      if (sessionResult.success && sessionResult.messages && sessionResult.messages.length > 0) {
        currentSessionId = latestSession.id
        
        // Восстанавливаем сообщения из истории
        const historyMessages = sessionResult.messages.map(msg => ({
          id: messageIdCounter++,
          type: msg.type,
          content: msg.content,
          timestamp: new Date(msg.created_at),
          processing_time_ms: msg.processing_time_ms,
        }))
        
        // Заменяем приветственное сообщение на историю
        messages.value = historyMessages
        showMessages.value = true
        
        // Восстанавливаем выбранный документ из metadata сессии, если есть
        if (latestSession.metadata?.document_id) {
          const docsResult = await docsClient.getDocuments()
          if (docsResult.success && docsResult.documents) {
            const doc = docsResult.documents.find(d => d.id === latestSession.metadata.document_id)
            if (doc) {
              selectedDocument.value = doc
            }
          }
        }
        
        historyLoaded = true
        scrollToBottom()
      }
    }
  } catch (error) {
    logError('Ошибка загрузки истории чата:', error)
  }
}

watch(() => props.isVisible, (newVal) => {
  if (newVal) {
    scrollToBottom()
    // Загружаем историю при первом показе
    if (!historyLoaded) {
      loadChatHistory()
    }
  }
})

onMounted(() => {
  scrollToBottom()
  // Загружаем историю при монтировании
  if (props.isVisible && !historyLoaded) {
    loadChatHistory()
  }
})
</script>

<style scoped lang="scss">
@import './DocsAssistantChat.scss';
</style>
