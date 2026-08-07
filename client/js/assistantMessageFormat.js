import { sanitizeHtml } from '@/js/utils/sanitize'
import { logError } from '@/js/utils/logError.js'
import { apiClient } from '@/js/api/manager'
import { tGlobal, getCurrentBcp47 } from '@/i18n/index.js'

function escapeHtml(text) {
  if (!text) return ''
  const div = document.createElement('div')
  div.textContent = String(text)
  return div.innerHTML
}

export function parseMarkdownTable(markdownTable) {
  try {
    const lines = markdownTable.trim().split('\n').map((line) => line.trim()).filter(Boolean)
    if (lines.length < 2) return markdownTable

    let separatorIndex = -1
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].match(/^\|[\s\-:|]+\|$/)) {
        separatorIndex = i
        break
      }
    }
    if (separatorIndex === -1) return markdownTable

    const headerLine = lines[0]
    if (!headerLine.startsWith('|') || !headerLine.endsWith('|')) return markdownTable

    const headers = headerLine
      .split('|')
      .map((cell) => cell.trim())
      .filter((_, index, arr) => index > 0 && index < arr.length - 1)

    if (headers.length === 0) return markdownTable

    const rows = lines
      .slice(separatorIndex + 1)
      .filter((line) => line.startsWith('|') && line.endsWith('|'))
      .map((line) =>
        line
          .split('|')
          .map((cell) => cell.trim())
          .filter((_, index, arr) => index > 0 && index < arr.length - 1),
      )
      .filter((row) => row.length > 0)

    let html = '<div class="markdown-table-wrapper"><table class="markdown-table"><thead><tr>'
    headers.forEach((header) => {
      html += `<th>${escapeHtml(header)}</th>`
    })
    html += '</tr></thead>'

    if (rows.length > 0) {
      html += '<tbody>'
      rows.forEach((row) => {
        html += '<tr>'
        headers.forEach((_, index) => {
          html += `<td>${escapeHtml(row[index] || '')}</td>`
        })
        html += '</tr>'
      })
      html += '</tbody>'
    }

    html += '</table></div>'
    return html
  } catch (error) {
    logError('Ошибка парсинга markdown-таблицы', error)
    return markdownTable
  }
}

/**
 * Fenced code blocks ```lang\n...\n``` — до inline `code`, иначе остаются лишние backticks.
 */
