<template>
  <div 
    class="neural-message" 
    :class="[
      `neural-message--${message.type}`,
      { 'neural-message--streaming': message.streaming }
    ]"
  >
    <!-- Connection line decoration -->
    <div class="message-connector">
      <div class="connector-line"></div>
      <div class="connector-node"></div>
    </div>

    <!-- Avatar -->
    <div class="message-avatar" :style="avatarStyle">
      <div class="avatar-core">
        <User v-if="message.type === 'user'" :size="20" />
        <component v-else :is="moduleIcon" :size="20" />
      </div>
      <div class="avatar-ring"></div>
      <div v-if="message.streaming" class="avatar-pulse"></div>
    </div>

    <!-- Content -->
    <div class="message-body">
      <!-- Header -->
      <div class="message-header">
        <span class="message-author">{{ authorName }}</span>
        <div class="message-time-info">
          <span class="message-time">{{ formattedTime }}</span>
          <span v-if="message.processing_time_ms" class="message-processing-time">
            {{ formatProcessingTime(message.processing_time_ms) }}
          </span>
          <span 
            v-if="message.skill_name" 
            class="message-skill-badge"
            :title="skillCallTooltip"
          >
            <Sparkles :size="12" />
            {{ message.skill_name }}
          </span>
        </div>
      </div>

      <!-- Text Content -->
      <div class="message-content" v-html="formattedContent" @click="handleDownloadClick"></div>

      <!-- Streaming Cursor -->
      <span v-if="message.streaming" class="streaming-cursor"></span>

      <!-- Stage Indicator -->
      <div v-if="message.stage" class="message-stage">
        <div class="stage-spinner">
          <div class="spinner-ring"></div>
        </div>
        <span>{{ message.stage }}</span>
      </div>

      <!-- SQL Block -->
      <div v-if="message.sql" class="message-code-block">
        <div class="code-header">
          <div class="code-header__left">
            <Terminal :size="14" />
            <span>SQL QUERY</span>
          </div>
          <button class="code-copy" @click="copySql" :title="sqlCopied ? 'Скопировано!' : 'Копировать'">
            <Check v-if="sqlCopied" :size="14" />
            <Copy v-else :size="14" />
          </button>
        </div>
        <div class="code-content">
          <pre><code>{{ message.sql }}</code></pre>
          <div class="code-glow"></div>
        </div>
      </div>

      <!-- Chart -->
      <div v-if="chartConfig" class="message-chart">
        <div class="chart-header">
          <div class="chart-header__left">
            <Database :size="14" />
            <span>{{ chartConfig.title }}</span>
          </div>
          <button class="chart-download" @click="downloadChart" title="Скачать график">
            <Download :size="14" />
          </button>
        </div>
        <div class="chart-wrapper" :id="`chart-${message.id || Date.now()}`">
          <ApexCharts
            :key="`chart-${message.id || Date.now()}-${chartConfig.chart_type}`"
            :type="chartConfig.chart_type"
            :options="apexOptions"
            :series="apexSeries"
            :height="chartConfig.height || 400"
          />
        </div>
      </div>

      <!-- Data Table -->
      <div v-if="message.data?.data?.length" class="message-data">
        <div class="data-header">
          <div class="data-header__left">
            <Grid3x3 :size="14" />
            <span>РЕЗУЛЬТАТ</span>
          </div>
          <div class="data-header__right">
            <span class="data-count">{{ message.data.rows }} строк</span>
          </div>
        </div>
        
        <div class="data-table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th v-for="col in message.data.columns" :key="col">
                  <span class="th-content">{{ col }}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, idx) in paginatedData" :key="idx">
                <td v-for="col in message.data.columns" :key="col">
                  <span class="cell-value">{{ formatCell(row[col]) }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        
        <!-- Pagination -->
        <div v-if="totalPages > 1" class="data-pagination">
          <button 
            class="pagination-btn" 
            :disabled="currentPage === 1"
            @click="goToPage(currentPage - 1)"
          >
            <ChevronLeft :size="16" />
          </button>
          
          <div class="pagination-pages">
            <button 
              v-for="page in visiblePages" 
              :key="page"
              class="pagination-page"
              :class="{ 'pagination-page--active': page === currentPage }"
              @click="goToPage(page)"
            >
              {{ page }}
            </button>
          </div>
          
          <button 
            class="pagination-btn" 
            :disabled="currentPage === totalPages"
            @click="goToPage(currentPage + 1)"
          >
            <ChevronRight :size="16" />
          </button>
          
          <div class="pagination-goto">
            <input 
              type="number" 
              class="pagination-input"
              v-model.number="pageInput"
              :min="1"
              :max="totalPages"
              :placeholder="currentPage"
              @keydown.enter="goToInputPage"
            />
            <span class="pagination-goto-label">/ {{ totalPages }}</span>
            <button 
              class="pagination-goto-btn"
              @click="goToInputPage"
              :disabled="!pageInput || pageInput < 1 || pageInput > totalPages"
            >
              Перейти
            </button>
          </div>
          
          <span class="pagination-info">
            {{ paginationStart }}-{{ paginationEnd }} из {{ message.data.data.length }}
          </span>
        </div>
      </div>

      <!-- Error -->
      <div v-if="message.error" class="message-error">
        <AlertTriangle :size="16" />
        <span>{{ message.error }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { 
  User, Bot, Terminal, Copy, Check, 
  Grid3x3, AlertTriangle, Database, ChevronLeft, ChevronRight, Sparkles, Download
} from 'lucide-vue-next'
import { apiClient } from '@/js/api/manager'
import { sanitizeHtml } from '@/js/utils/sanitize'
import ApexCharts from 'vue3-apexcharts'

const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
  moduleConfig: {
    type: Object,
    default: null,
  },
})

