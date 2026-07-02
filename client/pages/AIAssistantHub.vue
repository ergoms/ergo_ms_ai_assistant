<template>
  <div class="neural-hub" :class="{ 'neural-hub--light': isLightTheme }">
    <!-- Анимированный нейронный фон -->
    <NeuralBackground 
      :node-count="60" 
      :connection-distance="180"
      :node-color="isLightTheme ? (activeModule === 'docs' ? '#6d28d9' : '#0f768a') : (activeModule === 'docs' ? '#8b5cf6' : '#3ae8ff')"
      :line-color="isLightTheme ? (activeModule === 'docs' ? '#6d28d9' : '#0f768a') : (activeModule === 'docs' ? '#8b5cf6' : '#3ae8ff')"
      :accelerated="isAIGenerating"
    />

    <!-- Боковая панель навигации (только статус) -->
    <aside class="neural-sidebar">
      <div class="sidebar-brand">
      <div class="brand-icon">
        <div class="brand-icon__core">
          <Sparkles :size="22" />
        </div>
      </div>
        <div class="brand-text">
          <span class="brand-title">NEURAL</span>
          <span class="brand-subtitle">ERGO MS</span>
        </div>
      </div>

      <div class="sidebar-status">
        <div class="status-indicator" :class="{ 'status-indicator--online': ollamaOnline }">
          <div class="status-dot"></div>
          <Cpu :size="14" />
          <span class="status-text">{{ currentModel }}</span>
        </div>
      </div>

      <!-- Create Chat Button -->
      <div class="sidebar-actions">
        <button class="create-chat-btn" @click="showChatTypeSelector = true" title="Создать новый чат">
          <Plus :size="16" />
          <span>Создать чат</span>
        </button>
      </div>

      <!-- Chat Sessions List -->
      <div class="sidebar-chat-list">
        <div class="chat-list-header">
          <span class="chat-list-title">Чаты</span>
        </div>
        <div class="chat-list-content">
          <template v-for="module in availableModules" :key="module.id">
            <div 
              v-if="getSessionsByModule(module.id).length > 0" 
              class="chat-list-group"
            >
              <div class="chat-list-group__header">
                <component :is="module.icon" :size="14" />
                <span>{{ module.name }}</span>
                <span class="chat-list-group__count">({{ getSessionsByModule(module.id).length }})</span>
              </div>
              <div 
                v-for="session in getSessionsByModule(module.id)" 
                :key="session.id"
                class="chat-list-item"
                :class="{ 'chat-list-item--active': currentChatSession?.id === session.id }"
                @click="loadChatSession(session.id, session.module)"
              >
                <div class="chat-list-item__icon">
                  <component 
                    :is="module.icon" 
                    :size="16" 
                  />
                </div>
                <div class="chat-list-item__content">
                  <div class="chat-list-item__title">{{ session.title || 'Без названия' }}</div>
                  <div class="chat-list-item__meta">
                    <span class="chat-list-item__time">{{ formatSessionTime(session.updated_at || session.created_at) }}</span>
                  </div>
                </div>
                <button 
                  class="chat-list-item__delete"
                  @click.stop="deleteChatSession(session.id)"
                  title="Удалить чат"
                >
                  <Trash2 :size="14" />
                </button>
              </div>
            </div>
          </template>
          <div v-if="chatSessions.length === 0" class="chat-list-empty">
            <span>Нет чатов</span>
          </div>
        </div>
      </div>
    </aside>

    <!-- Основная область контента -->
    <main class="neural-main">
      <!-- Заголовок модуля -->
      <header class="module-banner" :style="`--banner-color: ${currentModuleConfig?.color}`">
        <div class="banner-decoration">
          <div class="decoration-line"></div>
          <div class="decoration-dot"></div>
        </div>
        
        <div class="banner-content">
          <div class="banner-icon">
            <component :is="currentModuleConfig?.icon" :size="28" />
          </div>
          <div class="banner-info">
            <h1 class="banner-title">{{ currentModuleConfig?.name }}</h1>
            <p class="banner-desc">{{ currentModuleConfig?.description }}</p>
          </div>
        </div>

        <div class="banner-actions">
          <!-- Кнопка загрузки документов для модуля docs -->
          <button 
            v-if="activeModule === 'docs'" 
            class="action-btn action-btn--primary" 
            @click="showDocsUploader = !showDocsUploader"
            title="Загрузить документ"
          >
            <Upload :size="18" />
            <span>Загрузить</span>
          </button>
          
        </div>
      </header>

      <!-- Chat Type Selector Modal -->
      <ChatTypeSelector 
        :show="showChatTypeSelector" 
        @close="showChatTypeSelector = false"
        @select="handleChatTypeSelect"
      />

      <!-- Docs Module -->
      <template v-if="activeModule === 'docs' && !currentModuleConfig?.comingSoon">
        <div class="docs-module-wrapper">
          <DocsAssistantChat 
            ref="docsAssistantChatRef"
            :key="`docs-chat-${docsChatKey}`"
            :is-visible="true" 
            :hide-header="true"
            :force-show-uploader="showDocsUploader"
            @session-updated="handleDocsSessionUpdated"
          />
        </div>
      </template>

      <!-- Coming Soon State -->
      <div v-else-if="currentModuleConfig?.comingSoon" class="coming-soon">
        <div class="coming-soon__visual">
          <div class="coming-soon__icon" :style="{ color: currentModuleConfig?.color }">
            <component :is="currentModuleConfig?.icon" :size="64" />
          </div>
          <div class="coming-soon__particles">
            <span v-for="i in 8" :key="i" class="particle"></span>
          </div>
        </div>
        <h2 class="coming-soon__title">В РАЗРАБОТКЕ</h2>
        <p class="coming-soon__text">Модуль "{{ currentModuleConfig?.name }}" скоро будет доступен</p>
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

      <!-- Chat Module -->
      <template v-else-if="activeModule === 'chat'">
        <div ref="chatMessagesRef" class="messages-area">
          <div class="messages-wrapper">
            <HubMessage 
              v-for="msg in chatHistory" 
              :key="msg.id" 
              :message="msg" 
              :module-config="currentModuleConfig"
            />
            
            <!-- Typing Indicator -->
            <div v-if="chatLoading" class="typing-indicator">
              <!-- Connection line decoration -->
              <div class="message-connector">
                <div class="connector-line"></div>
                <div class="connector-node"></div>
              </div>
              
              <!-- Avatar -->
              <div class="typing-avatar" :style="`--avatar-color: ${currentModuleConfig?.color || '#3ae8ff'}`">
                <div class="avatar-core">
                  <component :is="currentModuleConfig?.icon" :size="20" />
                </div>
                <div class="avatar-ring"></div>
                <div class="avatar-pulse"></div>
              </div>
              
              <!-- Content -->
              <div class="typing-content">
                <div class="typing-text">Генерация ответа</div>
                <div class="typing-dots">
                  <span></span><span></span><span></span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="input-area">
          <!-- Suggestion Chips -->
          <div class="suggestions" v-if="chatHistory.length <= 1">
            <button 
              v-for="s in currentModuleConfig?.suggestions" 
              :key="s" 
              class="suggestion-chip"
              @click="sendChatMessage(s)"
            >
              <Zap :size="14" />
              <span>{{ s }}</span>
            </button>
          </div>

          <!-- Input Container -->
          <div class="input-container">
            <div class="input-decoration">
              <div class="input-corner input-corner--tl"></div>
              <div class="input-corner input-corner--tr"></div>
              <div class="input-corner input-corner--bl"></div>
              <div class="input-corner input-corner--br"></div>
            </div>
            
            <input
              ref="chatFileInputRef"
              type="file"
              class="file-input-hidden"
              accept=".pdf,.doc,.docx,.txt"
              multiple
              @change="handleChatFileSelect"
              style="display: none"
            />
            
            <button
              class="file-btn"
              :style="{ '--btn-color': currentModuleConfig?.color }"
              @click="triggerChatFileInput"
              :disabled="chatLoading"
              title="Загрузить файл"
            >
              <Upload :size="18" />
            </button>
            
            <textarea
              v-model="chatInput"
              class="input-field"
              :placeholder="currentModuleConfig?.settings?.placeholder"
              @keydown.enter.exact.prevent="sendChatMessage()"
              :disabled="chatLoading"
              rows="1"
              ref="chatInputRef"
            ></textarea>
            
            <button 
              class="send-btn"
              :style="{ '--btn-color': currentModuleConfig?.color }"
              @click="sendChatMessage()"
              :disabled="!chatInput.trim() || chatLoading"
            >
              <div class="send-btn__bg"></div>
              <Send :size="20" />
            </button>
          </div>
          
          <!-- File Info -->
          <div v-if="chatSelectedFiles.length > 0" class="files-section">
            <div class="files-list">
              <div 
                v-for="(file, index) in chatSelectedFiles" 
                :key="index"
                class="file-info"
              >
                <span class="file-name">{{ file.name }}</span>
                <button class="file-remove" @click="removeChatFile(index)" title="Удалить файл">
                  <X :size="14" />
                </button>
              </div>
            </div>
            
            <!-- Vectorization Toggle -->
            <div class="vectorization-toggle">
              <label class="toggle-label">
                <input
                  type="checkbox"
                  v-model="enableVectorization"
                  class="toggle-checkbox"
                />
                <span class="toggle-text">Векторизация файлов</span>
                <span class="toggle-hint">Использовать векторный поиск для более точных ответов</span>
              </label>
            </div>
          </div>
        </div>
      </template>

      <!-- BI Module -->
      <template v-else-if="activeModule === 'bi'">
        <!-- Connection Selection -->
        <div v-if="!selectedConnection" class="file-selector">
          <div class="file-header">
            <Database :size="24" />
            <div>
              <h3>Выберите подключение</h3>
              <p>Выберите подключение для анализа данных с помощью AI</p>
            </div>
          </div>
          
          <div class="file-grid">
            <div 
              v-for="connection in connections" 
              :key="connection.id"
              class="file-card"
              @click="selectConnection(connection)"
            >
              <div class="file-card__icon">
                <Database :size="28" />
              </div>
              <div class="file-card__info">
                <span class="file-card__name">{{ connection.name }}</span>
                <span class="file-card__meta">{{ connection.connector_type_display || connection.connector_type }}</span>
              </div>
              <div class="file-card__action">
                <ArrowRight :size="18" />
              </div>
            </div>

            <div v-if="connections.length === 0" class="file-empty">
              <FileQuestion :size="56" />
              <h4>Нет подключений</h4>
              <p>Создайте подключение для начала анализа</p>
              <router-link to="/bi/connections/new" class="upload-link">
                <Upload :size="18" />
                <span>Создать подключение</span>
              </router-link>
            </div>
          </div>
        </div>

        <!-- File Selection -->
        <div v-else-if="!selectedFile" class="file-selector">
          <div class="file-header">
            <Database :size="24" />
            <div>
              <h3>Выберите файл</h3>
              <p>Подключение: {{ selectedConnection.name }}</p>
            </div>
            <button class="btn btn-sm btn-outline-secondary ms-auto" @click="selectedConnection = null">
              <X :size="14" class="me-1" />
              Сменить подключение
            </button>
          </div>
          
          <div class="file-grid">
            <div 
              v-for="file in files" 
              :key="file.id"
              class="file-card"
              @click="selectFile(file)"
            >
              <div class="file-card__icon">
                <FileSpreadsheet :size="28" />
              </div>
              <div class="file-card__info">
                <span class="file-card__name">{{ file.name }}</span>
                <span class="file-card__meta">{{ file.file_type || 'file' }}</span>
              </div>
              <div class="file-card__action">
                <ArrowRight :size="18" />
              </div>
            </div>

            <div v-if="files.length === 0" class="file-empty">
              <FileQuestion :size="56" />
              <h4>Нет файлов</h4>
              <p>В этом подключении нет файлов</p>
            </div>
          </div>
        </div>

        <!-- BI Chat -->
        <template v-else>
          <div class="selected-source">
            <div class="source-info">
              <Database :size="16" />
              <span>{{ selectedConnection.name }}</span>
              <span class="source-separator">/</span>
              <FileSpreadsheet :size="16" />
              <span>{{ selectedFile.name }}</span>
            </div>
            <button class="source-change" @click="selectedFile = null">
              <X :size="16" />
              <span>Сменить</span>
            </button>
          </div>

          <div ref="biMessagesRef" class="messages-area">
            <div class="messages-wrapper">
              <HubMessage 
                v-for="msg in biHistory" 
                :key="msg.id" 
                :message="msg" 
                :module-config="currentModuleConfig"
              />
              
              <div v-if="biLoading" class="typing-indicator">
                <!-- Connection line decoration -->
                <div class="message-connector">
                  <div class="connector-line"></div>
                  <div class="connector-node"></div>
                </div>
                
                <!-- Avatar -->
                <div class="typing-avatar" :style="`--avatar-color: ${currentModuleConfig?.color || '#3ae8ff'}`">
                  <div class="avatar-core">
                    <component :is="currentModuleConfig?.icon" :size="20" />
                  </div>
                  <div class="avatar-ring"></div>
                  <div class="avatar-pulse"></div>
                </div>
                
                <!-- Content -->
                <div class="typing-content">
                  <div class="typing-text">Анализ данных</div>
                  <div class="typing-dots">
                    <span></span><span></span><span></span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="input-area">
            <div class="suggestions" v-if="biHistory.length <= 1">
              <button 
                v-for="s in currentModuleConfig?.suggestions" 
                :key="s" 
                class="suggestion-chip"
                @click="sendBIMessage(s)"
              >
                <Zap :size="14" />
                <span>{{ s }}</span>
              </button>
            </div>

            <div class="input-container">
              <div class="input-decoration">
                <div class="input-corner input-corner--tl"></div>
                <div class="input-corner input-corner--tr"></div>
                <div class="input-corner input-corner--bl"></div>
                <div class="input-corner input-corner--br"></div>
              </div>
              
              <textarea
                v-model="biInput"
                class="input-field"
                :placeholder="currentModuleConfig?.settings?.placeholder"
                @keydown.enter.exact.prevent="sendBIMessage()"
                :disabled="biLoading"
                rows="1"
              ></textarea>
              
              <button 
                class="send-btn"
                :style="{ '--btn-color': currentModuleConfig?.color }"
                @click="sendBIMessage()"
                :disabled="!biInput.trim() || biLoading"
              >
                <div class="send-btn__bg"></div>
                <Send :size="20" />
              </button>
            </div>
          </div>
        </template>
      </template>

    </main>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { 
  Sparkles, Cpu, Send, Zap, ArrowRight,
  Database, FileSpreadsheet, FileQuestion, Upload, X, Plus, Trash2
} from 'lucide-vue-next'
import { modules, getModuleById } from '../modules/index.js'
import NeuralBackground from '../components/NeuralBackground.vue'
import HubMessage from '../components/HubMessage.vue'
import ChatTypeSelector from '../components/ChatTypeSelector.vue'
import DocsAssistantChat from '../docs/DocsAssistantChat.vue'
import { ragClient } from '../rag/js/rag-client.js'
import { biClient } from '../bi/js/bi-client.js'
import { useToast } from '@/js/utils/toast.js'

