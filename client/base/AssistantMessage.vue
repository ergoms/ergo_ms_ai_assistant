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

        <!-- Sources (RAG citations) -->
        <div v-if="message.sources && message.sources.length > 0 && message.type === 'assistant'" class="message-sources">
          <button class="sources-toggle" @click="sourcesExpanded = !sourcesExpanded">
            <BookOpen :size="12" />
            <span>Источники ({{ message.sources.length }})</span>
            <ChevronDown :size="12" :class="{ 'rotate-180': sourcesExpanded }" />
          </button>
          <div v-if="sourcesExpanded" class="sources-list">
            <div v-for="(src, idx) in message.sources" :key="idx" class="source-chip">
              <FileText :size="11" />
              <span class="source-title">{{ src.document_title }}</span>
              <span v-if="src.preview" class="source-preview">{{ src.preview }}</span>
            </div>
          </div>
        </div>

        <!-- Feedback buttons (only for assistant messages that are not streaming) -->
        <div v-if="message.type === 'assistant' && !message.isStreaming && message.id" class="message-feedback">
          <button
            class="feedback-btn"
            :class="{ 'feedback-btn--active': feedbackGiven === 1 }"
            @click="sendFeedback(1)"
            title="Хороший ответ"
          >👍</button>
          <button
            class="feedback-btn"
            :class="{ 'feedback-btn--active': feedbackGiven === -1 }"
            @click="sendFeedback(-1)"
            title="Плохой ответ"
          >👎</button>
        </div>
      </div>
    </div>

    <div class="message-time">{{ formatTime(message.timestamp) }}</div>

    <!-- Suggestion chips (only for last assistant message) -->
    <div v-if="message.suggestions && message.suggestions.length > 0 && message.type === 'assistant' && !message.isStreaming" class="message-suggestions">
      <button
        v-for="(suggestion, idx) in message.suggestions"
        :key="idx"
        class="suggestion-chip"
        @click="$emit('suggest', suggestion)"
      >
        <Zap :size="11" />
        <span>{{ suggestion }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Sparkles, User, Terminal, Loader2, AlertCircle, BookOpen, ChevronDown, FileText, Zap } from 'lucide-vue-next'

const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['suggest', 'feedback'])

const sourcesExpanded = ref(false)
const feedbackGiven = ref(props.message.feedback || null)

