<template>
  <div class="document-uploader">
    <div class="document-uploader__header">
      <h6 class="mb-0">{{ t('ai_assistant.docs.uploader.title') }}</h6>
    </div>

    <div class="document-uploader__tabs">
      <button
        class="tab-btn"
        :class="{ active: mode === 'file' }"
        @click="mode = 'file'"
      >
        <Upload :size="16" class="me-1" />
        {{ t('ai_assistant.docs.uploader.tabFile') }}
      </button>
      <button
        class="tab-btn"
        :class="{ active: mode === 'text' }"
        @click="mode = 'text'"
      >
        <FileText :size="16" class="me-1" />
        {{ t('ai_assistant.docs.uploader.tabText') }}
      </button>
    </div>

    <!-- Загрузка файла -->
    <div v-if="mode === 'file'" class="document-uploader__content">
      <div class="mb-3">
        <label class="form-label">{{ t('ai_assistant.docs.uploader.nameLabel') }}</label>
        <input
          v-model="fileTitle"
          type="text"
          class="form-control"
          :placeholder="t('ai_assistant.docs.uploader.namePlaceholder')"
        />
      </div>

      <div class="mb-3">
        <label class="form-label">{{ t('ai_assistant.docs.uploader.fileLabel') }}</label>
        <div class="file-dropzone" :class="{ 'dragover': isDragging }" 
             @dragover.prevent="isDragging = true"
             @dragleave.prevent="isDragging = false"
             @drop.prevent="handleDrop">
          <input
            ref="fileInput"
            type="file"
            class="d-none"
            accept=".pdf,.docx,.txt"
            @change="handleFileSelect"
          />
          <div class="dropzone-content">
            <Upload :size="32" />
            <p class="mb-0 mt-2">
              {{ t('ai_assistant.docs.uploader.dropzoneHint') }}
              <button class="btn-link" @click="$refs.fileInput.click()">
                {{ t('ai_assistant.docs.uploader.chooseFile') }}
              </button>
            </p>
            <small class="text-muted">{{ t('ai_assistant.docs.uploader.supportedFormats') }}</small>
          </div>
        </div>
        <div v-if="selectedFile" class="mt-2">
          <div class="selected-file">
            <File :size="16" />
            <span>{{ selectedFile.name }}</span>
            <span class="file-size">{{ formatFileSize(selectedFile.size) }}</span>
            <button class="btn-remove" @click="removeFile">
              <X :size="14" />
            </button>
          </div>
        </div>
      </div>

      <div class="mb-3">
        <div class="form-check">
          <input
            v-model="indexImmediately"
            class="form-check-input"
            type="checkbox"
            id="indexFile"
          />
          <label class="form-check-label" for="indexFile">
            {{ t('ai_assistant.docs.uploader.indexImmediatelyFile') }}
          </label>
        </div>
      </div>

      <button
        class="btn btn-primary w-100"
        @click="uploadFile"
        :disabled="!fileTitle.trim() || !selectedFile || uploading"
      >
        <span v-if="uploading">
          <span class="spinner-border spinner-border-sm me-2" role="status"></span>
          {{ t('ai_assistant.docs.uploader.uploading') }}
        </span>
        <span v-else>
          <Upload :size="16" class="me-1" />
          {{ t('ai_assistant.docs.uploader.uploadBtn') }}
        </span>
      </button>
    </div>

    <!-- Ввод текста -->
    <div v-else class="document-uploader__content">
      <div class="mb-3">
        <label class="form-label">{{ t('ai_assistant.docs.uploader.nameLabel') }}</label>
        <input
          v-model="textTitle"
          type="text"
          class="form-control"
          :placeholder="t('ai_assistant.docs.uploader.namePlaceholder')"
        />
      </div>

      <div class="mb-3">
        <label class="form-label">{{ t('ai_assistant.docs.uploader.textLabel') }}</label>
        <textarea
          v-model="textContent"
          class="form-control"
          rows="8"
          :placeholder="t('ai_assistant.docs.uploader.textPlaceholder')"
        ></textarea>
      </div>

      <div class="mb-3">
        <div class="form-check">
          <input
            v-model="indexImmediately"
            class="form-check-input"
            type="checkbox"
            id="indexText"
          />
          <label class="form-check-label" for="indexText">
            {{ t('ai_assistant.docs.uploader.indexImmediatelyText') }}
          </label>
        </div>
      </div>

      <button
        class="btn btn-primary w-100"
        @click="createFromText"
        :disabled="!textTitle.trim() || !textContent.trim() || uploading"
      >
        <span v-if="uploading">
          <span class="spinner-border spinner-border-sm me-2" role="status"></span>
          {{ t('ai_assistant.docs.uploader.creating') }}
        </span>
        <span v-else>
          <Save :size="16" class="me-1" />
          {{ t('ai_assistant.docs.uploader.createBtn') }}
        </span>
      </button>
    </div>

    <div v-if="error" class="alert alert-danger mt-3 mb-0" style="background: color-mix(in srgb, var(--bs-danger) 80%, transparent); backdrop-filter: blur(10px);">
      {{ error }}
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Upload, FileText, File, X, Save } from 'lucide-vue-next'
import { useAppI18n } from '@/i18n/useAppI18n.js'
import { docsClient } from './js/docs-client.js'
import { useToast } from '@/js/utils/toast.js'

const { t } = useAppI18n()
const toast = useToast()

const emit = defineEmits(['document-uploaded', 'document-created'])

