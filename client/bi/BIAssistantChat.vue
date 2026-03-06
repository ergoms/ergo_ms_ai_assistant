<template>
  <div 
    v-if="isVisible" 
    class="assistant-chat assistant-chat--visible"
  >
    <div class="assistant-chat__header">
      <div class="assistant-chat__title">
        <Database :size="20" class="me-2" />
        <span>AI Ассистент - BI Анализ</span>
      </div>
      <div class="assistant-chat__controls">
        <router-link 
          to="/ai-assistant" 
          class="control-btn" 
          title="Открыть AI Hub"
        >
          <ExternalLink :size="18" />
        </router-link>
      </div>
    </div>

    <!-- Выбор подключения -->
    <div v-if="!selectedConnection" class="assistant-chat__connection-selector">
      <ConnectionSelector ref="connectionSelector" @connection-selected="onConnectionSelected" />
    </div>

    <!-- Выбор файла -->
    <div v-else-if="!selectedFile" class="assistant-chat__file-gallery">
      <FileGallery :connection-id="selectedConnection.id" ref="fileGallery" @file-selected="onFileSelected" />
    </div>

    <!-- Информация о выбранном подключении и файле -->
    <div v-if="selectedConnection && selectedFile" class="assistant-chat__selected-info">
      <div class="selected-info-item">
        <Database :size="14" />
        <span>{{ selectedConnection.name }}</span>
      </div>
      <div class="selected-info-item">
        <FileSpreadsheet :size="14" />
        <span>{{ selectedFile.name }}</span>
      </div>
      <button class="btn btn-sm btn-outline-secondary" @click="changeFile">
        Сменить файл
      </button>
    </div>

    <div ref="messagesContainer" class="assistant-chat__messages">
      <AssistantMessage v-for="message in messages" :key="message.id" :message="message" />
      <AssistantTyping v-if="isTyping" />
    </div>

    <div class="assistant-chat__input">
      <div class="input-wrapper">
        <div class="input-group">
          <input
            v-model="inputMessage"
            type="text"
            class="form-control"
            :placeholder="!selectedConnection ? 'Сначала выберите подключение' : !selectedFile ? 'Выберите файл для анализа' : 'Задайте вопрос к данным...'"
            @keypress.enter="sendMessage"
            :disabled="isTyping || !selectedConnection || !selectedFile"
          />
          <button
            class="btn btn-danger"
            @click="sendMessage"
            :disabled="!inputMessage.trim() || isTyping || !selectedConnection || !selectedFile"
          >
            <Send :size="18" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch } from 'vue'
import { Send, Database, FileSpreadsheet, ExternalLink } from 'lucide-vue-next'
import AssistantMessage from '../base/AssistantMessage.vue'
import AssistantTyping from '../base/AssistantTyping.vue'
import ConnectionSelector from './ConnectionSelector.vue'
import FileGallery from './FileGallery.vue'
import { biClient } from './js/bi-client.js'

const emit = defineEmits(['bi-query', 'close'])

const props = defineProps({
  isVisible: {
    type: Boolean,
    default: false,
  },
})

const messagesContainer = ref(null)
const connectionSelector = ref(null)
const fileGallery = ref(null)
const inputMessage = ref('')
const isTyping = ref(false)
const selectedConnection = ref(null)
const selectedFile = ref(null)
const ollamaChecked = ref(false)

let messageIdCounter = 1

const messages = ref([
  {
    id: messageIdCounter++,
    type: 'assistant',
    content:
      'Привет! Я ваш AI ассистент для анализа данных.\n\n**Что я умею:**\n• Анализировать табличные данные\n• Генерировать SQL запросы\n• Находить закономерности\n• Предоставлять статистику\n\n**Начните с выбора файла** для анализа данных!',
    timestamp: new Date(),
  },
])

const onConnectionSelected = (connection) => {
  selectedConnection.value = connection
  selectedFile.value = null
  addAssistantMessage(
    `Выбрано подключение: **${connection.name}**\n\nТеперь выберите файл для анализа.`,
  )
}

const onFileSelected = (file) => {
  selectedFile.value = file
  addAssistantMessage(
    `Выбран файл: **${file.name}**\n\nТеперь вы можете задавать вопросы к данным. Например:\n• "Покажи первые 10 строк"\n• "Какие колонки в файле?"\n• "Посчитай среднее значение"\n• "Найди максимум по категориям"`,
  )
}

const changeFile = () => {
  selectedFile.value = null
  addAssistantMessage('Выберите другой файл для анализа.')
}

