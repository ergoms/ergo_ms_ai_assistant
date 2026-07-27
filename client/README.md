# AI Assistant (клиент)

Единый хаб AI-ассистента: чат, документы и код. Тип чата выбирается при создании сессии.

## Как работает

1. В `modules/index.js` зарегистрированы конфиги подмодулей (`chat`, `docs`, `code`)
2. `AIAssistantHub.vue` переключает UI по `activeModule`
3. API-клиенты — `rag/js/rag-client.js` (чат/сессии) и `docs/js/docs-client.js` (документы)
4. Статус Ollama — через `ollama_framework/status/` (см. `js/ollamaStatusApi.js`)

## Каталог

```
modules/ai_assistant/client/
├── base/           # общие элементы чата (сообщение, индикатор набора)
├── components/     # UI хаба (HubMessage, ChatTypeSelector, NeuralBackground, …)
├── docs/           # подмодуль документов (DocsAssistantChat, uploader, docs-client)
├── rag/            # rag-client и module-config для чата/сессий
├── modules/        # реестр конфигов: chat, docs, code
├── pages/          # AIAssistantHub.vue
├── js/             # routes, endpoints, theme-defaults, composables
└── styles/         # theme-bootstrap, переменные, стили чата
```

## Встроенные подмодули

| Подмодуль | Назначение |
|-----------|------------|
| chat | обычный чат с ассистентом |
| docs | загрузка документов и Q&A (RAG) |
| code | чат по коду |

## Новый подмодуль

1. Конфиг в `modules/<имя>/config.js` и регистрация в `modules/index.js`
2. При необходимости — UI-ветка в `AIAssistantHub.vue` и клиент API в своей папке
3. Перезапуск клиента

API-клиент — через `@/js/api/manager`. Настройки Ollama передавай в теле запроса как `ollama_config`.
