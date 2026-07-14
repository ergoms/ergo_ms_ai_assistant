/**
 * Дефолты модульной темы AI-ассистента (синхронизировать с theme_seed.py на сервере).
 * Пара light+dark: modulePair связывает варианты; активный вариант — по глобальному режиму сайта.
 */
export default {
  moduleKey: 'ai_assistant',
  displayName: 'AI-ассистент',
  modulePair: 'default',
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
