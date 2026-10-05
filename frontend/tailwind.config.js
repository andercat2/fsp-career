/** @type {import('tailwindcss').Config} */
export default {
  // relative: пути считаются от файла конфигурации, а не от рабочего каталога процесса
  content: { relative: true, files: ['./index.html', './src/**/*.{ts,tsx}'] },
  theme: {
    extend: {
      colors: {
        // Палитра ФСП из брендбука (шаблон презентации организатора)
        fsp: {
          pink: '#FF0053',
          rose: '#FC3777',
          blush: '#FFD6E4',
          lavender: '#8A83D1',
          deep: '#310F53',
          purple: '#520978',
          ink: '#1C1D22',
        },
        surface: '#F7F6FA',
        line: '#ECEAF2',
      },
      fontFamily: {
        sans: ['Montserrat', 'system-ui', 'Segoe UI', 'Arial', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'Menlo', 'monospace'],
      },
      fontSize: {
        '2xs': ['11px', '15px'],
      },
      letterSpacing: { tightest: '-0.035em' },
      boxShadow: {
        soft: '0 1px 2px rgba(23, 14, 41, .04), 0 1px 1px rgba(23, 14, 41, .02)',
        card: '0 1px 2px rgba(23, 14, 41, .04), 0 8px 24px -16px rgba(49, 15, 83, .14)',
        lift: '0 2px 4px rgba(23, 14, 41, .04), 0 18px 40px -18px rgba(49, 15, 83, .28)',
        pop: '0 24px 64px -24px rgba(49, 15, 83, .45)',
        glow: '0 10px 30px -10px rgba(255, 0, 83, .55)',
        'inner-line': 'inset 0 0 0 1px rgba(236, 234, 242, 1)',
      },
      borderRadius: { '4xl': '2rem', '2.5xl': '1.25rem' },
      keyframes: {
        shimmer: { '100%': { transform: 'translateX(100%)' } },
        float: { '0%, 100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-10px)' } },
        'float-slow': { '0%, 100%': { transform: 'translateY(0) rotate(0deg)' }, '50%': { transform: 'translateY(-16px) rotate(2deg)' } },
        blob: {
          '0%, 100%': { transform: 'translate(0, 0) scale(1)' },
          '33%': { transform: 'translate(40px, -50px) scale(1.12)' },
          '66%': { transform: 'translate(-30px, 30px) scale(0.92)' },
        },
        'gradient-x': { '0%, 100%': { backgroundPosition: '0% 50%' }, '50%': { backgroundPosition: '100% 50%' } },
        marquee: { '0%': { transform: 'translateX(0)' }, '100%': { transform: 'translateX(-50%)' } },
        'pulse-ring': { '0%': { transform: 'scale(.9)', opacity: '.7' }, '100%': { transform: 'scale(1.6)', opacity: '0' } },
        'spin-slow': { to: { transform: 'rotate(360deg)' } },
      },
      animation: {
        shimmer: 'shimmer 1.6s infinite',
        float: 'float 6s ease-in-out infinite',
        'float-slow': 'float-slow 9s ease-in-out infinite',
        blob: 'blob 18s ease-in-out infinite',
        'gradient-x': 'gradient-x 8s ease infinite',
        marquee: 'marquee 40s linear infinite',
        'pulse-ring': 'pulse-ring 1.8s cubic-bezier(.22,1,.36,1) infinite',
        'spin-slow': 'spin-slow 24s linear infinite',
      },
    },
  },
  plugins: [],
}
