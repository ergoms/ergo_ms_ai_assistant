# ai_assistant

Доменный модуль AI-хаба ERGO MS: чат, RAG по документам, skills. Вызовы LLM идут только через модуль `ollama_framework` (ModuleBridge), без прямого доступа к `:11434`.

## Документация

- Агент: [`AGENTS.md`](AGENTS.md), [`.cursor/rules/ai-assistant.mdc`](.cursor/rules/ai-assistant.mdc)
- Клиентский обзор: [`client/README.md`](client/README.md)
- Справка CLI: [`ergoms.help.yaml`](ergoms.help.yaml)

## Зависимости

В [`integrations.yaml`](integrations.yaml) указано `requires: ollama_framework`. Без установленного и запущенного Ollama чат и embeddings недоступны.

Для векторного поиска нужны pgvector (`ergoms ai_assistant:install-pgvector` / `ensure-pgvector`). Модель embeddings — из `OLLAMA_EMBEDDINGS_MODEL`: имя библиотеки Ollama ставит `ergoms ollama_framework:pull-setup-models`, снимок Hugging Face (`deepvk/USER-bge-m3`) — [`huggingface_models.yaml`](huggingface_models.yaml) и `ergoms pull-huggingface-models --include-optional`.

## Настройка

Скопируйте [`modules/ai_assistant/.env.example`](.env.example) в `modules/ai_assistant/.env` (или задайте ключи в корневом `.env`). Основные переменные:

| Ключ | Назначение |
|------|------------|
| `OLLAMA_FRAMEWORK_TRANSPORT` | `local` (ModuleBridge) или `http` (REST ollama_framework) |
| `OLLAMA_BASE_URL` | URL Ollama на сервере (клиент **не** может переопределить) |
| `OLLAMA_DEFAULT_MODEL` / `OLLAMA_EMBEDDINGS_MODEL` | модели chat / embeddings. Embeddings — имя библиотеки Ollama или снимок Hugging Face `org/name` |
| `AI_ASSISTANT_CONCURRENCY_LIMIT` | лимит одновременных LLM-запросов в API (+ индексация Celery) |
| `AI_ASSISTANT_OLLAMA_COMPUTE_DEVICE` | `gpu` / `cpu` (опционально) |
| `RAG_SYSTEM_CORPUS_ENABLED` | индекс пользовательской справки (меню, UI, guides) |
| `RAG_SYSTEM_CORPUS_BEAT_ENABLED` | ежедневный sync корпуса через Celery Beat (по умолчанию `true`) |

## Пользовательский корпус RAG

Источники: боковое меню и каталог модулей (`user_description`), опубликованные пакеты `knowledge/` в media_api. В пакет ядро кладёт `user_guides`, `user_description` и автоматически собранный каталог экранов (маршруты, поля форм, кнопки). Ассистент не обходит чужие `modules/` и `core/` на диске: пакет читается с местного media или по подписанному URL владельца. Чанки пакетов при ответе режутся по правам ADP и по метке `audience` (`user` / `admin`): обычному пользователю админские гайды и полная карта меню не подмешиваются.

Если модель называет кнопку или поле, которых нет в справке, ответ заменяется отказом (`api/safety/grounding.py`). Проверка каталога без живой модели: `ergoms ai_assistant:howto-eval`; с Ollama добавьте `--ask`.

После смены меню или пакетов: `ergoms ai_assistant:sync-knowledge` (сразу) или дождаться ночного Beat / следующего setup-full. Нужны worker и Beat модуля: `ergoms start-worker --module=ai_assistant` и `ergoms start-beat --module=ai_assistant` (в монолите достаточно общих `start-worker` / `start-beat`).

Другие модули могут добавить `user_description` и необязательные `api/user_guides/*.md` для сценариев, которых нет в разметке. Экраны и поля подхватывает `ergoms publish-knowledge-packs` сам.

## Chat-профили (расширение другими модулями)

Хост-модуль может переиспользовать хаб и мини-чат без копирования Vue:

1. Сервер: `bridge.provide_many('ai_assistant.chat.profiles', key, { id, ask_stream_op, session_module, mini_chat_module, permission_module?, permission? })` и op `ask_stream` (`user`, `message`, `history`, `stream_callback` → `{ success, response, sources }`).
2. Клиент: `bridge.provideMany('ai_assistant.chat.profiles', id, { title, welcomeMessage, suggestions, permissionModule, permission, features, hubQuery, … })`.
3. Открытие: `bridge.call('ai_assistant.mini_chat.open', profileId)` или маршрут `/ai-assistant?profile=<id>`. Профили без права пользователя не показываются.
4. Stream UI ходит только в `POST /api/ai_assistant/chat/profiles/<id>/stream/` (прокси проверяет `permission_module`/`permission` хоста); сессии — `ChatSession` ассистента.
5. Сессии мини-чата пишутся с `module=mini_chat` (или `mini_chat_module` профиля) и не попадают в список хаба. Кнопка «Сохранить чат» в шапке виджета вызывает `POST /api/ai_assistant/chat_sessions/<id>/save/` и переносит сессию в хаб.

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
- Для RAG/embeddings всегда используется `OLLAMA_EMBEDDINGS_MODEL`, а не chat-модель из запроса. Снимок `org/name` идёт в sentence-transformers, не в `/api/embed`
- Статус для UI — только `GET /api/ai_assistant/ollama_status/`, не REST чужого модуля
- Файлы — media_api; bridge `document.parse` принимает только пути под `ai_assistant/` и требует `user`
- Идентификаторы сущностей — UUID; владелец сессий, документов и задач LLM — `user_public_id`, без FK на пользователя ядра (`api/schema.yaml` `isolated: true`)
- Роль для промпта и корпуса — только `PermissionService.is_admin` на сервере. Вход режет jailbreak и явные админ-инструкции, выход проверяется до сохранения ответа (`api/safety/policy.py`)

## Команды

```bash
ergoms ai_assistant:sync-knowledge
ergoms ai_assistant:howto-eval
ergoms ai_assistant:howto-eval --ask
ergoms ai_assistant:install-pgvector
ergoms ai_assistant:ensure-pgvector
```

При `ergoms setup` / Setup Full System: `install-pgvector` идёт до миграций (`include_in: setup-full`) и каждый раз проверяет расширение `vector` в схеме `core` (в `search_path` Django нет `public`). Повторный запуск не пропускает этот шаг, даже если файлы уже лежат в portable PostgreSQL. После миграций сначала публикуется пакет модуля (`ergoms publish-knowledge-packs --module=ai_assistant`), затем `sync-knowledge --sync`. Для chat нужна Ollama. Для embeddings — либо модель из `ollama_models.yaml` (`pull-setup-models`), либо снимок из `huggingface_models.yaml`, если в `OLLAMA_EMBEDDINGS_MODEL` указан `org/name`.

## Куда смотреть в коде

| Область | Путь |
|---------|------|
| Gateway к Ollama | `api/ollama_gateway.py` |
| ModuleBridge наружу | `api/integrations.py` |
| Chat / stream | `api/views/chat.py`, `chat_stream.py` |
| Промпты и роль | `api/rag/prompts.py`, `api/assistant_role.py` |
| Защита выдачи | `api/safety/policy.py` |
| RAG | `api/rag/` |
| Корпус / guides | `api/rag/system_corpus/`, `api/user_guides/` |
| Beat sync | `api/celery_beat_config.py`, `api/tasks.py` |
| Клиентские маршруты | `client/js/routes.js` |
| Тема модуля | `client/js/theme-defaults.js` |
