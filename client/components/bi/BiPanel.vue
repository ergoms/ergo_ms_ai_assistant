<template>
  <AssistantChatLayout
    ref="layoutRef"
    v-model="inputText"
    :placeholder="moduleConfig?.settings?.placeholder || 'Задайте вопрос к данным...'"
    :disabled="loading || !fileId"
    :show-empty="!fileId"
    :show-composer="Boolean(fileId)"
    :typing="loading && !hasStreaming"
    @send="send()"
  >
    <template #toolbar>
      <div class="bi-panel__pickers">
        <SelectBox
          v-model="connectionId"
          :options="connectionOptions"
          value-key="id"
          label-key="name"
          :include-all-option="false"
          placeholder="Подключение"
          searchable
          cast-to-number
          @update:model-value="onConnectionChange"
        />
        <SelectBox
          v-model="fileId"
          :options="fileOptions"
          value-key="id"
          label-key="name"
          :include-all-option="false"
          placeholder="Файл данных"
          :disabled="!connectionId || filesLoading"
          searchable
          cast-to-number
        />
      </div>
    </template>

    <template #empty>
      <Database :size="40" class="text-muted mb-3" />
      <h3 class="h5">Выберите подключение и файл</h3>
      <p class="text-muted mb-0">Для анализа данных укажите источник в панели выше.</p>
    </template>

    <template #messages>
      <p v-if="showEmptyState" class="text-muted text-center mb-0">
        Задайте вопрос к данным — чат сохранится после первого ответа.
      </p>
      <template v-else>
        <AssistantChatMessage
          v-for="msg in messages"
          :key="msg.id"
          :message="msg"
          :module-config="moduleConfig"
        />
      </template>
    </template>
  </AssistantChatLayout>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Database } from 'lucide-vue-next'
import SelectBox from '@/components/SelectBox.vue'
import AssistantChatLayout from '../chat/AssistantChatLayout.vue'
import AssistantChatMessage from '../chat/AssistantChatMessage.vue'
import { getModuleById } from '../../modules/index.js'
import { biClient } from '../../bi/js/bi-client.js'
import { ragClient } from '../../rag/js/rag-client.js'
import { mapApiMessages, nextLocalMessageId, useMessageHistory } from '../../js/composables/useAssistantStream.js'
import { logError } from '@/js/utils/logError.js'

const props = defineProps({
  sessionId: { type: String, default: null },
})

const emit = defineEmits(['session-created', 'draft-started'])

const moduleConfig = computed(() => getModuleById('bi'))
const { messages, clearMessages, setMessages, addUserMessage } = useMessageHistory()

const connectionId = ref(null)
const fileId = ref(null)
const connections = ref([])
const files = ref([])
const filesLoading = ref(false)
const inputText = ref('')
const loading = ref(false)
const layoutRef = ref(null)
const restoringSession = ref(false)

const connectionOptions = computed(() =>
  connections.value.map((c) => ({ id: c.id, name: c.name })),
)

const fileOptions = computed(() =>
  files.value.map((f) => ({ id: f.id, name: f.name })),
)

const selectedFile = computed(() => files.value.find((f) => f.id === fileId.value) || null)
const showEmptyState = computed(() => messages.value.length === 0 && !loading.value)
const hasStreaming = computed(() => messages.value.some((m) => m.streaming))

function scrollToBottom() {
  layoutRef.value?.scrollToBottom()
}

function mapBiMessages(apiMessages) {
  return mapApiMessages(apiMessages).map((msg) => {
    const meta = msg.metadata || {}
    if (meta.sql) msg.sql = meta.sql
    if (meta.data) {
      msg.data = {
        data: meta.data,
        rows: meta.rows,
        columns: meta.columns,
      }
    }
    if (meta.document) msg.document = meta.document
    return msg
  })
}

async function loadConnections() {
  const result = await biClient.getConnections()
  if (result.success) {
    connections.value = result.connections
  }
}

async function loadFiles() {
  if (!connectionId.value) {
    files.value = []
    return
  }
  filesLoading.value = true
  try {
    const result = await biClient.getConnectionFiles(connectionId.value)
    files.value = result.success ? result.files : []
  } finally {
    filesLoading.value = false
  }
}

function onConnectionChange() {
  if (restoringSession.value) return
  fileId.value = null
  if (!props.sessionId) {
    clearMessages()
  }
  loadFiles()
}

async function restoreBiContextFromSession(sessionData, apiMessages) {
  restoringSession.value = true
  try {
    const metaFileId = sessionData?.metadata?.file_id
    if (metaFileId && connections.value.length === 0) {
      await loadConnections()
    }
    if (metaFileId) {
      for (const conn of connections.value) {
        const connFiles = await biClient.getConnectionFiles(conn.id)
        if (connFiles.success && connFiles.files?.find((f) => f.id === metaFileId)) {
          connectionId.value = conn.id
          await loadFiles()
          fileId.value = metaFileId
          break
        }
      }
    }
    setMessages(mapBiMessages(apiMessages))
    scrollToBottom()
  } finally {
    restoringSession.value = false
  }
}

async function loadSession(sessionId) {
  if (!sessionId) {
    clearMessages()
    connectionId.value = null
    fileId.value = null
    return
  }
  const result = await ragClient.getChatSession(sessionId)
  if (result.success) {
    await restoreBiContextFromSession(result.session, result.messages)
  }
}

async function send(text) {
  const messageText = (text || inputText.value).trim()
  if (!messageText || loading.value || !selectedFile.value) return

  if (!props.sessionId && messages.value.length === 0) {
    emit('draft-started', 'bi')
  }

  addUserMessage(messageText)
  inputText.value = ''
  loading.value = true
  scrollToBottom()

  const responseId = nextLocalMessageId()

  try {
    await biClient.askQuestionStream(
      selectedFile.value.id,
      messageText,
      true,
      null,
      (event) => {
        let msg = messages.value.find((m) => m.id === responseId)
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
          messages.value.push(msg)
          loading.value = false
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
            if (event.processing_time_ms) msg.processing_time_ms = event.processing_time_ms
            break
          case 'document_created':
            if (event.filename && event.download_url) {
              msg.document = { filename: event.filename, download_url: event.download_url }
              msg.content += `\n\n[Скачать ${event.filename}](${event.download_url})`
            }
            break
          case 'chart_created':
            if (event.chart_config) msg.chart_config = event.chart_config
            break
          case 'session_info':
            if (event.session_id) {
              emit('session-created', { sessionId: event.session_id, module: 'bi' })
            }
            if (event.skill_name) {
              msg.skill_name = event.skill_name
              msg.skill_call = event.skill_call
            }
            if (event.chart_config) msg.chart_config = event.chart_config
            msg.streaming = false
            break
          case 'error':
            msg.content = `Ошибка: ${event.message || 'Неизвестная ошибка'}`
            msg.streaming = false
            break
          default:
            break
        }
        scrollToBottom()
      },
      props.sessionId,
    )
  } catch (error) {
    logError('Ошибка BI-запроса', error)
    messages.value.push({
      id: nextLocalMessageId(),
      type: 'assistant',
      content: `Ошибка: ${error.message}`,
      timestamp: new Date(),
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

function reset() {
  clearMessages()
  inputText.value = ''
  if (!props.sessionId) {
    connectionId.value = null
    fileId.value = null
  }
}

watch(
  () => props.sessionId,
  (id) => {
    loadSession(id)
  },
  { immediate: true },
)

loadConnections()

defineExpose({ reset, loadSession })
</script>

<style lang="scss" scoped>
.bi-panel__pickers {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}
</style>
