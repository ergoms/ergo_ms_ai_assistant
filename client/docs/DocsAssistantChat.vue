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
        <span>AI Ассистент - База знаний</span>
      </div>
      <div class="assistant-chat__controls">
        <button 
          class="control-btn btn-primary" 
          @click="showUploader = !showUploader"
          title="Загрузить документ"
        >
          <Upload :size="18" />
          <span class="ms-1">Загрузить</span>
        </button>
        <router-link 
          to="/ai-assistant" 
          class="control-btn" 
          title="Открыть AI Hub"
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
        Загрузить документ
      </button>
    </div>

    <!-- Модальное окно загрузки документов -->
    <teleport to="body">
      <div v-if="showUploader" class="upload-modal-overlay" @click.self="showUploader = false">
        <div class="upload-modal">
          <div class="upload-modal__header">
            <div class="upload-modal__title">
              <Upload :size="24" class="me-2" />
              <h5 class="mb-0">Загрузка документа</h5>
            </div>
            <button class="upload-modal__close" @click="showUploader = false" title="Закрыть">
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
          Индексирован
        </span>
        <span v-else class="badge bg-warning ms-2">
          Не индексирован
        </span>
      </div>
      <div class="selected-info-actions">
        <button class="btn btn-sm btn-outline-secondary" @click="showDocumentSelector = true; selectedDocument = null">
          Сменить документ
        </button>
        <button class="btn btn-sm btn-outline-secondary" @click="selectedDocument = null">
          Убрать фильтр
        </button>
      </div>
    </div>

    <!-- Кнопка выбора документа, если не выбран -->
    <div v-if="!selectedDocument && showMessages" class="assistant-chat__document-selector-toggle">
      <div class="document-actions">
        <button class="btn btn-sm btn-primary" @click="showUploader = !showUploader">
          <Upload :size="14" class="me-1" />
          Загрузить документ
        </button>
        <button class="btn btn-sm btn-outline-primary" @click="showDocumentSelector = !showDocumentSelector">
          <FileText :size="14" class="me-1" />
          {{ showDocumentSelector ? 'Скрыть список' : 'Выбрать документ' }}
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
            title="Загрузить документ"
            :disabled="isTyping"
          >
            <Upload :size="18" />
          </button>
          <input
            v-model="inputMessage"
            type="text"
            class="form-control"
            :placeholder="selectedDocument ? 'Задайте вопрос к документу...' : 'Задайте вопрос по базе знаний...'"
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
            💡 Перетащите файл в область выше или используйте форму загрузки
          </small>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch, computed, onMounted } from 'vue'
import { Send, FileText, ExternalLink, Upload, X } from 'lucide-vue-next'
import AssistantMessage from '../base/AssistantMessage.vue'
import AssistantTyping from '../base/AssistantTyping.vue'
import DocumentSelector from './DocumentSelector.vue'
import DocumentUploader from './DocumentUploader.vue'
import { docsClient } from './js/docs-client.js'
import { ragClient } from '../rag/js/rag-client.js'
import { getModuleById } from '../modules/index.js'
import { logError } from '@/js/utils/logError.js'

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
  console.log('Resetting docs chat...')
  
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
    content: 'Привет! Я ваш AI ассистент для работы с базой знаний.\n\n**Что я умею:**\n• Отвечать на вопросы на основе загруженных документов\n• Искать информацию в базе знаний\n• Работать с документами Word, PDF и текстовыми файлами\n\n**Начните работу:**\n1. Нажмите кнопку "Загрузить" вверху для добавления документов\n2. Или выберите существующий документ из списка\n3. После загрузки документ будет автоматически проиндексирован (если выбрана опция)\n4. Затем задавайте вопросы к документам!',
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
    content: 'Привет! Я ваш AI ассистент для работы с базой знаний.\n\n**Что я умею:**\n• Отвечать на вопросы на основе загруженных документов\n• Искать информацию в базе знаний\n• Работать с документами Word, PDF и текстовыми файлами\n\n**Начните работу:**\n1. Нажмите кнопку "Загрузить" вверху для добавления документов\n2. Или выберите существующий документ из списка\n3. После загрузки документ будет автоматически проиндексирован (если выбрана опция)\n4. Затем задавайте вопросы к документам!',
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
    addAssistantMessage('Документ отменен. Теперь поиск будет по всем документам.')
    showMessages.value = true
    return
  }

  selectedDocument.value = document
  showDocumentSelector.value = false
  showMessages.value = true
  
  if (document.is_indexed) {
    const chunksText = document.chunks_count > 0 
      ? `${document.chunks_count} ${document.chunks_count === 1 ? 'фрагмент' : document.chunks_count < 5 ? 'фрагмента' : 'фрагментов'}`
      : 'готов к поиску'
    
    addAssistantMessage(
      `Выбран документ: **${document.title}**\n\n` +
      `✅ Документ проиндексирован${document.chunks_count > 0 ? ` (${chunksText})` : ''}. ` +
      `Теперь поиск будет выполняться только в этом документе. ` +
      `Вы можете задавать вопросы к документу. Например:\n\n` +
      `• "О чем этот документ?"\n` +
      `• "Найди информацию о..."\n` +
      `• "Что говорится про..."`
    )
  } else {
    addAssistantMessage(
      `Выбран документ: **${document.title}**\n\n` +
      `⚠️ **Внимание:** Документ не проиндексирован. ` +
      `Для поиска по документу необходимо его индексировать. ` +
      `Используйте кнопку индексации в списке документов. ` +
      `Пока поиск будет выполняться по всем проиндексированным документам.`
    )
  }
}