import { useThemeMode } from '@/composables/useThemeMode.js'

const { isLight: isLightTheme } = useThemeMode()

// Module state
const activeModule = ref('chat')
const currentModuleConfig = computed(() => getModuleById(activeModule.value))

// Вычисляем, генерирует ли AI ответ сейчас (для ускорения нейронного фона)
const isAIGenerating = computed(() => {
  // Проверяем загрузку в чате или BI
  if (chatLoading.value || biLoading.value) return true
  
  // Проверяем есть ли сообщения в режиме streaming
  const hasChatStreaming = chatHistory.value.some(msg => msg.streaming)
  const hasBiStreaming = biHistory.value.some(msg => msg.streaming)
  
  return hasChatStreaming || hasBiStreaming
})


// Ollama status
const currentModel = ref('Загрузка...')
const ollamaOnline = ref(false)

// Chat state
const chatMessagesRef = ref(null)
const chatInputRef = ref(null)
const chatFileInputRef = ref(null)
const chatInput = ref('')
const chatLoading = ref(false)
let chatMsgId = 1
const chatHistory = ref([])
const currentChatSession = ref(null)
const chatSessions = ref([])
const chatSelectedFiles = ref([])
const enableVectorization = ref(false)
const toast = useToast()

// BI state
const biMessagesRef = ref(null)
const biInput = ref('')
const biLoading = ref(false)
const selectedConnection = ref(null)
const selectedFile = ref(null)
const connections = ref([])
const files = ref([])
let biMsgId = 1
const biHistory = ref([])

