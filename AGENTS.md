# ai_assistant — инструкции агенту

Доменный модуль AI-хаба: чат, RAG/документы, skills. LLM — только через `ollama_framework` (ModuleBridge).

## Куда смотреть

- Правила Cursor модуля — `.cursor/rules/ai-assistant.mdc`
- Gateway к Ollama — `api/ollama_gateway.py` (только `bridge.call` / свой REST proxy)
- Мост наружу — `api/integrations.py`
- Клиент — `client/js/` (routes, endpoints, theme-defaults, locales)

## Запрещено

- `from modules.ollama_framework…` — только `bridge.call('ollama_framework.*')` через gateway
- Клиентский REST к чужому модулю (`ollama_framework/status/`) — использовать `ai_assistant/ollama_status/`
- Прямой httpx к `:11434` из этого модуля

## Обязательно

- Вызовы LLM/embeddings — `api/ollama_gateway.py`
- Статус Ollama для UI — `GET ai_assistant/ollama_status/`
- Ошибки на клиенте — `logError` / `logWarn` с import из `@/js/utils/logError.js`
- Тема — `theme-defaults.js` + `useModuleThemeMode('ai_assistant')`
- Пользовательский корпус RAG — `ergoms ai_assistant:sync-knowledge` (меню, UI-строки, guides; не `.docs`/rules)
- Chat messages — через `api/rag/chat_messages.py` (помощник пользователя сайта, не разработчика)
