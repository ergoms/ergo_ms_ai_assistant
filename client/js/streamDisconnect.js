/**
 * Обрыв SSE (F5 / закрытие вкладки / kill Daphne) — не показывать как ошибку чата.
 * Worker Celery продолжает генерацию; UI дотягивает ответ через pending recovery.
 */
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
