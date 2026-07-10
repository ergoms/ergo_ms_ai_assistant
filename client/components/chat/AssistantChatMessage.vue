<template>
  <div
    class="asst-msg"
    :class="{ 'asst-msg--own': isOwn }"
    :style="moduleStyle"
  >
    <div v-if="!isOwn" class="asst-msg__avatar">
      <component :is="moduleIcon" :size="18" />
    </div>

    <div class="asst-msg__body">
      <div v-if="!isOwn" class="asst-msg__author">{{ authorName }}</div>

      <div class="asst-msg__content">
        <div
          v-if="formattedContent"
          v-html="formattedContent"
          @click="onContentClick"
        />
        <span v-if="isStreaming" class="asst-msg__streaming-cursor" />

        <AssistantSqlBlock v-if="message.sql" :sql="message.sql" />
        <AssistantChartBlock
          v-if="chartConfig"
          :chart-config="chartConfig"
          :message-id="message.id"
        />
        <AssistantDataTable v-if="message.data?.data?.length" :data="message.data" />
      </div>

      <div v-if="message.stage && isStreaming" class="asst-msg__stage">
        {{ message.stage }}
      </div>

      <div v-if="message.error" class="alert alert-danger py-2 px-3 mb-0 mt-1 small">
        {{ message.error }}
      </div>

      <div class="asst-msg__meta">
        <span v-if="formattedTime" class="asst-msg__time">{{ formattedTime }}</span>
        <span v-if="message.processing_time_ms">{{ formatProcessingTime(message.processing_time_ms) }}</span>
        <span v-if="message.skill_name" class="badge bg-secondary" :title="skillCallTooltip">
          {{ message.skill_name }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Bot } from 'lucide-vue-next'
import AssistantSqlBlock from './blocks/AssistantSqlBlock.vue'
import AssistantChartBlock from './blocks/AssistantChartBlock.vue'
import AssistantDataTable from './blocks/AssistantDataTable.vue'
import {
  formatMessageContent,
  formatMessageTime,
  formatProcessingTime,
  handleDocumentDownloadClick,
} from '../../js/assistantMessageFormat.js'

const props = defineProps({
  message: { type: Object, required: true },
  moduleConfig: { type: Object, default: null },
})

const isOwn = computed(() => props.message.type === 'user')

const isStreaming = computed(() => Boolean(props.message.streaming || props.message.isStreaming))

const moduleIcon = computed(() => props.moduleConfig?.icon || Bot)

const moduleStyle = computed(() => ({
  '--module-color': props.moduleConfig?.color || 'var(--bs-primary)',
}))

const authorName = computed(() => {
  if (isOwn.value) return 'Вы'
  return props.moduleConfig?.name || 'AI-ассистент'
})

const formattedTime = computed(() => formatMessageTime(props.message.timestamp))

const formattedContent = computed(() => formatMessageContent(props.message.content))

const chartConfig = computed(() => props.message.metadata?.chart_config || props.message.chart_config)

const skillCallTooltip = computed(() => {
  if (!props.message.skill_call) return ''
  return JSON.stringify(props.message.skill_call, null, 2)
})

function onContentClick(event) {
  handleDocumentDownloadClick(event)
}
</script>

<style lang="scss" scoped>
@import '../../styles/_assistant-chat.scss';
</style>
