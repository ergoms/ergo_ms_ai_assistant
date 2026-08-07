<template>
  <div class="neural-background" ref="containerRef">
    <canvas ref="canvasRef" class="neural-canvas"></canvas>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useUiModes } from '@/composables/useUiModes.js'
import { useBreakpoint } from '@/composables/useBreakpoint.js'

const containerRef = ref(null)
const canvasRef = ref(null)

const { reducedMotionActive } = useUiModes()
const { isCompactLayout } = useBreakpoint()

let animationId = null
let nodes = []
let mouse = { x: 0, y: 0 }
let ctx = null
let width = 0
let height = 0

// Параметры анимации
let currentSpeedMultiplier = 1
let targetSpeedMultiplier = 1

const props = defineProps({
  nodeCount: {
    type: Number,
    default: 50
  },
  connectionDistance: {
    type: Number,
    default: 150
  },
  nodeColor: {
    type: String,
    default: '#f14336',
  },
  lineColor: {
    type: String,
    default: '#f14336',
  },
  accelerated: {
    type: Boolean,
    default: false
  }
})

const effectiveNodeCount = computed(() => {
  if (reducedMotionActive.value) {
    return 0
  }
  if (isCompactLayout.value) {
    return 20
  }
  return props.nodeCount
})

// Плавная интерполяция скорости
watch(() => props.accelerated, (isAccelerated) => {
  targetSpeedMultiplier = isAccelerated ? 2 : 1
})

class Node {
  constructor(x, y) {
    this.x = x
    this.y = y
    this.baseVx = (Math.random() - 0.5) * 0.5
    this.baseVy = (Math.random() - 0.5) * 0.5
    this.vx = this.baseVx
    this.vy = this.baseVy
    this.radius = Math.random() * 2 + 1
    this.pulsePhase = Math.random() * Math.PI * 2
    this.basePulseSpeed = 0.02 + Math.random() * 0.02
    this.pulseSpeed = this.basePulseSpeed
    // Параметры вспышки
    this.flashIntensity = 0
    this.flashDecay = 0.02 + Math.random() * 0.02
  }

  update(speedMultiplier) {
    // Применяем множитель скорости
    this.vx = this.baseVx * speedMultiplier
    this.vy = this.baseVy * speedMultiplier
    this.pulseSpeed = this.basePulseSpeed * speedMultiplier
    
    this.x += this.vx
    this.y += this.vy
    this.pulsePhase += this.pulseSpeed

    // Затухание вспышки
    if (this.flashIntensity > 0) {
      this.flashIntensity -= this.flashDecay * speedMultiplier
      if (this.flashIntensity < 0) this.flashIntensity = 0
    }

    // Случайная вспышка (чаще при ускорении)
    const flashChance = speedMultiplier > 1.3 ? 0.008 : 0.002
    if (Math.random() < flashChance && this.flashIntensity < 0.1) {
      this.flashIntensity = 0.6 + Math.random() * 0.4
    }

    // Отталкивание от границ
    if (this.x < 0 || this.x > width) {
      this.baseVx *= -1
      this.vx *= -1
    }
    if (this.y < 0 || this.y > height) {
      this.baseVy *= -1
      this.vy *= -1
    }

    // Притяжение к курсору
    const dx = mouse.x - this.x
    const dy = mouse.y - this.y
    const dist = Math.sqrt(dx * dx + dy * dy)
    if (dist < 200 && dist > 0) {
      const force = (200 - dist) / 200 * 0.01
      this.baseVx += (dx / dist) * force
      this.baseVy += (dy / dist) * force
    }

    // Ограничение скорости
    const maxSpeed = 1 * speedMultiplier
    const speed = Math.sqrt(this.baseVx * this.baseVx + this.baseVy * this.baseVy)
    if (speed > maxSpeed) {
      this.baseVx = (this.baseVx / speed) * maxSpeed
      this.baseVy = (this.baseVy / speed) * maxSpeed
    }
  }

