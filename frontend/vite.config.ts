import { defineConfig } from 'vite'
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

/** 从模块 id 中提取 npm 包名（支持 scoped 包）。 */
function packageName(id: string): string | undefined {
  return id.match(/node_modules\/(@[^/]+\/[^/]+|[^/]+)/)?.[1]
}

// clsx/tailwind-merge 被业务代码与 recharts 共用，显式归入常驻 chunk，
// 否则 Rollup 会把 clsx 并进 vendor-charts，导致主入口同步拉取整个图表库
const REACT_PACKAGES = new Set([
  'react',
  'react-dom',
  'react-router',
  'scheduler',
  'react-is',
  'clsx',
  'tailwind-merge',
])

// recharts 及其专属依赖
const CHART_PACKAGES = new Set([
  'recharts',
  'recharts-scale',
  'victory-vendor',
  'react-smooth',
  'internmap',
  'decimal.js-light',
  'fast-equals',
  'eventemitter3',
  'tiny-invariant',
  'lodash',
  'prop-types',
  'react-transition-group',
])

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          const name = packageName(id)
          if (!name) return undefined
          if (REACT_PACKAGES.has(name)) return 'vendor-react'
          if (name.startsWith('@tanstack/')) return 'vendor-tanstack'
          if (CHART_PACKAGES.has(name) || name.startsWith('d3-'))
            return 'vendor-charts'
          return undefined
        },
      },
    },
  },
})
