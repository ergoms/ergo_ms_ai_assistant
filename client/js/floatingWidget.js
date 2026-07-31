/**
 * Плавающий мини-чат AI-ассистента — регистрация в shell.floating_widgets.
 */

import { defineAsyncComponent, markRaw } from 'vue'

import bridge from '@/integrations/ModuleBridge.js'
import { FLOATING_WIDGETS_GROUP } from '@/integrations/moduleContracts.js'

bridge.provideMany(FLOATING_WIDGETS_GROUP, 'ai_assistant_mini_chat', {
  id: 'ai_assistant_mini_chat',
  order: 10,
  component: markRaw(
    defineAsyncComponent(() => import('../components/OllamaMiniChatWidget.vue')),
  ),
})
