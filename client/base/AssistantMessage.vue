<template>
  <div class="neural-chat-message" :class="`neural-chat-message--${message.type}`">
    <div class="message-row">
      <!-- Avatar -->
      <div class="message-avatar" :class="`message-avatar--${message.type}`">
        <User v-if="message.type === 'user'" :size="18" />
        <Sparkles v-else :size="18" />
        <div class="avatar-glow"></div>
      </div>

      <!-- Content bubble -->
      <div class="message-bubble">
        <!-- Text content -->
        <div v-if="message.content" class="message-text" v-html="formatMarkdown(message.content)"></div>
        
        <!-- SQL query -->
        <div v-if="message.sql" class="message-code">
          <div class="code-label">
            <Terminal :size="12" />
            <span>SQL</span>
          </div>
          <pre><code>{{ message.sql }}</code></pre>
        </div>

        <!-- SQL generating -->
        <div v-if="message.sqlGenerating" class="message-code message-code--generating">
          <div class="code-label">
            <Loader2 :size="12" class="spinning" />
            <span>{{ t('ai_assistant.message.generatingShort') }}</span>
          </div>
          <pre><code>{{ message.sqlGenerating }}</code></pre>
        </div>

        <!-- Data table -->
        <div v-if="message.data && message.data.data && message.data.data.length > 0" class="message-table">
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th v-for="col in message.data.columns" :key="col">{{ col }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, idx) in message.data.data" :key="idx">
                  <td v-for="col in message.data.columns" :key="col">{{ row[col] }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="table-meta">{{ t('ai_assistant.message.rowsCount', message.data.data.length) }}</div>
        </div>

        <!-- Error -->
        <div v-if="message.error" class="message-error">
          <AlertCircle :size="14" />
          <span>{{ message.error }}</span>
        </div>

        <!-- Stage -->
        <div v-if="message.stage && message.streaming" class="message-stage">
          <Loader2 :size="12" class="spinning" />
          <span>{{ message.stage }}</span>
        </div>
      </div>
    </div>

    <div class="message-time">{{ formatTime(message.timestamp) }}</div>
  </div>
</template>

<script setup>
import { Sparkles, User, Terminal, Loader2, AlertCircle } from '@lucide/vue'
import { useAppI18n } from '@/i18n/useAppI18n.js'
import { getCurrentBcp47 } from '@/i18n/index.js'
import { formatMessageContent } from '../js/assistantMessageFormat.js'

const { t } = useAppI18n()

defineProps({
  message: {
    type: Object,
    required: true,
  },
})

const formatMarkdown = (text) => formatMessageContent(text, {
  thinkingLabel: t('ai_assistant.message.thinking'),
})

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString(getCurrentBcp47(), {
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<style lang="scss" scoped>
@import './AssistantMessage.scss';
</style>
