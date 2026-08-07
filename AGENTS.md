# ai_assistant — инструкции агенту

Доменный модуль AI-хаба: чат, RAG/документы, skills. LLM — только через `ollama_framework` (ModuleBridge).

## Куда смотреть

- Правила Cursor модуля — `.cursor/rules/ai-assistant.mdc`
- Обзор для людей — `README.md`
- Gateway к Ollama — `api/ollama_gateway.py` (`map_ollama_config` + `bridge.call` / HTTP REST)
- Мост наружу — `api/integrations.py`
- Клиент — `client/js/` (routes, endpoints, theme-defaults, locales)

## Запрещено

- `from modules.ollama_framework…` — только `bridge.call('ollama_framework.*')` через gateway
- Клиентский REST к чужому модулю (`ollama_framework/status/`) — использовать `ai_assistant/ollama_status/`
- Прямой httpx к `:11434` из этого модуля
- Принимать клиентский `base_url` / `compute_device` / `num_gpu` в `ollama_config` (SSRF) — только whitelist в `map_ollama_config`

## Обязательно

- Вызовы LLM/embeddings — `api/ollama_gateway.py`; `base_url` и лимиты нагрузки — из `.env` модуля
- Параллелизм LLM — `AI_ASSISTANT_CONCURRENCY_LIMIT` (семафор в gateway); индексация RAG — Celery `index_knowledge_document`
- Embeddings — только `OLLAMA_EMBEDDINGS_MODEL` (не chat-`model` из запроса; иначе Ollama 501)
- Статус Ollama для UI — `GET ai_assistant/ollama_status/`
- Bridge ops с данными пользователя — передавать `user`; `chat.message.add` без user запрещён
- `document.parse` — media_api path под `ai_assistant/` + `user`, не произвольный FS path
- Ошибки на клиенте — `logError` / `logWarn` с import из `@/js/utils/logError.js`
- Тема — `theme-defaults.js` + `useModuleThemeMode('ai_assistant')`
- Пользовательский корпус RAG — `ergoms ai_assistant:sync-knowledge` (меню, UI, `system_corpus/guides`, `modules/*/api/user_guides/*.md`; не `.docs`/rules)
- Setup-full — `include_in: setup-full-after-migrate` (`--sync`); ежедневно — Celery Beat (`celery_beat_config.py`, `RAG_SYSTEM_CORPUS_BEAT_ENABLED`)
- Описания модулей для корпуса — `user_description` в `PERMISSION_CATALOG`
- Модели Ollama для setup-full — `ollama_models.yaml` (pull через `ergoms ollama_framework:pull-setup-models`)
- Chat messages — через `api/rag/chat_messages.py` (помощник пользователя сайта, не разработчика)

## Команды

```bash
ergoms ai_assistant:sync-knowledge
ergoms ai_assistant:install-pgvector
ergoms ai_assistant:ensure-pgvector
```