// Docs state
const showDocsUploader = ref(false)
const docsAssistantChatRef = ref(null)
const docsChatKey = ref(0) // Ключ для принудительного пересоздания компонента

// Chat type selector modal
const showChatTypeSelector = ref(false)

// Available modules for selector
const availableModules = computed(() => {
  return modules.filter(m => !m.comingSoon)
})

// Initialize chat with welcome message
const initChat = (session = null) => {
  const config = getModuleById('chat')
  if (session && session.messages && session.messages.length > 0) {
    // Загружаем сообщения из сессии
    chatHistory.value = session.messages.map(msg => ({
      id: msg.id,
      type: msg.type,
      content: msg.content,
      timestamp: msg.created_at,
      processing_time_ms: msg.processing_time_ms,
      request_started_at: msg.request_started_at,
      response_received_at: msg.response_received_at,
      skill_name: msg.metadata?.skill_name || null,
      skill_call: msg.metadata?.skill_call || null,
      chart_config: msg.metadata?.chart_config || null,
      metadata: msg.metadata || {},
    }))
  } else {
    chatHistory.value = [{
      id: chatMsgId++,
      type: 'assistant',
      content: config?.settings?.welcomeMessage || 'Привет! Чем могу помочь?',
      timestamp: new Date(),
    }]
  }
}

// Load chat sessions for all modules
const loadChatSessions = async () => {
  // Загружаем сессии для всех модулей
  const allSessions = []
  for (const module of availableModules.value) {
    const result = await ragClient.getChatSessions(module.id)
    if (result.success && result.sessions) {
      allSessions.push(...result.sessions)
    }
  }
  // Сортируем по дате обновления (новые сверху)
  chatSessions.value = allSessions.sort((a, b) => {
    const dateA = new Date(a.updated_at || a.created_at || 0)
    const dateB = new Date(b.updated_at || b.created_at || 0)
    return dateB.getTime() - dateA.getTime()
  })
}

// Получить сессии для конкретного модуля
const getSessionsByModule = (moduleId) => {
  return chatSessions.value.filter(session => session.module === moduleId)
}

// Форматировать время сессии
const formatSessionTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  
  if (diffMins < 1) return 'только что'
  if (diffMins < 60) return `${diffMins} мин назад`
  if (diffHours < 24) return `${diffHours} ч назад`
  if (diffDays < 7) return `${diffDays} дн назад`
  
  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
  })
}

// Удалить сессию чата
const deleteChatSession = async (sessionId) => {
  try {
    const result = await ragClient.deleteChatSession(sessionId)
    if (result.success) {
      // Удаляем из локального списка
      chatSessions.value = chatSessions.value.filter(s => s.id !== sessionId)
      
      // Если удаляемая сессия была активной, очищаем текущую сессию
      if (currentChatSession.value?.id === sessionId) {
        currentChatSession.value = null
        if (activeModule.value === 'chat') {
          initChat()
        } else if (activeModule.value === 'docs') {
          docsChatKey.value++
        }
      }
      
      toast.success('Чат удален')
    } else {
      toast.error(result.error || 'Не удалось удалить чат')
    }
  } catch (error) {
    logError('Ошибка удаления чата:', error)
    toast.error('Ошибка удаления чата')
  }
}

// Load specific chat session (kept for BI module compatibility)
const loadChatSession = async (sessionId, moduleId = null) => {
  const result = await ragClient.getChatSession(sessionId)
  if (result.success) {
    currentChatSession.value = { id: sessionId, ...result.session }
    const sessionModule = moduleId || result.session.module || 'chat'
    
    // Переключаемся на модуль чата, если он указан
    if (sessionModule !== activeModule.value) {
      activeModule.value = sessionModule
    }
    
    if (sessionModule === 'bi') {
      // Восстанавливаем файл и подключение из metadata сессии
      if (result.session.metadata && result.session.metadata.file_id) {
        const fileId = result.session.metadata.file_id
        
        // Загружаем подключения, если еще не загружены
        if (connections.value.length === 0) {
          await loadConnections()
        }
        
        // Ищем файл во всех подключениях
        let foundFile = null
        let foundConnection = null
        
        for (const conn of connections.value) {
          const connFiles = await biClient.getConnectionFiles(conn.id)
          if (connFiles.success && connFiles.files) {
            foundFile = connFiles.files.find(f => f.id === fileId)
            if (foundFile) {
              foundConnection = conn
              break
            }
          }
        }
        
        // Если файл найден, устанавливаем его
        if (foundFile && foundConnection) {
          selectedConnection.value = foundConnection
          selectedFile.value = foundFile
          await loadFiles() // Загружаем файлы для выбранного подключения
        } else {
          // Если файл не найден, показываем предупреждение
          toast.warning('Файл из истории не найден. Возможно, он был удален.')
        }
      }
      
      // Загружаем историю для BI модуля
      biHistory.value = result.messages.map(msg => {
        const biMsg = {
          id: msg.id,
          type: msg.type,
          content: msg.content,
          timestamp: msg.created_at,
          processing_time_ms: msg.processing_time_ms,
          request_started_at: msg.request_started_at,
          response_received_at: msg.response_received_at,
          skill_name: msg.metadata?.skill_name || null,
          skill_call: msg.metadata?.skill_call || null,
          chart_config: msg.metadata?.chart_config || null,
          metadata: msg.metadata || {},
        }
        // Добавляем BI-специфичные поля из metadata
        if (msg.metadata) {
          if (msg.metadata.sql) biMsg.sql = msg.metadata.sql
          if (msg.metadata.data) biMsg.data = { 
            data: msg.metadata.data,
            rows: msg.metadata.rows,
            columns: msg.metadata.columns,
          }
          if (msg.metadata.document) biMsg.document = msg.metadata.document
          if (msg.metadata.chart_config) biMsg.chart_config = msg.metadata.chart_config
        }
        return biMsg
      })
      scrollToBottom(biMessagesRef)
    } else {
      // Загружаем историю для обычного чата
      initChat({ messages: result.messages })
      scrollToBottom(chatMessagesRef)
    }
  } else {
    toast.error(result.error || 'Не удалось загрузить чат')
  }
}

// Handle chat type selection from modal
const handleChatTypeSelect = async (moduleId) => {
  try {
    const module = getModuleById(moduleId)
    if (!module) {
      toast.error('Модуль не найден')
      return
    }

    // Создаем новую сессию для выбранного модуля
    const title = `Новый чат: ${module.name}`
    const result = await ragClient.createChatSession(title, moduleId)
    
    if (result.success) {
      // Переключаемся на выбранный модуль
      activeModule.value = moduleId
      
      // Устанавливаем текущую сессию
      currentChatSession.value = {
        id: result.session.id,
        module: moduleId,
      }
      
      // Инициализируем чат в зависимости от модуля
      if (moduleId === 'chat') {
        initChat()
      } else if (moduleId === 'bi') {
        biHistory.value = []
      } else if (moduleId === 'docs') {
        docsChatKey.value++
        nextTick(() => {
          if (docsAssistantChatRef.value && typeof docsAssistantChatRef.value.resetChat === 'function') {
            docsAssistantChatRef.value.resetChat()
          }
        })
      }
      
      // Обновляем список чатов после создания
      await loadChatSessions()
    } else {
      toast.error(result.error || 'Не удалось создать чат')
    }
  } catch (error) {
    logError('Ошибка создания чата:', error)
    toast.error('Ошибка создания чата')
  }
}


