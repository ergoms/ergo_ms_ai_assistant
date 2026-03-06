<template>
  <div class="neural-button-container">
    <!-- Expand button -->
    <div
      v-if="!isActive"
      class="neural-expand-btn"
      @click="goToHub"
      title="Открыть AI Hub"
    >
      <ExternalLink :size="16" />
    </div>
    
    <!-- Main neural button -->
    <div
      class="neural-button"
      :class="{ 
        'neural-button--active': isActive, 
        'neural-button--pulse': isPulsing 
      }"
      @click="toggleChat"
    >
      <!-- Hexagon frame -->
      <svg class="neural-button__hexagon" viewBox="0 0 100 100">
        <polygon 
          class="hexagon-bg" 
          points="50,3 93,25 93,75 50,97 7,75 7,25"
        />
        <polygon 
          class="hexagon-border" 
          points="50,3 93,25 93,75 50,97 7,75 7,25"
        />
        <polygon 
          class="hexagon-glow" 
          points="50,3 93,25 93,75 50,97 7,75 7,25"
        />
      </svg>
      
      <!-- Core icon -->
      <div class="neural-button__core">
        <Sparkles :size="24" class="neural-button__icon" />
      </div>
      
      <!-- Orbiting ring -->
      <div class="neural-button__orbit">
        <div class="orbit-dot"></div>
      </div>
      
      <!-- Pulse rings -->
      <div class="neural-button__pulse-ring"></div>
      <div class="neural-button__pulse-ring neural-button__pulse-ring--delayed"></div>
      
      <!-- Notification -->
      <div v-if="hasNewMessage" class="neural-button__notification">
        <span class="notification-dot"></span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Sparkles, ExternalLink } from 'lucide-vue-next'

const router = useRouter()
const emit = defineEmits(['toggle-chat'])

const isActive = ref(false)
const isPulsing = ref(false)
const hasNewMessage = ref(false)

const toggleChat = () => {
  isActive.value = !isActive.value
  emit('toggle-chat', isActive.value)
}

const goToHub = () => {
  router.push('/ai-assistant')
}

const startPulsing = () => {
  isPulsing.value = true
}

const stopPulsing = () => {
  isPulsing.value = false
}

const showNotification = () => {
  hasNewMessage.value = true
}

const hideNotification = () => {
  hasNewMessage.value = false
}

const setActive = (value) => {
  isActive.value = value
}

defineExpose({
  startPulsing,
  stopPulsing,
  showNotification,
  hideNotification,
  setActive,
})
</script>

<style lang="scss" scoped>
// Neon colors
$neon-cyan: #3ae8ff;
$neon-purple: #a855f7;
$neon-green: #22ff8d;
$neon-pink: #ff6eb4;

.neural-button-container {
  position: fixed;
  bottom: 24px;
  left: 24px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.neural-expand-btn {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, rgba(58, 232, 255, 0.15), rgba(168, 85, 247, 0.15));
  border: 1px solid rgba(58, 232, 255, 0.3);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: $neon-cyan;
  opacity: 0;
  transform: scale(0.8) translateY(10px);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  backdrop-filter: blur(10px);

  &:hover {
    background: linear-gradient(135deg, rgba(58, 232, 255, 0.25), rgba(168, 85, 247, 0.25));
    border-color: $neon-cyan;
    transform: scale(1.05) translateY(0);
    box-shadow: 
      0 0 20px rgba(58, 232, 255, 0.3),
      0 0 40px rgba(58, 232, 255, 0.1);
  }
}

.neural-button-container:hover .neural-expand-btn {
  opacity: 1;
  transform: scale(1) translateY(0);
}

