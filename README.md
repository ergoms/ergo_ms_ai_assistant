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
| `OLLAMA_DEFAULT_MODEL` / `OLLAMA_EMBEDDINGS_MODEL` | модели chat / embeddings |
| `AI_ASSISTANT_CONCURRENCY_LIMIT` | лимит одновременных LLM-запросов в API (+ индексация Celery) |
| `AI_ASSISTANT_OLLAMA_COMPUTE_DEVICE` | `gpu` / `cpu` (опционально) |

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

## Куда смотреть в коде

| Область | Путь |
|---------|------|
| Gateway к Ollama | `api/ollama_gateway.py` |
| ModuleBridge наружу | `api/integrations.py` |
| Chat / stream | `api/views/chat.py`, `chat_stream.py` |
| RAG | `api/rag/` |
| Клиентские маршруты | `client/js/routes.js` |
| Тема модуля | `client/js/theme-defaults.js` |