// Scroll helpers
const scrollToBottom = (container) => {
  nextTick(() => {
    if (container?.value) {
      container.value.scrollTop = container.value.scrollHeight
    }
  })
}

// Chat methods
let chatStreamingMsgId = null

const sendChatMessage = async (text) => {
  const messageText = text || chatInput.value.trim()
  if (!messageText || chatLoading.value) return

  chatHistory.value.push({ 
    id: chatMsgId++, 
    type: 'user', 
    content: messageText,
    timestamp: new Date(),
  })
  chatInput.value = ''
  chatLoading.value = true
  chatStreamingMsgId = null
  scrollToBottom(chatMessagesRef)

  try {
    await ragClient.sendMessageStream(
      messageText,
      (chunk) => {
        if (!chatStreamingMsgId) {
          chatStreamingMsgId = chatMsgId++
          chatHistory.value.push({
            id: chatStreamingMsgId,
            type: 'assistant',
            content: chunk,
            timestamp: new Date(),
            streaming: true,
          })
          chatLoading.value = false
        } else {
          const msg = chatHistory.value.find(m => m.id === chatStreamingMsgId)
          if (msg) {
            msg.content += chunk
          }
        }
        scrollToBottom(chatMessagesRef)
      },
      (fullResponse, metadata) => {
        if (chatStreamingMsgId) {
          const msg = chatHistory.value.find(m => m.id === chatStreamingMsgId)
          if (msg) {
            if (fullResponse) msg.content = fullResponse
            msg.streaming = false
            if (metadata) {
              msg.processing_time_ms = metadata.processing_time_ms
              msg.timestamp = metadata.timestamp ? new Date(metadata.timestamp) : new Date()
              msg.skill_name = metadata.skill_name || null
              msg.skill_call = metadata.skill_call || null
              msg.chart_config = metadata.chart_config || null
              msg.metadata = metadata
            }
          }
        } else if (fullResponse) {
          chatHistory.value.push({
            id: chatMsgId++,
            type: 'assistant',
            content: fullResponse,
            timestamp: metadata?.timestamp ? new Date(metadata.timestamp) : new Date(),
            processing_time_ms: metadata?.processing_time_ms,
            skill_name: metadata?.skill_name || null,
            skill_call: metadata?.skill_call || null,
            chart_config: metadata?.chart_config || null,
            metadata: metadata || {},
          })
        }
        
        // Обновляем session_id если он был создан
        if (metadata?.session_id) {
          currentChatSession.value = { id: metadata.session_id }
          loadChatSessions()
        }
        
        chatLoading.value = false
        chatStreamingMsgId = null
        // Очищаем выбранные файлы после отправки
        chatSelectedFiles.value = []
        if (chatFileInputRef.value) {
          chatFileInputRef.value.value = ''
        }
        scrollToBottom(chatMessagesRef)
      },
      (errorMsg) => {
        if (chatStreamingMsgId) {
          const msg = chatHistory.value.find(m => m.id === chatStreamingMsgId)
          if (msg) {
            msg.content += `\n\nОшибка: ${errorMsg}`
            msg.streaming = false
          }
        } else {
          chatHistory.value.push({
            id: chatMsgId++,
            type: 'assistant',
            content: `Ошибка: ${errorMsg}`,
            timestamp: new Date(),
          })
        }
        chatLoading.value = false
        chatStreamingMsgId = null
        scrollToBottom(chatMessagesRef)
      },
      null, // ollamaConfig
      currentChatSession.value?.id, // sessionId
      activeModule.value, // module
      chatSelectedFiles.value.length > 0 ? chatSelectedFiles.value : null, // files
      enableVectorization.value // enableVectorization
    )
  } catch (e) {
    if (chatStreamingMsgId) {
      const msg = chatHistory.value.find(m => m.id === chatStreamingMsgId)
      if (msg) {
        msg.content += `\n\nОшибка: ${e.message}`
        msg.streaming = false
      }
    } else {
      chatHistory.value.push({
        id: chatMsgId++,
        type: 'assistant',
        content: `Ошибка: ${e.message}`,
        timestamp: new Date(),
      })
    }
    chatLoading.value = false
    chatStreamingMsgId = null
    scrollToBottom(chatMessagesRef)
  }
}

// Chat file methods
const triggerChatFileInput = () => {
  if (chatFileInputRef.value) {
    chatFileInputRef.value.click()
  }
}

const handleChatFileSelect = (event) => {
  const files = Array.from(event.target.files || [])
  if (files.length === 0) return
  
  const allowedTypes = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain']
  const allowedExtensions = ['.pdf', '.doc', '.docx', '.txt']
  const maxSize = 10 * 1024 * 1024 // 10 МБ
  
  const validFiles = []
  const errors = []
  
  files.forEach((file) => {
    const fileExtension = '.' + file.name.split('.').pop().toLowerCase()
    
    // Проверяем тип файла
    if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(fileExtension)) {
      errors.push(`"${file.name}" - неподдерживаемый тип файла`)
      return
    }
    
    // Проверяем размер файла
    if (file.size > maxSize) {
      errors.push(`"${file.name}" - файл слишком большой (максимум 10 МБ)`)
      return
    }
    
    // Проверяем, не добавлен ли уже такой файл
    if (chatSelectedFiles.value.some(f => f.name === file.name && f.size === file.size)) {
      errors.push(`"${file.name}" - файл уже добавлен`)
      return
    }
    
    validFiles.push(file)
  })
  
  // Показываем ошибки, если есть
  if (errors.length > 0) {
    toast.error(errors.join('\n'))
  }
  
  // Добавляем валидные файлы
  if (validFiles.length > 0) {
    chatSelectedFiles.value.push(...validFiles)
    const fileNames = validFiles.map(f => f.name).join(', ')
    toast.success(`Загружено файлов: ${validFiles.length}. ${fileNames}`)
  }
  
  // Очищаем input для возможности повторной загрузки тех же файлов
  if (chatFileInputRef.value) {
    chatFileInputRef.value.value = ''
  }
}

const removeChatFile = (index) => {
  if (index >= 0 && index < chatSelectedFiles.value.length) {
    chatSelectedFiles.value.splice(index, 1)
  }
}

// BI methods
const loadConnections = async () => {
  try {
    const result = await biClient.getConnections()
    if (result.success) connections.value = result.connections
  } catch (e) {
    logError('Ошибка загрузки подключений:', e)
  }
}

const loadFiles = async () => {
  if (!selectedConnection.value) {
    files.value = []
    return
  }
  try {
    const result = await biClient.getConnectionFiles(selectedConnection.value.id)
    if (result.success) files.value = result.files
  } catch (e) {
    logError('Ошибка загрузки файлов:', e)
    files.value = []
  }
}

const selectConnection = (connection) => {
  selectedConnection.value = connection
  selectedFile.value = null
  files.value = []
  loadFiles()
}

const selectFile = async (file) => {
  selectedFile.value = file
  
  // Загружаем историю чатов для этого файла (BI модуль)
  const result = await ragClient.getChatSessions('bi')
  if (result.success && result.sessions) {
    // Ищем сессию для этого файла
    const fileSession = result.sessions.find(s => 
      s.metadata?.file_id === file.id || s.title?.includes(file.name)
    )
    
    if (fileSession) {
      // Загружаем существующую сессию
      await loadChatSession(fileSession.id, 'bi')
      currentChatSession.value = { id: fileSession.id, ...fileSession }
    } else {
      // Создаем новую сессию
      currentChatSession.value = null
      biHistory.value = [{
        id: biMsgId++,
        type: 'assistant',
        content: `Файл **${file.name}** из подключения **${selectedConnection.value.name}** выбран для анализа. Задайте вопрос к данным.`,
        timestamp: new Date(),
      }]
    }
  } else {
    // Если не удалось загрузить, показываем приветственное сообщение
    currentChatSession.value = null
    biHistory.value = [{
      id: biMsgId++,
      type: 'assistant',
      content: `Файл **${file.name}** из подключения **${selectedConnection.value.name}** выбран для анализа. Задайте вопрос к данным.`,
      timestamp: new Date(),
    }]
  }
}