const sqlCopied = ref(false)

// Pagination state
const ROWS_PER_PAGE = 20
const currentPage = ref(1)

const totalPages = computed(() => {
  if (!props.message.data?.data?.length) return 1
  return Math.ceil(props.message.data.data.length / ROWS_PER_PAGE)
})

const paginatedData = computed(() => {
  if (!props.message.data?.data?.length) return []
  const start = (currentPage.value - 1) * ROWS_PER_PAGE
  const end = start + ROWS_PER_PAGE
  return props.message.data.data.slice(start, end)
})

const paginationStart = computed(() => {
  return (currentPage.value - 1) * ROWS_PER_PAGE + 1
})

const paginationEnd = computed(() => {
  const end = currentPage.value * ROWS_PER_PAGE
  return Math.min(end, props.message.data?.data?.length || 0)
})

const visiblePages = computed(() => {
  const pages = []
  const total = totalPages.value
  const current = currentPage.value
  
  if (total <= 5) {
    for (let i = 1; i <= total; i++) pages.push(i)
  } else {
    if (current <= 3) {
      pages.push(1, 2, 3, 4, 5)
    } else if (current >= total - 2) {
      pages.push(total - 4, total - 3, total - 2, total - 1, total)
    } else {
      pages.push(current - 2, current - 1, current, current + 1, current + 2)
    }
  }
  
  return pages.filter(p => p >= 1 && p <= total)
})

const goToPage = (page) => {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page
  }
}

// Page input for direct navigation
const pageInput = ref(null)

const goToInputPage = () => {
  if (pageInput.value && pageInput.value >= 1 && pageInput.value <= totalPages.value) {
    currentPage.value = pageInput.value
    pageInput.value = null
  }
}

const moduleIcon = computed(() => {
  if (props.moduleConfig?.icon) return props.moduleConfig.icon
  return Bot
})

const moduleColor = computed(() => {
  return props.moduleConfig?.color || '#3ae8ff'
})

const avatarStyle = computed(() => {
  if (props.message.type === 'user') {
    return { '--avatar-color': '#4f8fff' }
  }
  return { '--avatar-color': moduleColor.value }
})

const authorName = computed(() => {
  if (props.message.type === 'user') return 'Вы'
  return props.moduleConfig?.name || 'Neural'
})

const formattedTime = computed(() => {
  if (!props.message.timestamp) return ''
  const date = new Date(props.message.timestamp)
  return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
})

const formatProcessingTime = (ms) => {
  if (!ms) return ''
  if (ms < 1000) return `${ms}мс`
  const seconds = (ms / 1000).toFixed(1)
  return `${seconds}с`
}

