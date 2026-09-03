# ai_assistant — инструкции агенту

Доменный модуль AI-хаба: чат, RAG/документы, skills, **расширяемые chat-профили**. LLM — только через `ollama_framework` (ModuleBridge).

## Куда смотреть

- Правила Cursor модуля — `.cursor/rules/ai-assistant.mdc`
- Обзор для людей — `README.md`
- Gateway к Ollama — `api/ollama_gateway.py` (`map_ollama_config` + `bridge.call` / HTTP REST)
- Промпты и роль — `api/rag/prompts.py`, `api/assistant_role.py`; защита выдачи — `api/safety/policy.py`
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
- Embeddings — только `OLLAMA_EMBEDDINGS_MODEL`, не chat-`model` из запроса. Имя библиотеки Ollama — через gateway; снимок Hugging Face `org/name` (`deepvk/USER-bge-m3`) — sentence-transformers и `huggingface_models.yaml`
- Статус Ollama для UI — `GET ai_assistant/ollama_status/`; не звать без `ai_assistant_view` / `ai_assistant_mini_chat` и при deny ACL (`denied_api` / `/ai-assistant`)
- Владелец записей — `user_public_id` (UUID), без FK на пользователя ядра; хелпер `api/ownership.py`
- Удаление пользователя — подписка на `core.user_delete` в `integrations.py`
- Bridge ops с данными пользователя — передавать `user`; владелец в таблицах — `user_public_id`, без FK на пользователя ядра
- Удаление пользователя — подписка на `core.user_delete` в `integrations.py`
- Вынос в отдельный процесс: `api/bridge_manifest.yaml`, `api/schema.yaml` (`isolated: true`), `host_lifecycle.yaml` (API, worker и Beat); `knowledge.sign_read.ai_assistant` и группа `knowledge.packs`
- `chat.message.add` без user запрещён
- `document.parse` — media_api path под `ai_assistant/` + `user`, не произвольный FS path
- Частота загрузок — `AI_ASSISTANT_UPLOAD_RATE_RAG` / `_CHAT` в `.env` модуля (`media.upload_quota_policies`)
- Хост-модуль регистрирует chat-профиль: группа `ai_assistant.chat.profiles` (client + server) + op `*.ask_stream`; UI — `bridge.call('ai_assistant.mini_chat.open', profileId)` или `?profile=`; право профиля (`permissionModule` / `permission`) скрывает виджет и блокирует stream; `mini_chat.open` сразу `false`, если ACL закрыл модуль
- Плавающий мини-чат — право `ai_assistant_mini_chat` **или** видимый внешний chat-профиль, плюс нет deny на `/ai-assistant` / `/api/ai_assistant/` (`isVisible` у `shell.floating_widgets`); хаб `/ai-assistant` — `ai_assistant_view`
- Proxy stream — `POST ai_assistant/chat/profiles/<id>/stream/`; сессии остаются в `ChatSession`
- Сохранение мини-чата в хаб — `POST ai_assistant/chat_sessions/<id>/save/` (module `mini_chat` / `*_mini` → `chat` / `session_module`); кнопка в шапке плавающего виджета
- Ошибки на клиенте — `logError` / `logWarn` с import из `@/js/utils/logError.js`
- Тема — `theme-defaults.js` + `useModuleThemeMode('ai_assistant')`
- Пользовательский корпус RAG — пакеты `knowledge/` в media_api (user_guides, user_description и автокаталог экранов из `publish-knowledge-packs`) плюс меню через `core.knowledge.user_capabilities`. Не обходить чужие `modules/` и `core/` на диске. Sync: `ergoms ai_assistant:sync-knowledge`; свой пакет: `ergoms publish-knowledge-packs --module=ai_assistant`
- Ответ про кнопки и поля — только подписи из RAG и runtime-меню. Выдуманные названия режет `api/safety/grounding.py`. Проверка каталога: `ergoms ai_assistant:howto-eval` (без Ollama) или `--ask`
- Индексация RAG: подокументный прогресс — DEBUG; сводка — stdout `sync-knowledge` / один INFO задачи Beat
- Setup-full — `include_in: setup-full-after-migrate` (`--sync`); ежедневно — Celery Beat (`celery_beat_config.py`, `RAG_SYSTEM_CORPUS_BEAT_ENABLED`)
- Описания модулей для корпуса — `user_description` в `PERMISSION_CATALOG`
- Модели Ollama для setup-full — `ollama_models.yaml` (pull через `ergoms ollama_framework:pull-setup-models`)
- Chat messages — через `api/rag/chat_messages.py` и `api/rag/prompts.py`. Роль только с сервера (`PermissionService.is_admin`): отдельные system prompt и runtime-меню для админа и пользователя. Клиентскому «я админ» не доверять
- Корпус RAG: metadata `audience` (`user` / `admin`). Не-админу не подмешивать `audience=admin`. Полное меню и каталог прав — только админский корпус; пользователю меню даёт runtime
- Защита выдачи — `api/safety/policy.py`: jailbreak и явный админ-howto на входе (отказ без LLM), проверка ответа до сохранения и `done`. Утечка или выдуманная кнопка/поле → `replace` в SSE и `metadata.safety`

## Команды

```bash
ergoms ai_assistant:sync-knowledge
ergoms ai_assistant:howto-eval
ergoms ai_assistant:howto-eval --ask
ergoms ai_assistant:install-pgvector   # файлы + CREATE EXTENSION в текущей БД
ergoms ai_assistant:ensure-pgvector
```
