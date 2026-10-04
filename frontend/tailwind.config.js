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
        surface: '#F6F4FA',
      },
      fontFamily: {
        sans: ['Montserrat', 'system-ui', 'Segoe UI', 'Arial', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'Menlo', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(49,15,83,.04), 0 8px 24px -12px rgba(49,15,83,.18)',
        pop: '0 20px 50px -20px rgba(49,15,83,.45)',
      },
      borderRadius: { '4xl': '2rem' },
    },
  },
  plugins: [],
}
