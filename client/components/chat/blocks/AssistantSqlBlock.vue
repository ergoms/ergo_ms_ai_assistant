<template>
  <div class="asst-block">
    <div class="asst-block__header">
      <div class="asst-block__header-left">
        <Terminal :size="14" />
        <span>SQL</span>
      </div>
      <button
        type="button"
        class="btn btn-link btn-sm p-0"
        :title="copied ? 'Скопировано' : 'Копировать'"
        @click="copySql"
      >
        <Check v-if="copied" :size="14" />
        <Copy v-else :size="14" />
      </button>
    </div>
    <div class="asst-block__body asst-block__code">
      <pre><code>{{ sql }}</code></pre>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Terminal, Copy, Check } from 'lucide-vue-next'
import { logError } from '@/js/utils/logError.js'

const props = defineProps({
  sql: { type: String, required: true },
})

const copied = ref(false)

async function copySql() {
  if (!props.sql) return
  try {
    await navigator.clipboard.writeText(props.sql)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch (error) {
    logError('Не удалось скопировать SQL', error)
  }
}
</script>

<style lang="scss" scoped>
@import '../../../styles/_assistant-chat.scss';
</style>
