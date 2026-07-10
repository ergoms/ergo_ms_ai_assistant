<template>
  <div class="asst-composer">
    <div v-if="suggestions?.length" class="asst-composer__suggestions">
      <button
        v-for="item in suggestions"
        :key="item"
        type="button"
        class="btn btn-sm btn-outline-secondary"
        :disabled="disabled"
        @click="$emit('suggestion-click', item)"
      >
        {{ item }}
      </button>
    </div>

    <div v-if="files?.length" class="asst-composer__files">
      <span v-for="(file, index) in files" :key="`${file.name}-${index}`" class="asst-composer__file">
        {{ file.name }}
        <button type="button" class="btn btn-link btn-sm p-0" @click="$emit('remove-file', index)">
          <X :size="14" />
        </button>
      </span>
    </div>

    <div class="asst-composer__row">
      <input
        v-if="showAttach"
        ref="fileInputRef"
        type="file"
        class="d-none"
        :accept="attachAccept"
        :multiple="attachMultiple"
        @change="onFileChange"
      />
      <button
        v-if="showAttach"
        type="button"
        class="btn btn-link asst-composer__btn"
        title="Прикрепить файл"
        :disabled="disabled"
        @click="fileInputRef?.click()"
      >
        <Paperclip :size="18" />
      </button>

      <textarea
        ref="textareaRef"
        :value="modelValue"
        class="form-control asst-composer__textarea"
        :placeholder="placeholder"
        rows="1"
        :disabled="disabled"
        @input="onInput"
        @keydown="onKeydown"
      />

      <button
        type="button"
        class="btn btn-link asst-composer__btn asst-composer__btn--send"
        title="Отправить"
        :disabled="disabled || !modelValue.trim()"
        @click="$emit('send')"
      >
        <SendHorizonal :size="18" />
      </button>
    </div>

    <slot name="footer" />
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { Paperclip, SendHorizonal, X } from 'lucide-vue-next'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: 'Напишите сообщение...' },
  disabled: { type: Boolean, default: false },
  showAttach: { type: Boolean, default: false },
  attachAccept: { type: String, default: '' },
  attachMultiple: { type: Boolean, default: false },
  files: { type: Array, default: () => [] },
  suggestions: { type: Array, default: () => [] },
})

const textareaRef = ref(null)
const fileInputRef = ref(null)

function autoResize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 120)}px`
}

const emit = defineEmits(['update:modelValue', 'send', 'attach', 'remove-file', 'suggestion-click'])

function onInput(event) {
  emit('update:modelValue', event.target.value)
  autoResize()
}

function onKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    if (!props.disabled && props.modelValue.trim()) {
      emit('send')
    }
  }
}

function onFileChange(event) {
  const selected = Array.from(event.target.files || [])
  if (selected.length) {
    emit('attach', selected)
  }
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

watch(
  () => props.modelValue,
  () => nextTick(autoResize),
)

watch(
  () => props.disabled,
  (value) => {
    if (!value) nextTick(autoResize)
  },
)
</script>

<style lang="scss" scoped>
@import '../../styles/_assistant-chat.scss';
</style>
