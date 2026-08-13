import { WandSparkles } from 'lucide-vue-next'
import ToolOptimizer from './views/ToolOptimizer.vue'


const plugin = {
  id: 'tool_optimizer',
  routes: [{ path: 'tool-optimizer', component: ToolOptimizer }],
  menus: [{ path: '/tool-optimizer', label: '参数优化', icon: WandSparkles }],
}

if (typeof window !== 'undefined' && (window as any).Foxran) {
  ;(window as any).Foxran.registerPlugin(plugin)
}

export default plugin
