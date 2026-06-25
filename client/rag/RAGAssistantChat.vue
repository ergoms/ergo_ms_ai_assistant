<template>
  <div 
    v-if="isVisible" 
    class="neural-chat neural-chat--visible"
    :class="{ 'neural-chat--light': isLightTheme }"
  >
    <!-- Заголовок -->
    <div class="neural-chat__header">
      <div class="neural-chat__brand">
        <div class="brand-icon">
          <Sparkles :size="18" />
          <div class="brand-icon__ring"></div>
        </div>
        <div class="brand-text">
          <span class="brand-title">NEURAL</span>
          <span class="brand-subtitle">AI Ассистент</span>
        </div>
      </div>
      <div class="neural-chat__controls">
        <router-link 
          to="/ai-assistant" 
          class="control-btn" 
          title="Открыть AI Hub"
        >
          <ExternalLink :size="16" />
        </router-link>
      </div>
    </div>

    <!-- Сообщения -->
    <div ref="messagesContainer" class="neural-chat__messages">
      <AssistantMessage 
        v-for="message in messages" 
        :key="message.id" 
        :message="message"
        :class="{ 'streaming': message.isStreaming }"
      />
      <AssistantTyping v-if="isTyping && !hasStreamingContent" />
    </div>

    <!-- Ввод -->
    <div class="neural-chat__input">
      <div class="input-container">
        <div class="input-glow"></div>
        <input
          v-model="inputMessage"
          type="text"
          class="input-field"
          placeholder="Задайте вопрос..."
          @keypress.enter="sendMessage"
          :disabled="isTyping"
        />
        <button
          class="send-btn"
          @click="sendMessage"
          :disabled="!inputMessage.trim() || isTyping"
        >
          <Send :size="18" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch, computed, onMounted, onUnmounted } from 'vue'
import { Send, Sparkles, ExternalLink } from 'lucide-vue-next'
import AssistantMessage from '../base/AssistantMessage.vue'
import AssistantTyping from '../base/AssistantTyping.vue'
import { ragClient } from './js/rag-client.js'
import { logError } from '@/js/utils/logError.js'

const props = defineProps({
  isVisible: {
    type: Boolean,
    default: false,
  },
})

// Синхронизация с общей темой приложения
const getSystemTheme = () => {
  const theme = localStorage.getItem('theme') || 'auto'
  if (theme === 'auto') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  return theme
}

const isLightTheme = ref(getSystemTheme() === 'light')

const updateTheme = () => {
  isLightTheme.value = getSystemTheme() === 'light'
}

let themeObserver = null

onMounted(() => {
  // Наблюдаем за изменениями data-bs-theme
  themeObserver = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.attributeName === 'data-bs-theme') {
        updateTheme()
      }
    })
  })
  
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-bs-theme']
  })
  
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', updateTheme)
})

onUnmounted(() => {
  if (themeObserver) {
    themeObserver.disconnect()
  }
  window.matchMedia('(prefers-color-scheme: dark)').removeEventListener('change', updateTheme)
})

const messagesContainer = ref(null)
const inputMessage = ref('')
const isTyping = ref(false)
const ollamaChecked = ref(false)

let messageIdCounter = 1

const messages = ref([
  {
    id: messageIdCounter++,
    type: 'assistant',
    content:
      'Привет! Я ваш AI ассистент.\n\n**Чем могу помочь:**\n• Ответить на вопросы\n• Помочь с навигацией\n• Объяснить функционал системы\n\nЗадайте вопрос, и я постараюсь помочь!',
    timestamp: new Date(),
  },
])

// Проверяем, есть ли контент в streaming сообщении
const hasStreamingContent = computed(() => {
  const streamingMsg = messages.value.find(m => m.isStreaming)
  return streamingMsg && streamingMsg.content && streamingMsg.content.length > 0
})

// ID текущего streaming сообщения
let streamingMessageId = null

