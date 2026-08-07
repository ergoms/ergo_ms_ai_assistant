<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Bot, Eraser, X } from 'lucide-vue-next'
import ModuleThemeScope from '@/components/ModuleThemeScope.vue'
import { useAppI18n } from '@/i18n/useAppI18n.js'
import { useBreakpoint } from '@/composables/useBreakpoint.js'
import {
  isOllamaMiniChatOpen,
  miniChatPanelMounted,
  miniChatDragPosition,
  closeOllamaMiniChat,
  setMiniChatDragPosition,
} from '../js/ollamaMiniChatStore.js'
import { useOllamaStatus } from '../js/composables/useOllamaStatus.js'
import OllamaMiniChat from './OllamaMiniChat.vue'

const props = defineProps({
  menuRightEdge: {
    type: String,
    default: '',
  },
})

const { t } = useAppI18n()
const { isShellDesktop } = useBreakpoint()
const {
  status: ollamaStatus,
  modelSubtitle,
} = useOllamaStatus({ autoPoll: true })

const widgetSubtitle = computed(() => modelSubtitle.value || t('ai_assistant.brandSubtitle'))
const showModelCaption = computed(() => Boolean(modelSubtitle.value))

const isOpen = computed(() => isOllamaMiniChatOpen.value)
const isMounted = computed(() => miniChatPanelMounted.value)

const panelRef = ref(null)
const chatRef = ref(null)
const showClearConfirm = ref(false)
const isDragging = ref(false)
let dragOffsetX = 0
let dragOffsetY = 0
let activePointerId = null

watch(isOpen, (open) => {
  if (!open) {
    showClearConfirm.value = false
  }
})

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

function onClearChat() {
  showClearConfirm.value = true
}

function cancelClearChat() {
  showClearConfirm.value = false
}

function confirmClearChat() {
  showClearConfirm.value = false
  chatRef.value?.clearChat?.()
}

onBeforeUnmount(() => {
  stopDragging()
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="isMounted"
      class="ollama-widget-host"
      :class="{ 'ollama-widget-host--open': isOpen }"
      :aria-hidden="isOpen ? 'false' : 'true'"
    >
      <ModuleThemeScope module-key="ai_assistant">
        <Transition name="ollama-widget-panel">
          <div
            v-show="isOpen"
            ref="panelRef"
            class="ollama-widget"
            :class="{ 'ollama-widget--dragging': isDragging }"
            role="dialog"
            aria-modal="false"
            :aria-label="t('ai_assistant.apps.ollamaChat')"
            :inert="!isOpen"
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
                  <div
                    class="ollama-widget__subtitle"
                    :class="{ 'ai-model-caption': showModelCaption }"
                  >{{ widgetSubtitle }}</div>
                </div>
              </div>
              <div class="ollama-widget__actions">
                <button
                  type="button"
                  class="ollama-widget__icon-btn"
                  :aria-label="t('ai_assistant.apps.clearChat')"
                  :title="t('ai_assistant.apps.clearChat')"
                  :disabled="showClearConfirm"
                  @click="onClearChat"
                >
                  <Eraser :size="18" />
                </button>
                <button
                  type="button"
                  class="ollama-widget__icon-btn"
                  :aria-label="t('ai_assistant.apps.close')"
                  :title="t('ai_assistant.apps.close')"
                  @click="closeOllamaMiniChat"
                >
                  <X :size="18" />
                </button>
              </div>
            </header>

            <div class="ollama-widget__body">
              <OllamaMiniChat
                ref="chatRef"
                compact
                :ollama-status="ollamaStatus"
                @close="closeOllamaMiniChat"
              />

              <div
                v-if="showClearConfirm"
                class="ollama-widget__confirm"
                role="alertdialog"
                aria-modal="true"
                :aria-label="t('ai_assistant.apps.clearChatTitle')"
              >
                <div class="ollama-widget__confirm-card">
                  <p class="ollama-widget__confirm-title">{{ t('ai_assistant.apps.clearChatTitle') }}</p>
                  <p class="ollama-widget__confirm-text">{{ t('ai_assistant.apps.clearChatConfirm') }}</p>
                  <div class="ollama-widget__confirm-actions">
                    <button
                      type="button"
                      class="ollama-widget__confirm-btn ollama-widget__confirm-btn--ghost"
                      @click="cancelClearChat"
                    >
                      {{ t('common.cancel') }}
                    </button>
                    <button
                      type="button"
                      class="ollama-widget__confirm-btn ollama-widget__confirm-btn--danger"
                      @click="confirmClearChat"
                    >
                      {{ t('ai_assistant.apps.clearChat') }}
                    </button>
                  </div>
                </div>
              </div>
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

  &--open .ollama-widget {
    pointer-events: auto;
  }
}

.ollama-widget-host :deep(.module-theme-scope) {
  display: contents;
}

.ollama-widget {
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
    0 0 0 1px color-mix(in srgb, var(--ai-accent, #f14336) 8%, transparent);
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
    color-mix(in srgb, var(--ai-accent, #f14336) 18%, var(--ai-bg-secondary, #18181a)),
    var(--ai-bg-secondary, #18181a)
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
  background: var(--ai-accent, #f14336);
  color: #fff;
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

  &.ai-model-caption {
    font-weight: 600;
    font-family: var(--font-family-mono);
    font-variant-numeric: tabular-nums;
  }
}

.ollama-widget__actions {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  flex-shrink: 0;
}

.ollama-widget__icon-btn {
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

  &:hover:not(:disabled) {
    background: var(--ai-bg-elevated, var(--color-hover-background));
    color: var(--ai-text-primary, var(--color-primary-text));
  }

  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
}

.ollama-widget__body {
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.ollama-widget__confirm {
  position: absolute;
  inset: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: color-mix(in srgb, var(--ai-bg-primary, #111) 72%, transparent);
  backdrop-filter: blur(2px);
}

.ollama-widget__confirm-card {
  width: min(100%, 280px);
  padding: 1rem;
  border-radius: 12px;
  border: 1px solid var(--ai-border, var(--color-border));
  background: var(--ai-bg-secondary, var(--color-primary-background, #18181a));
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.28);
}

.ollama-widget__confirm-title {
  margin: 0 0 0.35rem;
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--ai-text-primary, var(--color-primary-text));
}

.ollama-widget__confirm-text {
  margin: 0 0 0.875rem;
  font-size: 0.8125rem;
  line-height: 1.4;
  color: var(--ai-text-secondary, var(--color-secondary-text));
}

.ollama-widget__confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

.ollama-widget__confirm-btn {
  border: none;
  border-radius: 8px;
  padding: 0.4rem 0.75rem;
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;

  &--ghost {
    background: transparent;
    color: var(--ai-text-secondary, var(--color-secondary-text));

    &:hover {
      background: var(--ai-bg-elevated, var(--color-hover-background));
      color: var(--ai-text-primary, var(--color-primary-text));
    }
  }

  &--danger {
    background: var(--ai-accent, var(--color-accent, #d0322d));
    color: #fff;

    &:hover {
      filter: brightness(1.08);
    }
  }
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
