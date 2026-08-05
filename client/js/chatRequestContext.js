import { getCurrentLocale } from '@/i18n/index.js'

/** Заголовки для SSE/fetch chat (axios уже ставит Accept-Language). */
export function buildChatRequestHeaders(authToken = '') {
  return {
    Authorization: authToken ? `Bearer ${authToken}` : '',
    'Content-Type': 'application/json',
    'Accept-Language': getCurrentLocale(),
  }
}

/** Язык UI для явной передачи на сервер (профиль — источник истины, поле для согласованности). */
export function withUiLanguage(payload) {
  return {
    ...payload,
    ui_language: getCurrentLocale(),
  }
}
