# AI Assistant (клиент)

Ассистент в toolbar меню. Модуль чата выбирается по текущему URL.

## Как работает

1. В `module-config.json` у подмодуля — паттерны URL
2. При смене страницы подгружается нужный чат и клиент API
3. У каждого подмодуля свои настройки Ollama (модель, температура)

## Каталог

```
modules/ai_assistant/client/
├── base/           # общие элементы чата
├── core/           # module-config.js, AssistantModuleManager.js
├── bi/, rag/, docs/  # подмодули по разделам
├── modules/        # реестр конфигов
├── pages/          # AIAssistantHub.vue
├── js/             # routes, menu, assistantService.js
└── components/
```

## Встроенные подмодули

| Подмодуль | URL | Назначение |
|-----------|-----|------------|
| bi | `/bi/*` | SQL, файлы, графики |
| rag | остальное (default) | простой чат |
| docs | документы | загрузка и Q&A |

## Новый подмодуль

1. Папка в `modules/ai_assistant/client/<имя>/`
2. `module-config.json` — `routePatterns`, блок `ollama`
3. `<Имя>AssistantChat.vue` + `js/<имя>-client.js`
4. Перезапуск клиента — регистрация автоматическая

Пример `module-config.json`:

```json
{
  "name": "my-part",
  "routePatterns": ["^/my-part"],
  "isDefault": false,
  "ollama": {
    "model": "mistral7b-tuned",
    "temperature": 0.3,
    "contextWindow": 4096,
    "maxTokens": 512
  }
}
```

API-клиент — через `@/js/api/manager`, настройки Ollama передавай в теле запроса как `ollama_config`.

## Программный доступ

```javascript
import { assistantModuleManager } from '../core/AssistantModuleManager.js'

const mod = await assistantModuleManager.loadModuleForRoute('/bi/...')
// mod.component, mod.client, mod.config
```
