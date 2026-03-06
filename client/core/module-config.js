/**
 * ДИНАМИЧЕСКАЯ КОНФИГУРАЦИЯ МОДУЛЕЙ AI-АССИСТЕНТА
 * 
 * Автоматически обнаруживает все модули в директории ai-assistant
 * и загружает их конфигурацию из файлов module-config.json
 */

// Автоматически находим все конфигурационные файлы модулей
const moduleConfigs = import.meta.glob('../*/module-config.json', { eager: true })

// Автоматически находим все компоненты чатов модулей
const chatComponents = import.meta.glob('../*/*AssistantChat.vue')

// Автоматически находим все клиенты модулей (eager: true для избежания конфликтов со статическими импортами)
const moduleClients = import.meta.glob('../*/js/*-client.js', { eager: true })

/**
 * Извлекает имя модуля из пути
 */
function extractModuleName(path) {
  const match = path.match(/\/([^/]+)\/(module-config\.json|.*AssistantChat\.vue|.*-client\.js)$/)
  return match ? match[1] : null
}

/**
 * Преобразует строковые паттерны в регулярные выражения
 */
function parseRoutePatterns(patterns) {
  if (!patterns || !Array.isArray(patterns)) {
    return []
  }
  
  return patterns
    .map(pattern => {
      // Если уже RegExp, возвращаем как есть
      if (pattern instanceof RegExp) {
        return pattern
      }
      
      // Если не строка, пропускаем
      if (typeof pattern !== 'string') {
        console.warn('AI Assistant: Invalid route pattern type:', typeof pattern, pattern)
        return null
      }
      
      try {
        // Преобразуем строку в RegExp, добавляя ^ в начало если нет
        const patternStr = pattern.startsWith('^') ? pattern : `^${pattern}`
        return new RegExp(patternStr)
      } catch (error) {
        console.warn('AI Assistant: Failed to parse route pattern:', pattern, error)
        return null
      }
    })
    .filter(pattern => pattern !== null) // Удаляем null значения
}

/**
 * Создает динамическую конфигурацию модулей
 */
function buildDynamicModuleConfig() {
  const config = {}
  
  // Обрабатываем найденные конфигурационные файлы
  Object.entries(moduleConfigs).forEach(([path, moduleData]) => {
    const moduleName = extractModuleName(path)
    if (!moduleName || moduleName === 'base' || moduleName === 'core' || moduleName === 'js') {
      return
    }
    
    const configData = moduleData.default || moduleData
    
    // Находим компонент для этого модуля
    const componentPath = Object.keys(chatComponents).find(p => 
      p.includes(`/${moduleName}/`) && p.includes('AssistantChat.vue')
    )
    
    // Находим клиент для этого модуля
    const clientPath = Object.keys(moduleClients).find(p => 
      p.includes(`/${moduleName}/js/`) && p.includes('-client.js')
    )
    
    if (componentPath && clientPath) {
      // Преобразуем строковые паттерны в RegExp
      const routePatterns = parseRoutePatterns(configData.routePatterns)
      
      // Получаем уже загруженный клиент (eager: true)
      const clientModule = moduleClients[clientPath]
      // Ищем экспорт клиента (может быть именованный или default)
      // Форматы: biClient, ragClient, crmClient и т.д. (lowercase)
      const clientName = `${moduleName}Client`
      // Также пробуем варианты: biClient, BiClient, BIClient
      const camelCaseName = moduleName.charAt(0).toUpperCase() + moduleName.slice(1) + 'Client'
      const upperCaseName = moduleName.toUpperCase() + 'Client'
      const client = clientModule?.[clientName] || clientModule?.[camelCaseName] || clientModule?.[upperCaseName] || clientModule?.default || (clientModule && Object.values(clientModule)[0])
      
      config[moduleName] = {
        name: moduleName,
        routePatterns: routePatterns,
        component: () => import(/* @vite-ignore */ componentPath),
        client: client ? () => Promise.resolve(client) : null,
        isDefault: configData.isDefault || false,
        ollama: configData.ollama || null, // Настройки Ollama для модуля
      }
    }
  })
  
  return config
}

/**
 * Динамически построенная конфигурация модулей
 */
export const moduleConfig = buildDynamicModuleConfig()

/**
 * Определяет активный модуль по текущему роуту
 * @param {string} routePath - путь текущего роута
 * @returns {Object} конфигурация модуля
 */
export function getActiveModule(routePath) {
  // Если нет модулей, возвращаем null
  if (Object.keys(moduleConfig).length === 0) {
    console.warn('AI Assistant: No modules found in configuration')
    return null
  }
  
  // Проверяем все модули кроме default
  for (const config of Object.values(moduleConfig)) {
    if (config.isDefault) continue
    
    // Проверяем, что routePatterns существует и является массивом
    if (!config.routePatterns || !Array.isArray(config.routePatterns)) {
      continue
    }
    
    for (const pattern of config.routePatterns) {
      // Проверяем, что pattern является RegExp
      if (!(pattern instanceof RegExp)) {
        console.warn(`AI Assistant: Invalid route pattern in module ${config.name}:`, pattern)
        continue
      }
      
      if (pattern.test(routePath)) {
        return config
      }
    }
  }
  
  // Возвращаем модуль по умолчанию
  const defaultModule = Object.values(moduleConfig).find(m => m.isDefault)
  return defaultModule || Object.values(moduleConfig)[0] || null
}

/**
 * Получает имя активного модуля
 * @param {string} routePath - путь текущего роута
 * @returns {string} имя модуля
 */
export function getActiveModuleName(routePath) {
  return getActiveModule(routePath).name
}

/**
 * Получает список всех доступных модулей
 * @returns {Array<string>}
 */
export function getAvailableModules() {
  return Object.keys(moduleConfig)
}

/**
 * Получает конфигурацию модуля по имени
 * @param {string} moduleName - имя модуля
 * @returns {Object|null}
 */
export function getModuleConfig(moduleName) {
  return moduleConfig[moduleName] || null
}
