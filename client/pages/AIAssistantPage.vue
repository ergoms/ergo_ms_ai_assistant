<template>
  <div class="admin-page ai-assistant-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">AI-ассистент</h1>
        <p class="page-subtitle text-muted mb-0">
          Чат, анализ данных и база знаний
        </p>
      </div>
      <div class="page-header__actions">
        <div class="ai-assistant-page__status-line" :title="status.message">
          <span
            class="ai-assistant-page__status-dot"
            :class="statusVariant === 'success' ? 'ai-assistant-page__status-dot--ok' : 'ai-assistant-page__status-dot--err'"
          />
          <span class="ai-assistant-page__status-text">{{ statusLabel }}</span>
        </div>
        <button
          type="button"
          class="btn btn-sm btn-outline-secondary"
          :disabled="ollamaLoading"
          @click="refreshOllama(true)"
        >
          <RefreshCw :size="14" :class="{ spinning: ollamaLoading }" />
        </button>
      </div>
    </div>

    <div v-if="!status.available" class="alert alert-warning mx-0 mb-3">
      {{ status.message }}
      <span class="d-block small mt-1">Запустите Ollama: <code>ergoms ollama_framework:start-ollama</code></span>
    </div>

    <div class="content-card ai-assistant-page__layout">
      <SessionSidebar
        :loading="sessionsLoading"
        :search-query="searchQuery"
        :filter-module="filterModule"
        :sessions-by-module="sessionsByModule"
        :active-session-id="activeSessionId"
        :draft-session="draftSession"
        @update:search-query="setSearchQuery"
        @update:filter-module="setFilterModule"
        @new-chat="showNewChatModal = true"
        @select-session="handleSelectSession"
        @delete-session="handleDeleteSession"
      />

      <main class="ai-assistant-page__workspace">
        <div class="ai-assistant-page__workspace-header">
          <div v-if="!activeSessionId" class="ai-assistant-page__module-chips">
            <button
              v-for="module in moduleOptions"
              :key="module.id"
              type="button"
              class="ai-assistant-page__module-chip"
              :class="{ 'ai-assistant-page__module-chip--active': activeModule === module.id }"
              :style="{ '--chip-color': module.color }"
              @click="handleModuleChange(module.id)"
            >
              <component :is="module.icon" :size="16" />
              <span>{{ module.name }}</span>
            </button>
            <SelectBox
              class="ai-assistant-page__module-select"
              :model-value="activeModule"
              :options="moduleOptions"
              value-key="id"
              label-key="name"
              :include-all-option="false"
              @update:model-value="handleModuleChange"
            />
          </div>
          <div v-else class="ai-assistant-page__module-title">
            <component :is="currentModuleConfig?.icon" :size="18" />
            <span>{{ currentModuleConfig?.name }}</span>
          </div>
        </div>

        <div class="ai-assistant-page__panel">
          <div v-if="currentModuleConfig?.comingSoon" class="ai-assistant-page__coming-soon">
            <h2 class="h5">В разработке</h2>
            <p class="text-muted mb-0">Модуль «{{ currentModuleConfig?.name }}» скоро будет доступен.</p>
          </div>

          <ChatPanel
            v-else-if="activeModule === 'chat'"
            ref="chatPanelRef"
            :session-id="activeSessionId"
            @session-created="handleSessionCreated"
            @draft-started="handleDraftStarted"
          />
          <BiPanel
            v-else-if="activeModule === 'bi'"
            ref="biPanelRef"
            :session-id="activeSessionId"
            @session-created="handleSessionCreated"
            @draft-started="handleDraftStarted"
          />
          <DocsPanel
            v-else-if="activeModule === 'docs'"
            ref="docsPanelRef"
            :session-id="activeSessionId"
            @session-created="handleSessionCreated"
            @draft-started="handleDraftStarted"
          />
        </div>
      </main>
    </div>

    <NewChatModal
      :visible="showNewChatModal"
      @close="showNewChatModal = false"
      @select="handleNewChatSelect"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import SelectBox from '@/components/SelectBox.vue'
import { confirmDelete } from '@/js/utils/confirm.js'
import { useToast } from '@/js/utils/toast.js'
import { useOllamaStatus } from '../js/composables/useOllamaStatus.js'
import { useAssistantSessions } from '../js/composables/useAssistantSessions.js'
import SessionSidebar from '../components/session/SessionSidebar.vue'
import NewChatModal from '../components/NewChatModal.vue'
import ChatPanel from '../components/chat/ChatPanel.vue'
import BiPanel from '../components/bi/BiPanel.vue'
import DocsPanel from '../docs/DocsPanel.vue'
import { modules, getModuleById } from '../modules/index.js'

