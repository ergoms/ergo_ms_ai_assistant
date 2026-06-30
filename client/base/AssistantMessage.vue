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
            <span>Генерация...</span>
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
          <div class="table-meta">{{ message.data.data.length }} строк</div>
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
  
  lines.slice(0, 20).forEach((line, idx) => {
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
      
      tableLines.forEach((tl, idx) => {
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
          console.warn('[AssistantMessage] Не удалось распарсить таблицу (ID:', tableId, '), возвращаем исходный текст')
        }
      } else {
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
    tables.forEach((table, idx) => {
    })
  } else {
    const linesWithPipe = processedLines.filter(l => l.includes('|'))
    if (linesWithPipe.length > 0) {
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
    const replacement = `<div class="think-block"><div class="think-block__header">💭 Размышления:</div><div class="think-block__content">${think.content}</div></div>`
    if (content.includes(placeholder)) {
      content = content.replace(placeholder, replacement)
    } else {
      console.warn('[AssistantMessage] Плейсхолдер think не найден в контенте:', placeholder)
    }
  })
  
  // Заменяем плейсхолдеры таблиц на HTML ПЕРЕД заменой переносов строк
  tables.forEach(table => {
    const placeholder = `__TABLE_PLACEHOLDER_${table.id}__`
    // Заменяем плейсхолдер на HTML таблицу
    const regex = new RegExp(placeholder.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g')
    if (content.includes(placeholder)) {
      content = content.replace(regex, table.html)
    } else {
      console.warn('[AssistantMessage] Плейсхолдер таблицы не найден в контенте:', placeholder)
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
  return date.toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<style lang="scss" scoped>
@import '../styles/variables';

.neural-chat-message {
  display: flex;
  flex-direction: column;
  margin-bottom: 1rem;

  &--user {
    align-items: flex-end;
    
    .message-row {
      flex-direction: row-reverse;
    }
  }

  &--assistant {
    align-items: flex-start;
  }
}

.message-row {
  display: flex;
  gap: 0.75rem;
  max-width: 85%;
  align-items: flex-start;
}

.message-avatar {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: $radius-md;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  color: white;

  &--user {
    background: $neon-blue;
  }

  &--assistant {
    background: $neon-cyan;
  }
}


.message-bubble {
  flex: 1;
  padding: 1rem 1.5rem;
  border-radius: 12px;
  background: color-mix(in srgb, var(--nc-bg-elevated, #{$dark-bg-elevated}) 88%, transparent);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--nc-border, #{$dark-border});
  position: relative;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

// Светлая тема - применяем через родительский селектор
[data-bs-theme="light"] .message-bubble {
  background: #ffffff;
  border: 1px solid rgba(226, 232, 240, 0.8);
  box-shadow: 
    0 1px 3px rgba(0, 0, 0, 0.1),
    0 4px 12px rgba(0, 0, 0, 0.05);
}

@media (prefers-color-scheme: light) {
  .message-bubble {
    background: #ffffff;
    border: 1px solid rgba(226, 232, 240, 0.8);
    box-shadow: 
      0 1px 3px rgba(0, 0, 0, 0.1),
      0 4px 12px rgba(0, 0, 0, 0.05);
  }
}

.neural-chat-message--user .message-bubble {
  background: rgba($neon-blue, 0.1);
  border-color: rgba($neon-blue, 0.3);
}

[data-bs-theme="light"] .neural-chat-message--user .message-bubble {
  background: #f0f7ff;
  border-color: rgba(79, 143, 255, 0.3);
  box-shadow: 
    0 1px 3px rgba(79, 143, 255, 0.15),
    0 4px 12px rgba(79, 143, 255, 0.08);
}

@media (prefers-color-scheme: light) {
  .neural-chat-message--user .message-bubble {
    background: #f0f7ff;
    border-color: rgba(79, 143, 255, 0.3);
    box-shadow: 
      0 1px 3px rgba(79, 143, 255, 0.15),
      0 4px 12px rgba(79, 143, 255, 0.08);
  }
}

.message-text {
  font-size: $font-size-lg; // Увеличенный размер шрифта
  line-height: $line-height-relaxed;
  color: var(--nc-text-primary, #{$dark-text-primary});
  word-wrap: break-word;
  overflow-wrap: break-word;
  word-break: break-word;

  :deep(code) {
    background: rgba(58, 232, 255, 0.15);
    padding: 0.2em 0.5em;
    border-radius: $radius-sm;
    font-size: 0.95em; // Немного увеличенный размер
    color: $neon-cyan;
  }

  :deep(strong) {
    color: var(--nc-text-primary, white);
    font-weight: $font-weight-semibold;
  }

  :deep(em) {
    color: $neon-purple;
  }

  // Стили для thinking блоков
  :deep(.think-block) {
    margin: $spacing-lg 0;
    padding: $spacing-lg;
    background: rgba(168, 85, 247, 0.1);
    border: 1px solid rgba(168, 85, 247, 0.3);
    border-radius: $radius-lg;
    border-left: 4px solid $neon-purple;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  :deep(.think-block__header) {
    font-size: $font-size-sm; // Увеличенный размер
    font-weight: $font-weight-semibold;
    color: $neon-purple;
    margin-bottom: $spacing-md;
  }

  :deep(.think-block__content) {
    font-size: $font-size-base; // Увеличенный размер
    color: var(--nc-text-secondary, #{$dark-text-secondary});
    line-height: $line-height-relaxed;
    white-space: pre-wrap;
    word-wrap: break-word;
    overflow-wrap: break-word;
  }

  // Стили для таблиц
  :deep(.markdown-table-wrapper) {
    margin: $spacing-lg 0;
    overflow-x: auto;
    border-radius: $radius-lg;
    max-width: 100%;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  :deep(.markdown-table) {
    width: 100%;
    min-width: 500px;
    border-collapse: collapse;
    font-size: $font-size-base; // Увеличенный размер шрифта в таблицах
    background: var(--nc-bg-elevated, #{$dark-bg-elevated});
    border: 1px solid rgba(58, 232, 255, 0.2);
    
    th, td {
      padding: $spacing-md $spacing-lg; // Увеличенные отступы
      text-align: left;
      border-bottom: 1px solid rgba(58, 232, 255, 0.1);
      word-wrap: break-word;
      overflow-wrap: break-word;
      white-space: normal;
    }
    
    th {
      background: rgba(58, 232, 255, 0.1);
      font-weight: $font-weight-semibold;
      color: var(--nc-text-primary, #{$dark-text-primary});
      font-size: $font-size-sm; // Увеличенный размер для заголовков
      position: sticky;
      top: 0;
      z-index: 1;
    }
    
    td {
      color: var(--nc-text-secondary, #{$dark-text-secondary});
    }
    
    tbody tr {
      transition: background 0.2s;
      
      &:hover {
        background: rgba(58, 232, 255, 0.05);
      }
      
      &:last-child td {
        border-bottom: none;
      }
    }
  }
}

[data-bs-theme="light"] .message-text {
  color: #000000;
  
  :deep(code) {
    background: rgba(15, 118, 138, 0.1);
    color: #0f768a;
  }
  
  :deep(strong) {
    color: #000000;
  }
  
  :deep(em) {
    color: #7c3aed;
  }
  
  :deep(.think-block) {
    background: rgba(124, 58, 237, 0.08);
    border: 1px solid rgba(124, 58, 237, 0.2);
    border-left: 4px solid #7c3aed;
    box-shadow: 
      0 2px 8px rgba(0, 0, 0, 0.08),
      0 1px 2px rgba(0, 0, 0, 0.04);
  }
  
  :deep(.think-block__header) {
    color: #7c3aed;
  }
  
  :deep(.think-block__content) {
    color: #000000;
  }
  
  :deep(.markdown-table-wrapper) {
    box-shadow: 
      0 2px 8px rgba(0, 0, 0, 0.08),
      0 1px 2px rgba(0, 0, 0, 0.04);
  }
  
  :deep(.markdown-table) {
    background: #ffffff;
    border: 1px solid rgba(226, 232, 240, 0.8);
    
    th, td {
      border-bottom: 1px solid rgba(226, 232, 240, 0.6);
    }
    
    th {
      background: #f1f5f9;
      color: #000000;
      border-bottom: 2px solid #e2e8f0;
    }
    
    td {
      color: #000000;
      background: #ffffff;
    }
    
    tbody tr:hover {
      background: rgba(15, 118, 138, 0.05);
    }
  }
}

@media (prefers-color-scheme: light) {
  .message-text {
    color: #000000;
    
    :deep(code) {
      background: rgba(15, 118, 138, 0.1);
      color: #0f768a;
    }
    
    :deep(strong) {
      color: #000000;
    }
    
    :deep(em) {
      color: #7c3aed;
    }
    
    :deep(.think-block) {
      background: rgba(124, 58, 237, 0.08);
      border: 1px solid rgba(124, 58, 237, 0.2);
      border-left: 4px solid #7c3aed;
      box-shadow: 
        0 2px 8px rgba(0, 0, 0, 0.08),
        0 1px 2px rgba(0, 0, 0, 0.04);
    }
    
    :deep(.think-block__header) {
      color: #7c3aed;
    }
    
    :deep(.think-block__content) {
      color: #000000;
    }
    
    :deep(.markdown-table-wrapper) {
      box-shadow: 
        0 2px 8px rgba(0, 0, 0, 0.08),
        0 1px 2px rgba(0, 0, 0, 0.04);
    }
    
    :deep(.markdown-table) {
      background: #ffffff;
      border: 1px solid rgba(226, 232, 240, 0.8);
      
      th, td {
        border-bottom: 1px solid rgba(226, 232, 240, 0.6);
      }
      
      th {
        background: #f1f5f9;
        color: #000000;
        border-bottom: 2px solid #e2e8f0;
      }
      
      td {
        color: #000000;
        background: #ffffff;
      }
      
      tbody tr:hover {
        background: rgba(15, 118, 138, 0.05);
      }
    }
  }
}

.message-code {
  margin-top: $spacing-md;
  background: var(--nc-bg-base, #{$dark-bg-secondary});
  border-radius: $radius-lg;
  overflow: hidden;
  border: 1px solid $neon-cyan-medium;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  
  &--generating {
    border-color: $neon-purple-light;
    
    .code-label {
      color: $neon-purple;
    }
  }
}
  
@media (prefers-color-scheme: light) {
  .message-code {
    background: #f8fafc;
    border: 1px solid rgba(226, 232, 240, 0.8);
    box-shadow: 
      0 2px 8px rgba(0, 0, 0, 0.08),
      0 1px 2px rgba(0, 0, 0, 0.04);
  }
}
  
[data-bs-theme="light"] .message-code {
  background: #f8fafc;
  border: 1px solid rgba(226, 232, 240, 0.8);
  box-shadow: 
    0 2px 8px rgba(0, 0, 0, 0.08),
    0 1px 2px rgba(0, 0, 0, 0.04);
}

@media (prefers-color-scheme: light) {
  .message-code--generating {
    border-color: rgba(124, 58, 237, 0.2);
    
    .code-label {
      color: #7c3aed;
    }
  }
}

[data-bs-theme="light"] .message-code--generating {
  border-color: rgba(124, 58, 237, 0.2);
  
  .code-label {
    color: #7c3aed;
  }
}

.code-label {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  padding: $spacing-sm $spacing-md;
  background: rgba(58, 232, 255, 0.15);
  border-bottom: 1px solid $dark-border;
  font-size: $font-size-sm; // Увеличенный размер
  font-weight: $font-weight-semibold;
  color: $neon-cyan;
}

@media (prefers-color-scheme: light) {
  .code-label {
    background: rgba(15, 118, 138, 0.1);
    border-bottom: 1px solid rgba(226, 232, 240, 0.6);
    color: #0f768a;
  }
}

[data-bs-theme="light"] .code-label {
  background: rgba(15, 118, 138, 0.1);
  border-bottom: 1px solid rgba(226, 232, 240, 0.6);
  color: #0f768a;
}

.message-code pre {
  margin: 0;
  padding: $spacing-md;
  overflow-x: auto;
  font-size: $font-size-base; // Увеличенный размер
  line-height: $line-height-relaxed;
  color: $neon-green;
}

@media (prefers-color-scheme: light) {
  .message-code pre {
    color: #059669;
  }
}

[data-bs-theme="light"] .message-code pre {
  color: #059669;
}

.message-table {
  margin-top: $spacing-md;
  border-radius: $radius-lg;
  overflow: hidden;
  border: 1px solid $neon-green-light;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

@media (prefers-color-scheme: light) {
  .message-table {
    border: 1px solid rgba(226, 232, 240, 0.8);
    box-shadow: 
      0 2px 8px rgba(0, 0, 0, 0.08),
      0 1px 2px rgba(0, 0, 0, 0.04);
  }
}

[data-bs-theme="light"] .message-table {
  border: 1px solid rgba(226, 232, 240, 0.8);
  box-shadow: 
    0 2px 8px rgba(0, 0, 0, 0.08),
    0 1px 2px rgba(0, 0, 0, 0.04);
}

.table-scroll {
  max-height: 250px;
  overflow: auto;
}

.message-table table {
  width: 100%;
  border-collapse: collapse;
  font-size: $font-size-base; // Увеличенный размер
  background: var(--nc-bg-elevated, #{$dark-bg-elevated});
}

@media (prefers-color-scheme: light) {
  .message-table table {
    background: #ffffff;
  }
}

[data-bs-theme="light"] .message-table table {
  background: #ffffff;
}

.message-table th,
.message-table td {
  padding: $spacing-md $spacing-lg; // Увеличенные отступы
  text-align: left;
  border-bottom: 1px solid $neon-green-light;
  white-space: nowrap;
}

@media (prefers-color-scheme: light) {
  .message-table th,
  .message-table td {
    border-bottom: 1px solid rgba(226, 232, 240, 0.6);
  }
}

[data-bs-theme="light"] .message-table th,
[data-bs-theme="light"] .message-table td {
  border-bottom: 1px solid rgba(226, 232, 240, 0.6);
}

.message-table th {
  background: $neon-green-light;
  font-size: $font-size-sm; // Увеличенный размер
  font-weight: $font-weight-semibold;
  color: $neon-green;
  text-transform: uppercase;
  position: sticky;
  top: 0;
}

@media (prefers-color-scheme: light) {
  .message-table th {
    background: #f1f5f9;
    color: #000000;
    border-bottom: 2px solid #e2e8f0;
  }
}

[data-bs-theme="light"] .message-table th {
  background: #f1f5f9;
  color: #000000;
  border-bottom: 2px solid #e2e8f0;
}

.message-table td {
  color: var(--nc-text-primary, #{$dark-text-primary});
}

@media (prefers-color-scheme: light) {
  .message-table td {
    color: #000000;
    background: #ffffff;
  }
}

[data-bs-theme="light"] .message-table td {
  color: #000000;
  background: #ffffff;
}

.table-meta {
  padding: $spacing-sm $spacing-md;
  font-size: $font-size-sm; // Увеличенный размер
  color: var(--nc-text-muted, #{$dark-text-muted});
  background: $neon-green-light;
  border-top: 1px solid $neon-green-light;
}

@media (prefers-color-scheme: light) {
  .table-meta {
    background: rgba(241, 245, 249, 0.8);
    color: #64748b;
    border-top: 1px solid rgba(226, 232, 240, 0.6);
  }
}

[data-bs-theme="light"] .table-meta {
  background: rgba(241, 245, 249, 0.8);
  color: #64748b;
  border-top: 1px solid rgba(226, 232, 240, 0.6);
}

.message-error {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  margin-top: $spacing-sm;
  padding: $spacing-sm $spacing-sm;
  background: $neon-red-light;
  border-radius: $radius-sm;
  font-size: $font-size-sm;
  color: $neon-red;
}

.message-stage {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  margin-top: $spacing-sm;
  font-size: $font-size-sm;
  color: var(--nc-text-muted, #{$dark-text-muted});
}

.message-time {
  font-size: 0.7rem;
  color: var(--nc-text-muted, #{$dark-text-muted});
  margin-top: $spacing-xs;
  padding: 0 $spacing-sm;
}
</style>
