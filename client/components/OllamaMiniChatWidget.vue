<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { Bot, X } from 'lucide-vue-next'
import ModuleThemeScope from '@/components/ModuleThemeScope.vue'
import { useAppI18n } from '@/i18n/useAppI18n.js'
import { useBreakpoint } from '@/composables/useBreakpoint.js'
import {
  isOllamaMiniChatOpen,
  miniChatDragPosition,
  closeOllamaMiniChat,
  setMiniChatDragPosition,
} from '../js/ollamaMiniChatStore.js'
import OllamaMiniChat from './OllamaMiniChat.vue'

const props = defineProps({
  menuRightEdge: {
    type: String,
    default: '',
  },
})

const { t } = useAppI18n()
const { isShellDesktop } = useBreakpoint()

const isOpen = computed(() => isOllamaMiniChatOpen.value)

const panelRef = ref(null)
const isDragging = ref(false)
let dragOffsetX = 0
let dragOffsetY = 0
let activePointerId = null

/** Слева у края меню (desktop) или у левого края экрана (mobile). */
const defaultLeft = computed(() => {
  if (isShellDesktop.value && props.menuRightEdge) {
    return `calc(${props.menuRightEdge} + 0.75rem)`
  }
  return 'max(1rem, env(safe-area-inset-left, 0px))'
})

const panelStyle = computed(() => {
  const dragged = miniChatDragPosition.value
  if (dragged) {
    return {
      left: `${dragged.left}px`,
      top: `${dragged.top}px`,
      bottom: 'auto',
      right: 'auto',
    }
  }
  return { left: defaultLeft.value }
})

function clampPosition(left, top, width, height) {
  const margin = 8
  const maxLeft = Math.max(margin, window.innerWidth - width - margin)
  const maxTop = Math.max(margin, window.innerHeight - height - margin)
  return {
    left: Math.min(Math.max(margin, left), maxLeft),
    top: Math.min(Math.max(margin, top), maxTop),
  }
}

function onHeaderPointerDown(event) {
  if (event.button != null && event.button !== 0) {
    return
  }
  if (event.target?.closest?.('button, a, input, textarea')) {
    return
  }
  const panel = panelRef.value
  if (!panel) {
    return
  }

  const rect = panel.getBoundingClientRect()
  dragOffsetX = event.clientX - rect.left
  dragOffsetY = event.clientY - rect.top
  activePointerId = event.pointerId
  isDragging.value = true

  try {
    event.currentTarget.setPointerCapture(event.pointerId)
  } catch {
    /* capture необязателен */
  }

  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
  window.addEventListener('pointercancel', onPointerUp)
  event.preventDefault()
}

function onPointerMove(event) {
  if (!isDragging.value || (activePointerId != null && event.pointerId !== activePointerId)) {
    return
  }
  const panel = panelRef.value
  if (!panel) {
    return
  }
  const width = panel.offsetWidth
  const height = panel.offsetHeight
  const next = clampPosition(
    event.clientX - dragOffsetX,
    event.clientY - dragOffsetY,
    width,
    height,
  )
  setMiniChatDragPosition(next)
}

function onPointerUp(event) {
  if (activePointerId != null && event.pointerId !== activePointerId) {
    return
  }
  stopDragging()
}

function stopDragging() {
  isDragging.value = false
  activePointerId = null
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
  window.removeEventListener('pointercancel', onPointerUp)
}

onBeforeUnmount(() => {
  stopDragging()
})
</script>

