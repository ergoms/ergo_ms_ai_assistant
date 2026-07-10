<template>
  <div class="asst-chat">
    <div v-if="$slots.toolbar" class="asst-chat__toolbar">
      <slot name="toolbar" />
    </div>

    <div v-if="showEmpty" class="asst-chat__empty">
      <slot name="empty" />
    </div>

    <div v-else ref="messagesRef" class="asst-chat__messages">
      <slot name="messages" />
      <div v-if="typing" class="asst-chat__typing" aria-hidden="true">
        <span /><span /><span />
      </div>
    </div>

    <AssistantComposer
      v-if="showComposer"
      :model-value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      :show-attach="showAttach"
      :attach-accept="attachAccept"
      :attach-multiple="attachMultiple"
      :files="files"
      :suggestions="suggestions"
      @update:model-value="$emit('update:modelValue', $event)"
      @send="$emit('send')"
      @attach="$emit('attach', $event)"
      @remove-file="$emit('remove-file', $event)"
      @suggestion-click="$emit('suggestion-click', $event)"
    >
      <template v-if="$slots['composer-footer']" #footer>
        <slot name="composer-footer" />
      </template>
    </AssistantComposer>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import AssistantComposer from './AssistantComposer.vue'

defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: 'Напишите сообщение...' },
  disabled: { type: Boolean, default: false },
  showComposer: { type: Boolean, default: true },
  showEmpty: { type: Boolean, default: false },
  typing: { type: Boolean, default: false },
  showAttach: { type: Boolean, default: false },
  attachAccept: { type: String, default: '' },
  attachMultiple: { type: Boolean, default: false },
  files: { type: Array, default: () => [] },
  suggestions: { type: Array, default: () => [] },
})

defineEmits(['update:modelValue', 'send', 'attach', 'remove-file', 'suggestion-click'])

const messagesRef = ref(null)

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

defineExpose({ scrollToBottom, messagesRef })
</script>

<style lang="scss" scoped>
@import '../../styles/_assistant-chat.scss';
</style>