const sendBIMessage = async (text) => {
  const messageText = text || biInput.value.trim()
  if (!messageText || biLoading.value || !selectedFile.value) return

  biHistory.value.push({ 
    id: biMsgId++, 
    type: 'user', 
    content: messageText,
    timestamp: new Date(),
  })
  biInput.value = ''
  biLoading.value = true
  scrollToBottom(biMessagesRef)

  const responseId = biMsgId++

  try {
    await biClient.askQuestionStream(
      selectedFile.value.id, 
      messageText, 
      true, 
      null, 
      (event) => {
        let msg = biHistory.value.find(m => m.id === responseId)
        if (!msg) {
          msg = { 
            id: responseId, 
            type: 'assistant', 
            content: '', 
            sql: null, 
            data: null, 
            stage: '',
            timestamp: new Date(),
            streaming: true,
          }
          biHistory.value.push(msg)
          biLoading.value = false
        }

        switch (event.type) {
          case 'stage':
            msg.stage = event.message || event.text || ''
            break
          case 'sql':
            msg.sql = event.text || ''
            msg.stage = ''
            break
          case 'commentary':
            msg.content += event.text || ''
            break
          case 'complete':
            msg.data = { rows: event.rows, columns: event.columns, data: event.data }
            msg.sql = event.sql || msg.sql
            msg.stage = ''
            msg.streaming = false
            if (event.processing_time_ms) {
              msg.processing_time_ms = event.processing_time_ms
            }
            break
          case 'document_created':
            // Документ создан - добавляем ссылку на скачивание
            if (event.filename && event.download_url) {
              msg.document = {
                filename: event.filename,
                download_url: event.download_url
              }
              msg.content += `\n\n📄 [Скачать ${event.filename}](${event.download_url})`
            }
            break
          case 'chart_created':
            // График создан - добавляем конфигурацию
            if (event.chart_config && msg) {
              msg.chart_config = event.chart_config
            }
            break
          case 'session_info':
            // Обновляем session_id если он был создан
            if (event.session_id) {
              currentChatSession.value = { id: event.session_id }
              loadChatSessions()
            }
            if (event.processing_time_ms && msg) {
              msg.processing_time_ms = event.processing_time_ms
            }
            // Добавляем информацию о навыке
            if (event.skill_name && msg) {
              msg.skill_name = event.skill_name
              msg.skill_call = event.skill_call
            }
            // Добавляем конфигурацию графика
            if (event.chart_config && msg) {
              msg.chart_config = event.chart_config
            }
            break
          case 'error':
            msg.content = `Ошибка: ${event.message || event.text}`
            msg.stage = ''
            msg.streaming = false
            break
          case 'done':
            msg.stage = ''
            msg.streaming = false
            // Добавляем конфигурацию графика из события
            if (event.chart_config && msg) {
              msg.chart_config = event.chart_config
            }
            break
        }
        scrollToBottom(biMessagesRef)
      },
      currentChatSession.value?.id // sessionId
    )
  } catch (e) {
    biHistory.value.push({ 
      id: biMsgId++, 
      type: 'assistant', 
      content: `Ошибка: ${e.message}`,
      timestamp: new Date(),
    })
  } finally {
    biLoading.value = false
    scrollToBottom(biMessagesRef)
  }
}


// Обработчик обновления сессии для модуля docs
const handleDocsSessionUpdated = async () => {
  // Обновляем список сессий после сохранения новой сессии
  await loadChatSessions()
}

// Watch for module changes
watch(activeModule, () => {
  loadChatSessions()
  // Очищаем текущую сессию при смене модуля
  if (activeModule.value !== currentChatSession.value?.module) {
    currentChatSession.value = null
    if (activeModule.value === 'chat') {
      initChat()
    }
    // Сбрасываем состояние для модуля docs
    if (activeModule.value === 'docs') {
      showDocsUploader.value = false
    }
  }
})

const checkOllamaStatus = async () => {
  try {
    const status = await ragClient.checkOllamaStatus()
    ollamaOnline.value = status.available
    currentModel.value = status.available ? (status.model || 'Ollama') : 'Недоступен'
  } catch {
    ollamaOnline.value = false
    currentModel.value = 'Ошибка'
  }
}

onMounted(() => {
  initChat()
  loadConnections()
  checkOllamaStatus()
  loadChatSessions()
})
</script>

<style lang="scss" scoped>
@import '../styles/variables';

.neural-hub {
  --bg-base: #{$dark-bg-primary};
  --bg-panel: #{$dark-bg-secondary};
  --bg-elevated: #{$dark-bg-elevated};
  --bg-hover: #{$dark-bg-hover};
  --border-subtle: #{$dark-border};
  --border-accent: #{$dark-border-accent};
  --text-primary: #{$dark-text-primary};
  --text-secondary: #{$dark-text-secondary};
  --text-muted: #{$dark-text-muted};
  --text-placeholder: #{$dark-text-placeholder};
  --accent: #{$neon-cyan};
  --accent-glow: #{$neon-cyan-glow};

  display: flex;
  height: 100vh;
  background: var(--bg-base);
  color: var(--text-primary);
  font-family: $font-family-base;
  font-weight: 400;
  position: relative;
  overflow: hidden;

  &--light {
    --bg-base: #{$light-bg-primary};
    --bg-panel: #{$light-bg-secondary};
    --bg-elevated: #{$light-bg-elevated};
    --bg-hover: #{$light-bg-hover};
    --border-subtle: #{$light-border};
    --border-accent: rgba(15, 118, 138, 0.3);
    --text-primary: #{$light-text-primary};
    --text-secondary: #{$light-text-secondary};
    --text-muted: #{$light-text-muted};
    --text-placeholder: #{$light-text-placeholder};
    --accent: #0f768a;
    --accent-glow: #0a5f6e;
  }
}

// === SIDEBAR ===
.neural-sidebar {
  width: $sidebar-width;
  background: var(--bg-panel);
  border-right: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 10;
  backdrop-filter: blur(20px);
  overflow: hidden;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: $spacing-md;
  padding: $spacing-lg;
  border-bottom: 1px solid var(--border-subtle);
}

.brand-icon {
  width: 48px;
  height: 48px;
}

.brand-icon {
  width: 48px;
  height: 48px;
}

.brand-icon__core {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: $neon-cyan;
  border-radius: $radius-md;
  color: white;
}


.brand-text {
  display: flex;
  flex-direction: column;
}

.brand-title {
  font-size: $font-size-xl;
  font-weight: 700;
  color: $neon-cyan;
}

.brand-subtitle {
  font-size: $font-size-xs;
  font-weight: 600;
  color: var(--text-muted);
}

.sidebar-controls {
  position: absolute;
  top: $spacing-lg;
  right: $spacing-lg;
}

.ctrl-btn {
  width: 36px;
  height: 36px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: $radius-md;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all $transition-fast;

  &:hover {
    background: var(--accent);
    color: white;
    border-color: var(--accent);
    box-shadow: $glow-cyan;
  }
}

.sidebar-modules {
  flex: 1;
  padding: $spacing-md;
  overflow-y: auto;
}

.modules-label {
  display: block;
  font-size: $font-size-xs;
  color: var(--text-muted);
  padding: $spacing-sm $spacing-md;
  margin-bottom: $spacing-sm;
}

