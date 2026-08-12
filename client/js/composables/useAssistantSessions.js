import { ref, computed } from 'vue'
import { useRouteQueryState } from '@/composables/useRouteQueryState.js'
import { ragClient } from '../../rag/js/rag-client.js'
import { modules } from '../../modules/index.js'
import { logError } from '@/js/utils/logError.js'
import { tGlobal } from '@/i18n/index.js'

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
      list = list.filter((s) => (s.title || tGlobal('ai_assistant.untitled')).toLowerCase().includes(q))
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

  async function loadSessions(moduleId = 'chat') {
    loading.value = true
    try {
      const result = await ragClient.getChatSessions(moduleId || 'chat')
      const list = result.success && result.sessions ? result.sessions : []
      sessions.value = list.sort((a, b) => {
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

  async function createSession(moduleId = 'chat', title) {
    const sessionTitle = title || tGlobal('ai_assistant.sidebar.newChat')
    return ragClient.createChatSession(sessionTitle, moduleId || 'chat')
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
    draftSession.value = { module: moduleId, title: tGlobal('ai_assistant.newDialogDraft') }
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
