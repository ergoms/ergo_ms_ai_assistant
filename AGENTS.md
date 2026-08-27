# ai_assistant — инструкции агенту

Доменный модуль AI-хаба: чат, RAG/документы, skills, **расширяемые chat-профили**. LLM — только через `ollama_framework` (ModuleBridge).

## Куда смотреть

- Правила Cursor модуля — `.cursor/rules/ai-assistant.mdc`
- Обзор для людей — `README.md`
- Gateway к Ollama — `api/ollama_gateway.py` (`map_ollama_config` + `bridge.call` / HTTP REST)
- Мост наружу — `api/integrations.py`, `api/chat_profiles.py`
- Chat profiles (клиент) — `client/js/chatProfiles.js`, `chatTransport.js`, `miniChatBridge.js`, `aiAssistantAccess.js`
- Клиент — `client/js/` (routes, endpoints, theme-defaults, locales)

## Запрещено

- `from modules.ollama_framework…` — только `bridge.call('ollama_framework.*')` через gateway
- Клиентский REST к чужому модулю (`ollama_framework/status/`) — использовать `ai_assistant/ollama_status/`
- Прямой httpx к `:11434` из этого модуля
- Принимать клиентский `base_url` / `compute_device` / `num_gpu` в `ollama_config` (SSRF) — только whitelist в `map_ollama_config`
- Доменный KAG / корпус чужого модуля внутри ai_assistant — только proxy + chat profile

## Обязательно

- Вызовы LLM/embeddings — `api/ollama_gateway.py`; `base_url` и лимиты нагрузки — из `.env` модуля
- Параллелизм LLM — `AI_ASSISTANT_CONCURRENCY_LIMIT` (семафор в gateway); индексация RAG — Celery `index_knowledge_document`
- Embeddings — только `OLLAMA_EMBEDDINGS_MODEL` (имя библиотеки Ollama, не chat-`model` из запроса; иначе Ollama 501). Снимок Hugging Face `org/name` в этой переменной игнорируется, берётся `embeddinggemma`
- Статус Ollama для UI — `GET ai_assistant/ollama_status/`; не звать без `ai_assistant_view` / `ai_assistant_mini_chat` и при deny ACL (`denied_api` / `/ai-assistant`)
- Владелец записей — `user_public_id` (UUID), без FK на пользователя ядра; хелпер `api/ownership.py`
- Удаление пользователя — подписка на `core.user_delete` в `integrations.py`
- Bridge ops с данными пользователя — передавать `user`; владелец в таблицах — `user_public_id`, без FK на пользователя ядра
- Удаление пользователя — подписка на `core.user_delete` в `integrations.py`
- Вынос в отдельный процесс: `api/bridge_manifest.yaml`, `api/schema.yaml` (`isolated: true`), `host_lifecycle.yaml` (API, worker и Beat)
- `chat.message.add` без user запрещён
- `document.parse` — media_api path под `ai_assistant/` + `user`, не произвольный FS path
- Частота загрузок — `AI_ASSISTANT_UPLOAD_RATE_RAG` / `_CHAT` в `.env` модуля (`media.upload_quota_policies`)
- Хост-модуль регистрирует chat-профиль: группа `ai_assistant.chat.profiles` (client + server) + op `*.ask_stream`; UI — `bridge.call('ai_assistant.mini_chat.open', profileId)` или `?profile=`; право профиля (`permissionModule` / `permission`) скрывает виджет и блокирует stream; `mini_chat.open` сразу `false`, если ACL закрыл модуль
- Плавающий мини-чат — право `ai_assistant_mini_chat` **или** видимый внешний chat-профиль, плюс нет deny на `/ai-assistant` / `/api/ai_assistant/` (`isVisible` у `shell.floating_widgets`); хаб `/ai-assistant` — `ai_assistant_view`
- Proxy stream — `POST ai_assistant/chat/profiles/<id>/stream/`; сессии остаются в `ChatSession`
- Ошибки на клиенте — `logError` / `logWarn` с import из `@/js/utils/logError.js`
- Тема — `theme-defaults.js` + `useModuleThemeMode('ai_assistant')`
- Пользовательский корпус RAG — `ergoms ai_assistant:sync-knowledge` (меню, UI, `system_corpus/guides`, `modules/*/api/user_guides/*.md`; не `.docs`/rules)
- Индексация RAG: подокументный прогресс — DEBUG; сводка — stdout `sync-knowledge` / один INFO задачи Beat
- Setup-full — `include_in: setup-full-after-migrate` (`--sync`); ежедневно — Celery Beat (`celery_beat_config.py`, `RAG_SYSTEM_CORPUS_BEAT_ENABLED`)
- Описания модулей для корпуса — `user_description` в `PERMISSION_CATALOG`
- Модели Ollama для setup-full — `ollama_models.yaml` (pull через `ergoms ollama_framework:pull-setup-models`)
- Chat messages — через `api/rag/chat_messages.py` (помощник пользователя сайта, не разработчика)

## Команды

```bash
ergoms ai_assistant:sync-knowledge
ergoms ai_assistant:install-pgvector   # файлы + CREATE EXTENSION в текущей БД
ergoms ai_assistant:ensure-pgvector
```
