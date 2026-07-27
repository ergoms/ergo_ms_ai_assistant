import { ref, computed, onMounted, onUnmounted } from 'vue'
import { fetchOllamaStatus, resetOllamaStatusCache } from '../ollamaStatusApi.js'
import { tGlobal } from '@/i18n/index.js'

const POLL_INTERVAL_MS = 60000

export function useOllamaStatus(options = {}) {
  const { includeEmbeddings = false, autoPoll = true } = options

  const loading = ref(false)
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

  const statusLabel = computed(() => {
    if (loading.value && !status.value.available) {
      return tGlobal('ai_assistant.ollama.checking')
    }
    if (status.value.available) {
      return status.value.model || 'Ollama'
    }
    return status.value.message || tGlobal('ai_assistant.modelUnavailable')
  })

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

  onMounted(() => {
    refresh(true)
    if (autoPoll) {
      startPolling()
    }
  })

  onUnmounted(() => {
    stopPolling()
  })

  return {
    loading,
    status,
    statusLabel,
    statusVariant,
    refresh,
    startPolling,
    stopPolling,
  }
}