const formattedContent = computed(() => {
  if (!props.message.content) return ''
  
  let content = props.message.content
  
  // Обрабатываем markdown таблицы ПЕРЕД обработкой переносов строк
  // Ищем паттерн: строки с |, включая разделитель с ---
  // Более простой и надежный паттерн - ищем блоки с несколькими строками, начинающимися с |
  const tableRegex = /((?:\|[^\n]+\|\s*\n)+)/g
  const tables = []
  let tableIndex = 0
  
  content = content.replace(tableRegex, (match) => {
    // Проверяем, что это действительно таблица (есть разделитель с ---)
    const hasSeparator = /\|[\s\-:]+\|/.test(match)
    if (!hasSeparator) {
      return match // Не таблица, возвращаем как есть
    }
    
    // Проверяем, что есть минимум 2 строки (заголовок + разделитель)
    const lines = match.split('\n').filter(l => l.trim().startsWith('|'))
    if (lines.length < 2) {
      return match // Не таблица
    }
    
    const tableId = `markdown-table-${tableIndex++}`
    const htmlTable = parseMarkdownTable(match)
    if (htmlTable === match) {
      return match // Парсинг не удался, возвращаем как есть
    }
    tables.push({ id: tableId, html: htmlTable })
    return `\n\n__TABLE_PLACEHOLDER_${tableId}__\n\n`
  })
  
  // Обрабатываем остальной markdown
  content = content
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Markdown ссылки [text](url) -> кликабельные ссылки с data-атрибутом для скачивания
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, text, url) => {
      // Проверяем, это ссылка на документ для скачивания?
      if (url.includes('/api/ai_assistant/documents/download/')) {
        return `<a href="#" class="download-link" data-download-url="${url}" data-filename="${text}">${text}</a>`
      }
      // Обычная ссылка
      return `<a href="${url}" target="_blank">${text}</a>`
    })
  
  // Заменяем плейсхолдеры таблиц на HTML ПЕРЕД заменой переносов строк
  tables.forEach(table => {
    const placeholder = `__TABLE_PLACEHOLDER_${table.id}__`
    content = content.replace(placeholder, table.html)
  })
  
  // Заменяем переносы строк на <br> в последнюю очередь
  content = content.replace(/\n/g, '<br>')
  
  return sanitizeHtml(content)
})

const parseMarkdownTable = (markdownTable) => {
  try {
    const lines = markdownTable.trim().split('\n').map(line => line.trim()).filter(line => line)
    
    if (lines.length < 2) return markdownTable // Не таблица
    
    // Находим строку с разделителем
    let separatorIndex = -1
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].match(/^\|[\s\-:|]+\|$/)) {
        separatorIndex = i
        break
      }
    }
    
    if (separatorIndex === -1) return markdownTable // Нет разделителя
    
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
    
    if (headers.length === 0) return markdownTable // Нет заголовков
    
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
      .filter(row => row.length > 0)
    
    // Формируем HTML таблицу
    let html = '<div class="markdown-table-wrapper"><table class="markdown-table">'
    
    // Заголовки
    html += '<thead><tr>'
    headers.forEach(header => {
      html += `<th>${escapeHtml(header)}</th>`
    })
    html += '</tr></thead>'
    
    // Данные
    if (rows.length > 0) {
      html += '<tbody>'
      rows.forEach(row => {
        html += '<tr>'
        headers.forEach((_, index) => {
          const cell = row[index] || ''
          html += `<td>${escapeHtml(cell)}</td>`
        })
        html += '</tr>'
      })
      html += '</tbody>'
    }
    
    html += '</table></div>'
    
    return html
  } catch (error) {
    console.error('Ошибка парсинга таблицы:', error)
    return markdownTable
  }
}

const escapeHtml = (text) => {
  if (!text) return ''
  const div = document.createElement('div')
  div.textContent = String(text)
  return div.innerHTML
}

const skillCallTooltip = computed(() => {
  if (!props.message.skill_call) return ''
  return JSON.stringify(props.message.skill_call, null, 2)
})

const formatCell = (value) => {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'number') {
    return Number.isInteger(value) ? value : value.toFixed(2)
  }
  const str = String(value)
  return str.length > 50 ? str.slice(0, 47) + '...' : str
}

