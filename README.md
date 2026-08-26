# ai_assistant

Доменный модуль AI-хаба ERGO MS: чат, RAG по документам, skills. Вызовы LLM идут только через модуль `ollama_framework` (ModuleBridge), без прямого доступа к `:11434`.

## Документация

- Агент: [`AGENTS.md`](AGENTS.md), [`.cursor/rules/ai-assistant.mdc`](.cursor/rules/ai-assistant.mdc)
- Клиентский обзор: [`client/README.md`](client/README.md)
- Справка CLI: [`ergoms.help.yaml`](ergoms.help.yaml)

## Зависимости

В [`integrations.yaml`](integrations.yaml) указано `requires: ollama_framework`. Без установленного и запущенного Ollama чат и embeddings недоступны.

Для векторного поиска нужны pgvector (`ergoms ai_assistant:install-pgvector` / `ensure-pgvector`) и модели из [`ollama_models.yaml`](ollama_models.yaml) (pull через `ergoms ollama_framework:pull-setup-models`).

## Настройка

Скопируйте [`modules/ai_assistant/.env.example`](.env.example) в `modules/ai_assistant/.env` (или задайте ключи в корневом `.env`). Основные переменные:

| Ключ | Назначение |
|------|------------|
| `OLLAMA_FRAMEWORK_TRANSPORT` | `local` (ModuleBridge) или `http` (REST ollama_framework) |
| `OLLAMA_BASE_URL` | URL Ollama на сервере (клиент **не** может переопределить) |
| `OLLAMA_DEFAULT_MODEL` / `OLLAMA_EMBEDDINGS_MODEL` | модели chat / embeddings (embeddings — имя библиотеки Ollama, не `org/name` с Hugging Face) |
| `AI_ASSISTANT_CONCURRENCY_LIMIT` | лимит одновременных LLM-запросов в API (+ индексация Celery) |
| `AI_ASSISTANT_OLLAMA_COMPUTE_DEVICE` | `gpu` / `cpu` (опционально) |
| `RAG_SYSTEM_CORPUS_ENABLED` | индекс пользовательской справки (меню, UI, guides) |
| `RAG_SYSTEM_CORPUS_BEAT_ENABLED` | ежедневный sync корпуса через Celery Beat (по умолчанию `true`) |

## Пользовательский корпус RAG

Источники: боковое меню, каталог модулей (`user_description` + права), ru-подписи UI, guides в `api/rag/system_corpus/guides/` и hook `modules/*/api/user_guides/*.md`.

После смены меню или модулей: `ergoms ai_assistant:sync-knowledge` (сразу) или дождаться ночного Beat / следующего setup-full. Нужны `ergoms start-worker` и `ergoms start-beat` для фонового расписания.

Другие модули могут добавить пользовательские шпаргалки в свой `api/user_guides/*.md` и строку `user_description` в `PERMISSION_CATALOG`.

## Chat-профили (расширение другими модулями)

Хост-модуль может переиспользовать хаб и мини-чат без копирования Vue:

1. Сервер: `bridge.provide_many('ai_assistant.chat.profiles', key, { id, ask_stream_op, session_module, mini_chat_module, permission_module?, permission? })` и op `ask_stream` (`user`, `message`, `history`, `stream_callback` → `{ success, response, sources }`).
2. Клиент: `bridge.provideMany('ai_assistant.chat.profiles', id, { title, welcomeMessage, suggestions, permissionModule, permission, features, hubQuery, … })`.
3. Открытие: `bridge.call('ai_assistant.mini_chat.open', profileId)` или маршрут `/ai-assistant?profile=<id>`. Профили без права пользователя не показываются.
4. Stream UI ходит только в `POST /api/ai_assistant/chat/profiles/<id>/stream/` (прокси проверяет `permission_module`/`permission` хоста); сессии — `ChatSession` ассистента.

Доменный KAG / свои эмбеддинги остаются в хост-модуле.

## Права ADP

Назначаются ролевым группам в админке (модульные права):

| Ключ | Назначение |
|---|---|
| `ai_assistant_view` | Страница хаба `/ai-assistant` |
| `ai_assistant_mini_chat` | Пункт «AI ассистент» в меню приложений и плавающий мини-чат. Без права виджет скрыт |

Глобальный администратор имеет все права. Мини-чат не входит в базовый `_view`: его выдают отдельным правом группе роли.

## Безопасность (кратко)

- `ollama_config` из клиента проходит whitelist в `api/ollama_gateway.map_ollama_config` — без `base_url` и compute-полей с клиента
- Для RAG/embeddings всегда используется `OLLAMA_EMBEDDINGS_MODEL`, а не chat-модель из запроса
- Статус для UI — только `GET /api/ai_assistant/ollama_status/`, не REST чужого модуля
- Файлы — media_api; bridge `document.parse` принимает только пути под `ai_assistant/` и требует `user`
- Идентификаторы сущностей — UUID

## Команды

```bash
ergoms ai_assistant:sync-knowledge
ergoms ai_assistant:install-pgvector
ergoms ai_assistant:ensure-pgvector
```

При `ergoms setup` / Setup Full System: `install-pgvector` идёт до миграций (`include_in: setup-full`) и каждый раз проверяет расширение `vector` в схеме `core` (в `search_path` Django нет `public`). Повторный запуск не пропускает этот шаг, даже если файлы уже лежат в portable PostgreSQL. `sync-knowledge --sync` — после миграций (`include_in: setup-full-after-migrate`). Нужны Ollama и модель embeddings (их ставит `ollama_framework:pull-setup-models` в том же setup-full).

## Куда смотреть в коде

| Область | Путь |
|---------|------|
| Gateway к Ollama | `api/ollama_gateway.py` |
| ModuleBridge наружу | `api/integrations.py` |
| Chat / stream | `api/views/chat.py`, `chat_stream.py` |
| RAG | `api/rag/` |
| Корпус / guides | `api/rag/system_corpus/`, `api/user_guides/` |
| Beat sync | `api/celery_beat_config.py`, `api/tasks.py` |
| Клиентские маршруты | `client/js/routes.js` |
| Тема модуля | `client/js/theme-defaults.js` |
