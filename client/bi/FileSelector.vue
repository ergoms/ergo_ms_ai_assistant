<template>
  <div class="file-selector">
    <div class="file-selector__header">
      <h6 class="mb-2">Выберите файл для анализа</h6>
      <button class="btn btn-sm btn-outline-secondary" @click="refreshFiles">
        <RefreshCw :size="14" class="me-1" />
        Обновить
      </button>
    </div>

    <div v-if="loading" class="text-center py-3">
      <div class="spinner-border spinner-border-sm" role="status">
        <span class="visually-hidden">Загрузка...</span>
      </div>
    </div>

    <div v-else-if="error" class="alert alert-danger">
      {{ error }}
    </div>

    <div v-else-if="files.length === 0" class="alert alert-info">
      У вас пока нет загруженных файлов. Загрузите файлы в модуле BI.
    </div>

    <div v-else class="file-list">
      <div
        v-for="file in files"
        :key="file.id"
        class="file-item"
        :class="{ 'file-item--selected': selectedFileId === file.id }"
        @click="selectFile(file)"
      >
        <div class="file-item__icon">
          <FileSpreadsheet v-if="file.file_type === 'csv'" :size="20" />
          <FileSpreadsheet v-else-if="file.file_type === 'xlsx'" :size="20" />
          <File v-else :size="20" />
        </div>
        <div class="file-item__info">
          <div class="file-item__name">{{ file.name }}</div>
          <div class="file-item__meta">
            <span class="badge bg-secondary">{{ file.file_type }}</span>
            <span class="file-item__date">{{ formatDate(file.uploaded_at) }}</span>
          </div>
        </div>
        <div v-if="selectedFileId === file.id" class="file-item__check">
          <Check :size="20" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { RefreshCw, FileSpreadsheet, File, Check } from 'lucide-vue-next'
import { biClient } from './js/bi-client.js'

const emit = defineEmits(['file-selected'])

const files = ref([])
const loading = ref(false)
const error = ref(null)
const selectedFileId = ref(null)

const loadFiles = async () => {
  loading.value = true
  error.value = null

  try {
    const result = await biClient.getUserFiles()

    if (result.success) {
      files.value = result.files
    } else {
      error.value = result.error
    }
  } catch (err) {
    error.value = 'Ошибка загрузки файлов: ' + err.message
  } finally {
    loading.value = false
  }
}

const refreshFiles = () => {
  loadFiles()
}

const selectFile = (file) => {
  selectedFileId.value = file.id
  emit('file-selected', file)
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('ru-RU', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(() => {
  loadFiles()
})

defineExpose({
  refreshFiles,
  selectedFile: () => files.value.find((f) => f.id === selectedFileId.value),
})
</script>

<style scoped>
.file-selector {
  padding: 1rem;
}

.file-selector__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.file-selector__header h6 {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
}

.file-list {
  max-height: 300px;
  overflow-y: auto;
}

.file-item {
  display: flex;
  align-items: center;
  padding: 0.75rem;
  border: 1px solid #e9ecef;
  border-radius: 0.375rem;
  margin-bottom: 0.5rem;
  cursor: pointer;
  transition: all 0.2s;
}

.file-item:hover {
  background-color: #f8f9fa;
  border-color: #dee2e6;
}

.file-item--selected {
  background-color: #e7f3ff;
  border-color: #0d6efd;
}

.file-item__icon {
  flex-shrink: 0;
  margin-right: 0.75rem;
  color: #6c757d;
}

.file-item--selected .file-item__icon {
  color: #0d6efd;
}

.file-item__info {
  flex: 1;
  min-width: 0;
}

.file-item__name {
  font-weight: 500;
  font-size: 0.9rem;
  margin-bottom: 0.25rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-item__meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: #6c757d;
}

.file-item__date {
  font-size: 0.75rem;
}

.file-item__check {
  flex-shrink: 0;
  color: #0d6efd;
  margin-left: 0.5rem;
}
</style>