function extractFencedCodeBlocks(text) {
  const blocks = []
  let index = 0
  const replaced = text.replace(/```([^\n`]*)\n?([\s\S]*?)```/g, (_match, langRaw, code) => {
    const lang = String(langRaw || '').trim()
    const id = `code-block-${index++}`
    const langClass = lang ? ` language-${escapeHtml(lang)}` : ''
    const langAttr = lang ? ` data-lang="${escapeHtml(lang)}"` : ''
    const codeBody = String(code || '').replace(/^\n+/, '').replace(/\n+$/, '')
    blocks.push({
      id,
      html:
        `<pre class="markdown-code-block"${langAttr}>` +
        `<code class="markdown-code${langClass}">${escapeHtml(codeBody)}</code>` +
        `</pre>`,
    })
    return `\n__CODE_PLACEHOLDER_${id}__\n`
  })
  return { text: replaced, blocks }
}

function extractThinkBlocks(text, thinkingLabel) {
  const blocks = []
  let index = 0
  const thinkRegex = /<think>([\s\S]*?)<\/think>/gi
  const replaced = text.replace(thinkRegex, (_match, thinkContent) => {
    const id = `think-block-${index++}`
    blocks.push({
      id,
      html:
        `<div class="think-block">` +
        `<div class="think-block__header">${escapeHtml(thinkingLabel)}</div>` +
        `<div class="think-block__content">${escapeHtml(String(thinkContent || '').trim())}</div>` +
        `</div>`,
    })
    return `__THINK_PLACEHOLDER_${id}__`
  })
  return { text: replaced, blocks }
}

export function formatMessageContent(content, options = {}) {
  if (!content) return ''

  const thinkingLabel =
    options.thinkingLabel || tGlobal('ai_assistant.message.thinking')

  let text = String(content)

  const { text: afterCode, blocks: codeBlocks } = extractFencedCodeBlocks(text)
  text = afterCode

  const { text: afterThink, blocks: thinkBlocks } = extractThinkBlocks(text, thinkingLabel)
  text = afterThink

  const tableRegex = /((?:\|[^\n]+\|\s*\n)+)/g
  const tables = []
  let tableIndex = 0

  text = text.replace(tableRegex, (match) => {
    const hasSeparator = /\|[\s\-:]+\|/.test(match)
    if (!hasSeparator) return match
    const lines = match.split('\n').filter((l) => l.trim().startsWith('|'))
    if (lines.length < 2) return match

    const tableId = `markdown-table-${tableIndex++}`
    const htmlTable = parseMarkdownTable(match)
    if (htmlTable === match) return match
    tables.push({ id: tableId, html: htmlTable })
    return `\n\n__TABLE_PLACEHOLDER_${tableId}__\n\n`
  })

  text = text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`\n]+)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, linkText, url) => {
      if (url.includes('/api/ai_assistant/documents/download/')) {
        return `<a href="#" class="download-link" data-download-url="${url}" data-filename="${linkText}">${linkText}</a>`
      }
      return `<a href="${url}" target="_blank" rel="noopener noreferrer">${linkText}</a>`
    })

  codeBlocks.forEach((block) => {
    text = text.replace(`__CODE_PLACEHOLDER_${block.id}__`, block.html)
  })
  thinkBlocks.forEach((block) => {
    text = text.replace(`__THINK_PLACEHOLDER_${block.id}__`, block.html)
  })
  tables.forEach((table) => {
    text = text.replace(`__TABLE_PLACEHOLDER_${table.id}__`, table.html)
  })

  // Убираем лишние пустые строки — иначе вокруг кода появляются «дыры»
  text = text.replace(/\n{3,}/g, '\n\n')

  // Не ломаем переносы внутри block-элементов
  text = text.replace(
    /(<(?:pre|div|table)[\s\S]*?<\/(?:pre|div|table)>)|([^<]+)|(<[^>]+>)/g,
    (match, block, plain, tag) => {
      if (block) return block
      if (tag) return tag
      return plain.replace(/\n/g, '<br>')
    },
  )

  // Схлопываем br вокруг блоков и серии br
  text = text
    .replace(/(?:<br>\s*)+(<(?:pre|div|table)\b)/gi, '$1')
    .replace(/(<\/(?:pre|div|table)>)(?:\s*<br>)+/gi, '$1')
    .replace(/(?:<br>\s*){3,}/g, '<br><br>')

  return sanitizeHtml(text)
}

export function formatProcessingTime(ms) {
  if (!ms && ms !== 0) return ''
  const locale = getCurrentBcp47()
  if (ms < 1000) {
    return tGlobal('ai_assistant.message.durationMs', { ms: Math.round(ms) })
  }
  const sec = (ms / 1000).toLocaleString(locale, {
    minimumFractionDigits: ms % 1000 === 0 ? 0 : 1,
    maximumFractionDigits: 1,
  })
  return tGlobal('ai_assistant.message.durationSec', { sec })
}

export function formatCell(value) {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'number') {
    return Number.isInteger(value) ? value : value.toFixed(2)
  }
  const str = String(value)
  return str.length > 50 ? `${str.slice(0, 47)}...` : str
}

export function formatMessageTime(timestamp) {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString(getCurrentBcp47(), { hour: '2-digit', minute: '2-digit' })
}

export async function handleDocumentDownloadClick(event) {
  const link = event.target.closest('.download-link')
  if (!link) return

  event.preventDefault()
  event.stopPropagation()

  const downloadUrl = link.getAttribute('data-download-url')
  const filename = link.getAttribute('data-filename') || 'document.docx'
  if (!downloadUrl) return

  try {
    let endpoint
    if (downloadUrl.startsWith('http://') || downloadUrl.startsWith('https://')) {
      const url = new URL(downloadUrl)
      endpoint = url.pathname.replace('/api/', '')
    } else {
      endpoint = downloadUrl.startsWith('/api/')
        ? downloadUrl.replace('/api/', '')
        : downloadUrl
    }

    const response = await apiClient.downloadFile(endpoint, {}, 'GET', true)
    if (response.success && response.data instanceof Blob) {
      const blobUrl = URL.createObjectURL(response.data)
      const a = document.createElement('a')
      a.href = blobUrl
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(blobUrl)
    } else {
      logError('Ошибка скачивания файла', response.message)
    }
  } catch (error) {
    logError('Ошибка при скачивании документа', error)
  }
}