const sendMessage = () => {
  if (!inputMessage.value.trim() || isTyping.value || !selectedFile.value) {
    return
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
  isTyping.value = true

  emit('bi-query', {
    fileId: selectedFile.value.id,
    question: messageText,
  })

  scrollToBottom()
}

const addAssistantMessage = (content, data = null) => {
  const assistantMessage = {
    id: messageIdCounter++,
    type: 'assistant',
    content: content,
    data: data,
    timestamp: new Date(),
  }

  messages.value.push(assistantMessage)
  isTyping.value = false
  scrollToBottom()
}

const updateStreamingMessage = (messageId, updates) => {
  isTyping.value = false
  
  let message = messages.value.find(m => m.id === messageId)
  
  if (!message) {
    message = {
      id: messageId,
      type: 'assistant',
      content: '',
      streaming: true,
      stage: '',
      sql: '',
      sqlGenerating: '',
      data: null,
      error: null,
      timestamp: new Date(),
    }
    messages.value.push(message)
  }
  
  Object.assign(message, updates)
  
  scrollToBottom()
}

const finalizeStreamingMessage = (messageId) => {
  const message = messages.value.find(m => m.id === messageId)
  
  if (message) {
    message.streaming = false
    message.stage = ''
  }
  
  isTyping.value = false
  scrollToBottom()
}

const setTyping = (typing) => {
  isTyping.value = typing
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

watch(
  () => messages.value.length,
  () => {
    scrollToBottom()
  },
)

watch(
  () => props.isVisible,
  async (newValue) => {
    if (newValue && !ollamaChecked.value) {
      ollamaChecked.value = true
      await checkOllamaConnection()
    }
  },
  { immediate: true }
)

const checkOllamaConnection = async () => {
  try {
    isTyping.value = true
    const status = await biClient.checkOllamaStatus()
    
    if (!status.available) {
      addAssistantMessage(
        `**Внимание:** Не удалось подключиться к Ollama.\n\n` +
        `**Что нужно сделать:**\n` +
        `1. Убедитесь, что Ollama установлен и запущен\n` +
        `2. Проверьте доступность Ollama по адресу: http://localhost:11434\n` +
        `3. Установите Ollama: https://ollama.com/download\n\n` +
        `**Текущая ошибка:** ${status.message || 'Неизвестная ошибка'}\n\n` +
        `Без подключения к Ollama анализ данных будет недоступен.`
      )
    }
  } catch (error) {
    console.error('Ошибка проверки Ollama:', error)
    addAssistantMessage(
      `**Ошибка проверки подключения к Ollama:**\n\n${error.message}\n\n` +
      `Пожалуйста, убедитесь, что Ollama запущен и доступен.`
    )
  } finally {
    isTyping.value = false
  }
}

defineExpose({
  addAssistantMessage,
  updateStreamingMessage,
  finalizeStreamingMessage,
  setTyping,
})
</script>

<style scoped>
.assistant-chat {
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  width: auto;
  height: 550px;
  background: linear-gradient(145deg, #ffffff, #f8f9fa);
  border-radius: 12px;
  box-shadow:
    0 12px 40px rgba(220, 53, 69, 0.15),
    0 4px 12px rgba(0, 0, 0, 0.1);
  border: 2px solid rgba(220, 53, 69, 0.1);
  z-index: 9998;
  display: flex;
  flex-direction: column;
  transform: translateY(20px) scale(0.95);
  opacity: 0;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  backdrop-filter: blur(10px);
  margin-bottom: 10px;
}

.assistant-chat--visible {
  transform: translateY(0) scale(1);
  opacity: 1;
}

.assistant-chat__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: linear-gradient(135deg, #dc3545, #c82333);
  border-radius: 12px 12px 0 0;
  color: white;
}

.assistant-chat__title {
  display: flex;
  align-items: center;
  font-weight: 600;
  font-size: 14px;
}

.assistant-chat__controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.control-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: white;
  cursor: pointer;
  transition: all 0.2s ease;
  text-decoration: none;
}

.control-btn:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: scale(1.05);
  color: white;
}

.assistant-chat__connection-selector,
.assistant-chat__file-gallery {
  max-height: 350px;
  overflow-y: auto;
  background: white;
  border-bottom: 1px solid rgba(220, 53, 69, 0.1);
}

.assistant-chat__selected-info {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1rem;
  background: #e7f3ff;
  border-bottom: 1px solid rgba(13, 110, 253, 0.2);
  flex-wrap: wrap;
}

.selected-info-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  font-weight: 500;
  color: #0d6efd;
}

.assistant-chat__messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: linear-gradient(to bottom, #ffffff, #f8f9fa);
}

.assistant-chat__messages::-webkit-scrollbar {
  width: 4px;
}

.assistant-chat__messages::-webkit-scrollbar-track {
  background: rgba(220, 53, 69, 0.1);
  border-radius: 2px;
}

.assistant-chat__messages::-webkit-scrollbar-thumb {
  background: linear-gradient(to bottom, #dc3545, #c82333);
  border-radius: 2px;
}

.assistant-chat__input {
  padding: 16px;
  border-top: 1px solid rgba(220, 53, 69, 0.1);
  background: linear-gradient(145deg, #f8f9fa, #ffffff);
  border-radius: 0 0 12px 12px;
}

.assistant-chat__input .form-control {
  border: 2px solid rgba(220, 53, 69, 0.2);
  border-right: none;
  border-radius: 8px 0 0 8px;
  padding: 10px 14px;
  transition: all 0.3s ease;
  font-size: 14px;
}

.assistant-chat__input .form-control:focus {
  box-shadow: 0 0 0 0.2rem rgba(220, 53, 69, 0.25);
  border-color: #dc3545;
}

.assistant-chat__input .btn {
  border-radius: 0 8px 8px 0;
  border: 2px solid #dc3545;
  padding: 10px 16px;
  transition: all 0.3s ease;
}

.assistant-chat__input .btn:hover {
  background: linear-gradient(135deg, #e74c3c, #dc3545);
  transform: scale(1.02);
}

@media (max-width: 1200px) {
  .assistant-chat {
    position: fixed;
    bottom: 20px;
    left: 20px;
    right: 20px;
    width: auto;
    height: 400px;
    margin-bottom: 0;
  }
}
</style>
