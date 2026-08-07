/**
 * Accent темы AI-ассистента для inline-style и canvas (где нужен resolved color).
 */

export const AI_ACCENT_CSS = 'var(--ai-accent, var(--color-accent))'

function toHexChannel(value) {
  return Math.max(0, Math.min(255, Number(value) || 0)).toString(16).padStart(2, '0')
}

/** rgb(a)/#hex → #rrggbb (для canvas с суффиксом альфы). */
export function cssColorToHex(color, fallback = '#f14336') {
  if (!color) return fallback
  const trimmed = String(color).trim()
  if (/^#[0-9a-fA-F]{6}$/.test(trimmed)) return trimmed.toLowerCase()
  if (/^#[0-9a-fA-F]{3}$/.test(trimmed)) {
    const [, r, g, b] = trimmed
    return `#${r}${r}${g}${g}${b}${b}`.toLowerCase()
  }
  const match = trimmed.match(/^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)/i)
  if (!match) return fallback
  return `#${toHexChannel(match[1])}${toHexChannel(match[2])}${toHexChannel(match[3])}`
}

/**
 * Резолвит CSS-цвет (в т.ч. var(--ai-accent)) в #rrggbb для canvas.
 */
export function resolveCssColor(el, cssColor, fallback = '#f14336') {
  if (!cssColor) return fallback
  if (!cssColor.includes('var(') && !cssColor.includes('color-mix(')) {
    return cssColorToHex(cssColor, fallback)
  }
  if (!el || typeof getComputedStyle === 'undefined') {
    return fallback
  }
  const probe = document.createElement('span')
  probe.setAttribute('aria-hidden', 'true')
  probe.style.cssText = [
    'position:absolute',
    'width:0',
    'height:0',
    'overflow:hidden',
    'pointer-events:none',
    `color:${cssColor}`,
  ].join(';')
  el.appendChild(probe)
  const resolved = getComputedStyle(probe).color
  probe.remove()
  if (!resolved || resolved === 'rgba(0, 0, 0, 0)' || resolved === 'transparent') {
    return fallback
  }
  return cssColorToHex(resolved, fallback)
}