.neural-button {
  width: 70px;
  height: 70px;
  position: relative;
  cursor: pointer;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);

  &:hover {
    transform: scale(1.08);

    .hexagon-border {
      stroke: $neon-cyan;
      stroke-width: 2;
    }

    .hexagon-glow {
      opacity: 0.6;
    }

    .neural-button__core {
      box-shadow: 
        0 0 30px rgba(58, 232, 255, 0.5),
        0 0 60px rgba(58, 232, 255, 0.3);
    }

    .orbit-dot {
      box-shadow: 0 0 10px $neon-cyan;
    }
  }

  &--active {
    .hexagon-bg {
      fill: rgba(34, 255, 141, 0.15);
    }

    .hexagon-border {
      stroke: $neon-green;
    }

    .neural-button__core {
      background: linear-gradient(135deg, $neon-green, darken($neon-green, 20%));
      box-shadow: 
        0 0 30px rgba(34, 255, 141, 0.5),
        0 0 60px rgba(34, 255, 141, 0.3);
    }

    .orbit-dot {
      background: $neon-green;
    }
  }

  &--pulse {
    .neural-button__pulse-ring {
      animation: pulse-expand 1.5s ease-out infinite;
    }
  }
}

.neural-button__hexagon {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.hexagon-bg {
  fill: rgba(58, 232, 255, 0.1);
  transition: fill 0.3s ease;
}

.hexagon-border {
  fill: none;
  stroke: rgba(58, 232, 255, 0.5);
  stroke-width: 1.5;
  transition: all 0.3s ease;
}

.hexagon-glow {
  fill: none;
  stroke: $neon-cyan;
  stroke-width: 3;
  opacity: 0;
  filter: blur(4px);
  transition: opacity 0.3s ease;
}

.neural-button__core {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 44px;
  height: 44px;
  background: linear-gradient(135deg, $neon-cyan, $neon-purple);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  transition: all 0.3s ease;
  box-shadow: 
    0 0 20px rgba(58, 232, 255, 0.4),
    0 0 40px rgba(58, 232, 255, 0.2);
}

.neural-button__icon {
  animation: icon-float 3s ease-in-out infinite;
}

@keyframes icon-float {
  0%, 100% { transform: translateY(0) rotate(0deg); }
  50% { transform: translateY(-2px) rotate(5deg); }
}

.neural-button__orbit {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 60px;
  height: 60px;
  animation: orbit-rotate 8s linear infinite;
}

.orbit-dot {
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 6px;
  height: 6px;
  background: $neon-cyan;
  border-radius: 50%;
  transition: all 0.3s ease;
}

@keyframes orbit-rotate {
  from { transform: translate(-50%, -50%) rotate(0deg); }
  to { transform: translate(-50%, -50%) rotate(360deg); }
}

.neural-button__pulse-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 70px;
  height: 70px;
  border: 1px solid $neon-cyan;
  border-radius: 50%;
  opacity: 0;
  pointer-events: none;

  &--delayed {
    animation-delay: 0.75s;
  }
}

@keyframes pulse-expand {
  0% {
    transform: translate(-50%, -50%) scale(0.8);
    opacity: 0.8;
  }
  100% {
    transform: translate(-50%, -50%) scale(1.5);
    opacity: 0;
  }
}

.neural-button__notification {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.notification-dot {
  width: 12px;
  height: 12px;
  background: linear-gradient(135deg, $neon-pink, #ff4499);
  border-radius: 50%;
  border: 2px solid #0a0a0b;
  animation: notification-pulse 2s ease-in-out infinite;
  box-shadow: 0 0 15px rgba(255, 110, 180, 0.6);
}

@keyframes notification-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.2); }
}

// Mobile responsive
@media (max-width: 768px) {
  .neural-button-container {
    bottom: 16px;
    left: 16px;
  }

  .neural-button {
    width: 60px;
    height: 60px;
  }

  .neural-button__core {
    width: 38px;
    height: 38px;
  }

  .neural-button__orbit {
    width: 52px;
    height: 52px;
  }

  .neural-expand-btn {
    width: 36px;
    height: 36px;
  }
}
</style>
