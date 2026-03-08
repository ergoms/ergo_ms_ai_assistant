<template>
  <div
    v-if="isVisible"
    class="assistant-chat assistant-chat--visible"
  >
    <div class="assistant-chat__header">
      <div class="assistant-chat__title">
        <Database :size="20" class="me-2" />
        <span>AI Ассистент - BI Анализ</span>
      </div>
      <div class="assistant-chat__controls">
        <router-link
          to="/ai-assistant"
          class="control-btn"
          title="Открыть AI Hub"
        >
          <ExternalLink :size="18" />
        </router-link>
      </div>
    </div>

    <div class="assistant-chat__wip">
      <div class="wip-badge">
        <Construction :size="40" class="wip-badge__icon" />
        <span class="wip-badge__title">В разработке</span>
        <p class="wip-badge__desc">
          Функциональность BI-анализа табличных данных<br />
          находится в активной разработке и будет<br />
          доступна в ближайших обновлениях.
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Database, ExternalLink, Construction } from 'lucide-vue-next'

defineProps({
  isVisible: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['bi-query', 'close'])

defineExpose({
  addAssistantMessage: () => {},
  updateStreamingMessage: () => {},
  finalizeStreamingMessage: () => {},
  setTyping: () => {},
})
</script>

<style scoped>
.assistant-chat {
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  width: auto;
  height: 550px;
  background: linear-gradient(145deg, #ffffff, #f8f9fa);
  border-radius: 12px;
  box-shadow:
    0 12px 40px rgba(220, 53, 69, 0.15),
    0 4px 12px rgba(0, 0, 0, 0.1);
  border: 2px solid rgba(220, 53, 69, 0.1);
  z-index: 9998;
  display: flex;
  flex-direction: column;
  transform: translateY(20px) scale(0.95);
  opacity: 0;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  backdrop-filter: blur(10px);
  margin-bottom: 10px;
}

.assistant-chat--visible {
  transform: translateY(0) scale(1);
  opacity: 1;
}

.assistant-chat__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: linear-gradient(135deg, #dc3545, #c82333);
  border-radius: 12px 12px 0 0;
  color: white;
  flex-shrink: 0;
}

.assistant-chat__title {
  display: flex;
  align-items: center;
  font-weight: 600;
  font-size: 14px;
}

.assistant-chat__controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.control-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: white;
  cursor: pointer;
  transition: all 0.2s ease;
  text-decoration: none;
}

.control-btn:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: scale(1.05);
  color: white;
}

.assistant-chat__wip {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(to bottom, #ffffff, #f8f9fa);
  border-radius: 0 0 12px 12px;
}

.wip-badge {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 32px;
  text-align: center;
}

.wip-badge__icon {
  color: #dc3545;
  opacity: 0.6;
}

.wip-badge__title {
  font-size: 22px;
  font-weight: 700;
  color: #dc3545;
  letter-spacing: 0.02em;
}

.wip-badge__desc {
  font-size: 14px;
  color: #6c757d;
  line-height: 1.6;
  margin: 0;
}

@media (max-width: 1200px) {
  .assistant-chat {
    position: fixed;
    bottom: 20px;
    left: 20px;
    right: 20px;
    width: auto;
    height: 400px;
    margin-bottom: 0;
  }
}
</style>
