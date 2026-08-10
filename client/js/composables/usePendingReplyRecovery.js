/**
 * Дотягивание ответа ассистента после обрыва SSE (F5 / nginx 499).
 * Пока ждём — UI держит индикатор «генерации».
 *
 * Успех только когда локально больше не ждём ответ (после apply с сервера
 * или если пользователь уже получил сообщение другим путём).
 * «Сессия на сервере когда-то завершилась» само по себе НЕ успех —
 * локально может быть новый user-message без ответа.
 */
import { ragClient } from '../../rag/js/rag-client.js'
import { logError } from '@/js/utils/logError.js'
import {
  isAwaitingAssistantReply,
  shouldPreferServerMessages,
} from '../ollamaMiniChatStore.js'
import { mapApiMessages } from './useAssistantStream.js'

/** Генерация может дописаться в БД после обрыва SSE (фоновый поток API). */
const DEFAULT_DELAYS_MS = [
  0, 800, 1600, 2500, 4000, 6000, 8000, 10000, 12000, 15000, 20000, 25000, 30000,
]

function countUserMessages(messages) {
  if (!Array.isArray(messages)) return 0
  return messages.filter((msg) => msg?.type === 'user').length
}

/** На сервере есть непустой assistant сразу после последнего user. */
function serverHasReplyForLatestUser(mapped) {
  if (!Array.isArray(mapped) || !mapped.length) return false
  for (let i = mapped.length - 1; i >= 0; i -= 1) {
    const msg = mapped[i]
    if (msg?.type === 'user') {
      const next = mapped[i + 1]
      return Boolean(
        next
        && next.type === 'assistant'
        && String(next.content || '').trim(),
      )
    }
  }
  return false
}

/**
 * @param {object} options
 * @param {string|null|undefined} options.sessionId
 * @param {() => any[]} options.getLocalMessages
 * @param {(mapped: any[]) => void} options.applyMessages
 * @param {(pending: boolean) => void} options.setPending
 * @param {() => void} [options.onInterrupted]
 * @param {number[]} [options.delaysMs]
 * @returns {Promise<boolean>} true если ответ дотянут
 */
export async function recoverPendingReply({
  sessionId,
  getLocalMessages,
  applyMessages,
  setPending,
  onInterrupted,
  delaysMs = DEFAULT_DELAYS_MS,
}) {
  if (!sessionId) {
    setPending(false)
    return false
  }

  setPending(true)
  const localUserBaseline = countUserMessages(getLocalMessages() || [])

  for (const delay of delaysMs) {
    if (delay) {
      await new Promise((resolve) => setTimeout(resolve, delay))
    }
    try {
      const localBefore = getLocalMessages() || []
      if (!isAwaitingAssistantReply(localBefore)) {
        setPending(false)
        return true
      }

      const fetched = await ragClient.getChatSession(sessionId)
      if (!fetched?.success) {
        break
      }
      const mapped = mapApiMessages(fetched.messages)
      const serverUsers = countUserMessages(mapped)
      const serverAnsweredCurrentTurn = (
        serverUsers >= localUserBaseline
        && serverHasReplyForLatestUser(mapped)
      )

      if (
        mapped.length
        && (serverAnsweredCurrentTurn || shouldPreferServerMessages(localBefore, mapped))
      ) {
        applyMessages(mapped)
      }

      if (!isAwaitingAssistantReply(getLocalMessages() || [])) {
        setPending(false)
        return true
      }
    } catch (error) {
      logError('Ошибка опроса ответа ассистента после обрыва SSE', error)
    }
  }

  setPending(false)
  const stillWaiting = isAwaitingAssistantReply(getLocalMessages() || [])
  if (stillWaiting && onInterrupted) {
    onInterrupted()
  }
  return false
}

export { isAwaitingAssistantReply }
