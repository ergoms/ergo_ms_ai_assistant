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
      <div class="hub-header sidebar-brand">
        <div class="brand-icon">
          <div class="brand-icon__core">
            <Sparkles :size="18" />
          </div>
        </div>
        <div class="brand-text">
          <span class="brand-title">{{ t('ai_assistant.brand') }}</span>
          <span class="brand-subtitle" :class="{ 'ai-model-caption': modelSubtitle }">{{ brandSubtitleText }}</span>
        </div>
      </div>

      <div class="sidebar-sessions">
        <slot name="sidebar" />
      </div>
    </aside>

    <main class="neural-main">
      <slot />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Sparkles } from 'lucide-vue-next'
import { useAppI18n } from '@/i18n/useAppI18n.js'
import { useModuleThemeMode } from '@/composables/useModuleThemeMode.js'
import NeuralBackground from './NeuralBackground.vue'

const props = defineProps({
  moduleConfig: { type: Object, default: null },
  activeModule: { type: String, default: 'chat' },
  accelerated: { type: Boolean, default: false },
  modelSubtitle: { type: String, default: null },
})

const { t } = useAppI18n()
const { isLight: isLightTheme } = useModuleThemeMode('ai_assistant')

const brandSubtitleText = computed(() => {
  if (props.modelSubtitle) {
    return props.modelSubtitle
  }
  return t('ai_assistant.brandSubtitle')
})

const nodeColor = computed(() => {
  if (isLightTheme.value) return '#d0322d'
  return '#f14336'
})
</script>

<style lang="scss" scoped>
.sidebar-sessions {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;

  :deep(.session-sidebar) {
    width: 100%;
    height: 100%;
    border-right: none;
    background: transparent;
    padding: 0.875rem 0.875rem 1rem;
    box-sizing: border-box;
  }
}
</style>
