<template>
  <div class="document-selector">
    <div class="document-selector__header">
      <h6 class="mb-2">Выберите документ</h6>
      <SearchInput
        v-model="searchQuery"
        placeholder="Поиск документов..."
        layout="grow"
        :show-icon="true"
        class="mb-2"
      />
      <div class="header-actions">
        <button class="btn btn-sm btn-outline-secondary" @click="refreshDocuments">
          <RefreshCw :size="14" class="me-1" :class="{ spinning: loading }" />
          Обновить
        </button>
        <button class="btn btn-sm btn-primary" @click="showUploader = !showUploader">
          <Upload :size="14" class="me-1" />
          Загрузить
        </button>
      </div>
    </div>

    <!-- Загрузчик документов -->
    <div v-if="showUploader" class="document-selector__uploader mb-3">
      <DocumentUploader
        @document-uploaded="handleDocumentUploaded"
        @document-created="handleDocumentCreated"
      />
    </div>

    <!-- Список документов -->
    <div v-if="loading" class="text-center py-3">
      <div class="spinner-border spinner-border-sm" role="status">
        <span class="visually-hidden">Загрузка...</span>
      </div>
    </div>

    <div v-else-if="error" class="alert alert-danger" style="background: color-mix(in srgb, var(--bs-danger) 80%, transparent); backdrop-filter: blur(10px);">
      {{ error }}
    </div>

    <div v-else-if="filteredDocuments.length === 0" class="empty-state">
      <div class="empty-state__icon">
        <FileText :size="48" />
      </div>
      <h6 class="empty-state__title">
        {{ searchQuery.trim() ? 'Ничего не найдено' : 'Нет документов' }}
      </h6>
      <p class="empty-state__text">
        {{ searchQuery.trim() ? 'Измените запрос или загрузите новый документ' : 'Загрузите документ, чтобы начать работу с базой знаний' }}
      </p>
      <button v-if="!searchQuery.trim()" class="btn btn-primary" @click="showUploader = true">
        <Upload :size="16" class="me-2" />
        Загрузить первый документ
      </button>
    </div>

    <div v-else class="document-list">
      <div
        v-for="document in filteredDocuments"
        :key="document.id"
        class="document-item"
        :class="{ 'document-item--selected': selectedDocumentId === document.id }"
        @click="selectDocument(document)"
      >
        <div class="document-item__icon">
          <FileText v-if="!document.has_file" :size="20" />
          <File v-else-if="document.file_type === 'pdf'" :size="20" />
          <FileText v-else-if="document.file_type === 'docx'" :size="20" />
          <FileText v-else :size="20" />
        </div>
        <div class="document-item__info">
          <div class="document-item__name">{{ document.title }}</div>
          <div class="document-item__meta">
            <span v-if="document.file_type" class="badge bg-secondary me-2">
              {{ document.file_type.toUpperCase() }}
            </span>
            <span v-if="document.is_indexed" class="badge bg-success me-2">
              Индексирован ({{ document.chunks_count }})
            </span>
            <span v-else class="badge bg-warning me-2">
              Не индексирован
            </span>
            <span class="document-item__date">{{ formatDate(document.created_at) }}</span>
          </div>
          <div v-if="document.content_preview" class="document-item__preview">
            {{ document.content_preview }}
          </div>
        </div>
        <div v-if="selectedDocumentId === document.id" class="document-item__check">
          <Check :size="20" />
        </div>
        <div class="document-item__actions">
          <button
            class="action-btn"
            :title="document.is_indexed ? 'Переиндексировать' : 'Индексировать'"
            @click.stop="toggleIndex(document)"
          >
            <Database :size="14" />
          </button>
          <button
            class="action-btn text-danger"
            title="Удалить"
            @click.stop="deleteDocument(document)"
          >
            <Trash2 :size="14" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RefreshCw, Upload, FileText, File, Check, Database, Trash2 } from 'lucide-vue-next'
import SearchInput from '@/components/SearchInput.vue'
import { docsClient } from './js/docs-client.js'
import DocumentUploader from './DocumentUploader.vue'
import { useToast } from '@/js/utils/toast.js'
import { confirmDelete } from '@/js/utils/confirm.js'

const toast = useToast()

const emit = defineEmits(['document-selected'])

const documents = ref([])
const loading = ref(false)
const error = ref(null)
const selectedDocumentId = ref(null)
const showUploader = ref(false)
const searchQuery = ref('')

const filteredDocuments = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return documents.value
  return documents.value.filter((doc) => {
    const title = (doc.title || '').toLowerCase()
    const preview = (doc.content_preview || '').toLowerCase()
    return title.includes(q) || preview.includes(q)
  })
})

