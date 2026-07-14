/**
 * AI Hub - Module Registry
 */

import chatConfig from './chat/config.js'
import codeConfig from './code/config.js'
import docsConfig from './docs/config.js'

export const modules = [
  chatConfig,
  codeConfig,
  docsConfig,
]

export const getEnabledModules = () => modules.filter((m) => m.enabled)

export const getModuleById = (id) => modules.find((m) => m.id === id)

export default modules
