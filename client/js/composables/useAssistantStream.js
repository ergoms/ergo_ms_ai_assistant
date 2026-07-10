import { ref } from 'vue'

let localMessageId = 1

export function nextLocalMessageId() {
  return localMessageId++
}

export function resetLocalMessageIds(start = 1) {
  localMessageId = start
}

/**
 * Преобразует сообщения API в формат UI HubMessage.
 */
export function mapApiMessages(messages) {
  return (messages || []).map((msg) => ({
    id: msg.id,
    type: msg.type || msg.message_type,
    content: msg.content,
    timestamp: msg.created_at ? new Date(msg.created_at) : new Date(),
    processing_time_ms: msg.processing_time_ms,
    request_started_at: msg.request_started_at,
    response_received_at: msg.response_received_at,
    skill_name: msg.metadata?.skill_name || null,
    skill_call: msg.metadata?.skill_call || null,
    chart_config: msg.metadata?.chart_config || null,
    sql: msg.metadata?.sql || msg.sql || null,
    data: msg.metadata?.data || msg.data || null,
    metadata: msg.metadata || {},
  }))
}

/**
 * Composable для локальной истории сообщений с поддержкой streaming.
 */
export function useMessageHistory() {
  const messages = ref([])
  let streamingMsgId = null

  function clearMessages() {
    messages.value = []
    streamingMsgId = null
  }

  function setMessages(list) {
    messages.value = list
    streamingMsgId = null
  }

  function addUserMessage(content) {
    const msg = {
      id: nextLocalMessageId(),
      type: 'user',
      content,
      timestamp: new Date(),
    }
    messages.value.push(msg)
    return msg
  }

  function startAssistantStream() {
    streamingMsgId = nextLocalMessageId()
    const msg = {
      id: streamingMsgId,
      type: 'assistant',
      content: '',
      timestamp: new Date(),
      streaming: true,
    }
    messages.value.push(msg)
    return msg
  }

  function appendStreamChunk(chunk) {
    if (!streamingMsgId) {
      startAssistantStream()
    }
    const msg = messages.value.find((m) => m.id === streamingMsgId)
    if (msg) {
      msg.content += chunk
    }
  }

  function finishAssistantStream(fullResponse, metadata = {}) {
    let msg = streamingMsgId
      ? messages.value.find((m) => m.id === streamingMsgId)
      : null

    if (!msg && fullResponse) {
      msg = {
        id: nextLocalMessageId(),
        type: 'assistant',
        content: fullResponse,
        timestamp: new Date(),
      }
      messages.value.push(msg)
    }

    if (msg) {
      if (fullResponse) msg.content = fullResponse
      msg.streaming = false
      if (metadata.processing_time_ms) msg.processing_time_ms = metadata.processing_time_ms
      if (metadata.timestamp) msg.timestamp = new Date(metadata.timestamp)
      if (metadata.skill_name) msg.skill_name = metadata.skill_name
      if (metadata.skill_call) msg.skill_call = metadata.skill_call
      if (metadata.chart_config) msg.chart_config = metadata.chart_config
      msg.metadata = metadata
    }

    streamingMsgId = null
    return msg
  }

  function setAssistantError(errorMsg) {
    if (streamingMsgId) {
      const msg = messages.value.find((m) => m.id === streamingMsgId)
      if (msg) {
        msg.content = `Ошибка: ${errorMsg}`
        msg.streaming = false
        streamingMsgId = null
        return
      }
    }
    messages.value.push({
      id: nextLocalMessageId(),
      type: 'assistant',
      content: `Ошибка: ${errorMsg}`,
      timestamp: new Date(),
    })
    streamingMsgId = null
  }

  return {
    messages,
    clearMessages,
    setMessages,
    addUserMessage,
    startAssistantStream,
    appendStreamChunk,
    finishAssistantStream,
    setAssistantError,
  }
}