  draw() {
    const pulse = Math.sin(this.pulsePhase) * 0.5 + 0.5
    const r = this.radius + pulse * 1.5
    
    // Основной узел
    ctx.beginPath()
    ctx.arc(this.x, this.y, r, 0, Math.PI * 2)
    ctx.fillStyle = props.nodeColor
    ctx.fill()

    // Базовое свечение
    const gradient = ctx.createRadialGradient(this.x, this.y, 0, this.x, this.y, r * 4)
    gradient.addColorStop(0, `${props.nodeColor}40`)
    gradient.addColorStop(1, 'transparent')
    ctx.beginPath()
    ctx.arc(this.x, this.y, r * 4, 0, Math.PI * 2)
    ctx.fillStyle = gradient
    ctx.fill()

    // Эффект вспышки
    if (this.flashIntensity > 0) {
      // Яркое белое ядро вспышки
      const flashR = r * (1 + this.flashIntensity * 0.5)
      ctx.beginPath()
      ctx.arc(this.x, this.y, flashR, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(255, 255, 255, ${this.flashIntensity * 0.7})`
      ctx.fill()
      
      // Цветное свечение вспышки
      const flashGlow = ctx.createRadialGradient(this.x, this.y, 0, this.x, this.y, r * 8)
      const glowAlpha = Math.floor(this.flashIntensity * 150).toString(16).padStart(2, '0')
      const glowAlpha2 = Math.floor(this.flashIntensity * 60).toString(16).padStart(2, '0')
      flashGlow.addColorStop(0, `${props.nodeColor}${glowAlpha}`)
      flashGlow.addColorStop(0.5, `${props.nodeColor}${glowAlpha2}`)
      flashGlow.addColorStop(1, 'transparent')
      ctx.beginPath()
      ctx.arc(this.x, this.y, r * 8, 0, Math.PI * 2)
      ctx.fillStyle = flashGlow
      ctx.fill()
    }
  }
}

const initCanvas = () => {
  const canvas = canvasRef.value
  const container = containerRef.value
  if (!canvas || !container) return

  ctx = canvas.getContext('2d')
  width = container.offsetWidth
  height = container.offsetHeight
  canvas.width = width
  canvas.height = height

  // Создание узлов
  nodes = []
  const count = effectiveNodeCount.value
  for (let i = 0; i < count; i++) {
    nodes.push(new Node(
      Math.random() * width,
      Math.random() * height
    ))
  }
  if (count === 0 && ctx) {
    ctx.clearRect(0, 0, width, height)
  }
}

const drawConnections = () => {
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const dx = nodes[i].x - nodes[j].x
      const dy = nodes[i].y - nodes[j].y
      const dist = Math.sqrt(dx * dx + dy * dy)

      if (dist < props.connectionDistance) {
        const opacity = (1 - dist / props.connectionDistance) * 0.6
        ctx.beginPath()
        ctx.moveTo(nodes[i].x, nodes[i].y)
        ctx.lineTo(nodes[j].x, nodes[j].y)
        ctx.strokeStyle = `${props.lineColor}${Math.floor(opacity * 255).toString(16).padStart(2, '0')}`
        ctx.lineWidth = opacity * 2
        ctx.stroke()
      }
    }
  }
}

const animate = () => {
  if (!ctx || effectiveNodeCount.value === 0) {
    return
  }
  
  // Плавная интерполяция скорости
  const lerpFactor = 0.05
  currentSpeedMultiplier += (targetSpeedMultiplier - currentSpeedMultiplier) * lerpFactor
  
  ctx.clearRect(0, 0, width, height)
  
  // Обновление и отрисовка узлов
  nodes.forEach(node => {
    node.update(currentSpeedMultiplier)
    node.draw()
  })
  
  // Рисуем связи
  drawConnections()
  
  animationId = requestAnimationFrame(animate)
}

const handleResize = () => {
  initCanvas()
}

const handleMouseMove = (e) => {
  const rect = containerRef.value?.getBoundingClientRect()
  if (rect) {
    mouse.x = e.clientX - rect.left
    mouse.y = e.clientY - rect.top
  }
}

const stopAnimation = () => {
  if (animationId) {
    cancelAnimationFrame(animationId)
    animationId = null
  }
}

const startAnimation = () => {
  stopAnimation()
  if (!reducedMotionActive.value && effectiveNodeCount.value > 0) {
    animate()
  }
}

watch([reducedMotionActive, isCompactLayout], () => {
  initCanvas()
  startAnimation()
})

onMounted(() => {
  initCanvas()
  startAnimation()
  
  window.addEventListener('resize', handleResize)
  containerRef.value?.addEventListener('mousemove', handleMouseMove)
})

onUnmounted(() => {
  stopAnimation()
  window.removeEventListener('resize', handleResize)
  containerRef.value?.removeEventListener('mousemove', handleMouseMove)
})
</script>

<style lang="scss" scoped>
.neural-background {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
  pointer-events: all;
  z-index: 0;
  background: var(--bg-panel);
}

.neural-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  filter: blur(3px);
}

</style>