<template>
  <Teleport to="body">
    <div v-if="isOpen" class="ollama-widget-host">
      <ModuleThemeScope module-key="ai_assistant">
        <Transition name="ollama-widget-panel">
          <div
            v-if="isOpen"
            ref="panelRef"
            class="ollama-widget"
            :class="{ 'ollama-widget--dragging': isDragging }"
            role="dialog"
            aria-modal="false"
            :aria-label="t('ai_assistant.apps.ollamaChat')"
            :style="panelStyle"
          >
            <header
              class="ollama-widget__header"
              :title="t('ai_assistant.apps.dragHint')"
              @pointerdown="onHeaderPointerDown"
            >
              <div class="ollama-widget__brand">
                <span class="ollama-widget__avatar" aria-hidden="true">
                  <Bot :size="20" />
                </span>
                <div class="ollama-widget__titles">
                  <div class="ollama-widget__title">{{ t('ai_assistant.apps.ollamaChat') }}</div>
                  <div class="ollama-widget__subtitle">{{ t('ai_assistant.brandSubtitle') }}</div>
                </div>
              </div>
              <button
                type="button"
                class="ollama-widget__close"
                :aria-label="t('ai_assistant.apps.close')"
                @click="closeOllamaMiniChat"
              >
                <X :size="18" />
              </button>
            </header>

            <div class="ollama-widget__body">
              <OllamaMiniChat compact @close="closeOllamaMiniChat" />
            </div>
          </div>
        </Transition>
      </ModuleThemeScope>
    </div>
  </Teleport>
</template>

<style scoped lang="scss">
.ollama-widget-host {
  position: fixed;
  inset: 0;
  z-index: 1080;
  pointer-events: none;
}

.ollama-widget-host :deep(.module-theme-scope) {
  display: contents;
}

.ollama-widget {
  pointer-events: auto;
  position: fixed;
  bottom: max(1rem, env(safe-area-inset-bottom, 0px));
  width: min(380px, calc(100vw - 1.5rem));
  height: min(560px, calc(100dvh - 2rem));
  display: flex;
  flex-direction: column;
  border-radius: 16px;
  overflow: hidden;
  background: var(--ai-bg-secondary, var(--color-primary-background, #0e1118));
  color: var(--ai-text-primary, var(--color-primary-text));
  border: 1px solid var(--ai-border, var(--color-border));
  box-shadow:
    0 12px 40px rgba(0, 0, 0, 0.35),
    0 0 0 1px rgba(58, 232, 255, 0.08);
  transition: left 0.25s ease, top 0.25s ease;

  &--dragging {
    transition: none;
    user-select: none;
  }

  @media (width < $ui-bp-sm) {
    bottom: max(0.5rem, env(safe-area-inset-bottom, 0px));
    width: calc(100vw - 1rem);
    height: min(70dvh, 560px);
  }
}

.ollama-widget__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.75rem 0.875rem;
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--ai-accent, #3ae8ff) 18%, var(--ai-bg-secondary, #0e1118)),
    var(--ai-bg-secondary, #0e1118)
  );
  border-bottom: 1px solid var(--ai-border, var(--color-border));
  flex-shrink: 0;
  cursor: grab;
  touch-action: none;

  .ollama-widget--dragging & {
    cursor: grabbing;
  }
}

.ollama-widget__brand {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  min-width: 0;
  pointer-events: none;
}

.ollama-widget__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--ai-accent, #3ae8ff);
  color: #050508;
  flex-shrink: 0;
}

.ollama-widget__titles {
  min-width: 0;
}

.ollama-widget__title {
  font-size: 0.9375rem;
  font-weight: 600;
  line-height: 1.2;
}

.ollama-widget__subtitle {
  font-size: 0.75rem;
  color: var(--ai-text-secondary, var(--color-secondary-text));
  line-height: 1.2;
}

.ollama-widget__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--ai-text-secondary, var(--color-secondary-text));
  cursor: pointer;
  flex-shrink: 0;

  &:hover {
    background: var(--ai-bg-elevated, var(--color-hover-background));
    color: var(--ai-text-primary, var(--color-primary-text));
  }
}

.ollama-widget__body {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.ollama-widget-panel-enter-active,
.ollama-widget-panel-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.ollama-widget-panel-enter-from,
.ollama-widget-panel-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.96);
}
</style>