.module-card {
  display: flex;
  align-items: center;
  gap: $spacing-md;
  width: 100%;
  padding: $spacing-md;
  background: transparent;
  border: 1px solid transparent;
  border-radius: $radius-lg;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all $transition-fast;
  text-align: left;
  margin-bottom: $spacing-xs;
  position: relative;
  overflow: hidden;

  &__indicator {
    position: absolute;
    left: 0;
    top: 50%;
    transform: translateY(-50%);
    width: 3px;
    height: 0;
    background: var(--module-accent, var(--accent));
    border-radius: 0 2px 2px 0;
    transition: height $transition-fast;
  }

  &:hover {
    background: var(--bg-hover);
    border-color: var(--border-subtle);
    
    .module-card__indicator {
      height: 50%;
    }
    
    .module-card__arrow {
      transform: translateX(4px);
      opacity: 1;
    }
  }

  &--active {
    background: rgba(58, 232, 255, 0.08);
    border-color: var(--module-accent, var(--accent));
    
    .module-card__indicator {
      height: 70%;
      box-shadow: 0 0 10px var(--module-accent, var(--accent));
    }
    
    .module-card__icon {
      transform: scale(1.1);
    }
  }

  &--disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.module-card__icon {
  width: 44px;
  height: 44px;
  background: var(--bg-elevated);
  border-radius: $radius-md;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all $transition-fast;
}

.module-card__content {
  flex: 1;
  min-width: 0;
}

.module-card__name {
  display: block;
  font-size: $font-size-sm;
  font-weight: 600;
  color: var(--text-primary);
}

.module-card__desc {
  display: block;
  font-size: $font-size-xs;
  color: var(--text-muted);
  margin-top: 2px;
}

.module-card__badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  background: $neon-orange-light;
  color: $neon-orange;
  border-radius: $radius-sm;
}

.module-card__arrow {
  color: var(--text-muted);
  opacity: 0;
  transition: all $transition-fast;
}

.sidebar-status {
  padding: $spacing-md $spacing-lg;
  border-top: 1px solid var(--border-subtle);
  border-bottom: 1px solid var(--border-subtle);
}

.sidebar-actions {
  padding: $spacing-md;
  border-bottom: 1px solid var(--border-subtle);
}

.create-chat-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: $spacing-sm;
  padding: $spacing-md;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: $radius-md;
  font-size: $font-size-sm;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background: var(--accent-glow);
    box-shadow: 0 4px 12px rgba(58, 232, 255, 0.3);
  }

  &:active {
    transform: translateY(1px);
  }
}

// Chat list in sidebar
.sidebar-chat-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.chat-list-header {
  padding: $spacing-md;
  border-bottom: 1px solid var(--border-subtle);
}

.chat-list-title {
  font-size: $font-size-sm;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.chat-list-content {
  flex: 1;
  overflow-y: auto;
  padding: $spacing-sm;
}

.chat-list-item {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  padding: $spacing-sm $spacing-md;
  margin-bottom: $spacing-xs;
  background: transparent;
  border: 1px solid transparent;
  border-radius: $radius-md;
  cursor: pointer;
  transition: all $transition-fast;

  &:hover {
    background: var(--bg-hover);
    border-color: var(--border-subtle);

    .chat-list-item__delete {
      opacity: 1;
    }
  }

  &--active {
    background: rgba(58, 232, 255, 0.1);
    border-color: var(--accent);

    .chat-list-item__icon {
      color: var(--accent);
    }
  }
}

.chat-list-item__icon {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  transition: color $transition-fast;
}

.chat-list-item__content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.chat-list-item__title {
  font-size: $font-size-sm;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-list-item__meta {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  font-size: $font-size-xs;
  color: var(--text-muted);
}

.chat-list-item__module {
  font-weight: 500;
}

.chat-list-item__time {
  &::before {
    content: '•';
    margin-right: $spacing-sm;
  }
}

.chat-list-item__delete {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: $radius-sm;
  color: var(--text-muted);
  cursor: pointer;
  opacity: 0;
  transition: all $transition-fast;

  &:hover {
    background: rgba(255, 51, 102, 0.1);
    color: $neon-red;
  }
}

.chat-list-empty {
  padding: $spacing-lg;
  text-align: center;
  font-size: $font-size-sm;
  color: var(--text-muted);
}

// Chat list groups
.chat-list-group {
  margin-bottom: $spacing-lg;
  
  &:last-child {
    margin-bottom: 0;
  }
}

.chat-list-group__header {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  padding: $spacing-sm $spacing-md;
  margin-bottom: $spacing-xs;
  font-size: $font-size-xs;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--border-subtle);
}

.chat-list-group__count {
  margin-left: auto;
  font-weight: 500;
  color: var(--text-muted);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  font-size: $font-size-xs;
  color: var(--text-muted);

  &--online {
    .status-dot {
      background: $neon-green;
      box-shadow: 0 0 10px $neon-green;
    }
    .status-text {
      color: $neon-green;
    }
  }
}

.status-dot {
  width: 8px;
  height: 8px;
  background: $neon-red;
  border-radius: 50%;
  animation: status-pulse 2s ease-in-out infinite;
}

@keyframes status-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

// === MAIN AREA ===
.neural-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  z-index: 1;
}

.docs-module-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  min-height: 0;
  background: transparent;
  z-index: 1;
}

.module-banner {
  display: flex;
  align-items: center;
  padding: $spacing-lg $spacing-xl;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border-subtle);
  position: relative;
  backdrop-filter: blur(20px);
}

.banner-decoration {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--banner-color, var(--accent));
}

.banner-content {
  display: flex;
  align-items: center;
  gap: $spacing-md;
  flex: 1;
}