const copySql = async () => {
  if (!props.message.sql) return
  try {
    await navigator.clipboard.writeText(props.message.sql)
    sqlCopied.value = true
    setTimeout(() => { sqlCopied.value = false }, 2000)
  } catch (err) {
    console.error('Не удалось скопировать:', err)
  }
}

const handleDownloadClick = async (event) => {
  const link = event.target.closest('.download-link')
  if (!link) return
  
  event.preventDefault()
  event.stopPropagation()
  
  const downloadUrl = link.getAttribute('data-download-url')
  const filename = link.getAttribute('data-filename') || 'document.docx'
  
  if (!downloadUrl) return
  
  try {
    // Обрабатываем как абсолютный, так и относительный URL
    let endpoint
    if (downloadUrl.startsWith('http://') || downloadUrl.startsWith('https://')) {
      // Абсолютный URL - извлекаем путь
      const url = new URL(downloadUrl)
      endpoint = url.pathname.replace('/api/', '')
    } else {
      // Относительный URL - убираем /api/ если есть
      endpoint = downloadUrl.startsWith('/api/') 
        ? downloadUrl.replace('/api/', '')
        : downloadUrl
    }
    
    // Скачиваем файл через apiClient с авторизацией
    const response = await apiClient.downloadFile(endpoint, {}, 'GET', true)
    
    if (response.success && response.data instanceof Blob) {
      // Создаём Blob URL и скачиваем файл
      const blobUrl = URL.createObjectURL(response.data)
      const a = document.createElement('a')
      a.href = blobUrl
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(blobUrl)
    } else {
      console.error('Ошибка скачивания файла:', response.message)
    }
  } catch (error) {
    console.error('Ошибка при скачивании документа:', error)
  }
}

// Chart configuration
const chartConfig = computed(() => {
  return props.message.metadata?.chart_config || props.message.chart_config
})

const apexSeries = computed(() => {
  if (!chartConfig.value) return []
  
  const config = chartConfig.value
  const data = config.data || []
  
  if (config.chart_type === 'pie') {
    // Для pie графика возвращаем массив значений (labels будут в options)
    return data.map(item => item.value || 0)
  } else {
    // Для остальных типов возвращаем серию с данными
    return [{
      name: config.series_name || 'Данные',
      data: data.map(item => item.y || 0)
    }]
  }
})

const apexOptions = computed(() => {
  if (!chartConfig.value) return {}
  
  const config = chartConfig.value
  const data = config.data || []
  const colors = config.colors && config.colors.length > 0 
    ? config.colors 
    : ['#10B981', '#3B82F6', '#8B5CF6', '#F59E0B', '#EF4444', '#06B6D4']
  
  const baseOptions = {
    chart: {
      id: `chart-${props.message.id || Date.now()}`,
      type: config.chart_type,
      toolbar: {
        show: true,
        tools: {
          download: true
        }
      }
    },
    title: {
      text: config.title || 'График',
      style: {
        fontSize: '16px',
        fontWeight: 600,
        color: '#E5E7EB'
      }
    },
    colors: colors,
    legend: {
      show: config.show_legend !== false,
      position: 'bottom'
    },
    theme: {
      mode: 'dark'
    },
    tooltip: {
      theme: 'dark'
    }
  }
  
  if (config.chart_type === 'pie') {
    // Для pie графика
    baseOptions.labels = data.map(item => item.label || '')
    baseOptions.dataLabels = {
      enabled: true,
      formatter: (val) => `${val.toFixed(1)}%`
    }
  } else {
    // Для остальных типов
    baseOptions.xaxis = {
      categories: data.map(item => String(item.x || '')),
      title: {
        text: config.x_axis_label || ''
      }
    }
    baseOptions.yaxis = {
      title: {
        text: config.y_axis_label || ''
      }
    }
  }
  
  return baseOptions
})

