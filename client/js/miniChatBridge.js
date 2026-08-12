/**
 * Публичные client bridge ops для открытия мини-чата с профилем.
 */

import bridge from '@/integrations/ModuleBridge.js'
import { openMiniChat } from './ollamaMiniChatStore.js'
import { getChatProfile } from './chatProfiles.js'

bridge.provide('ai_assistant.mini_chat.open', async (profileId = 'default', options = {}) => {
  const profile = await getChatProfile(profileId)
  if (!profile) {
    return false
  }
  if (profile.permissionModule && profile.permission) {
    const { hasModulePermission } = await import('@/core/cms/adp/js/accessControl.js')
    const ok = await hasModulePermission(profile.permissionModule, profile.permission)
    if (!ok) return false
  }
  openMiniChat(profile.id, {
    storageKey: options.storageKey || profile.storageKey,
  })
  return true
})