.banner-icon {
  width: 56px;
  height: 56px;
  background: var(--banner-color, var(--accent));
  border-radius: $radius-lg;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.banner-title {
  font-size: $font-size-xl;
  font-weight: 700;
  margin: 0;
}

.banner-desc {
  font-size: $font-size-sm;
  color: var(--text-muted);
  margin: 4px 0 0;
}

.banner-actions {
  display: flex;
  gap: $spacing-sm;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  padding: $spacing-sm $spacing-md;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: $radius-md;
  color: var(--text-secondary);
  font-size: $font-size-sm;
  cursor: pointer;
  transition: all $transition-fast;

  &:hover {
    border-color: var(--accent);
    color: var(--accent);
  }

  &--danger:hover {
    background: $neon-red-light;
    border-color: $neon-red;
    color: $neon-red;
  }
}

// === MESSAGES ===
.messages-area {
  flex: 1;
  overflow-y: auto;
  position: relative;
}

.messages-wrapper {
  max-width: calc(#{$message-max-width} + #{$spacing-xl} * 2);
  margin: 0 auto;
  padding: $spacing-md 0;
}

.typing-indicator {
  display: flex;
  align-items: flex-start;
  gap: $spacing-md;
  padding: $spacing-lg $spacing-xl;
  position: relative;
}

// Connection line decoration (same as in HubMessage)
.typing-indicator .message-connector {
  position: absolute;
  left: calc(#{$spacing-xl} + 22px);
  top: 0;
  bottom: 0;
  width: 20px;
  pointer-events: none;
}

.typing-indicator .connector-line {
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 1px;
  background: linear-gradient(
    to bottom,
    transparent,
    var(--avatar-color, #{$neon-cyan}),
    transparent
  );
  opacity: 0.2;
  transition: opacity $transition-fast;
}

.typing-indicator .connector-node {
  position: absolute;
  left: 50%;
  top: calc(#{$spacing-lg} + 22px);
  width: 8px;
  height: 8px;
  background: var(--avatar-color, #{$neon-cyan});
  border-radius: 50%;
  transform: translateX(-50%);
  transition: all $transition-fast;
}

.typing-avatar {
  width: $message-avatar-size;
  height: $message-avatar-size;
  position: relative;
  flex-shrink: 0;
  z-index: 1;
}

.typing-avatar .avatar-core {
  position: absolute;
  inset: 4px;
  background: linear-gradient(135deg, var(--avatar-color, #{$neon-cyan}), rgba(0, 0, 0, 0.5));
  border-radius: $radius-md;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  z-index: 2;
}

.typing-avatar .avatar-ring {
  position: absolute;
  inset: 0;
  border: 2px solid var(--avatar-color, #{$neon-cyan});
  border-radius: $radius-md + 2px;
  opacity: 0.5;
}

.typing-avatar .avatar-pulse {
  position: absolute;
  inset: -4px;
  border: 1px solid var(--avatar-color, #{$neon-cyan});
  border-radius: $radius-lg;
  animation: avatar-pulse 2s ease-out infinite;
}

@keyframes avatar-pulse {
  0% { transform: scale(0.9); opacity: 0.8; }
  100% { transform: scale(1.2); opacity: 0; }
}

.typing-content {
  display: flex;
  flex-direction: column;
  gap: $spacing-xs;
}

.typing-text {
  font-size: $font-size-sm;
  color: var(--text-muted);
  font-family: $font-family-mono;
}

.typing-dots {
  display: flex;
  gap: 6px;

  span {
    width: 8px;
    height: 8px;
    background: var(--accent);
    border-radius: 50%;
    animation: typing-bounce 1.4s ease-in-out infinite;

    &:nth-child(2) { animation-delay: 0.2s; }
    &:nth-child(3) { animation-delay: 0.4s; }
  }
}

@keyframes typing-bounce {
  0%, 60%, 100% { 
    transform: translateY(0); 
    opacity: 0.4;
  }
  30% { 
    transform: translateY(-8px); 
    opacity: 1;
  }
}

// === INPUT AREA ===
.input-area {
  padding: $spacing-md $spacing-xl $spacing-xl;
  background: linear-gradient(to top, var(--bg-panel), transparent);
  position: relative;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: $spacing-sm;
  margin-bottom: $spacing-md;
  max-width: $message-max-width;
}

.suggestion-chip {
  display: inline-flex;
  align-items: center;
  gap: $spacing-xs;
  padding: $spacing-sm $spacing-md;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: $radius-full;
  font-size: $font-size-sm;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all $transition-fast;

  &:hover {
    background: rgba(58, 232, 255, 0.1);
    border-color: var(--accent);
    color: var(--accent);
    transform: translateY(-2px);
  }
}

.input-container {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  max-width: $message-max-width;
  position: relative;
}

.input-decoration {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 1;
}

.input-corner {
  position: absolute;
  width: 16px;
  height: 16px;
  border-color: var(--accent);
  border-style: solid;
  opacity: 0.5;
  transition: opacity $transition-fast;

  &--tl {
    top: 0;
    left: 0;
    border-width: 2px 0 0 2px;
    border-radius: 4px 0 0 0;
  }
  &--tr {
    top: 0;
    right: 112px; // Учитываем ширину send-btn (52px) + gap (8px) + file-btn (52px)
    border-width: 2px 2px 0 0;
    border-radius: 0 4px 0 0;
  }
  &--bl {
    bottom: 0;
    left: 0;
    border-width: 0 0 2px 2px;
    border-radius: 0 0 0 4px;
  }
  &--br {
    bottom: 0;
    right: 112px; // Учитываем ширину send-btn (52px) + gap (8px) + file-btn (52px)
    border-width: 0 2px 2px 0;
    border-radius: 0 0 4px 0;
  }
}

.input-container:focus-within .input-corner {
  opacity: 1;
}

.input-field {
  flex: 1;
  min-width: 0; // Позволяет flex элементу правильно сжиматься
  padding: $spacing-md $spacing-lg;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: $radius-lg;
  color: var(--text-primary);
  font-size: $font-size-base;
  font-family: inherit;
  resize: none;
  outline: none;
  transition: all $transition-fast;
  position: relative;
  z-index: 2; // Поле ввода поверх декораций

  &:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(58, 232, 255, 0.1);
  }

  &::placeholder {
    color: var(--text-placeholder);
  }
}

.send-btn {
  flex-shrink: 0; // Кнопка не сжимается
  width: 52px;
  height: 52px;
  min-width: 52px; // Минимальная ширина
  background: transparent;
  border: none;
  border-radius: $radius-lg;
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  transition: transform $transition-fast;
  z-index: 2; // Кнопка поверх декораций

  &__bg {
    position: absolute;
    inset: 0;
    background: var(--btn-color, var(--accent));
    border-radius: inherit;
    transition: all $transition-fast;
  }

  svg {
    position: relative;
    z-index: 1;
  }

  &:hover:not(:disabled) {
    transform: scale(1.05);
    
    .send-btn__bg {
      box-shadow: $glow-cyan;
    }
  }

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
}

.file-input-hidden {
  display: none;
}

.file-btn {
  flex-shrink: 0;
  width: 52px;
  height: 52px;
  min-width: 52px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: $radius-lg;
  color: var(--accent);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all $transition-fast;
  z-index: 2;
  position: relative;
  outline: none;
  
  &:hover:not(:disabled) {
    background: rgba(58, 232, 255, 0.1);
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(58, 232, 255, 0.1);
    transform: scale(1.05);
  }
  
  &:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(58, 232, 255, 0.1);
  }
  
  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  
  svg {
    position: relative;
    z-index: 1;
  }
}

.files-section {
  margin-top: $spacing-sm;
  max-width: $message-max-width;
}

.files-list {
  display: flex;
  flex-direction: column;
  gap: $spacing-xs;
  margin-bottom: $spacing-sm;
}

.file-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $spacing-sm;
  padding: $spacing-sm $spacing-md;
  background: rgba(58, 232, 255, 0.1);
  border: 1px solid var(--border-subtle);
  border-radius: $radius-md;
  font-size: $font-size-sm;
  
  .neural-hub--light & {
    background: rgba(15, 118, 138, 0.08);
  }
}

.file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--accent);
  font-family: Arial, sans-serif;
}

.file-remove {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: $radius-sm;
  color: var(--text-muted);
  cursor: pointer;
  transition: all $transition-fast;
  
  &:hover {
    background: rgba(58, 232, 255, 0.2);
    color: var(--accent);
  }
}

.vectorization-toggle {
  margin-top: $spacing-sm;
  padding: $spacing-sm $spacing-md;
  background: rgba(58, 232, 255, 0.05);
  border: 1px solid var(--border-subtle);
  border-radius: $radius-md;
  
  .neural-hub--light & {
    background: rgba(15, 118, 138, 0.05);
  }
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  cursor: pointer;
  user-select: none;
}

.toggle-checkbox {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: var(--accent);
}

.toggle-text {
  font-size: $font-size-sm;
  font-weight: 500;
  color: var(--text-primary);
  font-family: Arial, sans-serif;
}

.toggle-hint {
  font-size: $font-size-xs;
  color: var(--text-muted);
  margin-left: auto;
  font-family: Arial, sans-serif;
}

// === FILE SELECTOR ===
.file-selector {
  flex: 1;
  padding: $spacing-xl;
  overflow-y: auto;
}

.file-header {
  display: flex;
  align-items: center;
  gap: $spacing-md;
  margin-bottom: $spacing-xl;
  color: var(--accent);
  
  h3 {
    font-family: $font-family-display;
    font-size: $font-size-lg;
    margin: 0;
    color: var(--text-primary);
  }
  
  p {
    font-size: $font-size-sm;
    color: var(--text-muted);
    margin: 4px 0 0;
  }
}

.file-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: $spacing-md;
}

.file-card {
  display: flex;
  align-items: center;
  gap: $spacing-md;
  padding: $spacing-lg;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: $radius-lg;
  cursor: pointer;
  transition: all $transition-fast;

  &:hover {
    border-color: $neon-green;
    transform: translateY(-2px);
    box-shadow: $glow-green;

    .file-card__action {
      opacity: 1;
      transform: translateX(0);
    }
  }
}

.file-card__icon {
  width: 52px;
  height: 52px;
  background: $neon-green-light;
  border-radius: $radius-md;
  display: flex;
  align-items: center;
  justify-content: center;
  color: $neon-green;
}

.file-card__info {
  flex: 1;
  min-width: 0;
}

.file-card__name {
  display: block;
  font-size: $font-size-base;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-card__meta {
  display: block;
  font-size: $font-size-sm;
  color: var(--text-muted);
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-card__action {
  color: $neon-green;
  opacity: 0;
  transform: translateX(-8px);
  transition: all $transition-fast;
}

.file-empty {
  grid-column: 1 / -1;
  text-align: center;
  padding: $spacing-2xl;
  color: var(--text-muted);

  h4 {
    font-size: $font-size-lg;
    margin: $spacing-md 0 $spacing-xs;
    color: var(--text-secondary);
  }

  p {
    margin: 0 0 $spacing-lg;
  }
}

.upload-link {
  display: inline-flex;
  align-items: center;
  gap: $spacing-sm;
  padding: $spacing-md $spacing-lg;
  background: $neon-green;
  border-radius: $radius-lg;
  color: white;
  text-decoration: none;
  font-weight: 600;
  transition: all $transition-fast;

  &:hover {
    box-shadow: $glow-green;
    transform: translateY(-2px);
  }
}

.selected-source {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $spacing-md $spacing-xl;
  background: $neon-green-light;
  border-bottom: 1px solid rgba($neon-green, 0.3);
}

.source-info {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  font-size: $font-size-sm;
  font-weight: 600;
  color: $neon-green;
}

.source-separator {
  color: rgba($neon-green, 0.5);
  margin: 0 $spacing-xs;
}

.source-change {
  display: flex;
  align-items: center;
  gap: $spacing-xs;
  padding: $spacing-xs $spacing-md;
  background: transparent;
  border: 1px solid $neon-green;
  border-radius: $radius-md;
  color: $neon-green;
  font-size: $font-size-xs;
  cursor: pointer;
  transition: all $transition-fast;

  &:hover {
    background: $neon-green;
    color: white;
  }
}

// === COMING SOON ===
.coming-soon {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: $spacing-2xl;
  text-align: center;
}

.coming-soon__visual {
  position: relative;
  margin-bottom: $spacing-xl;
}

.coming-soon__icon {
  width: 120px;
  height: 120px;
  background: var(--bg-elevated);
  border-radius: $radius-2xl;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 1;
}

.coming-soon__particles {
  position: absolute;
  inset: -20px;

  .particle {
    position: absolute;
    width: 6px;
    height: 6px;
    background: var(--accent);
    border-radius: 50%;
    animation: particle-float 3s ease-in-out infinite;
    
    @for $i from 1 through 8 {
      &:nth-child(#{$i}) {
        top: random(100) * 1%;
        left: random(100) * 1%;
        animation-delay: $i * 0.2s;
        animation-duration: 2s + random(20) * 0.1s;
      }
    }
  }
}

@keyframes particle-float {
  0%, 100% { 
    transform: translateY(0) scale(1); 
    opacity: 0.3;
  }
  50% { 
    transform: translateY(-15px) scale(1.2); 
    opacity: 1;
  }
}

.coming-soon__title {
  font-family: $font-family-display;
  font-size: $font-size-2xl;
  font-weight: 700;
  letter-spacing: $letter-spacing-wider;
  margin: 0 0 $spacing-sm;
  color: var(--accent);
}

.coming-soon__text {
  font-size: $font-size-base;
  color: var(--text-muted);
  margin: 0 0 $spacing-xl;
}

.coming-soon__features {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: $spacing-sm;
  max-width: 500px;
}

.feature-chip {
  display: inline-flex;
  align-items: center;
  gap: $spacing-xs;
  padding: $spacing-sm $spacing-md;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: $radius-full;
  font-size: $font-size-sm;
  color: var(--text-secondary);
}

// === SCROLLBAR ===
.messages-area::-webkit-scrollbar,
.sidebar-modules::-webkit-scrollbar,
.file-selector::-webkit-scrollbar {
  width: 6px;
}

.messages-area::-webkit-scrollbar-track,
.sidebar-modules::-webkit-scrollbar-track,
.file-selector::-webkit-scrollbar-track {
  background: transparent;
}

.messages-area::-webkit-scrollbar-thumb,
.sidebar-modules::-webkit-scrollbar-thumb,
.file-selector::-webkit-scrollbar-thumb {
  background: var(--border-subtle);
  border-radius: 3px;

  &:hover {
    background: var(--accent);
  }
}


// === CHAT HISTORY SIDEBAR ===
.chat-history-sidebar {
  width: 320px;
  background: var(--bg-panel);
  border-left: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 10;
  backdrop-filter: blur(20px);
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $spacing-lg;
  border-bottom: 1px solid var(--border-subtle);

  h3 {
    font-family: $font-family-display;
    font-size: $font-size-lg;
    font-weight: 700;
    margin: 0;
    color: var(--text-primary);
  }
}

.history-new-btn {
  width: 32px;
  height: 32px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: $radius-md;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all $transition-fast;

  &:hover {
    background: var(--accent);
    color: white;
    border-color: var(--accent);
    box-shadow: $glow-cyan;
  }
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: $spacing-sm;
}

// History items in sidebar
.sidebar-history .history-item {
  display: flex;
  align-items: center;
  gap: $spacing-xs;
  width: 100%;
  padding: $spacing-sm $spacing-md;
  background: transparent;
  border: 1px solid transparent;
  border-radius: $radius-md;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all $transition-fast;
  text-align: left;
  position: relative;

  &:hover {
    background: var(--bg-hover);
    border-color: var(--border-subtle);

    .history-item__delete {
      opacity: 1;
    }
  }

  &--active {
    background: rgba(58, 232, 255, 0.08);
    border-color: var(--accent);
  }
}

// Legacy styles for right sidebar (if still used)
.history-item {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  width: 100%;
  padding: $spacing-md;
  background: transparent;
  border: 1px solid transparent;
  border-radius: $radius-lg;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all $transition-fast;
  text-align: left;
  margin-bottom: $spacing-xs;
  position: relative;

  &:hover {
    background: var(--bg-hover);
    border-color: var(--border-subtle);

    .history-item__delete {
      opacity: 1;
    }
  }

  &--active {
    background: rgba(58, 232, 255, 0.08);
    border-color: var(--accent);
  }
}

.history-item__content {
  flex: 1;
  min-width: 0;
}

.sidebar-history .history-item__title {
  display: block;
  font-size: $font-size-xs;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-item__title {
  display: block;
  font-size: $font-size-sm;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-history .history-item__meta {
  display: flex;
  align-items: center;
  gap: $spacing-xs;
  font-size: 10px;
  color: var(--text-muted);
}

.history-item__meta {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  font-size: $font-size-xs;
  color: var(--text-muted);
}

.history-item__time {
  font-family: $font-family-mono;
}

.sidebar-history .history-item__delete {
  opacity: 0;
  padding: 2px;
  background: transparent;
  border: 1px solid var(--border-subtle);
  border-radius: $radius-sm;
  color: var(--text-muted);
  cursor: pointer;
  transition: all $transition-fast;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  &:hover {
    background: $neon-red-light;
    border-color: $neon-red;
    color: $neon-red;
  }
}

.history-item__delete {
  opacity: 0;
  padding: $spacing-xs;
  background: transparent;
  border: 1px solid var(--border-subtle);
  border-radius: $radius-sm;
  color: var(--text-muted);
  cursor: pointer;
  transition: all $transition-fast;
  display: flex;
  align-items: center;
  justify-content: center;

  &:hover {
    background: $neon-red-light;
    border-color: $neon-red;
    color: $neon-red;
  }
}

.history-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: $spacing-2xl;
  color: var(--text-muted);
  text-align: center;

  p {
    margin-top: $spacing-md;
    font-size: $font-size-sm;
  }
}

.messages-area--with-history {
  margin-right: 320px;
}

// === RESPONSIVE ===
@media (max-width: $breakpoint-md) {
  .neural-sidebar {
    display: none;
  }

  .chat-history-sidebar {
    position: absolute;
    right: 0;
    top: 0;
    bottom: 0;
    z-index: 100;
    box-shadow: -4px 0 20px rgba(0, 0, 0, 0.3);
  }

  .messages-area--with-history {
    margin-right: 0;
  }

  .input-area {
    padding: $spacing-md;
  }

  .module-banner {
    padding: $spacing-md;
  }

  .banner-icon {
    width: 44px;
    height: 44px;
  }

  .banner-title {
    font-size: $font-size-lg;
  }
}
</style>
