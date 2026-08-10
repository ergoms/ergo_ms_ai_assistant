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

        <div v-if="loading" :key="typingAnimKey" class="typing-indicator">
          <div class="typing-avatar" :style="{ '--avatar-color': moduleAccent }">
            <div class="avatar-core">
              <component :is="moduleConfig?.icon" :size="18" />
            </div>
          </div>
          <div class="typing-content">
            <div class="typing-text">{{ t('ai_assistant.generating') }}</div>
            <div class="typing-dots" data-ergo-motion-safe="pulse">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="input-area">
      <div class="input-area__inner">
        <div v-if="hasSuggestions" class="suggestions-wrap">
          <button
            type="button"
            class="suggestions-toggle"
            :aria-expanded="suggestionsExpanded"
            @click="suggestionsExpanded = !suggestionsExpanded"
          >
            <ChevronDown
              :size="14"
              class="suggestions-chevron"
              :class="{ 'is-expanded': suggestionsExpanded }"
            />
            <span>
              {{
                suggestionsExpanded
                  ? t('ai_assistant.apps.hideSuggestions')
                  : t('ai_assistant.apps.showSuggestions')
              }}
            </span>
          </button>

          <div v-show="suggestionsExpanded" class="suggestions">
            <button
              v-for="s in moduleConfig?.suggestions"
              :key="s"
              type="button"
              class="suggestion-chip"
              :disabled="loading"
              @click="emit('send', s)"
            >
              <Zap :size="14" />
              <span>{{ s }}</span>
            </button>
          </div>
        </div>

        <div class="composer">
          <input
            ref="fileInputRef"
            type="file"
            class="file-input-hidden"
            accept=".pdf,.doc,.docx,.txt,.md,.csv,.xlsx,.xls,.png,.jpg,.jpeg,.webp,.gif"
            multiple
            @change="onFileSelect"
          />

          <button
            type="button"
            class="file-btn"
            :style="{ '--btn-color': moduleAccent }"
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
            :style="{ '--btn-color': moduleAccent }"
            :disabled="!inputModel.trim() || loading"
            :aria-label="t('ai_assistant.apps.send')"
            @click="emit('send')"
          >
            <span class="send-btn__bg" aria-hidden="true" />
            <Send :size="18" />
          </button>
        </div>

        <div v-if="selectedFiles.length > 0" class="files-section">
          <div class="files-list">
            <div
              v-for="(file, index) in selectedFiles"
              :key="`${file.name}-${index}`"
              class="file-info"
              :class="{ 'file-info--image': isImageFile(file) }"
            >
              <img
                v-if="isImageFile(file)"
                class="file-thumb"
                :src="previewUrl(file)"
                :alt="file.name"
              />
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
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ChevronDown, Send, Upload, X, Zap } from 'lucide-vue-next'
import { useAppI18n } from '@/i18n/useAppI18n.js'
import { AI_ACCENT_CSS } from '../js/themeAccent.js'
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
const suggestionsExpanded = ref(false)
/** Remount typing после снятия app-bootstrapping (F5 за nginx). */
const typingAnimKey = ref(0)

onMounted(() => {
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      if (props.loading) typingAnimKey.value += 1
    })
  })
})

watch(
  () => props.loading,
  (loading) => {
    if (loading) {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          typingAnimKey.value += 1
        })
      })
    }
  },
)

const moduleAccent = computed(() => props.moduleConfig?.color || AI_ACCENT_CSS)
const hasSuggestions = computed(() => (props.moduleConfig?.suggestions?.length ?? 0) > 0)

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

const IMAGE_EXT = /\.(png|jpe?g|webp|gif)$/i
const previewCache = new WeakMap()

function isImageFile(file) {
  return Boolean(file?.type?.startsWith('image/') || IMAGE_EXT.test(file?.name || ''))
}

function previewUrl(file) {
  if (!file || !isImageFile(file)) return ''
  let url = previewCache.get(file)
  if (!url) {
    url = URL.createObjectURL(file)
    previewCache.set(file, url)
  }
  return url
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
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  width: 100%;
  overflow: hidden;
}

.file-info--image {
  align-items: center;
}

.file-thumb {
  width: 36px;
  height: 36px;
  object-fit: cover;
  border-radius: 4px;
  flex-shrink: 0;
}
</style>
