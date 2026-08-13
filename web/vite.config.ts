import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import cssInjectedByJsPlugin from 'vite-plugin-css-injected-by-js'


export default defineConfig({
  plugins: [vue(), cssInjectedByJsPlugin()],
  build: {
    outDir: '../',
    emptyOutDir: false,
    lib: {
      entry: 'index.ts',
      name: 'ToolOptimizerPlugin',
      formats: ['umd'],
      fileName: () => 'index.umd.js',
    },
    rollupOptions: {
      external: ['vue', 'vue-router', 'lucide-vue-next'],
      output: {
        globals: {
          vue: 'Vue',
          'vue-router': 'VueRouter',
          'lucide-vue-next': 'LucideVueNext',
        },
      },
    },
  },
})
