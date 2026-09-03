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

const NAMED_ENTITIES = {
  nbsp: ' ',
  ensp: ' ',
  emsp: ' ',
  thinsp: ' ',
  amp: '&',
  lt: '<',
  gt: '>',
  quot: '"',
  apos: "'",
  mdash: '—',
  ndash: '–',
  hellip: '…',
  laquo: '«',
  raquo: '»',
}

/** Модель часто копирует HTML-отступы (&nbsp;) — в разметке они должны стать пробелами. */
export function decodeHtmlEntities(text) {
  let value = String(text || '')
  for (let step = 0; step < 2; step += 1) {
    const next = value.replace(/&(#x[0-9a-f]+|#\d+|[a-z][a-z0-9]*);/gi, (match, body) => {
      const token = String(body)
      if (token.startsWith('#')) {
        const code = token[1] === 'x' || token[1] === 'X'
          ? Number.parseInt(token.slice(2), 16)
          : Number.parseInt(token.slice(1), 10)
        if (!Number.isFinite(code) || code < 1 || code > 0x10ffff) return match
        try {
          const char = String.fromCodePoint(code)
          return char === '\u00a0' ? ' ' : char
        } catch {
          return match
        }
      }
      const named = NAMED_ENTITIES[token.toLowerCase()]
      return named === undefined ? match : named
    })
    if (next === value) break
    value = next
  }
  return value
}

const BR_TAG_RE = /<\s*br\b[^>]*>/gi
const BR_ENTITY_RE = /&lt;\s*br\b[^>]*&gt;/gi
const UNORDERED_LINE_RE = /^(?:[-*•]|—)\s+/
const ORDERED_LINE_RE = /^\d+\.\s+/
const BULLET_LINE_RE = /^(?:[-*•]|—|\d+\.)\s+/
const PLACEHOLDER_RE = /^%%MD_(?:CODE|THINK|TABLE)_[A-Za-z0-9-]+%%$/
const BLOCK_OPEN_RE = '(?:pre|div|table|blockquote|ul|ol|h[1-6]|hr)'
const BLOCK_CLOSE_RE = '(?:pre|div|table|blockquote|ul|ol|h[1-6])'