const downloadChart = async () => {
  if (!chartConfig.value) return
  
  try {
    const chartId = `chart-${props.message.id || Date.now()}`
    
    // Используем ApexCharts API для экспорта
    if (window.ApexCharts) {
      const dataURI = await window.ApexCharts.exec(chartId, 'dataURI', {
        scale: 2
      })
      
      if (dataURI && dataURI.imgURI) {
        const link = document.createElement('a')
        link.href = dataURI.imgURI
        link.download = `${(chartConfig.value.title || 'chart').replace(/[^a-z0-9]/gi, '_')}.png`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
      } else {
        console.warn('Не удалось получить изображение графика через ApexCharts API')
      }
    } else {
      console.warn('ApexCharts API недоступен')
    }
  } catch (error) {
    console.error('Ошибка при скачивании графика:', error)
  }
}
</script>

<style lang="scss" scoped>
@import '../styles/variables';

.neural-message {
  display: flex;
  gap: $spacing-md;
  padding: $spacing-lg $spacing-xl;
  position: relative;
  transition: all $transition-fast;

  &:hover {
    background: rgba(58, 232, 255, 0.02);

    .connector-line {
      opacity: 0.5;
    }

    .connector-node {
      transform: scale(1.2);
      box-shadow: $glow-cyan;
    }
  }

  &--user {
    .message-body {
      background: linear-gradient(135deg, rgba(79, 143, 255, 0.1), rgba(79, 143, 255, 0.05));
      border-color: rgba(79, 143, 255, 0.2);
    }

    .connector-node {
      background: $neon-blue;
    }
  }

  &--assistant {
    .message-body {
      background: linear-gradient(135deg, rgba(58, 232, 255, 0.08), rgba(168, 85, 247, 0.05));
      border-color: rgba(58, 232, 255, 0.15);
    }
  }

  &--streaming {
    .message-content {
      &::after {
        content: '';
        display: inline-block;
        width: 2px;
        height: 1.2em;
        background: var(--accent, #{$neon-cyan});
        margin-left: 4px;
        animation: cursor-blink 1s step-end infinite;
        vertical-align: text-bottom;
      }
    }
  }
}

// Connector decoration
.message-connector {
  position: absolute;
  left: calc(#{$spacing-xl} + 22px);
  top: 0;
  bottom: 0;
  width: 20px;
  pointer-events: none;
}

.connector-line {
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 1px;
  background: linear-gradient(
    to bottom,
    transparent,
    var(--avatar-color, #{$neon-cyan}),
    transparent
  );
  opacity: 0.2;
  transition: opacity $transition-fast;
}

.connector-node {
  position: absolute;
  left: 50%;
  top: calc(#{$spacing-lg} + 22px);
  width: 8px;
  height: 8px;
  background: var(--avatar-color, #{$neon-cyan});
  border-radius: 50%;
  transform: translateX(-50%);
  transition: all $transition-fast;
}

// Avatar
.message-avatar {
  width: $message-avatar-size;
  height: $message-avatar-size;
  position: relative;
  flex-shrink: 0;
  z-index: 1;
}

.avatar-core {
  position: absolute;
  inset: 4px;
  background: linear-gradient(135deg, var(--avatar-color), rgba(0, 0, 0, 0.5));
  border-radius: $radius-md;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  z-index: 2;
}

.avatar-ring {
  position: absolute;
  inset: 0;
  border: 2px solid var(--avatar-color);
  border-radius: $radius-md + 2px;
  opacity: 0.5;
}

.avatar-pulse {
  position: absolute;
  inset: -4px;
  border: 1px solid var(--avatar-color);
  border-radius: $radius-lg;
  animation: avatar-pulse 2s ease-out infinite;
}

@keyframes avatar-pulse {
  0% { transform: scale(0.9); opacity: 0.8; }
  100% { transform: scale(1.2); opacity: 0; }
}

// Body
.message-body {
  flex: 1;
  min-width: 0;
  max-width: $message-max-width;
  background: color-mix(in srgb, var(--bg-elevated) 30%, transparent);
  backdrop-filter: blur(30px);
  -webkit-backdrop-filter: blur(30px);
  border: 1px solid var(--border-subtle);
  border-radius: $radius-lg;
  padding: $spacing-md $spacing-lg;
  position: relative;

  // Corner cuts decoration
  &::before,
  &::after {
    content: '';
    position: absolute;
    width: 12px;
    height: 12px;
    border-style: solid;
    border-color: var(--avatar-color, #{$neon-cyan});
    opacity: 0.3;
  }

  &::before {
    top: -1px;
    left: -1px;
    border-width: 1px 0 0 1px;
    border-radius: $radius-lg 0 0 0;
  }

  &::after {
    bottom: -1px;
    right: -1px;
    border-width: 0 1px 1px 0;
    border-radius: 0 0 $radius-lg 0;
  }
}

.message-header {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  margin-bottom: $spacing-sm;
}

.message-author {
  font-family: $font-family-display;
  font-size: $font-size-sm;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: $letter-spacing-wide;
}

.message-time-info {
  display: flex;
  align-items: center;
  gap: $spacing-xs;
}

.message-time {
  font-family: $font-family-mono;
  font-size: $font-size-xs;
  color: var(--text-muted);
}

.message-processing-time {
  font-family: $font-family-mono;
  font-size: $font-size-xs;
  color: var(--accent);
  padding: 2px 6px;
  background: rgba(58, 232, 255, 0.1);
  border-radius: $radius-sm;
  border: 1px solid rgba(58, 232, 255, 0.2);
}

.message-skill-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-family: $font-family-mono;
  font-size: $font-size-xs;
  font-weight: 600;
  color: #a855f7;
  padding: 2px 8px;
  background: rgba(168, 85, 247, 0.15);
  border-radius: $radius-sm;
  border: 1px solid rgba(168, 85, 247, 0.3);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  cursor: help;
  transition: all $transition-fast;
  white-space: pre-wrap;
  
  svg {
    color: #a855f7;
  }
  
  &:hover {
    background: rgba(168, 85, 247, 0.25);
    border-color: rgba(168, 85, 247, 0.5);
    box-shadow: 0 0 8px rgba(168, 85, 247, 0.3);
  }
}

.message-content {
  font-family: Arial, sans-serif;
  font-size: $message-font-size;
  font-weight: 200;
  line-height: $line-height-relaxed;
  color: var(--text-secondary);
  word-wrap: break-word;

  :deep(strong) {
    font-weight: 600;
    color: var(--text-primary);
  }

  :deep(em) {
    font-style: italic;
    color: var(--accent);
  }

  :deep(code) {
    font-family: $font-family-mono;
    font-size: 0.9em;
    background: rgba(58, 232, 255, 0.1);
    padding: 2px 8px;
    border-radius: $radius-sm;
    color: $neon-cyan;
    border: 1px solid rgba(58, 232, 255, 0.2);
  }

  :deep(.download-link) {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(16, 185, 129, 0.08));
    border: 1px solid rgba(16, 185, 129, 0.4);
    border-radius: $radius-md;
    color: $neon-green;
    font-weight: 600;
    text-decoration: none;
    transition: all $transition-fast;
    cursor: pointer;

    &::before {
      content: '📄';
      font-size: 1.1em;
    }

    &:hover {
      background: linear-gradient(135deg, rgba(16, 185, 129, 0.25), rgba(16, 185, 129, 0.15));
      border-color: $neon-green;
      box-shadow: 0 0 12px rgba(16, 185, 129, 0.3);
      transform: translateY(-1px);
    }

    &:active {
      transform: translateY(0);
    }
  }

  :deep(.markdown-table-wrapper) {
    margin: $spacing-md 0;
    overflow-x: auto;
    border-radius: $radius-md;
    max-width: 100%;
  }

  :deep(.markdown-table) {
    width: 100%;
    min-width: 500px;
    border-collapse: collapse;
    font-family: Arial, sans-serif;
    font-size: $font-size-sm;
    background: var(--bg-base);
    border: 1px solid rgba(58, 232, 255, 0.2);
    
    th, td {
      padding: $spacing-sm $spacing-md;
      text-align: left;
      border-bottom: 1px solid rgba(58, 232, 255, 0.1);
      word-wrap: break-word;
      white-space: normal;
      font-family: Arial, sans-serif;
    }
    
    th {
      background: rgba(58, 232, 255, 0.1);
      font-weight: 600;
      color: var(--text-primary);
      font-family: Arial, sans-serif;
      text-transform: uppercase;
      font-size: $font-size-xs;
      letter-spacing: $letter-spacing-wide;
      position: sticky;
      top: 0;
      z-index: 1;
    }
    
    td {
      color: var(--text-secondary);
      font-family: Arial, sans-serif;
    }
    
    tbody tr {
      transition: background $transition-fast;
      
      &:hover {
        background: rgba(58, 232, 255, 0.05);
      }
      
      &:last-child td {
        border-bottom: none;
      }
    }
  }

  // Chart styles
  .message-chart {
    margin-top: $spacing-md;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(58, 232, 255, 0.2);
    border-radius: $radius-md;
    overflow: hidden;

    .chart-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: $spacing-sm $spacing-md;
      background: rgba(58, 232, 255, 0.05);
      border-bottom: 1px solid rgba(58, 232, 255, 0.1);

      &__left {
        display: flex;
        align-items: center;
        gap: $spacing-sm;
        color: $neon-cyan;
        font-weight: 600;
        font-size: 0.9rem;
      }

      .chart-download {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.3);
        border-radius: $radius-sm;
        color: $neon-green;
        cursor: pointer;
        transition: all $transition-fast;

        &:hover {
          background: rgba(16, 185, 129, 0.2);
          border-color: $neon-green;
          transform: translateY(-1px);
        }

        &:active {
          transform: translateY(0);
        }
      }
    }

    .chart-wrapper {
      padding: $spacing-md;
      background: rgba(0, 0, 0, 0.2);
    }
  }
}

@keyframes cursor-blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

// Stage indicator
.message-stage {
  display: inline-flex;
  align-items: center;
  gap: $spacing-sm;
  margin-top: $spacing-md;
  padding: $spacing-sm $spacing-md;
  background: rgba(58, 232, 255, 0.1);
  border: 1px solid rgba(58, 232, 255, 0.2);
  border-radius: $radius-full;
  font-family: $font-family-mono;
  font-size: $font-size-sm;
  color: $neon-cyan;
}

.stage-spinner {
  width: 16px;
  height: 16px;
  position: relative;
}

.spinner-ring {
  position: absolute;
  inset: 0;
  border: 2px solid transparent;
  border-top-color: $neon-cyan;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

// Code block
.message-code-block {
  margin-top: $spacing-md;
  border-radius: $radius-lg;
  overflow: hidden;
  background: var(--bg-base);
  border: 1px solid rgba(58, 232, 255, 0.2);
}

.code-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $spacing-sm $spacing-md;
  background: rgba(58, 232, 255, 0.05);
  border-bottom: 1px solid rgba(58, 232, 255, 0.1);
}

.code-header__left {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  font-family: $font-family-mono;
  font-size: $font-size-xs;
  font-weight: 600;
  color: $neon-cyan;
  letter-spacing: $letter-spacing-wider;
}

.code-copy {
  padding: $spacing-xs;
  background: transparent;
  border: 1px solid rgba(58, 232, 255, 0.3);
  border-radius: $radius-sm;
  color: $neon-cyan;
  cursor: pointer;
  transition: all $transition-fast;
  display: flex;
  align-items: center;
  justify-content: center;

  &:hover {
    background: $neon-cyan;
    color: $dark-bg-primary;
  }
}

.code-content {
  position: relative;
  padding: $spacing-md;
  overflow-x: auto;

  pre {
    margin: 0;
    font-family: $font-family-mono;
    font-size: $font-size-sm;
    line-height: $line-height-base;
    color: #a3e635;
  }
}

.code-glow {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 40px;
  background: linear-gradient(to bottom, rgba(163, 230, 53, 0.05), transparent);
  pointer-events: none;
}

// Data table
.message-data {
  margin-top: $spacing-md;
  border-radius: $radius-lg;
  overflow: hidden;
  border: 1px solid rgba(16, 185, 129, 0.2);
  background: var(--bg-base);
}

.data-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $spacing-sm $spacing-md;
  background: rgba(16, 185, 129, 0.05);
  border-bottom: 1px solid rgba(16, 185, 129, 0.1);
}

.data-header__left {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  font-family: $font-family-mono;
  font-size: $font-size-xs;
  font-weight: 600;
  color: $neon-green;
  letter-spacing: $letter-spacing-wider;
}

.data-count {
  font-family: $font-family-mono;
  font-size: $font-size-xs;
  color: var(--text-muted);
  padding: 2px 8px;
  background: rgba(16, 185, 129, 0.1);
  border-radius: $radius-sm;
}

.data-table-wrapper {
  overflow-x: auto;
  max-height: 300px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: $font-size-sm;

  th, td {
    padding: $spacing-sm $spacing-md;
    text-align: left;
    border-bottom: 1px solid rgba(16, 185, 129, 0.1);
    white-space: nowrap;
  }

  th {
    background: rgba(16, 185, 129, 0.05);
    font-family: $font-family-mono;
    font-weight: 600;
    color: $neon-green;
    font-size: $font-size-xs;
    text-transform: uppercase;
    letter-spacing: $letter-spacing-wide;
    position: sticky;
    top: 0;
    z-index: 1;
  }

  td {
    color: var(--text-primary);
  }

  tbody tr {
    transition: background $transition-fast;

    &:hover {
      background: rgba(16, 185, 129, 0.05);
    }
  }
}

.cell-value {
  display: inline-block;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}

// Pagination
.data-pagination {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  padding: $spacing-sm $spacing-md;
  background: rgba(16, 185, 129, 0.02);
  border-top: 1px solid rgba(16, 185, 129, 0.1);
}

.pagination-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: transparent;
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: $radius-sm;
  color: $neon-green;
  cursor: pointer;
  transition: all $transition-fast;

  &:hover:not(:disabled) {
    background: rgba(16, 185, 129, 0.1);
    border-color: $neon-green;
  }

  &:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }
}

