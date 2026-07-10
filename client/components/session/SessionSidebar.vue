<template>
  <aside class="session-sidebar">
    <div class="session-sidebar__toolbar">
      <SearchInput
        :model-value="searchQuery"
        placeholder="Поиск чатов..."
        layout="grow"
        :show-icon="true"
        @update:model-value="$emit('update:searchQuery', $event)"
      />
      <SelectBox
        :model-value="filterModule"
        :options="moduleFilterOptions"
        value-key="id"
        label-key="name"
        include-all-option
        all-label="Все модули"
        @update:model-value="$emit('update:filterModule', $event)"
      />
      <button type="button" class="btn btn-primary btn-sm w-100" @click="$emit('new-chat')">
        <Plus :size="16" class="me-1" />
        Новый чат
      </button>
    </div>

    <LoadingContentArea :loading="loading" min-height="12rem" class="session-sidebar__list">
      <div v-if="draftSession" class="session-item session-item--draft">
        <div
          class="session-item__icon"
          :style="{ color: getModuleColor(draftSession.module) }"
        >
          <component :is="getModuleIcon(draftSession.module)" :size="16" />
        </div>
        <div class="session-item__content">
          <span class="session-item__title">{{ draftSession.title }}</span>
          <span class="session-item__meta">Сохранится после ответа</span>
        </div>
      </div>

      <template v-for="module in enabledModules" :key="module.id">
        <div v-if="sessionsByModule[module.id]?.length" class="session-group">
          <div class="session-group__header">
            <component :is="module.icon" :size="14" :style="{ color: module.color }" />
            <span>{{ module.name }}</span>
            <span class="session-group__count">({{ sessionsByModule[module.id].length }})</span>
          </div>
          <div
            v-for="session in sessionsByModule[module.id]"
            :key="session.id"
            class="session-item"
            :class="{ 'session-item--active': activeSessionId === session.id }"
            @click="$emit('select-session', session.id, session.module)"
          >
            <div class="session-item__icon" :style="{ color: module.color }">
              <component :is="module.icon" :size="16" />
            </div>
            <div class="session-item__content">
              <span class="session-item__title">{{ session.title || 'Без названия' }}</span>
              <span class="session-item__meta">{{ formatSessionTime(session.updated_at || session.created_at) }}</span>
            </div>
            <DropDown class="session-item__menu" @click.stop>
              <template #main>
                <MoreHorizontal :size="16" />
              </template>
              <template #list>
                <li>
                  <span
                    class="dropdown-item text-danger"
                    @click="$emit('delete-session', session.id)"
                  >
                    <Trash2 :size="14" />
                    Удалить
                  </span>
                </li>
              </template>
            </DropDown>
          </div>
        </div>
      </template>

      <div v-if="!loading && !draftSession && totalCount === 0" class="session-empty">
        <MessageSquare :size="32" class="session-empty__icon" />
        <p class="mb-1">Нет чатов</p>
        <p class="session-empty__hint mb-0">Нажмите «Новый чат» или начните диалог в рабочей области.</p>
      </div>
    </LoadingContentArea>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { Plus, Trash2, MoreHorizontal, MessageSquare } from 'lucide-vue-next'
import SearchInput from '@/components/SearchInput.vue'
import SelectBox from '@/components/SelectBox.vue'
import DropDown from '@/components/DropDown.vue'
import LoadingContentArea from '@/components/LoadingContentArea.vue'
import { getRelativeTime } from '@/js/utils/timeUtils.js'
import { modules, getModuleById } from '../../modules/index.js'

const props = defineProps({
  loading: { type: Boolean, default: false },
  searchQuery: { type: String, default: '' },
  filterModule: { type: String, default: '' },
  sessionsByModule: { type: Object, default: () => ({}) },
  activeSessionId: { type: String, default: null },
  draftSession: { type: Object, default: null },
})

defineEmits(['update:searchQuery', 'update:filterModule', 'new-chat', 'select-session', 'delete-session'])

const enabledModules = computed(() => modules.filter((m) => !m.comingSoon))

const moduleFilterOptions = computed(() =>
  enabledModules.value.map((m) => ({ id: m.id, name: m.name })),
)

const totalCount = computed(() =>
  enabledModules.value.reduce((sum, m) => sum + (props.sessionsByModule[m.id]?.length || 0), 0),
)

function getModuleIcon(moduleId) {
  return getModuleById(moduleId)?.icon || MessageSquare
}

function getModuleColor(moduleId) {
  return getModuleById(moduleId)?.color || 'var(--bs-primary)'
}

function formatSessionTime(timestamp) {
  if (!timestamp) return ''
  return getRelativeTime(timestamp) || ''
}
</script>

<style lang="scss" scoped>
.session-sidebar {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-right: 1px solid var(--ui-border);
  padding: 1rem;
  background: var(--ui-surface);

  &__toolbar {
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
  }

  &__list {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    scrollbar-width: thin;
  }
}

.session-group {
  margin-bottom: 0.75rem;

  &__header {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--ui-text-muted, var(--bs-secondary-color));
    margin-bottom: 0.375rem;
    padding: 0 0.25rem;
  }

  &__count {
    font-weight: 400;
  }
}

.session-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.625rem;
  border-radius: 0.375rem;
  cursor: pointer;
  border: 1px solid transparent;

  &:hover {
    background: color-mix(in srgb, var(--ui-text) 4%, transparent);

    .session-item__menu {
      opacity: 1;
    }
  }

  &--active {
    background: color-mix(in srgb, var(--bs-primary) 10%, var(--ui-surface));
    border-color: color-mix(in srgb, var(--bs-primary) 30%, transparent);
  }

  &--draft {
    cursor: default;
    border-style: dashed;
    border-color: var(--ui-border);
    opacity: 0.85;
  }

  &__icon {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  &__content {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  &__title {
    font-size: 0.875rem;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  &__meta {
    font-size: 0.75rem;
    color: var(--ui-text-muted, var(--bs-secondary-color));
  }

  &__menu {
    opacity: 0;
    transition: opacity 0.15s;
    flex-shrink: 0;
  }
}

.session-empty {
  padding: 2rem 0.5rem;
  text-align: center;
  font-size: 0.875rem;
  color: var(--ui-text-muted, var(--bs-secondary-color));

  &__icon {
    margin-bottom: 0.75rem;
    opacity: 0.5;
  }

  &__hint {
    font-size: 0.8125rem;
  }
}
</style>
