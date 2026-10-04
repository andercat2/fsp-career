import { fileURLToPath } from 'node:url'

// Явный путь к конфигу Tailwind: сборка не зависит от каталога, из которого запущен Vite.
export default {
  plugins: {
    tailwindcss: { config: fileURLToPath(new URL('./tailwind.config.js', import.meta.url)) },
    autoprefixer: {},
  },
}
