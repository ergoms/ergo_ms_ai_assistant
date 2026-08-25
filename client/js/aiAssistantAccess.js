/**
 * UX-проверки доступа к хабу и API — до запросов, которые ACL всё равно отклонит.
 */

import { DEFAULT_CHAT_PROFILE_ID } from './chatProfiles.js'
import { AI_ASSISTANT_MODULE, AI_ASSISTANT_PERMISSIONS } from './permissionKeys.js'

export const AI_ASSISTANT_PAGE_PATH = '/ai-assistant'
export const AI_ASSISTANT_API_PREFIX = '/api/ai_assistant/'

export async function isAiAssistantAclDenied() {
  const {
    checkRouteAdpAccess,
    getPermissionsSnapshot,
    isApiPathDenied,
  } = await import('@/core/cms/adp/js/accessControl.js')

  const snapshot = await getPermissionsSnapshot()
  if (snapshot?.is_global_admin) {
    return false
  }
  if (!snapshot) {
    return true
  }
  if (await isApiPathDenied(AI_ASSISTANT_API_PREFIX)) {
    return true
  }
  const pageAllowed = await checkRouteAdpAccess(AI_ASSISTANT_PAGE_PATH)
  return !pageAllowed
}

export async function canUseAiAssistantChatUi() {
  if (await isAiAssistantAclDenied()) {
    return false
  }
  const { hasModulePermission } = await import('@/core/cms/adp/js/accessControl.js')
  if (await hasModulePermission(AI_ASSISTANT_MODULE, AI_ASSISTANT_PERMISSIONS.MINI_CHAT)) {
    return true
  }
  const { collectChatProfiles } = await import('./chatProfiles.js')
  const profiles = await collectChatProfiles()
  return profiles.some((profile) => profile.id !== DEFAULT_CHAT_PROFILE_ID)
}

export async function canFetchOllamaStatus() {
  if (await isAiAssistantAclDenied()) {
    return false
  }
  const { hasAnyModulePermission } = await import('@/core/cms/adp/js/accessControl.js')
  return hasAnyModulePermission(AI_ASSISTANT_MODULE, [
    AI_ASSISTANT_PERMISSIONS.VIEW,
    AI_ASSISTANT_PERMISSIONS.MINI_CHAT,
  ])
}
