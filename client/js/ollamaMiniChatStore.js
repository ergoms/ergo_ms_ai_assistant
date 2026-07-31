/**
 * Состояние плавающего мини-чата AI-ассистента (виджет поддержки).
 * Открытие — только из меню приложений.
 */

import { ref } from 'vue'

export const isOllamaMiniChatOpen = ref(false)
/** Позиция после перетаскивания: { left, top } в px или null (дефолт у меню). */
export const miniChatDragPosition = ref(null)

export function openOllamaMiniChat() {
  isOllamaMiniChatOpen.value = true
}

export function closeOllamaMiniChat() {
  isOllamaMiniChatOpen.value = false
}

export function dismissOllamaMiniChat() {
  isOllamaMiniChatOpen.value = false
}

export function setMiniChatDragPosition(position) {
  miniChatDragPosition.value = position
}

/** Точка входа из меню приложений. */
export function openOllamaMiniChatWidget() {
  openOllamaMiniChat()
}