const sendMessage = async () => {
  if (!inputMessage.value.trim() || isTyping.value) {
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

  scrollToBottom()

  // Создаём пустое сообщение ассистента для streaming
  streamingMessageId = messageIdCounter++
  const streamingMessage = {
    id: streamingMessageId,
    type: 'assistant',
    content: '',
    timestamp: new Date(),
    isStreaming: true,
  }
  messages.value.push(streamingMessage)

  try {
    await ragClient.sendMessageStream(
      messageText,
      // onChunk - добавляем текст по мере поступления
      (chunk) => {
        const msg = messages.value.find(m => m.id === streamingMessageId)
        if (msg) {
          msg.content += chunk
          scrollToBottom()
        }
      },
      // onDone - завершаем streaming
      (fullResponse) => {
        const msg = messages.value.find(m => m.id === streamingMessageId)
        if (msg) {
          msg.content = fullResponse
          msg.isStreaming = false
        }
        isTyping.value = false
        streamingMessageId = null
      },
      // onError - обрабатываем ошибку
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
      },
      null, // ollamaConfig
      null, // sessionId
      'chat' // module
    )
  } catch (error) {
    logError('Ошибка отправки сообщения:', error)
    
    const errorMessage = 
      error.response?.data?.error ||
      error.response?.data?.message ||
      error.message ||
      'Не удалось отправить сообщение'
    
    const msg = messages.value.find(m => m.id === streamingMessageId)
    if (msg) {
      msg.content = `**Ошибка подключения:** ${errorMessage}`
      msg.isStreaming = false
    }
    isTyping.value = false
    streamingMessageId = null
  }
}

const addAssistantMessage = (content) => {
  const assistantMessage = {
    id: messageIdCounter++,
    type: 'assistant',
    content: content,
    timestamp: new Date(),
  }

  messages.value.push(assistantMessage)
  scrollToBottom()
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
    const status = await ragClient.checkOllamaStatus()
    
    if (!status.available) {
      addAssistantMessage(
        `**Внимание:** Не удалось подключиться к Ollama.\n\n` +
        `**Что нужно сделать:**\n` +
        `1. Убедитесь, что Ollama установлен и запущен\n` +
        `2. Проверьте доступность Ollama по адресу: http://localhost:11434\n` +
        `3. Установите Ollama: https://ollama.com/download\n\n` +
        `**Текущая ошибка:** ${status.message || 'Неизвестная ошибка'}\n\n` +
        `Без подключения к Ollama я не смогу отвечать на ваши вопросы.`
      )
    }
  } catch (error) {
    logError('Ошибка проверки Ollama:', error)
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
})
</script>

<style scoped lang="scss">
@import '../styles/variables';

.neural-chat {
  // CSS переменные для тем
  --nc-bg-base: #{$dark-bg-secondary};
  --nc-bg-panel: #{$dark-bg-tertiary};
  --nc-bg-elevated: #{$dark-bg-elevated};
  --nc-border: #{$dark-border};
  --nc-text-primary: #{$dark-text-primary};
  --nc-text-muted: #{$dark-text-muted};
  --nc-accent: #{$neon-cyan};
  --nc-accent-secondary: #{$neon-purple};
  --nc-glow: #{rgba($neon-cyan, 0.4)};
  
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  width: auto;
  height: 550px;
  background: var(--nc-bg-panel);
  border-radius: $radius-xl;
  box-shadow:
    0 0 40px var(--nc-glow),
    0 20px 60px rgba(0, 0, 0, 0.5),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);
  border: 1px solid var(--nc-border);
  z-index: 9998;
  display: flex;
  flex-direction: column;
  backdrop-filter: blur(20px);
  margin-bottom: 10px;
  overflow: hidden;
  transition: $transition-base;
  
  // Светлая тема
  &--light {
    --nc-bg-base: #{$light-bg-primary};
    --nc-bg-panel: #{$light-bg-secondary};
    --nc-bg-elevated: #{$light-bg-tertiary};
    --nc-border: #{$light-border};
    --nc-text-primary: #{$light-text-primary};
    --nc-text-muted: #{$light-text-muted};
    --nc-accent: #0f768a;
    --nc-accent-secondary: #7c3aed;
    --nc-glow: #{rgba(#0f768a, 0.2)};
    
    box-shadow:
      0 0 30px var(--nc-glow),
      0 10px 40px rgba(0, 0, 0, 0.1);
  }
}

