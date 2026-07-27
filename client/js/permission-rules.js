import { tGlobal } from '@/i18n/index.js'

/**
 * Правила проверки прав для ai_assistant (UX).
 */
export default [
  {
    match: (to) =>
      to.name?.toString().startsWith('AIAssistant') ||
      to.path?.startsWith('/ai-assistant'),
    module: 'ai_assistant',
    permissions: ['ai_assistant_view'],
    get title() {
      return tGlobal('ai_assistant.access.title')
    },
    get message() {
      return tGlobal('ai_assistant.access.message')
    },
  },
]
