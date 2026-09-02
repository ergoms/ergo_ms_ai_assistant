/**
 * Основные API-пути модуля ai_assistant.
 * Эталон для клиентских клиентов (rag-client, docs-client и др.).
 */
export const endpoints = {
  chat: 'ai_assistant/chat/',
  chatStream: 'ai_assistant/chat/stream/',
  profileChatStream: (profileId) => `ai_assistant/chat/profiles/${profileId}/stream/`,
  ollamaStatus: 'ai_assistant/ollama_status/',
  embeddingsStatus: 'ai_assistant/embeddings_status/',
  chatSessions: 'ai_assistant/chat_sessions/',
  chatSessionDetail: (id) => `ai_assistant/chat_sessions/${id}/`,
  chatSessionSave: (id) => `ai_assistant/chat_sessions/${id}/save/`,
  knowledgeDocuments: 'ai_assistant/knowledge_documents/',
  knowledgeDocumentDetail: (id) => `ai_assistant/knowledge_documents/${id}/`,
  knowledgeDocumentIndex: (id) => `ai_assistant/knowledge_documents/${id}/index/`,
  knowledgeDocumentIndexStatus: (id) => `ai_assistant/knowledge_documents/${id}/index_status/`,
  knowledgeDocumentUnindex: (id) => `ai_assistant/knowledge_documents/${id}/unindex/`,
  knowledgeDocumentDownload: (id) => `ai_assistant/knowledge_documents/${id}/download/`,
  generatedDocumentDownload: (filePath) => `ai_assistant/documents/download/${filePath}`,
}

export default endpoints
