<template>
  <div class="neural-typing">
    <div class="typing-avatar">
      <Sparkles :size="18" />
      <div class="avatar-pulse"></div>
    </div>
    <div class="typing-content">
      <div class="typing-label">{{ t('ai_assistant.message.processing') }}</div>
      <div class="typing-wave">
        <span></span>
        <span></span>
        <span></span>
        <span></span>
        <span></span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Sparkles } from 'lucide-vue-next'
import { useAppI18n } from '@/i18n/useAppI18n.js'

const { t } = useAppI18n()
</script>

<style lang="scss" scoped>
@import '../styles/variables';

.neural-typing {
  display: flex;
  align-items: center;
  gap: $spacing-md;
  padding: $spacing-md $spacing-lg;
  margin-bottom: $spacing-md;
}

.typing-avatar {
  width: 40px;
  height: 40px;
  border-radius: $radius-lg;
  background: linear-gradient(135deg, $neon-cyan, $neon-purple);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
  box-shadow: $glow-cyan;
}

.avatar-pulse {
  position: absolute;
  inset: -6px;
  border: 1px solid $neon-cyan;
  border-radius: $radius-xl;
  animation: pulse-expand 2s ease-out infinite;
}

@keyframes pulse-expand {
  0% {
    transform: scale(0.8);
    opacity: 0.8;
  }
  100% {
    transform: scale(1.3);
    opacity: 0;
  }
}

.typing-content {
  display: flex;
  flex-direction: column;
  gap: $spacing-sm;
}

.typing-label {
  font-family: $font-family-mono;
  font-size: $font-size-xs;
  color: var(--nc-text-muted, #{$dark-text-muted});
  text-transform: uppercase;
  letter-spacing: $letter-spacing-widest;
}

.typing-wave {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 20px;

  span {
    width: 3px;
    height: 8px;
    background: $neon-cyan;
    border-radius: 2px;
    animation: wave 1.2s ease-in-out infinite;
    box-shadow: 0 0 8px $neon-cyan-light;

    &:nth-child(1) { animation-delay: 0s; }
    &:nth-child(2) { animation-delay: 0.1s; }
    &:nth-child(3) { animation-delay: 0.2s; }
    &:nth-child(4) { animation-delay: 0.3s; }
    &:nth-child(5) { animation-delay: 0.4s; }
  }
}

@keyframes wave {
  0%, 60%, 100% {
    height: 8px;
    opacity: 0.5;
  }
  30% {
    height: 20px;
    opacity: 1;
  }
}
</style>
