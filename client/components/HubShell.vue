<template>
  <div class="neural-hub" :class="{ 'neural-hub--light': isLightTheme }">
    <NeuralBackground
      :node-count="60"
      :connection-distance="180"
      :node-color="nodeColor"
      :line-color="nodeColor"
      :accelerated="accelerated"
    />

    <aside class="neural-sidebar">
      <div class="sidebar-brand">
        <div class="brand-icon">
          <div class="brand-icon__core">
            <Sparkles :size="22" />
          </div>
        </div>
        <div class="brand-text">
          <span class="brand-title">{{ t('ai_assistant.brand') }}</span>
          <span class="brand-subtitle">{{ t('ai_assistant.brandSubtitle') }}</span>
        </div>
      </div>

      <div class="sidebar-status">
        <div class="status-indicator" :class="{ 'status-indicator--online': ollamaOnline }">
          <div class="status-dot"></div>
          <Cpu :size="14" />
          <span class="status-text">{{ currentModel }}</span>
        </div>
      </div>

      <div class="sidebar-sessions">
        <slot name="sidebar" />
      </div>
    </aside>

    <main class="neural-main">
      <header class="module-banner" :style="`--banner-color: ${moduleConfig?.color}`">
        <div class="banner-decoration">
          <div class="decoration-line"></div>
          <div class="decoration-dot"></div>
        </div>

        <div class="banner-content">
          <div class="banner-icon">
            <component :is="moduleConfig?.icon" :size="28" />
          </div>
          <div class="banner-info">
            <h1 class="banner-title">{{ moduleConfig?.name }}</h1>
            <p class="banner-desc">{{ moduleConfig?.description }}</p>
          </div>
        </div>

        <div class="banner-actions">
          <slot name="banner-actions" />
        </div>
      </header>

      <slot />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Cpu, Sparkles } from 'lucide-vue-next'
import { useAppI18n } from '@/i18n/useAppI18n.js'
import { useModuleThemeMode } from '@/composables/useModuleThemeMode.js'
import NeuralBackground from './NeuralBackground.vue'

const props = defineProps({
  moduleConfig: { type: Object, default: null },
  activeModule: { type: String, default: 'chat' },
  ollamaOnline: { type: Boolean, default: false },
  currentModel: { type: String, default: '' },
  accelerated: { type: Boolean, default: false },
})

const { t } = useAppI18n()
const { isLight: isLightTheme } = useModuleThemeMode('ai_assistant')

const nodeColor = computed(() => {
  const docs = props.activeModule === 'docs'
  if (isLightTheme.value) {
    return docs ? '#6d28d9' : '#0f768a'
  }
  return docs ? '#8b5cf6' : '#3ae8ff'
})
</script>

<style lang="scss" scoped>
.sidebar-sessions {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;

  :deep(.session-sidebar) {
    width: 100%;
    border-right: none;
    background: transparent;
    padding: 0.75rem;
  }
}
</style>