const mode = ref('file')
const fileTitle = ref('')
const textTitle = ref('')
const textContent = ref('')
const selectedFile = ref(null)
const indexImmediately = ref(false)
const uploading = ref(false)
const error = ref(null)
const isDragging = ref(false)
const fileInput = ref(null)

const handleFileSelect = (event) => {
  const file = event.target.files[0]
  if (file) {
    selectedFile.value = file
    if (!fileTitle.value) {
      fileTitle.value = file.name.replace(/\.[^/.]+$/, '')
    }
  }
}

const handleDrop = (event) => {
  isDragging.value = false
  const file = event.dataTransfer.files[0]
  if (file) {
    selectedFile.value = file
    if (!fileTitle.value) {
      fileTitle.value = file.name.replace(/\.[^/.]+$/, '')
    }
  }
}

const removeFile = () => {
  selectedFile.value = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

const uploadFile = async () => {
  if (!fileTitle.value.trim() || !selectedFile.value) return

  uploading.value = true
  error.value = null

  try {
    const result = await docsClient.uploadDocument(
      selectedFile.value,
      fileTitle.value.trim(),
      '',
      {},
      indexImmediately.value
    )

    if (result.success) {
      toast.success(t('ai_assistant.docs.uploader.uploadSuccess'))
      emit('document-uploaded', result.document)
      
      // Сброс формы
      fileTitle.value = ''
      selectedFile.value = null
      if (fileInput.value) {
        fileInput.value.value = ''
      }
      indexImmediately.value = false
    } else {
      error.value = result.error || t('ai_assistant.docs.uploader.uploadErrorDefault')
      toast.error(error.value)
    }
  } catch (err) {
    error.value = err.message || t('ai_assistant.docs.uploader.unexpectedError')
    toast.error(error.value)
  } finally {
    uploading.value = false
  }
}

const createFromText = async () => {
  if (!textTitle.value.trim() || !textContent.value.trim()) return

  uploading.value = true
  error.value = null

  try {
    const result = await docsClient.createDocumentFromText(
      textTitle.value.trim(),
      textContent.value.trim(),
      '',
      {},
      indexImmediately.value
    )

    if (result.success) {
      toast.success(t('ai_assistant.docs.uploader.createSuccess'))
      emit('document-created', result.document)
      
      // Сброс формы
      textTitle.value = ''
      textContent.value = ''
      indexImmediately.value = false
    } else {
      error.value = result.error || t('ai_assistant.docs.uploader.createErrorDefault')
      toast.error(error.value)
    }
  } catch (err) {
    error.value = err.message || t('ai_assistant.docs.uploader.unexpectedError')
    toast.error(error.value)
  } finally {
    uploading.value = false
  }
}
</script>

<style scoped>
.document-uploader {
  padding: 0;
  background: transparent;
  --module-color: #8b5cf6;
}

.document-uploader :deep(.form-control) {
  background: color-mix(in srgb, var(--bs-body-bg) 50%, transparent);
  backdrop-filter: blur(5px);
  border-color: color-mix(in srgb, var(--bs-border-color) 40%, transparent);
  color: var(--bs-body-color);
}

.document-uploader :deep(.form-control:focus) {
  background: color-mix(in srgb, var(--bs-body-bg) 60%, transparent);
  border-color: var(--module-color, #8b5cf6);
  box-shadow: 0 0 0 0.2rem color-mix(in srgb, var(--module-color, #8b5cf6) 25%, transparent);
}

.document-uploader__header {
  margin-bottom: 1rem;
}

.document-uploader__tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
  border-bottom: 1px solid color-mix(in srgb, var(--bs-border-color) 40%, transparent);
}

.tab-btn {
  padding: 0.5rem 1rem;
  border: none;
  background: transparent;
  color: var(--bs-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.tab-btn:hover {
  color: var(--module-color, #8b5cf6);
  background: color-mix(in srgb, var(--module-color, #8b5cf6) 5%, transparent);
}

.tab-btn.active {
  color: var(--module-color, #8b5cf6);
  border-bottom-color: var(--module-color, #8b5cf6);
  background: color-mix(in srgb, var(--module-color, #8b5cf6) 8%, transparent);
}

.file-dropzone {
  border: 2px dashed color-mix(in srgb, var(--bs-border-color) 50%, transparent);
  border-radius: 0.5rem;
  padding: 2rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  background: color-mix(in srgb, var(--bs-body-bg) 30%, transparent);
  backdrop-filter: blur(5px);
}

.file-dropzone:hover,
.file-dropzone.dragover {
  border-color: var(--module-color, #8b5cf6);
  background-color: color-mix(in srgb, var(--module-color, #8b5cf6) 15%, transparent);
}

.dropzone-content {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.btn-link {
  background: none;
  border: none;
  color: var(--module-color, #8b5cf6);
  cursor: pointer;
  text-decoration: underline;
  padding: 0;
}

.selected-file {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem;
  background: color-mix(in srgb, var(--bs-body-bg) 40%, transparent);
  backdrop-filter: blur(8px);
  border-radius: 0.25rem;
  border: 1px solid color-mix(in srgb, var(--bs-border-color) 30%, transparent);
}

.file-size {
  margin-left: auto;
  color: var(--bs-secondary);
  font-size: 0.875rem;
}

.btn-remove {
  background: none;
  border: none;
  color: var(--bs-danger);
  cursor: pointer;
  padding: 0.25rem;
  display: flex;
  align-items: center;
}
</style>


