/**
 * Реестр chat-профилей ai_assistant (межмодульный контракт).
 *
 * Хост: bridge.provideMany(CHAT_PROFILES_GROUP, id, descriptor).
 * Константа строки дублируется у потребителей (не platform/ядро).
 */

import bridge from '@/integrations/ModuleBridge.js'
import { moduleManager } from '@/modules/index.js'
import { tGlobal } from '@/i18n/index.js'
import { getModuleById } from '../modules/index.js'

/** @type {string} */
export const CHAT_PROFILES_GROUP = 'ai_assistant.chat.profiles'

export const DEFAULT_CHAT_PROFILE_ID = 'default'

/**
 * @typedef {Object} ChatProfileDescriptor
 * @property {string} id
 * @property {number} [order]
 * @property {string} [icon] Lucide PascalCase
 * @property {string} [title]
 * @property {string} [welcomeMessage]
 * @property {string} [placeholder]
 * @property {string[]} [suggestions]
 * @property {string} [permissionModule]
 * @property {string} [permission]
 * @property {string} [sessionModule] ChatSession.module для хаба
 * @property {string} [miniChatModule] ChatSession.module для мини-чата
 * @property {string} [hubQuery] значение ?profile=
 * @property {string} [storageKey]
 * @property {{ files?: boolean, vectorization?: boolean, suggestions?: boolean }} [features]
 * @property {boolean} [openFromAppsMenu]
 * @property {boolean} [external] true — stream через profile proxy
 */

function buildDefaultProfile() {
  const chat = getModuleById('chat')
  return {
    id: DEFAULT_CHAT_PROFILE_ID,
    order: 0,
    icon: 'Bot',
    get title() {
      return tGlobal('ai_assistant.apps.ollamaChat')
    },
    get welcomeMessage() {
      return chat?.settings?.welcomeMessage || tGlobal('ai_assistant.modules.chat.welcome')
    },
    get placeholder() {
      return chat?.settings?.placeholder || tGlobal('ai_assistant.modules.chat.placeholder')
    },
    get suggestions() {
      return chat?.suggestions || []
    },
    permissionModule: 'ai_assistant',
    permission: 'ai_assistant_view',
    sessionModule: 'chat',
    miniChatModule: 'mini_chat',
    hubQuery: '',
    storageKey: 'ai_assistant.miniChat.v1',
    features: { files: true, vectorization: true, suggestions: true },
    openFromAppsMenu: true,
    external: false,
  }
}

/**
 * @param {ChatProfileDescriptor} raw
 * @returns {ChatProfileDescriptor|null}
 */
function normalizeExternalProfile(raw) {
  if (!raw || typeof raw !== 'object') return null
  const id = String(raw.id || '').trim()
  if (!id || id === DEFAULT_CHAT_PROFILE_ID) return null
  return {
    id,
    order: Number(raw.order) || 100,
    icon: raw.icon || 'BookOpen',
    title: raw.title || id,
    welcomeMessage: raw.welcomeMessage || '',
    placeholder: raw.placeholder || '',
    suggestions: Array.isArray(raw.suggestions) ? raw.suggestions : [],
    permissionModule: raw.permissionModule || id,
    permission: raw.permission || '',
    sessionModule: raw.sessionModule || `${id}_chat`,
    miniChatModule: raw.miniChatModule || `${id}_mini`,
    hubQuery: raw.hubQuery || id,
    storageKey: raw.storageKey || `ai_assistant.miniChat.${id}.v1`,
    features: {
      files: Boolean(raw.features?.files),
      vectorization: Boolean(raw.features?.vectorization),
      suggestions: raw.features?.suggestions !== false,
    },
    openFromAppsMenu: Boolean(raw.openFromAppsMenu),
    external: true,
  }
}

/**
 * @returns {Promise<ChatProfileDescriptor[]>}
 */
export async function collectChatProfiles() {
  if (!moduleManager.initialized) {
    await moduleManager.initialize()
  }
  const defaults = [buildDefaultProfile()]
  const external = Object.values(bridge.all(CHAT_PROFILES_GROUP) || {})
    .map(normalizeExternalProfile)
    .filter(Boolean)
    .sort((a, b) => (a.order ?? 100) - (b.order ?? 100))
  const all = [...defaults, ...external]
  const { hasModulePermission } = await import('@/core/cms/adp/js/accessControl.js')
  const visible = []
  for (const profile of all) {
    if (profile.permissionModule && profile.permission) {
      const ok = await hasModulePermission(profile.permissionModule, profile.permission)
      if (!ok) continue
    }
    visible.push(profile)
  }
  return visible
}

/**
 * @param {string} profileId
 * @returns {Promise<ChatProfileDescriptor|null>}
 */
export async function getChatProfile(profileId) {
  const id = String(profileId || DEFAULT_CHAT_PROFILE_ID).trim() || DEFAULT_CHAT_PROFILE_ID
  if (id === DEFAULT_CHAT_PROFILE_ID) {
    return buildDefaultProfile()
  }
  const all = await collectChatProfiles()
  return all.find((p) => p.id === id) || null
}

/**
 * UI-config совместимый с HubMessage / suggestions (как modules/chat/config).
 * @param {ChatProfileDescriptor} profile
 */
export function profileToModuleConfig(profile) {
  const chat = getModuleById('chat')
  return {
    id: profile.id,
    name: profile.title || '',
    description: '',
    icon: chat?.icon,
    color: chat?.color || 'var(--ai-accent, var(--color-accent))',
    colorLight: chat?.colorLight,
    enabled: true,
    settings: {
      welcomeMessage: profile.welcomeMessage,
      placeholder: profile.placeholder,
      maxTokens: chat?.settings?.maxTokens ?? 2048,
    },
    suggestions: profile.features?.suggestions === false ? [] : (profile.suggestions || []),
  }
}
