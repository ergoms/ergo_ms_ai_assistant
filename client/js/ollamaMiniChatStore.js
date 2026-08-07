/**
 * Состояние плавающего мини-чата AI-ассистента (виджет поддержки).
 * Открытие — только из меню приложений.
 * История и session_id живут в module-level refs, чтобы чат не сбрасывался при закрытии панели.
 */

import { ref } from 'vue'

export const isOllamaMiniChatOpen = ref(false)
/** Позиция после перетаскивания: { left, top } в px или null (дефолт у меню). */
export const miniChatDragPosition = ref(null)
/** Сообщения текущего мини-чата (null — ещё не инициализировали welcome). */
export const miniChatMessages = ref(null)
/** server session_id для продолжения диалога после закрытия панели. */
export const miniChatSessionId = ref(null)

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

export function setMiniChatMessages(messages) {
  miniChatMessages.value = messages
}

export function setMiniChatSessionId(sessionId) {
  miniChatSessionId.value = sessionId
}

/** Точка входа из меню приложений. */
export function openOllamaMiniChatWidget() {
  openOllamaMiniChat()
}
