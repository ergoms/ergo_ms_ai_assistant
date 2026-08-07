"""
Настройки модуля AI Assistant.

Единственный источник истины для RAG, Ollama embeddings и таймаутов модуля.
"""
from src.config.env import env


def _normalize_compute_device(value: str) -> str:
    normalized = (value or '').strip().lower()
    if normalized in ('auto', 'gpu', 'cpu'):
        return normalized
    return ''


# ============================================================================
# Ollama
# ============================================================================

OLLAMA_BASE_URL = env.str('OLLAMA_BASE_URL', default='http://127.0.0.1:11434')
OLLAMA_DEFAULT_MODEL = env.str('OLLAMA_DEFAULT_MODEL', default='mistral:latest')
OLLAMA_EMBEDDINGS_MODEL = env.str('OLLAMA_EMBEDDINGS_MODEL', default='embeddinggemma')

# Транспорт ollama_framework: local (ModuleBridge) или http (REST API)
OLLAMA_FRAMEWORK_TRANSPORT = env.str('OLLAMA_FRAMEWORK_TRANSPORT', default='local')
OLLAMA_FRAMEWORK_API_BASE = env.str('OLLAMA_FRAMEWORK_API_BASE', default='')

# gpu / cpu — переопределяет OLLAMA_COMPUTE_DEVICE ollama_framework для этого модуля.
# Пусто — наследовать глобальную настройку ollama_framework.
AI_ASSISTANT_OLLAMA_COMPUTE_DEVICE = _normalize_compute_device(
    env.str('AI_ASSISTANT_OLLAMA_COMPUTE_DEVICE', default=''),
)

# ============================================================================
# LLM (AI Assistant)
# ============================================================================

AI_ASSISTANT_REQUEST_TIMEOUT = env.float('AI_ASSISTANT_REQUEST_TIMEOUT', default=180.0)
AI_ASSISTANT_STREAM_TIMEOUT = env.float('AI_ASSISTANT_STREAM_TIMEOUT', default=300.0)
AI_ASSISTANT_SQL_TOKENS = env.int('AI_ASSISTANT_SQL_TOKENS', default=256)
AI_ASSISTANT_COMMENTARY_TOKENS = env.int('AI_ASSISTANT_COMMENTARY_TOKENS', default=192)
AI_ASSISTANT_TEMPERATURE_SQL = env.float('AI_ASSISTANT_TEMPERATURE_SQL', default=0.08)
AI_ASSISTANT_TEMPERATURE_COMMENTARY = env.float('AI_ASSISTANT_TEMPERATURE_COMMENTARY', default=0.24)
# Одновременные chat/embed в процессе API (семафор в ollama_gateway + пул httpx).
AI_ASSISTANT_CONCURRENCY_LIMIT = max(1, env.int('AI_ASSISTANT_CONCURRENCY_LIMIT', default=2))
AI_ASSISTANT_MAX_RETRIES = max(0, env.int('AI_ASSISTANT_MAX_RETRIES', default=2))
AI_ASSISTANT_KEEP_ALIVE = env.str('AI_ASSISTANT_KEEP_ALIVE', default='10m')

# ============================================================================
# RAG
# ============================================================================

RAG_ENABLED = env.bool('RAG_ENABLED', default=True)
# Размер chunk для chonkie RecursiveChunker/TableChunker (tokenizer='character').
RAG_CHUNK_SIZE = env.int('RAG_CHUNK_SIZE', default=1000)
# Overlap через OverlapRefinery (символы при tokenizer=character).
RAG_CHUNK_OVERLAP = env.int('RAG_CHUNK_OVERLAP', default=200)
# Лимиты vision-вложений в чате (байты исходного файла после localize).
AI_ASSISTANT_MAX_CHAT_IMAGES = env.int('AI_ASSISTANT_MAX_CHAT_IMAGES', default=4)
AI_ASSISTANT_MAX_IMAGE_BYTES = env.int('AI_ASSISTANT_MAX_IMAGE_BYTES', default=10 * 1024 * 1024)
RAG_TOP_K = env.int('RAG_TOP_K', default=8)
RAG_SIMILARITY_THRESHOLD = env.float('RAG_SIMILARITY_THRESHOLD', default=0.25)
RAG_MAX_CONTEXT_LENGTH = env.int('RAG_MAX_CONTEXT_LENGTH', default=6000)
RAG_EMBEDDING_DIMENSIONS = env.int('RAG_EMBEDDING_DIMENSIONS', default=768)

# Системный корпус (.docs, rules) — индексация и подмешивание в chat
RAG_SYSTEM_CORPUS_ENABLED = env.bool('RAG_SYSTEM_CORPUS_ENABLED', default=True)
RAG_INCLUDE_SYSTEM_IN_CHAT = env.bool('RAG_INCLUDE_SYSTEM_IN_CHAT', default=True)
RAG_SYSTEM_CORPUS_MAX_FILE_BYTES = env.int('RAG_SYSTEM_CORPUS_MAX_FILE_BYTES', default=1_000_000)
