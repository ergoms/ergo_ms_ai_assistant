/**
 * Единый формат отображения имени модели Ollama в UI.
 */
export function formatOllamaModelLabel(model) {
  if (model == null || typeof model !== 'string') {
    return ''
  }
  const trimmed = model.trim()
  if (!trimmed) {
    return ''
  }
  const colon = trimmed.indexOf(':')
  if (colon === -1) {
    return trimmed.toLowerCase()
  }
  const name = trimmed.slice(0, colon).toLowerCase()
  const tag = trimmed.slice(colon + 1).toLowerCase()
  return tag ? `${name}:${tag}` : name
}
