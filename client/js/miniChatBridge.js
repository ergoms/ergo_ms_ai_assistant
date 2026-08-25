/**
 * Публичные client bridge ops для открытия мини-чата с профилем.
 */

import bridge from '@/integrations/ModuleBridge.js'
import { DEFAULT_CHAT_PROFILE_ID, getChatProfile } from './chatProfiles.js'
import { openMiniChat } from './ollamaMiniChatStore.js'
import { AI_ASSISTANT_MODULE, AI_ASSISTANT_PERMISSIONS } from './permissionKeys.js'

bridge.provide('ai_assistant.mini_chat.open', async (profileId = 'default', options = {}) => {
  const requestedId = String(profileId || DEFAULT_CHAT_PROFILE_ID).trim()
    || DEFAULT_CHAT_PROFILE_ID
  const { hasModulePermission } = await import('@/core/cms/adp/js/accessControl.js')
  const { isAiAssistantAclDenied } = await import('./aiAssistantAccess.js')

  if (await isAiAssistantAclDenied()) {
    return false
  }

  if (requestedId === DEFAULT_CHAT_PROFILE_ID) {
    const ok = await hasModulePermission(
      AI_ASSISTANT_MODULE,
      AI_ASSISTANT_PERMISSIONS.MINI_CHAT,
    )
    if (!ok) return false
    const profile = await getChatProfile(DEFAULT_CHAT_PROFILE_ID)
    openMiniChat(DEFAULT_CHAT_PROFILE_ID, {
      storageKey: options.storageKey || profile?.storageKey,
    })
    return true
  }

  const profile = await getChatProfile(requestedId)
  if (!profile || profile.id !== requestedId) {
    return false
  }
  if (profile.permissionModule && profile.permission) {
    const ok = await hasModulePermission(profile.permissionModule, profile.permission)
    if (!ok) return false
  }
  openMiniChat(profile.id, {
    storageKey: options.storageKey || profile.storageKey,
  })
  return true
})