const toast = useToast()
const showNewChatModal = ref(false)
const chatPanelRef = ref(null)
const biPanelRef = ref(null)
const docsPanelRef = ref(null)

const {
  loading: ollamaLoading,
  status,
  statusLabel,
  statusVariant,
  refresh: refreshOllama,
} = useOllamaStatus()

const {
  loading: sessionsLoading,
  draftSession,
  activeSessionId,
  activeModule,
  searchQuery,
  filterModule,
  sessionsByModule,
  loadSessions,
  createSession,
  deleteSession,
  selectSession,
  selectModule,
  clearSession,
  startDraft,
  attachSession,
  setSearchQuery,
  setFilterModule,
  watchState,
} = useAssistantSessions()

const moduleOptions = computed(() =>
  modules.filter((m) => !m.comingSoon).map((m) => ({
    id: m.id,
    name: m.name,
    icon: m.icon,
    color: m.color,
  })),
)

const currentModuleConfig = computed(() => getModuleById(activeModule.value))

function resetActivePanel() {
  if (activeModule.value === 'chat') chatPanelRef.value?.reset()
  else if (activeModule.value === 'bi') biPanelRef.value?.reset()
  else if (activeModule.value === 'docs') docsPanelRef.value?.reset()
}

async function handleSelectSession(sessionId, moduleId) {
  await selectSession(sessionId, moduleId)
}

async function handleDeleteSession(sessionId) {
  const ok = await confirmDelete('Удаление чата', 'Вы уверены, что хотите удалить этот чат?')
  if (!ok) return

  const result = await deleteSession(sessionId)
  if (result.success) {
    if (activeSessionId.value === sessionId) {
      await clearSession()
      resetActivePanel()
    }
    await loadSessions()
    toast.success('Чат удалён')
  } else {
    toast.error(result.error || 'Не удалось удалить чат')
  }
}

async function handleNewChatSelect(moduleId) {
  showNewChatModal.value = false
  const moduleConfig = getModuleById(moduleId)
  if (!moduleConfig) {
    toast.error('Модуль не найден')
    return
  }

  const result = await createSession(moduleId, `Новый чат: ${moduleConfig.name}`)
  if (result.success) {
    await selectSession(result.session.id, moduleId)
    await loadSessions()
    resetActivePanel()
  } else {
    toast.error(result.error || 'Не удалось создать чат')
  }
}

function handleModuleChange(moduleId) {
  selectModule(moduleId)
  resetActivePanel()
}

function handleDraftStarted(moduleId) {
  startDraft(moduleId)
}

async function handleSessionCreated({ sessionId, module }) {
  await attachSession(sessionId, module)
  await loadSessions()
}

watchState(() => {
  loadSessions()
})

onMounted(() => {
  loadSessions()
})
</script>

<style lang="scss" scoped>
@import '@/core/cms/adp/admin/admin-page.scss';

.ai-assistant-page {
  display: flex;
  flex-direction: column;
  min-height: calc(100dvh - var(--admin-page-offset, 120px));

  &__status-line {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    max-width: 280px;
    font-size: 0.8125rem;
    color: var(--ui-text-muted, var(--bs-secondary-color));
  }

  &__status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;

    &--ok {
      background: var(--bs-success);
    }

    &--err {
      background: var(--bs-danger);
    }
  }

  &__status-text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__layout {
    flex: 1;
    display: flex;
    min-height: 0;
    padding: 0;
    overflow: hidden;
  }

  &__workspace {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
  }

  &__workspace-header {
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--ui-border);
    background: var(--ui-surface);
  }

  &__module-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
  }

  &__module-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.75rem;
    border: 1px solid var(--ui-border);
    border-radius: 999px;
    background: var(--ui-surface);
    color: var(--ui-text);
    font-size: 0.875rem;
    transition: border-color 0.15s, background 0.15s;

    &:hover {
      border-color: var(--chip-color, var(--bs-primary));
    }

    &--active {
      border-color: var(--chip-color, var(--bs-primary));
      background: color-mix(in srgb, var(--chip-color, var(--bs-primary)) 10%, var(--ui-surface));
      color: var(--chip-color, var(--bs-primary));
    }
  }

  &__module-select {
    display: none;
    min-width: 180px;
  }

  &__module-title {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: 600;
  }

  &__panel {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  &__coming-soon {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    text-align: center;
  }
}

.page-header__actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media (max-width: 640px) {
  .ai-assistant-page__module-chips {
    .ai-assistant-page__module-chip {
      display: none;
    }

    .ai-assistant-page__module-select {
      display: block;
      width: 100%;
    }
  }
}
</style>