const changeDocument = () => {
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
      `✅ Документ **${document.title}** успешно загружен и проиндексирован (${document.chunks_count} фрагментов). ` +
      `Теперь вы можете задавать вопросы к этому документу.`
    )
  } else {
    addAssistantMessage(
      `✅ Документ **${document.title}** успешно загружен. ` +
      `⚠️ Для поиска по документу необходимо его проиндексировать. ` +
      `Используйте кнопку индексации в списке документов.`
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
      `✅ Документ **${document.title}** успешно создан и проиндексирован (${document.chunks_count} фрагментов). ` +
      `Теперь вы можете задавать вопросы к этому документу.`
    )
  } else {
    addAssistantMessage(
      `✅ Документ **${document.title}** успешно создан. ` +
      `⚠️ Для поиска по документу необходимо его проиндексировать. ` +
      `Используйте кнопку индексации в списке документов.`
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
        `**Ошибка подключения к Ollama**\n\n` +
        `${status.message || 'Ollama недоступен'}\n\n` +
        `**Что нужно сделать:**\n` +
        `1. Убедитесь, что Ollama установлен и запущен\n` +
        `2. Проверьте доступность Ollama по адресу: http://localhost:11434\n` +
        `3. Установите Ollama: https://ollama.com/download`
      )
      return
    }

    if (!status.embeddings) {
      addAssistantMessage(
        `⚠️ **Внимание:** Сервис embeddings недоступен. ` +
        `Ответы могут быть не основаны на ваших документах.`
      )
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
        let errorMessage = errorMsg || 'Неизвестная ошибка'
        
        if (errorMessage.includes('Ollama') || errorMessage.includes('ollama')) {
          errorMessage = `**Ошибка подключения к Ollama**\n\n` +
            `${errorMessage}\n\n` +
            `**Что нужно сделать:**\n` +
            `1. Убедитесь, что Ollama установлен и запущен\n` +
            `2. Проверьте доступность Ollama по адресу: http://localhost:11434\n` +
            `3. Установите Ollama: https://ollama.com/download`
        }
        
        const msg = messages.value.find(m => m.id === streamingMessageId)
        if (msg) {
          msg.content = `**Ошибка:** ${errorMessage}`
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
      msg.content = `**Ошибка:** ${error.message || 'Не удалось отправить сообщение'}`
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
    addAssistantMessage(
      '⚠️ **Ошибка:** Поддерживаются только файлы форматов PDF, DOCX и TXT.'
    )
    return
  }
  
  // Открываем панель загрузки
  showUploader.value = true
  
  // Ждем, пока компонент отобразится, затем устанавливаем файл
  await nextTick()
  
  // Можно добавить автоматическое заполнение формы, но пока просто открываем панель
  addAssistantMessage(
    `📁 Обнаружен файл: **${validFiles[0].name}**\n\n` +
    `Используйте форму загрузки выше для загрузки файла.`
  )
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

<style scoped>
.assistant-chat {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  background: 
    radial-gradient(ellipse at top, color-mix(in srgb, var(--module-color, #8b5cf6) 8%, transparent) 0%, transparent 50%),
    radial-gradient(ellipse at bottom, color-mix(in srgb, var(--module-color, #8b5cf6) 5%, transparent) 0%, transparent 50%);
  position: relative;
  overflow: hidden;
  z-index: 1;
}

.assistant-chat::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image: 
    radial-gradient(circle at 20% 50%, color-mix(in srgb, var(--module-color, #8b5cf6) 6%, transparent) 0%, transparent 50%),
    radial-gradient(circle at 80% 80%, color-mix(in srgb, var(--module-color, #8b5cf6) 4%, transparent) 0%, transparent 50%);
  pointer-events: none;
  z-index: 0;
}

.assistant-chat.drag-over::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: color-mix(in srgb, var(--module-color, #8b5cf6) 10%, transparent);
  border: 2px dashed var(--module-color, #8b5cf6);
  border-radius: 0.5rem;
  z-index: 100;
  pointer-events: none;
}

.assistant-chat.drag-over::after {
  content: 'Перетащите файл сюда для загрузки';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: var(--module-color, #8b5cf6);
  color: white;
  padding: 1rem 2rem;
  border-radius: 0.5rem;
  font-weight: 600;
  z-index: 101;
  pointer-events: none;
  white-space: nowrap;
}

.assistant-chat__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border-bottom: 1px solid var(--bs-border-color);
}

.assistant-chat__title {
  display: flex;
  align-items: center;
  font-weight: 600;
}

.assistant-chat__controls {
  display: flex;
  gap: 0.5rem;
}

.control-btn {
  display: flex;
  align-items: center;
  padding: 0.25rem 0.5rem;
  color: var(--bs-secondary);
  text-decoration: none;
  border-radius: 0.25rem;
  transition: all 0.2s;
}

.control-btn:hover {
  color: var(--module-color, #8b5cf6);
  background-color: color-mix(in srgb, var(--module-color, #8b5cf6) 10%, transparent);
}

.control-btn.btn-primary {
  background-color: var(--module-color, #8b5cf6);
  color: white;
  padding: 0.375rem 0.75rem;
  border-radius: 0.375rem;
  display: flex;
  align-items: center;
  border: none;
  cursor: pointer;
}

.control-btn.btn-primary:hover {
  background-color: var(--module-color, #8b5cf6);
  opacity: 0.9;
  opacity: 0.9;
  color: white;
}

/* Модальное окно загрузки */
.upload-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.upload-modal {
  background: linear-gradient(135deg, 
    color-mix(in srgb, var(--bs-body-bg) 95%, transparent) 0%,
    color-mix(in srgb, var(--module-color, #8b5cf6) 15%, var(--bs-body-bg)) 100%
  );
  backdrop-filter: blur(20px);
  border-radius: 1rem;
  box-shadow: 
    0 20px 60px rgba(0, 0, 0, 0.5),
    0 0 0 1px color-mix(in srgb, var(--module-color, #8b5cf6) 30%, transparent),
    0 0 40px color-mix(in srgb, var(--module-color, #8b5cf6) 20%, transparent);
  width: 90%;
  max-width: 600px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  animation: slideUp 0.3s ease-out;
  overflow: hidden;
}

@keyframes slideUp {
  from {
    transform: translateY(30px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.upload-modal__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid color-mix(in srgb, var(--module-color, #8b5cf6) 30%, transparent);
  background: color-mix(in srgb, var(--module-color, #8b5cf6) 10%, transparent);
}

.upload-modal__title {
  display: flex;
  align-items: center;
  color: var(--module-color, #8b5cf6);
  font-weight: 600;
}

.upload-modal__close {
  background: transparent;
  border: 1px solid color-mix(in srgb, var(--bs-border-color) 40%, transparent);
  color: var(--bs-secondary);
  width: 36px;
  height: 36px;
  border-radius: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}

.upload-modal__close:hover {
  background: color-mix(in srgb, var(--bs-danger) 20%, transparent);
  border-color: var(--bs-danger);
  color: var(--bs-danger);
  transform: rotate(90deg);
}

.upload-modal__body {
  padding: 1.5rem;
  overflow-y: auto;
  flex: 1;
}

.upload-hint {
  text-align: center;
}

.assistant-chat__document-selector {
  flex: 1;
  overflow-y: auto;
  position: relative;
  z-index: 1;
}

.assistant-chat__document-selector-toggle {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid color-mix(in srgb, var(--bs-border-color) 50%, transparent);
  background: transparent;
}

.document-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.assistant-chat__document-selector-collapsed {
  max-height: 400px;
  overflow-y: auto;
  border-bottom: 1px solid color-mix(in srgb, var(--bs-border-color) 50%, transparent);
  background: transparent;
}

.assistant-chat__selected-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid color-mix(in srgb, var(--bs-border-color) 50%, transparent);
  background: color-mix(in srgb, var(--module-color, #8b5cf6) 10%, transparent);
  backdrop-filter: blur(5px);
  gap: 0.5rem;
}

.selected-info-actions {
  display: flex;
  gap: 0.5rem;
}

.selected-info-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  min-width: 0;
}

.selected-info-item span:not(.badge) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.assistant-chat__messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  background: transparent;
  position: relative;
  z-index: 1;
}

.assistant-chat__messages::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: 
    radial-gradient(ellipse at center, transparent 0%, color-mix(in srgb, var(--module-color, #8b5cf6) 3%, transparent) 100%);
  pointer-events: none;
  z-index: -1;
}

.assistant-chat__compact-upload {
  padding: 2rem;
  display: flex;
  justify-content: center;
  align-items: center;
  background: transparent;
  position: relative;
  z-index: 1;
}

.assistant-chat__input {
  padding: 1rem;
  border-top: 1px solid color-mix(in srgb, var(--bs-border-color) 50%, transparent);
  background: color-mix(in srgb, var(--bs-body-bg) 70%, transparent);
  backdrop-filter: blur(10px);
  position: relative;
  z-index: 2;
}

.input-wrapper {
  width: 100%;
}

.input-group {
  display: flex;
  gap: 0.5rem;
}

.form-control {
  flex: 1;
}

.streaming {
  opacity: 0.8;
}
</style>


