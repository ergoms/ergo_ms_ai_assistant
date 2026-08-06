/**
 * Дефолты модульной темы AI-ассистента.
 * Accent совпадает с ядром (bootstrap-variables / _theme.scss).
 * Пара light+dark: modulePair связывает варианты; активный вариант — по глобальному режиму сайта.
 */
export default {
  moduleKey: 'ai_assistant',
  displayName: 'AI-ассистент',
  modulePair: 'default',
  baseTheme: 'dark',
  colors: {
    headerBackground: 'rgba(17, 17, 18, 0.92)',
    authBackground: 'rgba(17, 17, 18, 0.95)',
    background: '#111112',
    border: '#555555',
    primaryText: '#c9cccf',
    // Читаемый muted на elevated (#2a2a2c); #6e6e6e давал контраст ~2:1
    secondaryText: '#a0a0a4',
    primaryBackground: '#18181a',
    secondaryBackground: '#2a2a2c',
    hoverBackground: '#3d3d3f',
    accent: '#f14336',
  },
  bootstrap_colors: {},
  moduleTokens: {
    neonCyan: '#f14336',
    neonPurple: '#a855f7',
    neonGreen: '#22ff8d',
    neonPink: '#ff6eb4',
    neonBlue: '#d0322d',
    glowCyan: '0 0 20px rgba(241, 67, 54, 0.4), 0 0 40px rgba(241, 67, 54, 0.2)',
  },
  systemThemes: [
    {
      name: 'Neural (AI-ассистент)',
      description: 'Системная пара тем AI-ассистента',
      base_theme: 'dark',
      module_pair: 'default',
      is_default: true,
    },
    {
      name: 'Neural (AI-ассистент)',
      description: 'Системная пара тем AI-ассистента',
      base_theme: 'light',
      module_pair: 'default',
      is_default: true,
      colors: {
        headerBackground: 'rgba(255, 255, 255, 0.92)',
        authBackground: 'rgba(255, 255, 255, 0.95)',
        background: '#f2f2f2',
        border: '#e0e0e0',
        primaryText: '#101223',
        secondaryText: '#6e6e6e',
        primaryBackground: '#ffffff',
        secondaryBackground: '#f1f1f1',
        hoverBackground: '#e1e1e1',
        accent: '#d0322d',
      },
    },
  ],
}
