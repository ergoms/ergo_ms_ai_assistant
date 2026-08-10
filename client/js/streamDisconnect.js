/**
 * Обрыв SSE (F5 / закрытие вкладки / kill Daphne) — не показывать как сетевую ошибку fetch.
 * Ответ дотягивается через pending recovery.
 *
 * Важно: браузер часто abort'ит fetch ДО beforeunload/pagehide.
 * Поэтому при disconnected нельзя писать «не удалось» — только pending.
 */

let pageUnloading = false

function markPageUnloading() {
  pageUnloading = true
}

if (typeof window !== 'undefined') {
  window.addEventListener('pagehide', markPageUnloading)
  window.addEventListener('beforeunload', markPageUnloading)
}

/** true, если вкладка уходит (F5 / закрытие / навигация). */
export function isPageUnloading() {
  return pageUnloading
}

export function isStreamDisconnectError(error) {
  if (!error) return false
  if (error.name === 'AbortError') return true
  const msg = String(error.message || error || '').toLowerCase()
  return (
    msg === 'failed to fetch'
    || msg.includes('networkerror')
    || msg.includes('load failed')
    || msg.includes('aborted')
    || msg.includes('the user aborted')
  )
}
