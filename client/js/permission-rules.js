import { tGlobal } from '@/i18n/index.js'
import { AI_ASSISTANT_PERMISSIONS } from './permissionKeys.js'

/**
 * Правила проверки прав для ai_assistant (UX).
 */
export default [
  {
    match: (to) =>
      to.name?.toString().startsWith('AIAssistant') ||
      to.path?.startsWith('/ai-assistant'),
    module: 'ai_assistant',
    permissions: [AI_ASSISTANT_PERMISSIONS.VIEW],
    get title() {
      return tGlobal('ai_assistant.access.title')
    },
    get message() {
      return tGlobal('ai_assistant.access.message')
    },
  },
]
