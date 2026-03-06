# AI Assistant

Модульная система AI-ассистента с автоматическим переключением модулей в зависимости от текущего роута. Каждый модуль может иметь свои настройки Ollama (модель, температура, окно контекста).

## Как это работает

1. **Автоматическое определение модуля**: При изменении роута система проверяет паттерны в `module-config.json` каждого модуля и выбирает подходящий модуль.

2. **Динамическая загрузка**: Компонент чата и API клиент модуля загружаются динамически только когда нужны.

3. **Настройки Ollama**: Каждый модуль может иметь свои настройки Ollama (модель, температура, окно контекста), которые передаются в API запросы.

4. **Интеграция**: Ассистент автоматически интегрирован в `MenuToolbar.vue` и доступен на всех страницах через кнопку в меню.

## Структура

```
ai-assistant/
├── base/                    # Базовые компоненты (общие для всех модулей)
│   ├── AssistantMessage.vue
│   ├── AssistantTyping.vue
│   └── AssistantButton.vue
├── core/                    # Ядро системы
│   ├── module-config.js     # Автоматическое обнаружение и загрузка модулей
│   └── AssistantModuleManager.js  # Менеджер модулей
├── bi/                      # Модуль для BI страниц (/bi/*)
│   ├── module-config.json   # Конфигурация модуля (роуты + настройки Ollama)
│   ├── BIAssistantChat.vue  # Компонент чата
│   ├── FileSelector.vue
│   └── js/
│       └── bi-client.js      # API клиент модуля
├── rag/                     # Модуль для простого RAG чата (по умолчанию)
│   ├── module-config.json   # Конфигурация модуля
│   ├── RAGAssistantChat.vue
│   └── js/
│       └── rag-client.js
└── js/
    └── assistantService.js  # Глобальный сервис для управления ассистентом
```

## Модули

### BI модуль (`/bi/*`)
- Выбор файлов для анализа
- Генерация SQL запросов через Ollama
- Анализ табличных данных
- Streaming ответы
- Анализ графиков

**Настройки Ollama:**
- Модель: `mistral7b-tuned`
- Температура: `0.1` (низкая для точного SQL)
- Окно контекста: `4096`
- Токены для SQL: `256`
- Токены для комментариев: `192`

### RAG модуль (по умолчанию)
- Простой чат с AI
- Ответы на общие вопросы
- Помощь с навигацией

**Настройки Ollama:**
- Модель: `mistral7b-tuned`
- Температура: `0.3` (выше для более естественных ответов)
- Окно контекста: `4096`
- Максимум токенов: `512`

## Как добавить свой модуль

### 1. Создайте структуру модуля

Создайте директорию с именем вашего модуля в `core/client/src/core/ai-assistant/`:

```
your-module/
├── module-config.json
├── YourModuleAssistantChat.vue
└── js/
    └── your-module-client.js
```

### 2. Создайте `module-config.json`

```json
{
  "name": "your-module",
  "routePatterns": [
    "^/your-module(/|$)",
    "^/your-module/.*"
  ],
  "isDefault": false,
  "ollama": {
    "baseUrl": "http://localhost:11434",
    "model": "mistral7b-tuned",
    "temperature": 0.2,
    "contextWindow": 4096,
    "maxTokens": 512
  }
}
```

**Параметры:**
- `name` - имя модуля (должно совпадать с именем директории)
- `routePatterns` - массив паттернов роутов (автоматически преобразуются в RegExp)
- `isDefault` - если `true`, модуль используется для всех роутов, которые не подходят под другие паттерны
- `ollama` - настройки Ollama для модуля:
  - `baseUrl` - URL Ollama API
  - `model` - название модели
  - `temperature` - температура генерации (0.0-1.0)
  - `contextWindow` - размер окна контекста
  - `maxTokens` - максимум токенов для генерации (для RAG модулей)
  - `sqlGenerationTokens` - лимит токенов для SQL генерации (для BI модулей)
  - `commentaryTokens` - лимит токенов для комментариев (для BI модулей)

### 3. Создайте компонент чата

Создайте файл `YourModuleAssistantChat.vue`:

```vue
<template>
  <div v-if="isVisible" class="assistant-chat">
    <!-- Ваш интерфейс чата -->
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { yourModuleClient } from './js/your-module-client.js'

const props = defineProps({
  isVisible: {
    type: Boolean,
    default: false,
  },
})

// Ваша логика чата
</script>
```

### 4. Создайте API клиент

Создайте файл `js/your-module-client.js`:

```javascript
import { apiClient } from '@/js/api/manager'

const endpoints = {
  yourEndpoint: 'your_module/endpoint/',
}

class YourModuleClient {
  constructor() {
    this.ollamaConfig = null
  }

  setOllamaConfig(config) {
    this.ollamaConfig = config
  }

  async sendMessage(message) {
    const requestBody = { message }
    
    // Добавляем настройки Ollama, если они есть
    if (this.ollamaConfig) {
      requestBody.ollama_config = {
        base_url: this.ollamaConfig.baseUrl,
        model: this.ollamaConfig.model,
        temperature: this.ollamaConfig.temperature,
        context_window: this.ollamaConfig.contextWindow,
        max_tokens: this.ollamaConfig.maxTokens,
      }
    }
    
    const response = await apiClient.post(endpoints.yourEndpoint, requestBody)
    return response
  }
}

export const yourModuleClient = new YourModuleClient()
export default YourModuleClient
```

### 5. Система автоматически обнаружит модуль

Модуль будет автоматически обнаружен системой при следующей загрузке приложения. Никаких дополнительных регистраций не требуется!

## Использование

### Через модульный менеджер

```javascript
import { assistantModuleManager } from '@/core/ai-assistant/core/AssistantModuleManager.js'

// Загрузка модуля для текущего роута
const module = await assistantModuleManager.loadModuleForRoute('/your-module')
// module.component - компонент чата
// module.client - API клиент модуля
// module.config - конфигурация модуля (включая настройки Ollama)
```

### Прямое использование клиента

```javascript
import { biClient } from '@/core/ai-assistant/bi/js/bi-client.js'

// Проверка доступности Ollama
const status = await biClient.checkOllamaStatus()

// Запрос с streaming
const result = await biClient.askQuestionStream(fileId, question, true, (event) => {
  // Обработка streaming событий
})
```

## Интеграция

Ассистент автоматически интегрирован в `MenuToolbar.vue` и работает на всех страницах:
- На страницах `/bi/*` - BI модуль с анализом данных
- На остальных страницах - RAG модуль с простым чатом
- На ваших страницах - ваш модуль (если настроены правильные паттерны роутов)