.pagination-pages {
  display: flex;
  gap: 4px;
}

.pagination-page {
  min-width: 32px;
  height: 32px;
  padding: 0 $spacing-sm;
  background: transparent;
  border: 1px solid rgba(16, 185, 129, 0.2);
  border-radius: $radius-sm;
  color: var(--text-secondary);
  font-family: $font-family-mono;
  font-size: $font-size-sm;
  cursor: pointer;
  transition: all $transition-fast;

  &:hover {
    background: rgba(16, 185, 129, 0.1);
    border-color: rgba(16, 185, 129, 0.4);
    color: $neon-green;
  }

  &--active {
    background: $neon-green;
    border-color: $neon-green;
    color: $dark-bg-primary;
    font-weight: 600;

    &:hover {
      background: $neon-green;
      color: $dark-bg-primary;
    }
  }
}

.pagination-goto {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: $spacing-sm;
  padding-left: $spacing-sm;
  border-left: 1px solid rgba(16, 185, 129, 0.2);
}

.pagination-input {
  width: 60px;
  height: 28px;
  padding: 0 $spacing-sm;
  background: var(--bg-elevated);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: $radius-sm;
  color: var(--text-primary);
  font-family: $font-family-mono;
  font-size: $font-size-sm;
  text-align: center;
  outline: none;
  transition: all $transition-fast;

  &:focus {
    border-color: $neon-green;
    box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.15);
  }

  &::placeholder {
    color: var(--text-muted);
  }

  // Hide spinners
  &::-webkit-outer-spin-button,
  &::-webkit-inner-spin-button {
    -webkit-appearance: none;
    margin: 0;
  }
  -moz-appearance: textfield;
}

.pagination-goto-label {
  font-family: $font-family-mono;
  font-size: $font-size-sm;
  color: var(--text-muted);
}

.pagination-goto-btn {
  padding: 4px $spacing-sm;
  background: transparent;
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: $radius-sm;
  color: $neon-green;
  font-size: $font-size-xs;
  font-weight: 500;
  cursor: pointer;
  transition: all $transition-fast;

  &:hover:not(:disabled) {
    background: rgba(16, 185, 129, 0.1);
    border-color: $neon-green;
  }

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
}

.pagination-info {
  margin-left: auto;
  font-family: $font-family-mono;
  font-size: $font-size-xs;
  color: var(--text-muted);
}

// Error
.message-error {
  display: inline-flex;
  align-items: center;
  gap: $spacing-sm;
  margin-top: $spacing-md;
  padding: $spacing-sm $spacing-md;
  background: rgba(255, 51, 102, 0.1);
  border: 1px solid rgba(255, 51, 102, 0.3);
  border-radius: $radius-md;
  font-size: $font-size-sm;
  color: $neon-red;
}
</style>