const loadDocuments = async () => {
  loading.value = true
  error.value = null

  try {
    const result = await docsClient.getDocuments()

    if (result.success) {
      documents.value = result.documents
    } else {
      error.value = result.error || 'Не удалось загрузить документы'
    }
  } catch (err) {
    error.value = 'Ошибка загрузки документов: ' + err.message
  } finally {
    loading.value = false
  }
}

const refreshDocuments = () => {
  loadDocuments()
}

const selectDocument = (document) => {
  selectedDocumentId.value = document.id
  emit('document-selected', document)
}

const handleDocumentUploaded = (document) => {
  showUploader.value = false
  loadDocuments()
  if (document.is_indexed) {
    selectDocument(document)
  }
}

const handleDocumentCreated = (document) => {
  showUploader.value = false
  loadDocuments()
  if (document.is_indexed) {
    selectDocument(document)
  }
}

const toggleIndex = async (document) => {
  try {
    if (document.is_indexed) {
      // Переиндексировать
      const result = await docsClient.indexDocument(document.id, true)
      if (result.success) {
        toast.success('Документ переиндексирован')
        loadDocuments()
      } else {
        toast.error(result.error || 'Ошибка индексации')
      }
    } else {
      // Индексировать
      const result = await docsClient.indexDocument(document.id, false)
      if (result.success) {
        toast.success('Документ индексирован')
        loadDocuments()
        selectDocument({ ...document, is_indexed: true })
      } else {
        toast.error(result.error || 'Ошибка индексации')
      }
    }
  } catch (err) {
    toast.error(err.message || 'Ошибка индексации')
  }
}

const deleteDocument = async (document) => {
  const ok = await confirmDelete('Удаление', `Удалить документ "${document.title}"?`)
  if (!ok) {
    return
  }

  try {
    const result = await docsClient.deleteDocument(document.id)
    if (result.success) {
      toast.success('Документ удален')
      if (selectedDocumentId.value === document.id) {
        selectedDocumentId.value = null
        emit('document-selected', null)
      }
      loadDocuments()
    } else {
      toast.error(result.error || 'Ошибка удаления')
    }
  } catch (err) {
    toast.error(err.message || 'Ошибка удаления')
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('ru-RU', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

// Экспортируем метод для вызова из родительского компонента
defineExpose({
  loadDocuments,
})

onMounted(() => {
  loadDocuments()
})
</script>

<style scoped>
.document-selector {
  padding: 1rem;
  background: transparent;
  --module-color: #8b5cf6;
  position: relative;
  z-index: 1;
}

.document-selector__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  background: transparent;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
}

.document-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  background: transparent;
  position: relative;
  z-index: 1;
}

.document-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem;
  border: 1px solid var(--bs-border-color);
  border-radius: 0.5rem;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.document-item:hover {
  border-color: var(--bs-primary);
  background-color: rgba(var(--bs-primary-rgb), 0.05);
}

.document-item--selected {
  border-color: var(--bs-primary);
  background-color: rgba(var(--bs-primary-rgb), 0.1);
}

.document-item__icon {
  flex-shrink: 0;
  color: var(--bs-primary);
}

.document-item__info {
  flex: 1;
  min-width: 0;
}

.document-item__name {
  font-weight: 600;
  margin-bottom: 0.25rem;
  word-break: break-word;
}

.document-item__meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
  flex-wrap: wrap;
}

.document-item__date {
  color: var(--bs-secondary);
  font-size: 0.875rem;
}

.document-item__preview {
  color: var(--bs-secondary);
  font-size: 0.875rem;
  margin-top: 0.25rem;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.document-item__check {
  flex-shrink: 0;
  color: var(--module-color, #8b5cf6);
}

.document-item__actions {
  display: flex;
  gap: 0.25rem;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.2s;
}

.document-item:hover .document-item__actions {
  opacity: 1;
}

.action-btn {
  background: none;
  border: none;
  padding: 0.25rem;
  cursor: pointer;
  color: var(--bs-secondary);
  display: flex;
  align-items: center;
  transition: color 0.2s;
}

.action-btn:hover {
  color: var(--module-color, #8b5cf6);
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.empty-state {
  text-align: center;
  padding: 3rem 1rem;
  background: transparent;
  position: relative;
  z-index: 1;
}

.empty-state__icon {
  color: var(--bs-secondary);
  margin-bottom: 1rem;
}

.empty-state__title {
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.empty-state__text {
  color: var(--bs-secondary);
  margin-bottom: 1.5rem;
}
</style>


