import { sanitizeHtml } from '@/js/utils/sanitize'
import { logError } from '@/js/utils/logError.js'
import { apiClient } from '@/js/api/manager'

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

export function formatMessageContent(content) {
  if (!content) return ''

  let text = content
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
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, linkText, url) => {
      if (url.includes('/api/ai_assistant/documents/download/')) {
        return `<a href="#" class="download-link" data-download-url="${url}" data-filename="${linkText}">${linkText}</a>`
      }
      return `<a href="${url}" target="_blank" rel="noopener noreferrer">${linkText}</a>`
    })

  tables.forEach((table) => {
    text = text.replace(`__TABLE_PLACEHOLDER_${table.id}__`, table.html)
  })

  text = text.replace(/\n/g, '<br>')
  return sanitizeHtml(text)
}

export function formatProcessingTime(ms) {
  if (!ms) return ''
  if (ms < 1000) return `${ms} мс`
  return `${(ms / 1000).toFixed(1)} с`
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
  return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
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
