<template>
  <div 
    class="neural-message" 
    :class="[
      `neural-message--${message.type}`,
      { 'neural-message--streaming': message.streaming || message.isStreaming }
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
          <button class="code-copy" @click="copySql" :title="sqlCopied ? t('common.copied') : t('common.copy')">
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
          <button class="chart-download" @click="downloadChart" :title="t('ai_assistant.message.downloadChart')">
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
            <span>{{ t('ai_assistant.message.resultLabel') }}</span>
          </div>
          <div class="data-header__right">
            <span class="data-count">{{ t('ai_assistant.message.rowsCount', message.data.rows) }}</span>
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
              {{ t('ai_assistant.message.goToPage') }}
            </button>
          </div>
          
          <span class="pagination-info">
            {{ paginationStart }}-{{ paginationEnd }} {{ t('common.of') }} {{ message.data.data.length }}
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
import { logError, logWarn } from '@/js/utils/logError.js'
import { buildApexOptions } from '@/composables/useApexTheme.js'
import { useAppI18n } from '@/i18n/useAppI18n.js'
import { getCurrentBcp47 } from '@/i18n/index.js'
import ApexCharts from 'vue3-apexcharts'

const { t } = useAppI18n()

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
  if (props.message.type === 'user') return t('ai_assistant.you')
  return props.moduleConfig?.name || 'Neural'
})

const formattedTime = computed(() => {
  if (!props.message.timestamp) return ''
  const date = new Date(props.message.timestamp)
  return date.toLocaleTimeString(getCurrentBcp47(), { hour: '2-digit', minute: '2-digit' })
})

const formatProcessingTime = (ms) => {
  if (!ms) return ''
  if (ms < 1000) return t('ai_assistant.message.durationMs', { ms })
  const seconds = (ms / 1000).toFixed(1)
  return t('ai_assistant.message.durationSec', { sec: seconds })
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
    logError('Ошибка парсинга таблицы:', error)
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
    logError('Не удалось скопировать:', err)
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
      logError('Ошибка скачивания файла:', response.message)
    }
  } catch (error) {
    logError('Ошибка при скачивании документа:', error)
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
      name: config.series_name || t('ai_assistant.message.seriesDefaultName'),
      data: data.map(item => item.y || 0)
    }]
  }
})

const apexOptions = computed(() => {
  if (!chartConfig.value) return {}

  const config = chartConfig.value
  const data = config.data || []
  const colors = config.colors?.length ? config.colors : undefined

  const overrides = {
    chart: {
      id: `chart-${props.message.id || Date.now()}`,
      type: config.chart_type,
      toolbar: { show: true, tools: { download: true } },
    },
    title: {
      text: config.title || t('ai_assistant.message.chartDefaultTitle'),
      style: { fontSize: '16px', fontWeight: 600 },
    },
    legend: {
      show: config.show_legend !== false,
      position: 'bottom',
    },
  }

  if (colors) {
    overrides.colors = colors
  }

  if (config.chart_type === 'pie') {
    overrides.labels = data.map((item) => item.label || '')
    overrides.dataLabels = {
      enabled: true,
      formatter: (val) => `${val.toFixed(1)}%`,
    }
  } else {
    overrides.xaxis = {
      categories: data.map((item) => String(item.x || '')),
      title: { text: config.x_axis_label || '' },
    }
    overrides.yaxis = {
      title: { text: config.y_axis_label || '' },
    }
  }

  return buildApexOptions(overrides)
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
        logWarn('Не удалось получить изображение графика через ApexCharts API')
      }
    } else {
      logWarn('ApexCharts API недоступен для экспорта графика')
    }
  } catch (error) {
    logError('Ошибка при скачивании графика:', error)
  }
}
</script>

<style lang="scss" scoped>
@import './HubMessage.scss';
</style>
