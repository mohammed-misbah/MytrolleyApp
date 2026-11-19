/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        forest: { DEFAULT: '#14402B', deep: '#0A1F15', light: '#28784F' },
        lime: { DEFAULT: '#ADD638', soft: '#E9EFEB' },
        danger: '#C73E3E',
        success: '#1E8A5A',
        canvas: '#F7F5F2',
        surface: '#FFFFFF',
        muted: '#F1EDE7',
        ink: '#1B1A17',
        subtle: '#6B665E',
        line: 'rgba(45,30,15,.07)',
        accent: '#EA7A3B',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        'page-title': ['26px', { lineHeight: '1.1', letterSpacing: '-.3px', fontWeight: '650' }],
        'section-title': ['18px', { lineHeight: '1.3', fontWeight: '650' }],
        'card-value': ['46px', { lineHeight: '1', letterSpacing: '-1.2px', fontWeight: '700' }],
        body: ['16px', { lineHeight: '140%' }],
        label: ['14px', { lineHeight: 'normal' }],
        button: ['14px', { lineHeight: 'normal', fontWeight: '650' }],
      },
      boxShadow: {
        card: '0 8px 28px rgba(60,40,20,.06), 0 1px 2px rgba(60,40,20,.04)',
        float: '0 8px 28px rgba(60,40,20,.10)',
        panel: '0 30px 80px rgba(40,25,10,.25)',
      },
      borderRadius: {
        control: '12px',
        card: '20px',
        modal: '22px',
        pill: '999px',
        tile: '16px',
      },
    },
  },
  plugins: [],
}
