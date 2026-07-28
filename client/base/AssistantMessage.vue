<template>
  <div class="neural-chat-message" :class="`neural-chat-message--${message.type}`">
    <div class="message-row">
      <!-- Avatar -->
      <div class="message-avatar" :class="`message-avatar--${message.type}`">
        <User v-if="message.type === 'user'" :size="18" />
        <Sparkles v-else :size="18" />
        <div class="avatar-glow"></div>
      </div>

      <!-- Content bubble -->
      <div class="message-bubble">
        <!-- Text content -->
        <div v-if="message.content" class="message-text" v-html="formatMarkdown(message.content)"></div>
        
        <!-- SQL query -->
        <div v-if="message.sql" class="message-code">
          <div class="code-label">
            <Terminal :size="12" />
            <span>SQL</span>
          </div>
          <pre><code>{{ message.sql }}</code></pre>
        </div>

        <!-- SQL generating -->
        <div v-if="message.sqlGenerating" class="message-code message-code--generating">
          <div class="code-label">
            <Loader2 :size="12" class="spinning" />
            <span>{{ t('ai_assistant.message.generatingShort') }}</span>
          </div>
          <pre><code>{{ message.sqlGenerating }}</code></pre>
        </div>

        <!-- Data table -->
        <div v-if="message.data && message.data.data && message.data.data.length > 0" class="message-table">
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th v-for="col in message.data.columns" :key="col">{{ col }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, idx) in message.data.data" :key="idx">
                  <td v-for="col in message.data.columns" :key="col">{{ row[col] }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="table-meta">{{ t('ai_assistant.message.rowsCount', message.data.data.length) }}</div>
        </div>

        <!-- Error -->
        <div v-if="message.error" class="message-error">
          <AlertCircle :size="14" />
          <span>{{ message.error }}</span>
        </div>

        <!-- Stage -->
        <div v-if="message.stage && message.streaming" class="message-stage">
          <Loader2 :size="12" class="spinning" />
          <span>{{ message.stage }}</span>
        </div>
      </div>
    </div>

    <div class="message-time">{{ formatTime(message.timestamp) }}</div>
  </div>
</template>

<script setup>
import { Sparkles, User, Terminal, Loader2, AlertCircle } from 'lucide-vue-next'
import { sanitizeHtml } from '@/js/utils/sanitize'
import { logError } from '@/js/utils/logError.js'
import { useAppI18n } from '@/i18n/useAppI18n.js'
import { getCurrentBcp47 } from '@/i18n/index.js'

const { t } = useAppI18n()

defineProps({
  message: {
    type: Object,
    required: true,
  },
})

const escapeHtml = (text) => {
  if (!text) return ''
  const div = document.createElement('div')
  div.textContent = String(text)
  return div.innerHTML
}

const parseMarkdownTable = (markdownTable) => {
  try {
    
    // Убираем пустые строки и нормализуем
    const lines = markdownTable
      .split('\n')
      .map(line => line.trim())
      .filter(line => line) // Убираем пустые строки
    
    
    if (lines.length < 2) {
      return markdownTable // Не таблица
    }
    
    // Находим строку с разделителем - более строгая проверка
    // Разделитель должен содержать только |, пробелы, дефисы и двоеточия
    let separatorIndex = -1
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]
      // Проверяем, что строка начинается и заканчивается на |
      if (line.startsWith('|') && line.endsWith('|')) {
        // Разделяем строку на ячейки по |
        const cells = line.split('|').map(cell => cell.trim()).filter(cell => cell)
        // Проверяем, что все ячейки содержат только дефисы, пробелы и двоеточия
        const allCellsAreSeparators = cells.length > 0 && cells.every(cell => /^[\s\-:]+$/.test(cell))
        if (allCellsAreSeparators) {
          separatorIndex = i
          break
        }
      }
    }
    
    if (separatorIndex === -1 || separatorIndex === 0) {
      return markdownTable // Нет разделителя или он первый
    }
    
    // Первая строка до разделителя - заголовки
    const headerLine = lines[0]
    if (!headerLine.startsWith('|') || !headerLine.endsWith('|')) {
      return markdownTable // Не таблица
    }
    
    const headers = headerLine
      .split('|')
      .map(cell => cell.trim())
      .filter((cell, index, arr) => {
        // Убираем пустые ячейки по краям таблицы
        return index > 0 && index < arr.length - 1
      })
    
    
    if (headers.length === 0) {
      return markdownTable // Нет заголовков
    }
    
    // Проверяем количество колонок в разделителе
    const separatorCells = lines[separatorIndex]
      .split('|')
      .map(cell => cell.trim())
      .filter((cell, index, arr) => index > 0 && index < arr.length - 1)
    
    // Количество колонок должно совпадать
    if (separatorCells.length !== headers.length) {
      return markdownTable // Несоответствие количества колонок
    }
    
    // Строки после разделителя - данные
    const dataLines = lines.slice(separatorIndex + 1)
    const rows = dataLines
      .filter(line => line.startsWith('|') && line.endsWith('|'))
      .map(line => {
        return line
          .split('|')
          .map(cell => cell.trim())
          .filter((cell, index, arr) => {
            // Убираем пустые ячейки по краям таблицы
            return index > 0 && index < arr.length - 1
          })
      })
      .filter(row => {
        // Убираем полностью пустые строки
        if (row.length === 0) return false
        // Проверяем, что количество ячеек соответствует заголовкам
        if (row.length !== headers.length) {
          return false
        }
        // Убираем строки, где все ячейки пустые
        return row.some(cell => cell.length > 0)
      })
    
    
    if (rows.length === 0) {
      return markdownTable // Нет данных
    }
    
    // Формируем HTML таблицу
    let html = '<div class="markdown-table-wrapper"><table class="markdown-table">'
    
    // Заголовки
    html += '<thead><tr>'
    headers.forEach(header => {
      html += `<th>${escapeHtml(header)}</th>`
    })
    html += '</tr></thead>'
    
    // Данные
    html += '<tbody>'
    rows.forEach(row => {
      html += '<tr>'
      headers.forEach((_, index) => {
        const cell = (row[index] || '').trim()
        html += `<td>${escapeHtml(cell)}</td>`
      })
      html += '</tr>'
    })
    html += '</tbody>'
    
    html += '</table></div>'
    
    
    return html
  } catch (error) {
    logError('[parseMarkdownTable] Ошибка парсинга таблицы:', error)
    return markdownTable
  }
}

