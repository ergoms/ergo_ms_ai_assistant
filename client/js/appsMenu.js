/**
 * Пункт «AI ассистент» в меню приложений — открывает плавающий мини-чат.
 */

import bridge from '@/integrations/ModuleBridge.js'
import { APPS_MENU_ITEMS_GROUP } from '@/integrations/moduleContracts.js'
import { tGlobal } from '@/i18n/index.js'
import { DEFAULT_CHAT_PROFILE_ID } from './chatProfiles.js'
import { AI_ASSISTANT_MODULE, AI_ASSISTANT_PERMISSIONS } from './permissionKeys.js'

async function checkOllamaChatVisibility() {
  const { isAiAssistantAclDenied } = await import('./aiAssistantAccess.js')
  if (await isAiAssistantAclDenied()) {
    return false
  }
  const { hasModulePermission } = await import('@/core/cms/adp/js/accessControl.js')
  return hasModulePermission(AI_ASSISTANT_MODULE, AI_ASSISTANT_PERMISSIONS.MINI_CHAT)
}

bridge.provideMany(APPS_MENU_ITEMS_GROUP, 'ai_assistant_ollama_chat', {
  id: 'ai_assistant_ollama_chat',
  order: 10,
  get title() {
    return tGlobal('ai_assistant.apps.ollamaChat')
  },
  icon: 'Bot',
  onClick: () => {
    return bridge.call('ai_assistant.mini_chat.open', DEFAULT_CHAT_PROFILE_ID, { default: false })
  },
  isVisible: checkOllamaChatVisibility,
})
