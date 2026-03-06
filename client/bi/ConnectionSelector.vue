<template>
  <div class="connection-selector">
    <div class="connection-selector__header">
      <h6 class="mb-2">Выберите подключение</h6>
      <button class="btn btn-sm btn-outline-secondary" @click="refreshConnections">
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

    <div v-else-if="connections.length === 0" class="alert alert-info">
      У вас пока нет подключений. Создайте подключение в модуле BI.
    </div>

    <div v-else class="connection-grid">
      <div
        v-for="connection in connections"
        :key="connection.id"
        class="connection-card"
        :class="{ 'connection-card--selected': selectedConnectionId === connection.id }"
        @click="selectConnection(connection)"
      >
        <div class="connection-card__icon">
          <Database :size="24" />
        </div>
        <div class="connection-card__info">
          <div class="connection-card__name">{{ connection.name }}</div>
          <div class="connection-card__meta">
            <span class="badge bg-secondary">{{ connection.connector_type_display || connection.connector_type }}</span>
          </div>
        </div>
        <div v-if="selectedConnectionId === connection.id" class="connection-card__check">
          <Check :size="20" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { RefreshCw, Database, Check } from 'lucide-vue-next'
import { biClient } from './js/bi-client.js'

const emit = defineEmits(['connection-selected'])

const connections = ref([])
const loading = ref(false)
const error = ref(null)
const selectedConnectionId = ref(null)

const loadConnections = async () => {
  loading.value = true
  error.value = null

  try {
    const result = await biClient.getConnections()

    if (result.success) {
      connections.value = result.connections
    } else {
      error.value = result.error
    }
  } catch (err) {
    error.value = 'Ошибка загрузки подключений: ' + err.message
  } finally {
    loading.value = false
  }
}

const refreshConnections = () => {
  loadConnections()
}

const selectConnection = (connection) => {
  selectedConnectionId.value = connection.id
  emit('connection-selected', connection)
}

onMounted(() => {
  loadConnections()
})

defineExpose({
  refreshConnections,
  selectedConnection: () => connections.value.find((c) => c.id === selectedConnectionId.value),
})
</script>

<style scoped>
.connection-selector {
  padding: 1rem;
}

.connection-selector__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.connection-selector__header h6 {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
}

.connection-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 1rem;
}

.connection-card {
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

.connection-card:hover {
  background-color: #f8f9fa;
  border-color: #dee2e6;
  transform: translateY(-2px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.connection-card--selected {
  background-color: #e7f3ff;
  border-color: #0d6efd;
}

.connection-card__icon {
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

.connection-card--selected .connection-card__icon {
  background: #0d6efd;
  color: white;
}

.connection-card__info {
  flex: 1;
  min-width: 0;
}

.connection-card__name {
  font-weight: 500;
  font-size: 0.9rem;
  margin-bottom: 0.25rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.connection-card__meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: #6c757d;
}

.connection-card__check {
  flex-shrink: 0;
  color: #0d6efd;
  margin-left: 0.5rem;
}
</style>


