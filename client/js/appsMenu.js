/**
 * Пункт «Ollama Chat» в меню приложений (AppsMenu).
 *
 * Регистрируется через ModuleBridge; подключается из integrations.js.
 */

import { Bot } from 'lucide-vue-next'
import { markRaw } from 'vue'

import bridge from '@/integrations/ModuleBridge.js'
import { APPS_MENU_ITEMS_GROUP } from '@/integrations/moduleContracts.js'
import { tGlobal } from '@/i18n/index.js'

async function checkOllamaChatVisibility() {
  const { hasModulePermission } = await import('@/core/cms/adp/js/accessControl.js')
  return hasModulePermission('ai_assistant', 'ai_assistant_view')
}

bridge.provideMany(APPS_MENU_ITEMS_GROUP, 'ai_assistant_ollama_chat', {
  id: 'ai_assistant_ollama_chat',
  order: 10,
  get title() {
    return tGlobal('ai_assistant.apps.ollamaChat')
  },
  icon: markRaw(Bot),
  route: { name: 'AIAssistantHub', query: { module: 'chat' } },
  isVisible: checkOllamaChatVisibility,
})
