<template>
  <ModalCenter
    standalone
    modal-id="aiAssistantChatTypeSelector"
    :title="t('ai_assistant.newChat.title')"
    :visible="show"
    size="lg"
    @close="close"
  >
    <p class="chat-type-selector__description">{{ t('ai_assistant.newChat.description') }}</p>

    <div class="chat-type-selector__grid">
      <button
        v-for="module in availableModules"
        :key="module.id"
        type="button"
        class="chat-type-card"
        :style="{ '--card-color': module.color }"
        @click="selectModule(module.id)"
      >
        <div class="chat-type-card__icon">
          <component :is="module.icon" :size="32" />
        </div>
        <div class="chat-type-card__content">
          <h3 class="chat-type-card__title">{{ module.name }}</h3>
          <p class="chat-type-card__description">{{ module.description }}</p>
        </div>
      </button>
    </div>
  </ModalCenter>
</template>

<script setup>
import { computed } from 'vue'
import ModalCenter from '@/components/ModalCenter.vue'
import { modules } from '../modules/index.js'
import { useAppI18n } from '@/i18n/useAppI18n.js'

const { t } = useAppI18n()

defineProps({
  show: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['close', 'select'])

const availableModules = computed(() => {
  return modules.filter(m => m.enabled && !m.comingSoon)
})

const close = () => {
  emit('close')
}

const selectModule = (moduleId) => {
  emit('select', moduleId)
  close()
}
</script>

<style lang="scss" scoped>
.chat-type-selector__description {
  margin: 0 0 1.5rem;
  color: var(--ai-text-secondary, var(--ui-text-muted));
  font-size: 0.875rem;
}

.chat-type-selector__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.chat-type-card {
  background: var(--ai-bg-tertiary, var(--ui-surface));
  border: 1px solid var(--ai-border, var(--ui-border));
  border-radius: 8px;
  padding: 1.25rem;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 0.75rem;
  color: inherit;

  &:hover {
    border-color: var(--card-color, var(--ai-accent));
    background: var(--ai-bg-elevated, var(--ui-surface-hover));
  }
}

.chat-type-card__icon {
  color: var(--card-color, var(--ai-accent));
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-type-card__content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.chat-type-card__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--ai-text-primary, var(--ui-text));
}

.chat-type-card__description {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--ai-text-secondary, var(--ui-text-muted));
  line-height: 1.4;
}
</style>
