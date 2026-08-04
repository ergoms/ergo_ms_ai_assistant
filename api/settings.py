"""
Настройки модуля AI Assistant.

Единственный источник истины для RAG, Ollama embeddings и таймаутов модуля.
"""
from src.config.env import env

# ============================================================================
# Ollama
# ============================================================================

OLLAMA_BASE_URL = env.str('OLLAMA_BASE_URL', default='http://127.0.0.1:11434')
OLLAMA_DEFAULT_MODEL = env.str('OLLAMA_DEFAULT_MODEL', default='mistral:latest')
OLLAMA_EMBEDDINGS_MODEL = env.str('OLLAMA_EMBEDDINGS_MODEL', default='embeddinggemma')

# Транспорт ollama_framework: local (ModuleBridge) или http (REST API)
OLLAMA_FRAMEWORK_TRANSPORT = env.str('OLLAMA_FRAMEWORK_TRANSPORT', default='local')
OLLAMA_FRAMEWORK_API_BASE = env.str('OLLAMA_FRAMEWORK_API_BASE', default='')

# ============================================================================
# LLM (AI Assistant)
# ============================================================================

AI_ASSISTANT_REQUEST_TIMEOUT = env.float('AI_ASSISTANT_REQUEST_TIMEOUT', default=180.0)
AI_ASSISTANT_STREAM_TIMEOUT = env.float('AI_ASSISTANT_STREAM_TIMEOUT', default=300.0)
AI_ASSISTANT_SQL_TOKENS = env.int('AI_ASSISTANT_SQL_TOKENS', default=256)
AI_ASSISTANT_COMMENTARY_TOKENS = env.int('AI_ASSISTANT_COMMENTARY_TOKENS', default=192)
AI_ASSISTANT_TEMPERATURE_SQL = env.float('AI_ASSISTANT_TEMPERATURE_SQL', default=0.08)
AI_ASSISTANT_TEMPERATURE_COMMENTARY = env.float('AI_ASSISTANT_TEMPERATURE_COMMENTARY', default=0.24)
AI_ASSISTANT_CONCURRENCY_LIMIT = env.int('AI_ASSISTANT_CONCURRENCY_LIMIT', default=8)
AI_ASSISTANT_MAX_RETRIES = env.int('AI_ASSISTANT_MAX_RETRIES', default=2)
AI_ASSISTANT_KEEP_ALIVE = env.str('AI_ASSISTANT_KEEP_ALIVE', default='10m')

# ============================================================================
# RAG
# ============================================================================

RAG_ENABLED = env.bool('RAG_ENABLED', default=True)
RAG_CHUNK_SIZE = env.int('RAG_CHUNK_SIZE', default=1000)
RAG_CHUNK_OVERLAP = env.int('RAG_CHUNK_OVERLAP', default=200)
RAG_TOP_K = env.int('RAG_TOP_K', default=8)
RAG_SIMILARITY_THRESHOLD = env.float('RAG_SIMILARITY_THRESHOLD', default=0.25)
RAG_MAX_CONTEXT_LENGTH = env.int('RAG_MAX_CONTEXT_LENGTH', default=6000)

# Системный корпус (.docs, rules) — индексация и подмешивание в chat
RAG_SYSTEM_CORPUS_ENABLED = env.bool('RAG_SYSTEM_CORPUS_ENABLED', default=True)
RAG_INCLUDE_SYSTEM_IN_CHAT = env.bool('RAG_INCLUDE_SYSTEM_IN_CHAT', default=True)
RAG_SYSTEM_CORPUS_MAX_FILE_BYTES = env.int('RAG_SYSTEM_CORPUS_MAX_FILE_BYTES', default=1_000_000)
