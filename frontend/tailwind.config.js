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
        success: '#17855F',
        canvas: '#F2F4F2',
        surface: '#FFFFFF',
        muted: '#F6F8F6',
        ink: '#13241B',
        subtle: '#5E6E65',
        line: 'rgba(18,45,32,.07)',
        accent: '#17855F',
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
        card: '0 10px 30px rgba(20,55,38,.07), 0 1px 2px rgba(20,55,38,.04)',
        float: '0 10px 30px rgba(20,55,38,.10)',
        panel: '0 30px 80px rgba(40,25,10,.25)',
      },
      borderRadius: {
        control: '14px',
        card: '22px',
        modal: '22px',
        pill: '999px',
        tile: '16px',
      },
    },
  },
  plugins: [],
}
