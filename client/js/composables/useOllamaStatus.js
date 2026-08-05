import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getPermissionsSnapshot } from '@/core/cms/adp/js/accessControl.js'
import { getSessionBootstrapCache } from '@/core/cms/js/sessionBootstrapCache.js'
import { fetchOllamaStatus, resetOllamaStatusCache } from '../ollamaStatusApi.js'
import { formatOllamaModelLabel } from '../formatOllamaModelLabel.js'
import { tGlobal } from '@/i18n/index.js'

const POLL_INTERVAL_MS = 60000

function readIsGlobalAdminFromBootstrap() {
  const permissions = getSessionBootstrapCache()?.permissions
  return Boolean(permissions?.is_global_admin)
}

export function useOllamaStatus(options = {}) {
  const { includeEmbeddings = false, autoPoll = true } = options

  const loading = ref(false)
  const isGlobalAdmin = ref(readIsGlobalAdminFromBootstrap())
  const status = ref({
    available: false,
    model: null,
    models: [],
    message: tGlobal('common.loading'),
    error: null,
    embeddings: undefined,
    embeddingsMessage: null,
  })

  let pollTimer = null

  const showModelInfo = computed(() => isGlobalAdmin.value)

  const modelDisplayName = computed(() => {
    if (!showModelInfo.value || !status.value.available || !status.value.model) {
      return ''
    }
    return formatOllamaModelLabel(status.value.model)
  })

  const modelSubtitle = computed(() => {
    if (!showModelInfo.value) {
      return null
    }
    if (loading.value && !status.value.available) {
      return tGlobal('ai_assistant.modelLoading')
    }
    if (modelDisplayName.value) {
      return modelDisplayName.value
    }
    if (!status.value.available) {
      return tGlobal('ai_assistant.modelUnavailable')
    }
    return null
  })

  /** Статус подключения для индикатора (без дублирования имени модели). */
  const connectionStatusLabel = computed(() => {
    if (!showModelInfo.value) {
      return ''
    }
    if (loading.value && !status.value.available) {
      return tGlobal('ai_assistant.modelLoading')
    }
    if (status.value.available) {
      return tGlobal('ai_assistant.ollama.available')
    }
    return status.value.message || tGlobal('ai_assistant.modelUnavailable')
  })

  /** @deprecated Используйте modelSubtitle или connectionStatusLabel. */
  const statusLabel = connectionStatusLabel

  const statusVariant = computed(() => (status.value.available ? 'success' : 'danger'))

  async function refresh(force = true) {
    loading.value = true
    try {
      if (force) {
        resetOllamaStatusCache()
      }
      const result = await fetchOllamaStatus({ force, includeEmbeddings })
      status.value = result
    } finally {
      loading.value = false
    }
  }

  function startPolling() {
    if (pollTimer) return
    pollTimer = setInterval(() => refresh(false), POLL_INTERVAL_MS)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  onMounted(async () => {
    refresh(true)
    if (autoPoll) {
      startPolling()
    }
    const snapshot = await getPermissionsSnapshot()
    isGlobalAdmin.value = Boolean(snapshot?.is_global_admin)
  })

  onUnmounted(() => {
    stopPolling()
  })

  return {
    loading,
    status,
    isGlobalAdmin,
    showModelInfo,
    modelDisplayName,
    modelSubtitle,
    connectionStatusLabel,
    statusLabel,
    statusVariant,
    refresh,
    startPolling,
    stopPolling,
  }
}
