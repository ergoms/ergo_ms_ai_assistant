<template>
  <div class="asst-block">
    <div class="asst-block__header">
      <div class="asst-block__header-left">
        <Table2 :size="14" />
        <span>Результат</span>
      </div>
      <span class="text-muted small">{{ data.rows }} строк</span>
    </div>
    <div class="asst-block__body asst-block__table-wrap">
      <table class="table table-sm table-striped mb-0 asst-data-table">
        <thead>
          <tr>
            <th v-for="col in data.columns" :key="col">{{ col }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in paginatedData" :key="idx">
            <td v-for="col in data.columns" :key="col">{{ formatCell(row[col]) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="totalPages > 1" class="asst-data-pagination">
      <button
        type="button"
        class="btn btn-sm btn-outline-secondary"
        :disabled="currentPage === 1"
        @click="goToPage(currentPage - 1)"
      >
        <ChevronLeft :size="16" />
      </button>
      <div class="asst-data-pagination__pages">
        <button
          v-for="page in visiblePages"
          :key="page"
          type="button"
          class="btn btn-sm"
          :class="page === currentPage ? 'btn-primary' : 'btn-outline-secondary'"
          @click="goToPage(page)"
        >
          {{ page }}
        </button>
      </div>
      <button
        type="button"
        class="btn btn-sm btn-outline-secondary"
        :disabled="currentPage === totalPages"
        @click="goToPage(currentPage + 1)"
      >
        <ChevronRight :size="16" />
      </button>
      <span class="asst-data-pagination__info">
        {{ paginationStart }}-{{ paginationEnd }} из {{ data.data.length }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Table2, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { formatCell } from '../../../js/assistantMessageFormat.js'

const ROWS_PER_PAGE = 20

const props = defineProps({
  data: { type: Object, required: true },
})

const currentPage = ref(1)

const totalPages = computed(() => {
  if (!props.data?.data?.length) return 1
  return Math.ceil(props.data.data.length / ROWS_PER_PAGE)
})

const paginatedData = computed(() => {
  if (!props.data?.data?.length) return []
  const start = (currentPage.value - 1) * ROWS_PER_PAGE
  return props.data.data.slice(start, start + ROWS_PER_PAGE)
})

const paginationStart = computed(() => (currentPage.value - 1) * ROWS_PER_PAGE + 1)

const paginationEnd = computed(() => {
  const end = currentPage.value * ROWS_PER_PAGE
  return Math.min(end, props.data?.data?.length || 0)
})

const visiblePages = computed(() => {
  const pages = []
  const total = totalPages.value
  const current = currentPage.value

  if (total <= 5) {
    for (let i = 1; i <= total; i++) pages.push(i)
  } else if (current <= 3) {
    pages.push(1, 2, 3, 4, 5)
  } else if (current >= total - 2) {
    pages.push(total - 4, total - 3, total - 2, total - 1, total)
  } else {
    pages.push(current - 2, current - 1, current, current + 1, current + 2)
  }

  return pages.filter((p) => p >= 1 && p <= total)
})

function goToPage(page) {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page
  }
}
</script>

<style lang="scss" scoped>
@import '../../../styles/_assistant-chat.scss';

.asst-block__table-wrap {
  overflow-x: auto;
  padding: 0;
}

.asst-data-table {
  font-size: 0.8125rem;
}

.asst-data-pagination {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
  padding: 0.5rem 0.625rem;
  border-top: 1px solid var(--ui-border, var(--bs-border-color));

  &__pages {
    display: flex;
    gap: 0.25rem;
  }

  &__info {
    margin-left: auto;
    font-size: 0.75rem;
    color: var(--ui-text-muted, var(--bs-secondary-color));
  }
}
</style>
