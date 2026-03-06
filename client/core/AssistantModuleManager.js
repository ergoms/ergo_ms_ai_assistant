/**
 * МЕНЕДЖЕР МОДУЛЕЙ AI-АССИСТЕНТА
 * 
 * Управляет загрузкой и переключением между модулями ассистента
 */

import { getActiveModule } from './module-config.js'

export class AssistantModuleManager {
  constructor() {
    this.currentModule = null
    this.currentModuleName = null
    this.loadedModules = new Map()
    this.moduleComponents = new Map()
    this.moduleClients = new Map()
  }

  /**
   * Определяет и загружает активный модуль по роуту
   * @param {string} routePath - путь текущего роута
   * @returns {Promise<Object>} загруженный модуль
   */
  async loadModuleForRoute(routePath) {
    const moduleConfig = getActiveModule(routePath)
    
    // Если модуль не найден, выбрасываем ошибку
    if (!moduleConfig) {
      throw new Error(`AI Assistant: No module found for route ${routePath}`)
    }
    
    // Если модуль уже загружен и активен, возвращаем его
    if (this.currentModuleName === moduleConfig.name && this.currentModule) {
      return this.currentModule
    }

    // Загружаем компонент модуля
    let component = this.moduleComponents.get(moduleConfig.name)
    if (!component) {
      const componentModule = await moduleConfig.component()
      component = componentModule.default || componentModule
      this.moduleComponents.set(moduleConfig.name, component)
    }

    // Загружаем клиент модуля
    let client = this.moduleClients.get(moduleConfig.name)
    if (!client) {
      const clientModule = await moduleConfig.client()
      client = clientModule.default || clientModule
      this.moduleClients.set(moduleConfig.name, client)
    }

    // Сохраняем текущий модуль
    this.currentModule = {
      name: moduleConfig.name,
      component,
      client,
      config: moduleConfig,
    }
    this.currentModuleName = moduleConfig.name

    return this.currentModule
  }

  /**
   * Получает текущий активный модуль
   * @returns {Object|null}
   */
  getCurrentModule() {
    return this.currentModule
  }

  /**
   * Получает имя текущего модуля
   * @returns {string|null}
   */
  getCurrentModuleName() {
    return this.currentModuleName
  }

  /**
   * Проверяет, нужно ли переключить модуль
   * @param {string} routePath - путь текущего роута
   * @returns {boolean}
   */
  shouldSwitchModule(routePath) {
    const newModule = getActiveModule(routePath)
    return this.currentModuleName !== newModule.name
  }

  /**
   * Очищает кеш модулей
   */
  clearCache() {
    this.loadedModules.clear()
    this.moduleComponents.clear()
    this.moduleClients.clear()
    this.currentModule = null
    this.currentModuleName = null
  }
}

// Создаем единственный экземпляр менеджера
export const assistantModuleManager = new AssistantModuleManager()

