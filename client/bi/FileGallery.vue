<template>
  <div class="file-gallery">
    <div class="file-gallery__header">
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
      В этом подключении нет файлов.
    </div>

    <div v-else class="file-grid">
      <div
        v-for="file in files"
        :key="file.id"
        class="file-card"
        :class="{ 'file-card--selected': selectedFileId === file.id }"
        @click="selectFile(file)"
      >
        <div class="file-card__icon">
          <FileSpreadsheet v-if="file.file_type === 'csv'" :size="24" />
          <FileSpreadsheet v-else-if="file.file_type === 'xlsx'" :size="24" />
          <File v-else :size="24" />
        </div>
        <div class="file-card__info">
          <div class="file-card__name">{{ file.name }}</div>
          <div class="file-card__meta">
            <span class="badge bg-secondary">{{ file.file_type }}</span>
            <span class="file-card__date">{{ formatDate(file.uploaded_at) }}</span>
          </div>
        </div>
        <div v-if="selectedFileId === file.id" class="file-card__check">
          <Check :size="20" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { RefreshCw, FileSpreadsheet, File, Check } from 'lucide-vue-next'
import { biClient } from './js/bi-client.js'

const props = defineProps({
  connectionId: {
    type: Number,
    required: true,
  },
})

const emit = defineEmits(['file-selected'])

const files = ref([])
const loading = ref(false)
const error = ref(null)
const selectedFileId = ref(null)

const loadFiles = async () => {
  if (!props.connectionId) {
    files.value = []
    return
  }

  loading.value = true
  error.value = null

  try {
    const result = await biClient.getConnectionFiles(props.connectionId)

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

watch(
  () => props.connectionId,
  () => {
    selectedFileId.value = null
    loadFiles()
  },
  { immediate: true }
)

defineExpose({
  refreshFiles,
  selectedFile: () => files.value.find((f) => f.id === selectedFileId.value),
})
</script>

<style scoped>
.file-gallery {
  padding: 1rem;
}

.file-gallery__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.file-gallery__header h6 {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
}

.file-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 1rem;
}

.file-card {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  border: 1px solid #e9ecef;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: all 0.2s;
  background: white;
}

.file-card:hover {
  background-color: #f8f9fa;
  border-color: #dee2e6;
  transform: translateY(-2px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.file-card--selected {
  background-color: #e7f3ff;
  border-color: #0d6efd;
}

.file-card__icon {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  background: #e7f3ff;
  border-radius: 0.375rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #0d6efd;
}

.file-card--selected .file-card__icon {
  background: #0d6efd;
  color: white;
}

.file-card__info {
  flex: 1;
  min-width: 0;
}

.file-card__name {
  font-weight: 500;
  font-size: 0.9rem;
  margin-bottom: 0.25rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-card__meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: #6c757d;
}

.file-card__date {
  font-size: 0.75rem;
}

.file-card__check {
  flex-shrink: 0;
  color: #0d6efd;
  margin-left: 0.5rem;
}
</style>

