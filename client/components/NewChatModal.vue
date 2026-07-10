<template>
  <ModalCenter
    standalone
    modal-id="aiAssistantNewChat"
    title="Создать новый чат"
    :visible="visible"
    size="md"
    @close="$emit('close')"
  >
    <p class="text-muted mb-3">Выберите тип чата для создания:</p>
    <div class="new-chat-grid">
      <button
        v-for="module in availableModules"
        :key="module.id"
        type="button"
        class="new-chat-card"
        :style="{ '--module-color': module.color }"
        @click="$emit('select', module.id)"
      >
        <component :is="module.icon" :size="28" class="new-chat-card__icon" />
        <div class="new-chat-card__body">
          <strong>{{ module.name }}</strong>
          <span>{{ module.description }}</span>
        </div>
      </button>
    </div>
  </ModalCenter>
</template>

<script setup>
import { computed } from 'vue'
import ModalCenter from '@/components/ModalCenter.vue'
import { modules } from '../modules/index.js'

defineProps({
  visible: { type: Boolean, default: false },
})

defineEmits(['close', 'select'])

const availableModules = computed(() => modules.filter((m) => m.enabled && !m.comingSoon))
</script>

<style lang="scss" scoped>
.new-chat-grid {
  display: grid;
  gap: 0.75rem;
}

.new-chat-card {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  width: 100%;
  padding: 0.875rem 1rem;
  border: 1px solid var(--ui-border);
  border-left: 4px solid var(--module-color, var(--bs-primary));
  border-radius: 0.5rem;
  background: var(--ui-surface);
  color: var(--ui-text);
  text-align: left;
  transition: border-color 0.15s, background 0.15s;

  &:hover {
    border-color: var(--module-color, var(--bs-primary));
    background: color-mix(in srgb, var(--module-color, var(--bs-primary)) 6%, var(--ui-surface));
  }

  &__icon {
    flex-shrink: 0;
    color: var(--module-color, var(--bs-primary));
  }

  &__body {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;

    span {
      font-size: 0.875rem;
      color: var(--ui-text-muted, var(--bs-secondary-color));
    }
  }
}
</style>
