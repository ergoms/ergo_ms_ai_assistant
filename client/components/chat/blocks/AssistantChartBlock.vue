<template>
  <div class="asst-block">
    <div class="asst-block__header">
      <div class="asst-block__header-left">
        <BarChart3 :size="14" />
        <span>{{ chartConfig.title || 'График' }}</span>
      </div>
      <button type="button" class="btn btn-link btn-sm p-0" title="Скачать график" @click="downloadChart">
        <Download :size="14" />
      </button>
    </div>
    <div class="asst-block__body">
      <ApexCharts
        :key="chartKey"
        :type="chartConfig.chart_type"
        :options="apexOptions"
        :series="apexSeries"
        :height="chartConfig.height || 320"
      />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { BarChart3, Download } from 'lucide-vue-next'
import ApexCharts from 'vue3-apexcharts'
import { buildApexOptions } from '@/composables/useApexTheme.js'
import { logError } from '@/js/utils/logError.js'

const props = defineProps({
  chartConfig: { type: Object, required: true },
  messageId: { type: [String, Number], default: null },
})

const chartId = computed(() => `asst-chart-${props.messageId || 'new'}`)

const chartKey = computed(() => `${chartId.value}-${props.chartConfig.chart_type}`)

const apexSeries = computed(() => {
  const config = props.chartConfig
  const data = config.data || []

  if (config.chart_type === 'pie') {
    return data.map((item) => item.value || 0)
  }

  return [{
    name: config.series_name || 'Данные',
    data: data.map((item) => item.y || 0),
  }]
})

const apexOptions = computed(() => {
  const config = props.chartConfig
  const data = config.data || []
  const colors = config.colors?.length
    ? config.colors
    : undefined

  const overrides = {
    chart: {
      id: chartId.value,
      type: config.chart_type,
      toolbar: { show: true, tools: { download: true } },
    },
    title: {
      text: config.title || 'График',
      style: { fontSize: '14px', fontWeight: 600 },
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

async function downloadChart() {
  try {
    if (!window.ApexCharts) return

    const dataURI = await window.ApexCharts.exec(chartId.value, 'dataURI', { scale: 2 })
    if (!dataURI?.imgURI) return

    const link = document.createElement('a')
    link.href = dataURI.imgURI
    link.download = `${(props.chartConfig.title || 'chart').replace(/[^a-z0-9]/gi, '_')}.png`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  } catch (error) {
    logError('Ошибка при скачивании графика', error)
  }
}
</script>

<style lang="scss" scoped>
@import '../../../styles/_assistant-chat.scss';
</style>
