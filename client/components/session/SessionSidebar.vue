<template>
  <aside class="session-sidebar">
    <div class="session-sidebar__toolbar">
      <SearchInput
        :model-value="searchQuery"
        :placeholder="t('ai_assistant.sidebar.searchPlaceholder')"
        layout="grow"
        :show-icon="true"
        @update:model-value="$emit('update:searchQuery', $event)"
      />
      <button type="button" class="btn btn-primary btn-sm w-100" @click="$emit('new-chat')">
        <Plus :size="16" class="me-1" />
        {{ t('ai_assistant.sidebar.newChat') }}
      </button>
    </div>

    <LoadingContentArea :loading="loading" min-height="12rem" class="session-sidebar__list">
      <div v-if="draftSession" class="session-item session-item--draft">
        <div class="session-item__icon">
          <MessageSquare :size="16" />
        </div>
        <div class="session-item__content">
          <span class="session-item__title">{{ draftSession.title }}</span>
          <span class="session-item__meta">{{ t('ai_assistant.sidebar.draftMeta') }}</span>
        </div>
      </div>

      <div
        v-for="session in sessions"
        :key="session.id"
        class="session-item"
        :class="{ 'session-item--active': activeSessionId === session.id }"
        @click="$emit('select-session', session.id)"
      >
        <div class="session-item__icon">
          <MessageSquare :size="16" />
        </div>
        <div class="session-item__content">
          <span class="session-item__title">{{ session.title || t('ai_assistant.untitled') }}</span>
          <span class="session-item__meta">{{ formatSessionTime(session.updated_at || session.created_at) }}</span>
        </div>
        <button
          type="button"
          class="session-item__delete"
          :title="t('ai_assistant.sidebar.delete')"
          :aria-label="t('ai_assistant.sidebar.delete')"
          @click.stop="$emit('delete-session', session.id)"
        >
          <Trash2 :size="14" />
        </button>
      </div>

      <div v-if="!loading && !draftSession && sessions.length === 0" class="session-empty">
        <MessageSquare :size="32" class="session-empty__icon" />
        <p class="mb-1">{{ t('ai_assistant.noChats') }}</p>
        <p class="session-empty__hint mb-0">{{ t('ai_assistant.sidebar.emptyHint') }}</p>
      </div>
    </LoadingContentArea>
  </aside>
</template>

<script setup>
import { Plus, Trash2, MessageSquare } from '@lucide/vue'
import SearchInput from '@/components/SearchInput.vue'
import LoadingContentArea from '@/components/LoadingContentArea.vue'
import { getRelativeTime } from '@/js/utils/timeUtils.js'
import { useAppI18n } from '@/i18n/useAppI18n.js'

const { t } = useAppI18n()

defineProps({
  loading: { type: Boolean, default: false },
  searchQuery: { type: String, default: '' },
  sessions: { type: Array, default: () => [] },
  activeSessionId: { type: String, default: null },
  draftSession: { type: Object, default: null },
})

defineEmits(['update:searchQuery', 'new-chat', 'select-session', 'delete-session'])

function formatSessionTime(timestamp) {
  if (!timestamp) return ''
  return getRelativeTime(timestamp) || ''
}
</script>

<style lang="scss" scoped>
.session-sidebar {
  width: 100%;
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-right: none;
  padding: 0;
  background: transparent;

  &__toolbar {
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-bottom: 0.75rem;

    :deep(.search-input) {
      --search-input-height: 38px;
      --search-input-font-size: 0.875rem;
    }

    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 38px;
      gap: 0.25rem;
      line-height: 1.2;
    }
  }

  &__list {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    scrollbar-width: thin;
  }
}

.session-item {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  min-height: 2.75rem;
  padding: 0.5rem 0.5rem 0.5rem 0.625rem;
  border-radius: 0.5rem;
  cursor: pointer;
  border: 1px solid transparent;
  box-sizing: border-box;

  &:hover {
    background: color-mix(in srgb, var(--text-primary, var(--ui-text)) 5%, transparent);

    .session-item__delete {
      opacity: 1;
    }
  }

  &--active {
    background: color-mix(in srgb, var(--accent, var(--bs-primary)) 10%, transparent);
    border-color: color-mix(in srgb, var(--accent, var(--bs-primary)) 28%, transparent);

    .session-item__delete {
      opacity: 1;
    }
  }

  &--draft {
    cursor: default;
    border-style: dashed;
    border-color: var(--border-subtle, var(--ui-border));
    opacity: 0.85;
  }

  &__icon {
    flex-shrink: 0;
    width: 1.75rem;
    height: 1.75rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 0.375rem;
    color: var(--accent, var(--bs-primary));
    background: color-mix(in srgb, var(--accent, var(--bs-primary)) 12%, transparent);
  }

  &__content {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 0.125rem;
  }

  &__title {
    font-size: 0.875rem;
    font-weight: 500;
    line-height: 1.25;
    color: var(--text-primary, var(--ui-text));
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  &__meta {
    font-size: 0.75rem;
    line-height: 1.2;
    color: var(--text-muted, var(--ui-text-muted, var(--bs-secondary-color)));
  }

  &__delete {
    flex-shrink: 0;
    width: 1.75rem;
    height: 1.75rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    border: none;
    border-radius: 0.375rem;
    background: transparent;
    color: var(--text-muted, var(--ui-text-muted));
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.15s, background 0.15s, color 0.15s;

    &:hover {
      background: color-mix(in srgb, var(--bs-danger, #dc3545) 12%, transparent);
      color: var(--bs-danger, #dc3545);
    }
  }
}

.session-empty {
  padding: 2rem 0.5rem;
  text-align: center;
  font-size: 0.875rem;
  color: var(--text-muted, var(--ui-text-muted, var(--bs-secondary-color)));

  &__icon {
    display: block;
    margin: 0 auto 0.75rem;
    opacity: 0.5;
  }

  &__hint {
    font-size: 0.8125rem;
  }
}
</style>
