<template>
  <Teleport to="body">
    <div v-if="show" class="chat-type-selector-overlay" @click.self="close">
      <div class="chat-type-selector">
        <div class="chat-type-selector__header">
          <h2 class="chat-type-selector__title">{{ t('ai_assistant.newChat.title') }}</h2>
          <button class="chat-type-selector__close" @click="close" :title="t('common.close')">
            <X :size="20" />
          </button>
        </div>
        
        <div class="chat-type-selector__content">
          <p class="chat-type-selector__description">{{ t('ai_assistant.newChat.description') }}</p>
          
          <div class="chat-type-selector__grid">
            <div
              v-for="module in availableModules"
              :key="module.id"
              class="chat-type-card"
              :style="{ '--card-color': module.color }"
              @click="selectModule(module.id)"
            >
              <div class="chat-type-card__icon">
                <component :is="module.icon" :size="32" />
              </div>
              <div class="chat-type-card__content">
                <h3 class="chat-type-card__title">{{ module.name }}</h3>
                <p class="chat-type-card__description">{{ module.description }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'
import { X } from 'lucide-vue-next'
import { Teleport } from 'vue'
import { modules } from '../modules/index.js'
import { useAppI18n } from '@/i18n/useAppI18n.js'

const { t } = useAppI18n()

const props = defineProps({
  show: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['close', 'select'])

const availableModules = computed(() => {
  return modules.filter(m => m.enabled && !m.comingSoon)
})

const close = () => {
  emit('close')
}

const selectModule = (moduleId) => {
  emit('select', moduleId)
  close()
}
</script>

<style lang="scss" scoped>
.chat-type-selector-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  padding: 20px;
}

.chat-type-selector {
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 8px;
  max-width: 800px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
}

.chat-type-selector__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid #333;
}

.chat-type-selector__title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #fff;
}

.chat-type-selector__close {
  background: none;
  border: none;
  color: #999;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.2s;

  &:hover {
    background: #333;
    color: #fff;
  }
}

.chat-type-selector__content {
  padding: 24px;
  overflow-y: auto;
}

.chat-type-selector__description {
  margin: 0 0 24px 0;
  color: #999;
  font-size: 14px;
}

.chat-type-selector__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.chat-type-card {
  background: #222;
  border: 1px solid #333;
  border-radius: 8px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 12px;

  &:hover {
    border-color: var(--card-color);
    background: #2a2a2a;
  }
}

.chat-type-card__icon {
  color: var(--card-color);
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-type-card__content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chat-type-card__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #fff;
}

.chat-type-card__description {
  margin: 0;
  font-size: 13px;
  color: #999;
  line-height: 1.4;
}
</style>
