<template>
  <div class="hub-chat-panel">
    <div ref="messagesRef" class="messages-area">
      <div class="messages-wrapper">
        <HubMessage
          v-for="msg in messages"
          :key="msg.id"
          :message="msg"
          :module-config="moduleConfig"
        />

        <div v-if="loading" class="typing-indicator">
          <div class="typing-avatar" :style="`--avatar-color: ${moduleConfig?.color || '#3ae8ff'}`">
            <div class="avatar-core">
              <component :is="moduleConfig?.icon" :size="18" />
            </div>
          </div>
          <div class="typing-content">
            <div class="typing-text">{{ t('ai_assistant.generating') }}</div>
            <div class="typing-dots">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="input-area">
      <div v-if="messages.length <= 1" class="suggestions">
        <button
          v-for="s in moduleConfig?.suggestions"
          :key="s"
          type="button"
          class="suggestion-chip"
          @click="emit('send', s)"
        >
          <Zap :size="14" />
          <span>{{ s }}</span>
        </button>
      </div>

      <div class="input-container">
        <input
          ref="fileInputRef"
          type="file"
          class="file-input-hidden"
          accept=".pdf,.doc,.docx,.txt"
          multiple
          style="display: none"
          @change="onFileSelect"
        />

        <button
          type="button"
          class="file-btn"
          :style="{ '--btn-color': moduleConfig?.color }"
          :disabled="loading"
          :title="t('ai_assistant.uploadFile')"
          :aria-label="t('ai_assistant.uploadFile')"
          @click="triggerFileInput"
        >
          <Upload :size="18" />
        </button>

        <textarea
          ref="inputRef"
          v-model="inputModel"
          class="input-field"
          :placeholder="moduleConfig?.settings?.placeholder"
          :disabled="loading"
          rows="1"
          @keydown.enter.exact.prevent="emit('send')"
        />

        <button
          type="button"
          class="send-btn"
          :style="{ '--btn-color': moduleConfig?.color }"
          :disabled="!inputModel.trim() || loading"
          :aria-label="t('ai_assistant.apps.send')"
          @click="emit('send')"
        >
          <div class="send-btn__bg"></div>
          <Send :size="18" />
        </button>
      </div>

      <div v-if="selectedFiles.length > 0" class="files-section">
        <div class="files-list">
          <div
            v-for="(file, index) in selectedFiles"
            :key="`${file.name}-${index}`"
            class="file-info"
          >
            <span class="file-name">{{ file.name }}</span>
            <button
              type="button"
              class="file-remove"
              :title="t('ai_assistant.removeFile')"
              @click="emit('remove-file', index)"
            >
              <X :size="14" />
            </button>
          </div>
        </div>

        <div class="vectorization-toggle">
          <label class="toggle-label">
            <input
              v-model="vectorizationModel"
              type="checkbox"
              class="toggle-checkbox"
            />
            <span class="toggle-text">{{ t('ai_assistant.vectorization') }}</span>
            <span class="toggle-hint">{{ t('ai_assistant.vectorizationHint') }}</span>
          </label>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { Send, Upload, X, Zap } from 'lucide-vue-next'
import { useAppI18n } from '@/i18n/useAppI18n.js'
import HubMessage from './HubMessage.vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  moduleConfig: { type: Object, default: null },
  input: { type: String, default: '' },
  selectedFiles: { type: Array, default: () => [] },
  enableVectorization: { type: Boolean, default: false },
})

const emit = defineEmits([
  'update:input',
  'update:enableVectorization',
  'send',
  'files-selected',
  'remove-file',
])

const { t } = useAppI18n()
const messagesRef = ref(null)
const inputRef = ref(null)
const fileInputRef = ref(null)

const inputModel = computed({
  get: () => props.input,
  set: (value) => emit('update:input', value),
})

const vectorizationModel = computed({
  get: () => props.enableVectorization,
  set: (value) => emit('update:enableVectorization', value),
})

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

function triggerFileInput() {
  fileInputRef.value?.click()
}

function onFileSelect(event) {
  emit('files-selected', event)
}

function clearFileInput() {
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

watch(
  () => [props.messages.length, props.loading, props.messages.at(-1)?.content],
  () => scrollToBottom(),
)

defineExpose({ scrollToBottom, clearFileInput, inputRef })
</script>

<style lang="scss" scoped>
.hub-chat-panel {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}
</style>