const formatMarkdown = (text) => {
  if (!text) return ''
  
  
  // Проверяем наличие таблиц в исходном тексте
  const tablePattern = /\|.*\|/g
  const tableMatches = text.match(tablePattern)
  if (tableMatches) {
    /* no-op */
  }
  
  // Сначала обрабатываем блоки <think> для thinking (ДО обработки таблиц, чтобы не конфликтовало)
  // Используем более надежное регулярное выражение, которое обрабатывает многострочные блоки
  // Важно: используем нежадное совпадение с флагом 's' (dotall) через [\s\S]
  const thinkRegex = /<think>([\s\S]*?)<\/think>/gi
  const thinkBlocks = []
  let thinkIndex = 0
  
  let content = text
  // Сбрасываем lastIndex для глобального регулярного выражения
  thinkRegex.lastIndex = 0
  let thinkMatch
  while ((thinkMatch = thinkRegex.exec(text)) !== null) {
    const thinkContent = thinkMatch[1]
    const fullMatch = thinkMatch[0]
    const thinkId = `think-block-${thinkIndex++}`
    // Экранируем HTML и сохраняем контент
    const escapedContent = escapeHtml(thinkContent.trim())
    thinkBlocks.push({ id: thinkId, content: escapedContent, original: fullMatch })
    // Заменяем весь блок включая теги на плейсхолдер (один перенос строки до и после)
    content = content.replace(fullMatch, `\n__THINK_PLACEHOLDER_${thinkId}__\n`)
  }
  
  
  // Затем обрабатываем таблицы
  // Более надежный подход: ищем таблицы построчно, собирая блоки
  const tables = []
  let tableIndex = 0
  
  // Разбиваем контент на строки для более точного поиска таблиц
  const lines = content.split('\n')
  const processedLines = []
  let i = 0
  
  lines.slice(0, 20).forEach((_line, _idx) => {
  })
  
  while (i < lines.length) {
    const line = lines[i]
    const trimmedLine = line.trim()
    
    // Проверяем, является ли строка частью таблицы (начинается и заканчивается на |)
    if (trimmedLine.startsWith('|') && trimmedLine.endsWith('|')) {
      
      // Начинаем собирать таблицу
      let tableStart = i
      let tableLines = [trimmedLine]
      i++
      
      // Собираем все последующие строки таблицы
      while (i < lines.length) {
        const nextLine = lines[i]
        const trimmedNextLine = nextLine.trim()
        
        // Если следующая строка тоже часть таблицы
        if (trimmedNextLine.startsWith('|') && trimmedNextLine.endsWith('|')) {
          tableLines.push(trimmedNextLine)
          i++
          continue
        }
        
        // Если пустая строка - пропускаем (может быть внутри таблицы)
        if (trimmedNextLine === '' && i + 1 < lines.length) {
          const afterEmpty = lines[i + 1].trim()
          // Если после пустой строки идет продолжение таблицы, пропускаем пустую строку
          if (afterEmpty.startsWith('|') && afterEmpty.endsWith('|')) {
            i++
            continue
          }
        }
        
        // Если не табличная строка - заканчиваем сбор таблицы
        break
      }
      
      tableLines.forEach((_tl, _idx) => {
      })
      
      // Проверяем, что это действительно таблица (есть разделитель)
      let hasSeparator = false
      let separatorIndex = -1
      for (let j = 0; j < tableLines.length; j++) {
        const tableLine = tableLines[j]
        if (tableLine.startsWith('|') && tableLine.endsWith('|')) {
          // Разделяем строку на ячейки по |
          const cells = tableLine.split('|').map(cell => cell.trim()).filter(cell => cell)
          
          // Проверяем, что все ячейки содержат только дефисы, пробелы и двоеточия
          const allCellsAreSeparators = cells.length > 0 && cells.every(cell => /^[\s\-:]+$/.test(cell))
          
          if (allCellsAreSeparators) {
            hasSeparator = true
            separatorIndex = j
            break
          }
        }
      }
      
      
      // Если это таблица, парсим её
      if (hasSeparator && tableLines.length >= 2 && separatorIndex > 0) {
        const tableText = tableLines.join('\n')
        const tableId = `markdown-table-${tableIndex++}`
        const htmlTable = parseMarkdownTable(tableText)
        
        // Если парсинг успешен (вернул HTML, а не исходный текст)
        if (htmlTable !== tableText && htmlTable.includes('<table')) {
          tables.push({ id: tableId, html: htmlTable })
          // Заменяем все строки таблицы на один плейсхолдер
          processedLines.push(`__TABLE_PLACEHOLDER_${tableId}__`)
          // Пропускаем все строки таблицы
          continue
        } else {
          // парсинг не удался — оставляем исходный текст
        }
      } else {
        /* no-op */
      }
      
      // Если не удалось распарсить как таблицу, добавляем строки как есть
      for (let k = tableStart; k < i; k++) {
        processedLines.push(lines[k])
      }
      continue
    }
    
    // Обычная строка - добавляем как есть
    processedLines.push(lines[i])
    i++
  }
  
  // Собираем контент обратно
  content = processedLines.join('\n')
  if (tables.length > 0) {
    tables.forEach((_table, _idx) => {
    })
  } else {
    const linesWithPipe = processedLines.filter(l => l.includes('|'))
    if (linesWithPipe.length > 0) {
      /* no-op */
    }
  }
  
  // Обрабатываем остальной markdown
  content = content
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
  
  // Заменяем плейсхолдеры thinking блоков на HTML
  thinkBlocks.forEach(think => {
    const placeholder = `__THINK_PLACEHOLDER_${think.id}__`
    const replacement = `<div class="think-block"><div class="think-block__header">💭 ${escapeHtml(t('ai_assistant.message.thinking'))}</div><div class="think-block__content">${think.content}</div></div>`
    if (content.includes(placeholder)) {
      content = content.replace(placeholder, replacement)
    }
  })
  
  // Заменяем плейсхолдеры таблиц на HTML ПЕРЕД заменой переносов строк
  tables.forEach(table => {
    const placeholder = `__TABLE_PLACEHOLDER_${table.id}__`
    // Заменяем плейсхолдер на HTML таблицу
    const regex = new RegExp(placeholder.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g')
    if (content.includes(placeholder)) {
      content = content.replace(regex, table.html)
    }
  })
  
  // Убираем множественные пустые строки (более 2 подряд) перед заменой на <br>
  content = content.replace(/\n{3,}/g, '\n\n')
  
  // Убираем пустые строки в начале и конце
  content = content.trim()
  
  // Заменяем переносы строк на <br> в последнюю очередь
  content = content.replace(/\n/g, '<br>')
  
  
  return sanitizeHtml(content)
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString(getCurrentBcp47(), {
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<style lang="scss" scoped>
@import './AssistantMessage.scss';
</style>