const sendFeedback = async (value) => {
  if (feedbackGiven.value === value) return
  feedbackGiven.value = value
  emit('feedback', { messageId: props.message.id, feedback: value })
  // Also send directly via fetch
  try {
    await fetch(`/api/ai_assistant/messages/${props.message.id}/feedback/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ feedback: value }),
    })
  } catch (e) {
    console.warn('Feedback send error:', e)
  }
}

const getCsrfToken = () => {
  const match = document.cookie.match(/csrftoken=([^;]+)/)
  return match ? match[1] : ''
}

const escapeHtml = (text) => {
  if (!text) return ''
  const div = document.createElement('div')
  div.textContent = String(text)
  return div.innerHTML
}

const parseMarkdownTable = (markdownTable) => {
  try {
    console.log('[parseMarkdownTable] Входные данные:', markdownTable.substring(0, 300))
    
    // Убираем пустые строки и нормализуем
    const lines = markdownTable
      .split('\n')
      .map(line => line.trim())
      .filter(line => line) // Убираем пустые строки
    
    console.log('[parseMarkdownTable] Обработанные строки:', lines.length)
    
    if (lines.length < 2) {
      console.log('[parseMarkdownTable] Недостаточно строк для таблицы')
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
          console.log('[parseMarkdownTable] Найден разделитель на строке:', i)
          break
        }
      }
    }
    
    if (separatorIndex === -1 || separatorIndex === 0) {
      console.log('[parseMarkdownTable] Разделитель не найден или он первый')
      return markdownTable // Нет разделителя или он первый
    }
    
    // Первая строка до разделителя - заголовки
    const headerLine = lines[0]
    if (!headerLine.startsWith('|') || !headerLine.endsWith('|')) {
      console.log('[parseMarkdownTable] Первая строка не является заголовком')
      return markdownTable // Не таблица
    }
    
    const headers = headerLine
      .split('|')
      .map(cell => cell.trim())
      .filter((cell, index, arr) => {
        // Убираем пустые ячейки по краям таблицы
        return index > 0 && index < arr.length - 1
      })
    
    console.log('[parseMarkdownTable] Заголовки:', headers)
    
    if (headers.length === 0) {
      console.log('[parseMarkdownTable] Нет заголовков')
      return markdownTable // Нет заголовков
    }
    
    // Проверяем количество колонок в разделителе
    const separatorCells = lines[separatorIndex]
      .split('|')
      .map(cell => cell.trim())
      .filter((cell, index, arr) => index > 0 && index < arr.length - 1)
    
    // Количество колонок должно совпадать
    if (separatorCells.length !== headers.length) {
      console.log('[parseMarkdownTable] Несоответствие количества колонок:', separatorCells.length, 'vs', headers.length)
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
          console.log('[parseMarkdownTable] Строка с несоответствующим количеством ячеек:', row.length, 'vs', headers.length)
          return false
        }
        // Убираем строки, где все ячейки пустые
        return row.some(cell => cell.length > 0)
      })
    
    console.log('[parseMarkdownTable] Найдено строк данных:', rows.length)
    
    if (rows.length === 0) {
      console.log('[parseMarkdownTable] Нет данных')
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
    
    console.log('[parseMarkdownTable] Сгенерирован HTML таблицы (длина:', html.length, ')')
    
    return html
  } catch (error) {
    console.error('[parseMarkdownTable] Ошибка парсинга таблицы:', error)
    return markdownTable
  }
}

const renderCodeBlock = (lang, code) => {
  const escapedCode = escapeHtml(code)
  const langLabel = lang ? lang.toUpperCase() : 'CODE'
  return `<div class="code-block"><div class="code-block__header"><span class="code-block__lang">${escapeHtml(langLabel)}</span><button class="code-block__copy" onclick="navigator.clipboard.writeText(this.closest('.code-block').querySelector('code').textContent)" title="Копировать">⧉</button></div><pre><code class="code-block__code lang-${escapeHtml(lang || 'text')}">${escapedCode}</code></pre></div>`
}

const formatMarkdown = (text) => {
  if (!text) return ''

  console.log('[AssistantMessage] ========== formatMarkdown START ==========')
  console.log('[AssistantMessage] Входной текст (полная длина:', text.length, '):')
  console.log(text)
  console.log('[AssistantMessage] Первые 1000 символов:', text.substring(0, 1000))
  
  // Проверяем наличие таблиц в исходном тексте
  const tablePattern = /\|.*\|/g
  const tableMatches = text.match(tablePattern)
  console.log('[AssistantMessage] Найдено строк с | в исходном тексте:', tableMatches ? tableMatches.length : 0)
  if (tableMatches) {
    console.log('[AssistantMessage] Примеры строк с |:', tableMatches.slice(0, 5))
  }
  
  // Обрабатываем fenced code blocks (```lang\ncode\n```) ПЕРВЫМИ — до всего остального
  const codeBlocks = []
  let codeBlockIndex = 0
  let content = text
  content = content.replace(/```(\w*)\n?([\s\S]*?)```/g, (match, lang, code) => {
    const id = `__CODE_BLOCK_${codeBlockIndex++}__`
    codeBlocks.push({ id, html: renderCodeBlock(lang, code.trim()) })
    return `\n${id}\n`
  })

  // Сначала обрабатываем блоки <think> для thinking (ДО обработки таблиц, чтобы не конфликтовало)
  // Используем более надежное регулярное выражение, которое обрабатывает многострочные блоки
  // Важно: используем нежадное совпадение с флагом 's' (dotall) через [\s\S]
  const thinkRegex = /<think>([\s\S]*?)<\/think>/gi
  const thinkBlocks = []
  let thinkIndex = 0

  // Сбрасываем lastIndex для глобального регулярного выражения
  thinkRegex.lastIndex = 0
  let thinkMatch
  while ((thinkMatch = thinkRegex.exec(text)) !== null) {
    const thinkContent = thinkMatch[1]
    const fullMatch = thinkMatch[0]
    console.log('[AssistantMessage] Найден think блок (длина контента:', thinkContent.length, ', полный блок:', fullMatch.length, '):', thinkContent.substring(0, 200))
    const thinkId = `think-block-${thinkIndex++}`
    // Экранируем HTML и сохраняем контент
    const escapedContent = escapeHtml(thinkContent.trim())
    thinkBlocks.push({ id: thinkId, content: escapedContent, original: fullMatch })
    // Заменяем весь блок включая теги на плейсхолдер (один перенос строки до и после)
    content = content.replace(fullMatch, `\n__THINK_PLACEHOLDER_${thinkId}__\n`)
  }
  
  console.log('[AssistantMessage] Всего найдено think блоков:', thinkBlocks.length)
  console.log('[AssistantMessage] Контент после обработки think блоков (первые 500 символов):', content.substring(0, 500))
  
  // Затем обрабатываем таблицы
  // Более надежный подход: ищем таблицы построчно, собирая блоки
  const tables = []
  let tableIndex = 0
  
  // Разбиваем контент на строки для более точного поиска таблиц
  const lines = content.split('\n')
  const processedLines = []
  let i = 0
  
  console.log('[AssistantMessage] Начинаем поиск таблиц, всего строк:', lines.length)
  console.log('[AssistantMessage] Первые 20 строк для анализа:')
  lines.slice(0, 20).forEach((line, idx) => {
    console.log(`[AssistantMessage] Строка ${idx}:`, JSON.stringify(line))
  })
  
  while (i < lines.length) {
    const line = lines[i]
    const trimmedLine = line.trim()
    
    // Проверяем, является ли строка частью таблицы (начинается и заканчивается на |)
    if (trimmedLine.startsWith('|') && trimmedLine.endsWith('|')) {
      console.log('[AssistantMessage] ✓ Найдена потенциальная строка таблицы на строке', i)
      console.log('[AssistantMessage] Строка:', JSON.stringify(trimmedLine))
      console.log('[AssistantMessage] Первые 150 символов:', trimmedLine.substring(0, 150))
      
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
      
      console.log('[AssistantMessage] Собрано строк таблицы:', tableLines.length)
      console.log('[AssistantMessage] Собранные строки таблицы:')
      tableLines.forEach((tl, idx) => {
        console.log(`[AssistantMessage]   [${idx}]:`, JSON.stringify(tl))
      })
      
      // Проверяем, что это действительно таблица (есть разделитель)
      let hasSeparator = false
      let separatorIndex = -1
      for (let j = 0; j < tableLines.length; j++) {
        const tableLine = tableLines[j]
        if (tableLine.startsWith('|') && tableLine.endsWith('|')) {
          // Разделяем строку на ячейки по |
          const cells = tableLine.split('|').map(cell => cell.trim()).filter(cell => cell)
          console.log(`[AssistantMessage] Проверка строки ${j} на разделитель:`, JSON.stringify(tableLine))
          console.log(`[AssistantMessage] Ячейки:`, cells)
          
          // Проверяем, что все ячейки содержат только дефисы, пробелы и двоеточия
          const allCellsAreSeparators = cells.length > 0 && cells.every(cell => /^[\s\-:]+$/.test(cell))
          console.log(`[AssistantMessage] Все ячейки являются разделителями:`, allCellsAreSeparators)
          
          if (allCellsAreSeparators) {
            hasSeparator = true
            separatorIndex = j
            console.log('[AssistantMessage] ✓ Найден разделитель на позиции', j, 'в собранной таблице')
            break
          }
        }
      }
      
      console.log('[AssistantMessage] Результат проверки разделителя:', { hasSeparator, separatorIndex, tableLinesLength: tableLines.length })
      
      // Если это таблица, парсим её
      if (hasSeparator && tableLines.length >= 2 && separatorIndex > 0) {
        const tableText = tableLines.join('\n')
        const tableId = `markdown-table-${tableIndex++}`
        console.log('[AssistantMessage] Найдена таблица (ID:', tableId, '):', tableText.substring(0, 300))
        const htmlTable = parseMarkdownTable(tableText)
        console.log('[AssistantMessage] Результат парсинга таблицы (ID:', tableId, ', длина HTML:', htmlTable.length, '):', htmlTable.substring(0, 300))
        
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
        console.log('[AssistantMessage] Собранные строки не являются таблицей (hasSeparator:', hasSeparator, ', length:', tableLines.length, ', separatorIndex:', separatorIndex, ')')
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
  console.log('[AssistantMessage] ========== РЕЗУЛЬТАТ ПОИСКА ТАБЛИЦ ==========')
  console.log('[AssistantMessage] Найдено таблиц:', tables.length)
  if (tables.length > 0) {
    tables.forEach((table, idx) => {
      console.log(`[AssistantMessage] Таблица ${idx + 1} (ID: ${table.id}):`, table.html.substring(0, 200))
    })
  } else {
    console.log('[AssistantMessage] ⚠️ ТАБЛИЦЫ НЕ НАЙДЕНЫ!')
    console.log('[AssistantMessage] Проверяем, есть ли строки с | в processedLines:')
    const linesWithPipe = processedLines.filter(l => l.includes('|'))
    console.log('[AssistantMessage] Строк с | в processedLines:', linesWithPipe.length)
    if (linesWithPipe.length > 0) {
      console.log('[AssistantMessage] Примеры строк с |:', linesWithPipe.slice(0, 5))
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
      console.log('[AssistantMessage] Заменен think плейсхолдер:', think.id)
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
      console.log('[AssistantMessage] Заменен плейсхолдер таблицы:', table.id)
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

  // Заменяем плейсхолдеры code blocks на HTML (после <br> замены)
  codeBlocks.forEach(block => {
    content = content.replace(
      new RegExp(block.id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'),
      block.html
    )
  })

  console.log('[AssistantMessage] ========== formatMarkdown END ==========')
  console.log('[AssistantMessage] Результат (длина:', content.length, '):', content.substring(0, 500))
  console.log('[AssistantMessage] Итого: think блоков:', thinkBlocks.length, ', таблиц:', tables.length)

  return content
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

// ─── Code blocks ────────────────────────────────────────────
:deep(.code-block) {
  margin: $spacing-md 0;
  border-radius: $radius-lg;
  overflow: hidden;
  border: 1px solid $neon-cyan-medium;
  background: var(--nc-bg-base, #{$dark-bg-secondary});
}

:deep(.code-block__header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $spacing-xs $spacing-md;
  background: rgba(58, 232, 255, 0.15);
  border-bottom: 1px solid $dark-border;
}

:deep(.code-block__lang) {
  font-size: $font-size-xs;
  font-weight: $font-weight-semibold;
  color: $neon-cyan;
  letter-spacing: $letter-spacing-wide;
}

:deep(.code-block__copy) {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--nc-text-muted, #{$dark-text-muted});
  font-size: $font-size-sm;
  padding: 0 $spacing-xs;
  &:hover { color: $neon-cyan; }
}

:deep(.code-block pre) {
  margin: 0;
  padding: $spacing-md;
  overflow-x: auto;
  font-size: $font-size-base;
  line-height: $line-height-relaxed;
  color: $neon-green;
}

[data-bs-theme="light"] :deep(.code-block) {
  background: #f8fafc;
  border-color: rgba(226, 232, 240, 0.8);
}
[data-bs-theme="light"] :deep(.code-block__lang) { color: #0f768a; }
[data-bs-theme="light"] :deep(.code-block pre) { color: #059669; }

// ─── Sources ────────────────────────────────────────────────
.message-sources {
  margin-top: $spacing-md;
  font-size: $font-size-xs;
}

.sources-toggle {
  display: flex;
  align-items: center;
  gap: $spacing-xs;
  background: rgba(58, 232, 255, 0.08);
  border: 1px solid rgba(58, 232, 255, 0.2);
  border-radius: $radius-sm;
  padding: $spacing-xs $spacing-sm;
  cursor: pointer;
  color: $neon-cyan;
  font-size: $font-size-xs;
  transition: $transition-fast;

  &:hover { background: rgba(58, 232, 255, 0.15); }

  .rotate-180 { transform: rotate(180deg); }
}

[data-bs-theme="light"] .sources-toggle {
  background: rgba(15, 118, 138, 0.08);
  border-color: rgba(15, 118, 138, 0.2);
  color: #0f768a;
}

.sources-list {
  margin-top: $spacing-xs;
  display: flex;
  flex-direction: column;
  gap: $spacing-xs;
}

.source-chip {
  display: flex;
  align-items: flex-start;
  gap: $spacing-xs;
  padding: $spacing-xs $spacing-sm;
  background: rgba(58, 232, 255, 0.05);
  border: 1px solid rgba(58, 232, 255, 0.15);
  border-radius: $radius-sm;
  font-size: $font-size-xs;
  color: var(--nc-text-secondary, #{$dark-text-secondary});
}

.source-title {
  font-weight: $font-weight-semibold;
  color: $neon-cyan;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 160px;
}

.source-preview {
  color: var(--nc-text-muted, #{$dark-text-muted});
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

// ─── Feedback ────────────────────────────────────────────────
.message-feedback {
  display: flex;
  gap: $spacing-xs;
  margin-top: $spacing-sm;
}

.feedback-btn {
  background: none;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: $radius-sm;
  padding: 2px $spacing-xs;
  cursor: pointer;
  font-size: $font-size-sm;
  opacity: 0.5;
  transition: $transition-fast;

  &:hover { opacity: 1; border-color: rgba(255,255,255,0.3); }
  &--active { opacity: 1; border-color: $neon-cyan; }
}

// ─── Suggestion chips ────────────────────────────────────────
.message-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: $spacing-xs;
  margin-top: $spacing-sm;
  padding: 0 0 0 $spacing-sm;
}

.suggestion-chip {
  display: flex;
  align-items: center;
  gap: $spacing-xs;
  padding: $spacing-xs $spacing-sm;
  background: rgba(168, 85, 247, 0.1);
  border: 1px solid rgba(168, 85, 247, 0.3);
  border-radius: 20px;
  font-size: $font-size-xs;
  color: $neon-purple;
  cursor: pointer;
  transition: $transition-fast;

  &:hover {
    background: rgba(168, 85, 247, 0.2);
    border-color: rgba(168, 85, 247, 0.5);
  }
}

[data-bs-theme="light"] .suggestion-chip {
  background: rgba(124, 58, 237, 0.08);
  border-color: rgba(124, 58, 237, 0.25);
  color: #7c3aed;
}
</style>