// Заголовок
.neural-chat__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $spacing-md $spacing-lg;
  background: linear-gradient(
    135deg,
    rgba($neon-cyan, 0.1) 0%,
    rgba($neon-purple, 0.05) 100%
  );
  border-bottom: 1px solid var(--nc-border);
  
  .neural-chat--light & {
    background: linear-gradient(
      135deg,
      rgba(#0f768a, 0.08) 0%,
      rgba(#7c3aed, 0.04) 100%
    );
  }
}

.neural-chat__brand {
  display: flex;
  align-items: center;
  gap: $spacing-md;
}

.brand-icon {
  position: relative;
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, var(--nc-accent), var(--nc-accent-secondary));
  border-radius: $radius-md;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 0 20px var(--nc-glow);
}

.brand-icon__ring {
  position: absolute;
  inset: -4px;
  border: 1.5px solid var(--nc-accent);
  border-radius: $radius-lg;
  opacity: 0.5;
  animation: ring-rotate 10s linear infinite;
}

@keyframes ring-rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.brand-text {
  display: flex;
  flex-direction: column;
}

.brand-title {
  font-size: $font-size-sm;
  font-weight: $font-weight-bold;
  letter-spacing: $letter-spacing-widest;
  background: linear-gradient(90deg, var(--nc-accent), var(--nc-accent-secondary));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.brand-subtitle {
  font-size: $font-size-xs;
  color: var(--nc-text-muted);
  letter-spacing: $letter-spacing-wide;
}

.neural-chat__controls {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
}

.control-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--nc-border);
  background: rgba($neon-cyan, 0.1);
  border-radius: $radius-md;
  color: var(--nc-accent);
  cursor: pointer;
  transition: $transition-fast;
  text-decoration: none;
  
  .neural-chat--light & {
    background: rgba(#0f768a, 0.1);
  }
}

.control-btn:hover {
  background: rgba($neon-cyan, 0.2);
  border-color: var(--nc-accent);
  box-shadow: 0 0 15px var(--nc-glow);
  color: var(--nc-accent);
}

// Сообщения
.neural-chat__messages {
  flex: 1;
  overflow-y: auto;
  padding: $spacing-md;
  display: flex;
  flex-direction: column;
  gap: $spacing-md;
  background: var(--nc-bg-base);
}

.neural-chat__messages::-webkit-scrollbar {
  width: 4px;
}

.neural-chat__messages::-webkit-scrollbar-track {
  background: rgba($neon-cyan, 0.05);
  border-radius: 2px;
}

.neural-chat__messages::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, var(--nc-accent), var(--nc-accent-secondary));
  border-radius: 2px;
}

// Ввод
.neural-chat__input {
  padding: $spacing-md;
  border-top: 1px solid var(--nc-border);
  background: var(--nc-bg-elevated);
}

.input-container {
  position: relative;
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  background: var(--nc-bg-base);
  border: 1px solid var(--nc-border);
  border-radius: $radius-lg;
  padding: $spacing-xs;
  transition: $transition-base;
  
  &:focus-within {
    border-color: var(--nc-accent);
    box-shadow: 
      0 0 20px var(--nc-glow),
      inset 0 0 20px rgba($neon-cyan, 0.05);
  }
}

.input-glow {
  position: absolute;
  inset: -1px;
  border-radius: calc(#{$radius-lg} + 1px);
  background: linear-gradient(90deg, var(--nc-accent), var(--nc-accent-secondary));
  opacity: 0;
  z-index: -1;
  transition: $transition-base;
  
  .input-container:focus-within & {
    opacity: 0.3;
    filter: blur(8px);
  }
}

.input-field {
  flex: 1;
  min-width: 0; // Позволяет flex элементу сжиматься
  background: transparent;
  border: none;
  padding: $spacing-sm $spacing-md;
  color: var(--nc-text-primary);
  font-size: $font-size-sm;
  outline: none;
  
  &::placeholder {
    color: var(--nc-text-muted);
  }
  
  &:disabled {
    opacity: 0.5;
  }
}

.send-btn {
  flex-shrink: 0; // Кнопка не сжимается
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  min-width: 40px; // Минимальная ширина
  background: linear-gradient(135deg, var(--nc-accent), darken($neon-cyan, 15%));
  border: none;
  border-radius: $radius-md;
  color: $dark-bg-primary;
  cursor: pointer;
  transition: $transition-fast;
  
  .neural-chat--light & {
    color: white;
  }
  
  &:hover:not(:disabled) {
    transform: scale(1.05);
    box-shadow: 0 0 20px var(--nc-glow);
  }
  
  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
}

@media (max-width: $breakpoint-lg) {
  .neural-chat {
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
