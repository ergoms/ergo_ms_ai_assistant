<template>
  <div class="mini-chat-quote" role="group" :aria-label="t('ai_assistant.apps.selectedQuote')">
    <blockquote class="mini-chat-quote__text">{{ text }}</blockquote>
    <button
      type="button"
      class="ui-btn ui-btn--secondary mini-chat-quote__remove"
      :aria-label="t('ai_assistant.apps.removeQuote')"
      :title="t('ai_assistant.apps.removeQuote')"
      @click="emit('remove')"
    >
      <X :size="16" aria-hidden="true" />
    </button>
  </div>
</template>

<script setup>
import { X } from '@lucide/vue'
import { useAppI18n } from '@/i18n/useAppI18n.js'

defineProps({ text: { type: String, required: true } })
const emit = defineEmits(['remove'])
const { t } = useAppI18n()
</script>

<style scoped>
.mini-chat-quote {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: .35rem;
  padding: .35rem .4rem .35rem .65rem;
  border-inline-start: 2px solid var(--ai-accent, var(--ui-accent));
  border-radius: var(--ui-radius, .5rem);
  background: var(--ai-bg-tertiary, var(--ui-surface));
  color: var(--ai-text-primary, var(--ui-text));
}

.mini-chat-quote__text {
  max-height: 5rem;
  margin: 0;
  overflow: auto;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  font-size: .8125rem;
}

.mini-chat-quote__remove {
  flex: none;
  display: grid;
  place-items: center;
  width: 2rem;
  min-height: 2rem;
  padding: 0;
}
</style>