function applyInlineMarkdown(text) {
  return String(text || '')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/__(.+?)__/g, '<strong>$1</strong>')
    .replace(/~~(.*?)~~/g, '<del>$1</del>')
    .replace(/`([^`\n]+)`/g, '<code>$1</code>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/(?<![\w*])_(?!_)(.+?)(?<!_)_(?![\w*])/g, '<em>$1</em>')
}

/** Жирный, курсив, код и переносы внутри уже извлечённого фрагмента. */
function formatInlineMarkdown(raw) {
  let text = String(raw || '')
  text = text.replace(BR_TAG_RE, '\n').replace(BR_ENTITY_RE, '\n')
  return applyInlineMarkdown(escapeHtml(text)).replace(/\n+/g, '<br>')
}

function isHorizontalRule(line) {
  const trimmed = String(line || '').trim()
  return /^(?:-{3,}|\*{3,}|_{3,})$/.test(trimmed)
}

function consumePrefixedLines(lines, start, test) {
  const items = []
  let index = start
  while (index < lines.length && test(lines[index].trim())) {
    items.push(lines[index].trim())
    index += 1
  }
  return { items, next: index }
}

/** Заголовки, линейки, цитаты и списки — то, что модель пишет вне таблиц. */
function formatBlockMarkdown(text) {
  const lines = String(text).split('\n')
  const out = []
  let i = 0

  while (i < lines.length) {
    const raw = lines[i]
    const trimmed = raw.trim()

    if (!trimmed) {
      out.push('')
      i += 1
      continue
    }

    if (PLACEHOLDER_RE.test(trimmed)) {
      out.push(trimmed)
      i += 1
      continue
    }

    if (isHorizontalRule(trimmed)) {
      out.push('<hr>')
      i += 1
      continue
    }

    const heading = trimmed.match(/^(#{1,6})\s+(.+?)(?:\s+#*)?$/)
    if (heading) {
      const level = heading[1].length
      const title = heading[2].replace(BR_TAG_RE, '').trim()
      out.push(`<h${level}>${title}</h${level}>`)
      i += 1
      continue
    }

    if (/^>\s?/.test(trimmed)) {
      const { items, next } = consumePrefixedLines(lines, i, (line) => /^>\s?/.test(line))
      const body = items.map((line) => line.replace(/^>\s?/, '')).join('\n')
      out.push(`<blockquote>${body}</blockquote>`)
      i = next
      continue
    }

    if (ORDERED_LINE_RE.test(trimmed)) {
      const { items, next } = consumePrefixedLines(lines, i, (line) => ORDERED_LINE_RE.test(line))
      const lis = items.map((line) => `<li>${line.replace(ORDERED_LINE_RE, '')}</li>`).join('')
      out.push(`<ol>${lis}</ol>`)
      i = next
      continue
    }

    if (UNORDERED_LINE_RE.test(trimmed)) {
      const { items, next } = consumePrefixedLines(lines, i, (line) => UNORDERED_LINE_RE.test(line))
      const lis = items.map((line) => `<li>${line.replace(UNORDERED_LINE_RE, '')}</li>`).join('')
      out.push(`<ul>${lis}</ul>`)
      i = next
      continue
    }

    out.push(raw)
    i += 1
  }

  return out.join('\n')
}

/** Модель иногда копирует HTML-списки в ячейку — сначала в markdown, потом экранируем. */
function htmlListsToMarkdown(text) {
  let value = String(text || '')
  if (!/<\s*(ul|ol|li|br|p)\b/i.test(value)) {
    return value
  }
  value = value.replace(BR_TAG_RE, '\n').replace(BR_ENTITY_RE, '\n')
  value = value.replace(/<\s*\/\s*p\s*>/gi, '\n').replace(/<\s*p\b[^>]*>/gi, '')
  value = value.replace(/<\s*\/\s*li\s*>\s*<\s*li\b[^>]*>/gi, '\n- ')
  value = value.replace(/<\s*li\b[^>]*>/gi, '\n- ')
  value = value.replace(/<\s*\/?\s*(ul|ol)\b[^>]*>/gi, '\n')
  value = value.replace(/<[^>]+>/g, '')
  return value
}

/** Ячейка markdown-таблицы: инлайн-разметка и список, если модель пишет пункты через <br>. */
function formatTableCell(raw) {
  let text = htmlListsToMarkdown(String(raw ?? ''))
  text = text.replace(BR_TAG_RE, '\n').replace(BR_ENTITY_RE, '\n')
  const lines = text.split(/\n/).map((line) => line.trim()).filter(Boolean)
  const asList = lines.length >= 2 && lines.every((line) => BULLET_LINE_RE.test(line))
  if (asList) {
    const items = lines.map((line) => formatInlineMarkdown(line.replace(BULLET_LINE_RE, '')))
    return `<ul>${items.map((item) => `<li>${item}</li>`).join('')}</ul>`
  }
  return formatInlineMarkdown(text)
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
      html += `<th>${formatTableCell(header)}</th>`
    })
    html += '</tr></thead>'

    if (rows.length > 0) {
      html += '<tbody>'
      rows.forEach((row) => {
        html += '<tr>'
        headers.forEach((_, index) => {
          html += `<td>${formatTableCell(row[index] || '')}</td>`
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
    return `\n%%MD_CODE_${id}%%\n`
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
    return `%%MD_THINK_${id}%%`
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
  text = decodeHtmlEntities(afterThink)

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
    return `\n\n%%MD_TABLE_${tableId}%%\n\n`
  })

  text = formatBlockMarkdown(text)
  text = applyInlineMarkdown(text)
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, linkText, url) => {
    if (url.includes('/api/ai_assistant/documents/download/')) {
      return `<a href="#" class="download-link" data-download-url="${url}" data-filename="${linkText}">${linkText}</a>`
    }
    return `<a href="${url}" target="_blank" rel="noopener noreferrer">${linkText}</a>`
  })

  codeBlocks.forEach((block) => {
    text = text.replace(`%%MD_CODE_${block.id}%%`, block.html)
  })
  thinkBlocks.forEach((block) => {
    text = text.replace(`%%MD_THINK_${block.id}%%`, block.html)
  })
  tables.forEach((table) => {
    text = text.replace(`%%MD_TABLE_${table.id}%%`, table.html)
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
    .replace(new RegExp(`(?:<br>\\s*)+(<(?:${BLOCK_OPEN_RE})\\b)`, 'gi'), '$1')
    .replace(new RegExp(`(</(?:${BLOCK_CLOSE_RE})>|<hr\\s*/?>)(?:\\s*<br>)+`, 'gi'), '$1')
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
