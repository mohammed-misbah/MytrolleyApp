/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        forest: {
          DEFAULT: '#273F2F',
          deep: '#1E3225',
          light: '#355641',
        },
        lime: {
          DEFAULT: '#ACD83D',
          soft: '#E8F5CC',
        },
        danger: '#E61F26',
        canvas: '#F5F7F4',
        surface: '#FFFFFF',
        muted: '#F0F3EE',
        ink: '#1E2A22',
        subtle: '#5E6B62',
        line: '#E2E8E1',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(20,40,25,0.05)',
        float: '0 6px 20px rgba(20,40,25,0.08)',
      },
      borderRadius: {
        control: '6px',
        card: '10px',
        modal: '14px',
      },
    },
  },
  plugins: [],
}
