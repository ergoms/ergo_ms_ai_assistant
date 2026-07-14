/**
 * Дефолты модульной темы AI-ассистента (синхронизировать с theme_seed.py на сервере).
 */
export default {
  moduleKey: 'ai_assistant',
  displayName: 'AI-ассистент',
  baseTheme: 'dark',
  colors: {
    headerBackground: 'rgba(10, 12, 18, 0.92)',
    authBackground: 'rgba(5, 5, 8, 0.95)',
    background: '#050508',
    border: 'rgba(58, 232, 255, 0.12)',
    primaryText: '#e8ecf4',
    secondaryText: '#a0aec0',
    primaryBackground: '#0e1118',
    secondaryBackground: '#13161f',
    hoverBackground: '#191d28',
    accent: '#3ae8ff',
  },
  bootstrap_colors: {},
  moduleTokens: {
    neonCyan: '#3ae8ff',
    neonPurple: '#a855f7',
    neonGreen: '#22ff8d',
    neonPink: '#ff6eb4',
    neonBlue: '#4f8fff',
    glowCyan: '0 0 20px rgba(58, 232, 255, 0.4), 0 0 40px rgba(58, 232, 255, 0.2)',
  },
  systemThemes: [
    {
      name: 'Neural Dark (AI-ассистент)',
      description: 'Системная тёмная тема AI-ассистента',
      base_theme: 'dark',
      is_default: true,
    },
    {
      name: 'Frost Light (AI-ассистент)',
      description: 'Системная светлая тема AI-ассистента',
      base_theme: 'light',
      is_default: false,
      colors: {
        headerBackground: 'rgba(248, 250, 252, 0.92)',
        authBackground: 'rgba(248, 250, 252, 0.95)',
        background: '#f8fafc',
        border: 'rgba(15, 118, 138, 0.15)',
        primaryText: '#0f172a',
        secondaryText: '#334155',
        primaryBackground: '#f1f5f9',
        secondaryBackground: '#e2e8f0',
        hoverBackground: '#cbd5e1',
        accent: '#0e7490',
      },
    },
  ],
}
