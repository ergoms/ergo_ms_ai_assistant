/**
 * Дотягивание ответа ассистента после обрыва SSE (F5 / nginx 499).
 * Пока ждём — UI держит индикатор «генерации».
 *
 * Генерация на сервере продолжается после обрыва клиента.
 * Без sessionId не сдаёмся сразу: ищем сессию на каждом тике опроса.
 */
import { ragClient } from '../../rag/js/rag-client.js'
import { logError } from '@/js/utils/logError.js'
import { whenSessionReady } from '@/js/sessionReady.js'
import {
  isAwaitingAssistantReply,
  shouldPreferServerMessages,
} from '../ollamaMiniChatStore.js'
import { mapApiMessages } from './useAssistantStream.js'

/**
 * Интервалы между опросами (мс). Суммарно ~6 мин ожидания LLM/RAG после F5.
 */
const DEFAULT_DELAYS_MS = [
  0, 800, 1600, 2500, 4000, 6000, 8000, 10000,
  12000, 15000, 20000, 25000, 30000, 30000, 30000,
  30000, 30000, 45000, 45000, 60000,
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
        && String(next.content || '').trim()
        && !next.interrupted,
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
 * @param {() => Promise<string|null|undefined>} [options.resolveSessionId]
 * @param {number[]} [options.delaysMs]
 * @returns {Promise<boolean>} true если ответ дотянут
 */
export async function recoverPendingReply({
  sessionId,
  getLocalMessages,
  applyMessages,
  setPending,
  onInterrupted,
  resolveSessionId,
  delaysMs = DEFAULT_DELAYS_MS,
}) {
  // Иначе getChatSessions/getChatSession на F5 уходят без токена → мгновенный fail
  try {
    await whenSessionReady()
  } catch (error) {
    logError('Ожидание session bootstrap перед recovery ответа', error)
  }

  let activeSessionId = sessionId || null
  setPending(true)

  const tryResolveSession = async () => {
    if (activeSessionId) return activeSessionId
    if (typeof resolveSessionId !== 'function') return null
    try {
      const resolved = await resolveSessionId()
      if (resolved) {
        activeSessionId = resolved
      }
    } catch (error) {
      logError('Ошибка поиска сессии для recovery ответа', error)
    }
    return activeSessionId
  }

  await tryResolveSession()
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

      const sid = await tryResolveSession()
      if (!sid) {
        // Сессия ещё не известна — продолжаем ждать, не показываем ошибку
        continue
      }

      const fetched = await ragClient.getChatSession(sid)
      if (!fetched?.success) {
        if (fetched?.status === 404) {
          activeSessionId = null
          continue
        }
        continue
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
