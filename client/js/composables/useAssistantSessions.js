import { ref, computed } from 'vue'
import { useRouteQueryState } from '@/composables/useRouteQueryState.js'
import { ragClient } from '../../rag/js/rag-client.js'
import { modules } from '../../modules/index.js'
import { logError } from '@/js/utils/logError.js'

const MODULE_IDS = modules.filter((m) => !m.comingSoon).map((m) => m.id)

export function useAssistantSessions() {
  const sessions = ref([])
  const loading = ref(false)
  const draftSession = ref(null)

  const { state: routeState, patchState, watchState } = useRouteQueryState({
    session: { default: '' },
    module: { default: 'chat', enum: ['', ...MODULE_IDS] },
    q: { default: '' },
    filterModule: { default: '' },
  })

  const activeSessionId = computed(() => routeState.value.session || null)
  const activeModule = computed(() => routeState.value.module || 'chat')
  const searchQuery = computed(() => routeState.value.q)
  const filterModule = computed(() => routeState.value.filterModule)

  const filteredSessions = computed(() => {
    let list = sessions.value

    if (filterModule.value) {
      list = list.filter((s) => s.module === filterModule.value)
    }

    const q = searchQuery.value.trim().toLowerCase()
    if (q) {
      list = list.filter((s) => (s.title || 'Без названия').toLowerCase().includes(q))
    }

    return list
  })

  const sessionsByModule = computed(() => {
    const grouped = {}
    for (const moduleId of MODULE_IDS) {
      grouped[moduleId] = filteredSessions.value.filter((s) => s.module === moduleId)
    }
    return grouped
  })

  async function loadSessions() {
    loading.value = true
    try {
      const allSessions = []
      for (const moduleConfig of modules.filter((m) => !m.comingSoon)) {
        const result = await ragClient.getChatSessions(moduleConfig.id)
        if (result.success && result.sessions) {
          allSessions.push(...result.sessions)
        }
      }
      sessions.value = allSessions.sort((a, b) => {
        const dateA = new Date(a.updated_at || a.created_at || 0)
        const dateB = new Date(b.updated_at || b.created_at || 0)
        return dateB.getTime() - dateA.getTime()
      })
    } catch (error) {
      logError('Ошибка загрузки сессий чата', error)
    } finally {
      loading.value = false
    }
  }

  async function loadSession(sessionId) {
    return ragClient.getChatSession(sessionId)
  }

  async function createSession(moduleId, title) {
    const moduleConfig = modules.find((m) => m.id === moduleId)
    const sessionTitle = title || `Новый чат: ${moduleConfig?.name || moduleId}`
    return ragClient.createChatSession(sessionTitle, moduleId)
  }

  async function deleteSession(sessionId) {
    return ragClient.deleteChatSession(sessionId)
  }

  function selectSession(sessionId, moduleId) {
    draftSession.value = null
    return patchState({ session: sessionId, module: moduleId }, { immediate: true })
  }

  function selectModule(moduleId) {
    return patchState({ module: moduleId, session: '' }, { immediate: true })
  }

  function clearSession() {
    draftSession.value = null
    return patchState({ session: '' }, { immediate: true })
  }

  function startDraft(moduleId) {
    draftSession.value = { module: moduleId, title: 'Новый диалог…' }
    return patchState({ session: '', module: moduleId }, { immediate: true })
  }

  function attachSession(sessionId, moduleId) {
    draftSession.value = null
    return patchState({ session: sessionId, module: moduleId }, { immediate: true, silent: true })
  }

  function setSearchQuery(value) {
    return patchState({ q: value })
  }

  function setFilterModule(value) {
    return patchState({ filterModule: value }, { immediate: true })
  }

  return {
    sessions,
    loading,
    draftSession,
    routeState,
    activeSessionId,
    activeModule,
    searchQuery,
    filterModule,
    filteredSessions,
    sessionsByModule,
    loadSessions,
    loadSession,
    createSession,
    deleteSession,
    selectSession,
    selectModule,
    clearSession,
    startDraft,
    attachSession,
    setSearchQuery,
    setFilterModule,
    patchState,
    watchState,
  }
}
