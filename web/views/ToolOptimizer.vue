<template>
  <div class="optimizer-page">
    <header class="page-header">
      <div>
        <div class="eyebrow">TOOL MIDDLEWARE</div>
        <h2>参数优化</h2>
        <p>在工具真正执行前，只重写你明确选择的字段。</p>
      </div>
      <div class="header-actions">
        <span class="status-pill"><Wrench class="icon" /> {{ tools.length }} 个工具</span>
        <span class="status-pill"><Cpu class="icon" /> {{ availableModelCount }} 个模型可用</span>
        <button class="button secondary" :disabled="loading" @click="loadData">
          <RefreshCw class="icon" :class="{ spinning: loading }" />刷新
        </button>
        <button v-if="isPersistedDraft" class="button danger-ghost" :disabled="saving" @click="handleDelete">
          <Trash2 class="icon" />删除
        </button>
        <button class="button primary" :disabled="!draft || saving" @click="handleSave">
          <Save class="icon" />{{ saving ? '保存中' : '保存规则' }}
        </button>
      </div>
    </header>

    <div v-if="feedback.text" class="feedback" :class="feedback.type">
      <CircleCheck v-if="feedback.type === 'success'" class="notice-icon" />
      <CircleAlert v-else class="notice-icon" />
      <span>{{ feedback.text }}</span>
      <button class="icon-button feedback-close" aria-label="关闭提示" @click="feedback.text = ''"><X /></button>
    </div>

    <div v-if="error" class="notice error-notice">
      <CircleAlert class="notice-icon" />
      <div><strong>无法加载配置</strong><span>{{ error }}</span></div>
      <button class="text-button" @click="loadData">重试</button>
    </div>

    <main v-else class="workspace" :class="{ loading }">
      <aside class="panel rule-panel">
        <div class="panel-heading">
          <div>
            <span class="panel-kicker">RULES</span>
            <h3>优化规则</h3>
          </div>
          <button class="icon-button" title="新建规则" @click="createDraft"><Plus /></button>
        </div>
        <div class="rule-search">
          <Search class="search-icon" />
          <input v-model="ruleQuery" placeholder="搜索规则" />
        </div>
        <div class="rule-list">
          <button
            v-for="rule in filteredRules"
            :key="rule.id"
            class="rule-card"
            :class="{ active: draft?.id === rule.id }"
            @click="selectRule(rule)"
          >
            <span class="rule-state" :class="{ on: rule.enabled }"></span>
            <span class="rule-copy">
              <strong>{{ rule.name }}</strong>
              <small>{{ rule.match.tools.length || '全部' }} 个工具 · {{ rule.targets.length }} 个字段</small>
            </span>
            <ChevronRight class="rule-chevron" />
          </button>
          <div v-if="!loading && filteredRules.length === 0" class="empty-state compact">
            <FileSliders class="empty-icon" />
            <strong>还没有规则</strong>
            <span>新建一条规则，选择要优化的工具字段。</span>
            <button class="button secondary" @click="createDraft"><Plus class="icon" />新建规则</button>
          </div>
        </div>
      </aside>

      <section class="panel mapping-panel">
        <div class="panel-heading mapping-heading">
          <div>
            <span class="panel-kicker">MATCH & TARGETS</span>
            <h3>工具与参数</h3>
          </div>
          <label v-if="draft" class="switch-label">
            <span>{{ draft.enabled ? '已启用' : '已停用' }}</span>
            <input v-model="draft.enabled" type="checkbox" />
            <i></i>
          </label>
        </div>

        <div v-if="draft" class="panel-body">
          <div v-if="validationErrors.length" class="validation-strip">
            <CircleAlert class="icon" />
            <span>{{ validationErrors[0] }}</span>
            <small v-if="validationErrors.length > 1">另有 {{ validationErrors.length - 1 }} 项</small>
          </div>
          <div class="field-grid two">
            <label class="field-block">
              <span>规则名称</span>
              <input v-model="draft.name" class="field-control" placeholder="例如：图片提示词增强" />
            </label>
            <label class="field-block">
              <span>优先级</span>
              <input v-model.number="draft.priority" class="field-control" type="number" />
            </label>
          </div>

          <label class="field-block">
            <span>目标工具</span>
            <div class="select-wrap">
              <select v-model="selectedToolName" class="field-control" @change="handleToolChange">
                <option value="">选择工具</option>
                <option v-for="tool in tools" :key="tool.name" :value="tool.name">{{ tool.name }}</option>
              </select>
              <ChevronDown class="select-icon" />
            </div>
          </label>

          <div v-if="selectedTool" class="tool-summary">
            <div class="tool-mark"><Wrench /></div>
            <div><strong>{{ selectedTool.name }}</strong><span>{{ selectedTool.description }}</span></div>
            <span class="type-badge">{{ selectedTool.tool_type }}</span>
          </div>

          <div class="section-label-row">
            <div>
              <span class="section-label">参数路径</span>
              <small>默认只开放提示词型字符串字段</small>
            </div>
            <span class="count-badge">已选 {{ draft.targets.length }}</span>
          </div>

          <div v-if="selectedTool" class="parameter-list">
            <label
              v-for="field in parameterFields"
              :key="field.path"
              class="parameter-row"
              :class="{ selected: isTargetSelected(field.path), locked: !field.safe && !draft.guardrails.allow_unsafe_fields }"
            >
              <input
                type="checkbox"
                :checked="isTargetSelected(field.path)"
                :disabled="!field.safe && !draft.guardrails.allow_unsafe_fields"
                @change="toggleTarget(field.path)"
              />
              <span class="parameter-main">
                <span class="parameter-name"><code>{{ field.path }}</code><span>{{ field.type }}</span></span>
                <small>{{ field.description || '该字段没有额外说明' }}</small>
              </span>
              <LockKeyhole v-if="!field.safe && !draft.guardrails.allow_unsafe_fields" class="lock-icon" />
              <Check v-else-if="isTargetSelected(field.path)" class="check-icon" />
            </label>
            <div v-if="parameterFields.length === 0" class="empty-state compact">
              <Braces class="empty-icon" /><strong>没有可配置字段</strong><span>该工具没有公开输入 Schema。</span>
            </div>
          </div>
          <div v-else class="empty-state tool-empty">
            <MousePointer2 class="empty-icon" />
            <strong>先选择一个工具</strong>
            <span>选择后会根据 JSON Schema 展开可优化参数。</span>
          </div>
        </div>
        <div v-else class="empty-state full-empty">
          <FileSliders class="empty-icon" /><strong>选择或新建规则</strong><span>规则决定何时拦截工具，以及允许模型修改哪些字段。</span>
        </div>
      </section>

      <aside class="panel optimizer-panel">
        <div class="panel-heading">
          <div><span class="panel-kicker">OPTIMIZER</span><h3>模型与指令</h3></div>
          <Sparkles class="heading-icon" />
        </div>
        <div v-if="draft" class="panel-body optimizer-body">
          <label class="field-block">
            <span>优化模型</span>
            <div class="select-wrap">
              <select v-model="primaryModel" class="field-control">
                <option value="">按回退标签路由</option>
                <option v-for="model in models" :key="model.name" :value="model.name" :disabled="!model.available">
                  {{ model.name }}{{ model.available ? '' : '（不可用）' }}
                </option>
              </select>
              <ChevronDown class="select-icon" />
            </div>
          </label>

          <label class="field-block">
            <span>回退标签</span>
            <input v-model="fallbackTagsText" class="field-control" placeholder="fast, default" />
            <small>精确模型不可用时，按标签寻找候选。</small>
          </label>

          <label class="field-block grow">
            <span>系统提示词</span>
            <textarea v-model="draft.optimizer.system_prompt" class="field-control textarea" placeholder="限定优化风格与不可改变的内容。"></textarea>
          </label>

          <label class="field-block grow">
            <span>优化指令</span>
            <textarea v-model="draft.optimizer.instruction_template" class="field-control textarea compact-textarea" placeholder="说明如何改写选中的参数。"></textarea>
          </label>

          <div class="field-grid two">
            <label class="field-block"><span>Temperature</span><input v-model.number="draft.optimizer.temperature" class="field-control" type="number" min="0" max="2" step="0.1" /></label>
            <label class="field-block"><span>单次超时 ms</span><input v-model.number="draft.execution.timeout_ms" class="field-control" type="number" min="500" step="500" /></label>
            <label class="field-block"><span>最多尝试次数</span><input v-model.number="draft.execution.max_retries" class="field-control" type="number" min="1" max="5" step="1" /></label>
          </div>

          <label class="field-block">
            <span>失败策略</span>
            <div class="segmented">
              <button :class="{ active: draft.execution.failure_policy === 'use_original' }" @click="draft.execution.failure_policy = 'use_original'">使用原参数</button>
              <button :class="{ active: draft.execution.failure_policy === 'fail_call' }" @click="draft.execution.failure_policy = 'fail_call'">终止调用</button>
            </div>
          </label>

          <details class="advanced-box">
            <summary><ShieldCheck class="icon" />安全与高级设置<ChevronDown class="summary-chevron" /></summary>
            <label><input v-model="draft.guardrails.preserve_urls" type="checkbox" />保留 URL</label>
            <label><input v-model="draft.guardrails.preserve_references" type="checkbox" />保留能力引用</label>
            <label><input v-model="draft.guardrails.deny_sensitive_fields" type="checkbox" />禁止敏感字段</label>
            <label class="warning-option"><input v-model="draft.guardrails.allow_unsafe_fields" type="checkbox" />允许非提示词字段</label>
          </details>
        </div>
      </aside>
    </main>

    <section v-if="draft" class="preview-panel">
      <div class="preview-heading">
        <div><span class="panel-kicker">TEST BENCH</span><h3>执行前预览</h3><p>预览只调用优化模型，不会执行目标工具。</p></div>
        <button class="button primary" :disabled="!canPreview || previewing" @click="handlePreview">
          <Play class="icon" />{{ previewing ? '优化中' : '运行预览' }}
        </button>
      </div>
      <div class="preview-grid">
        <label class="code-pane">
          <span>原始参数</span>
          <textarea v-model="rawParameterText" spellcheck="false"></textarea>
        </label>
        <div class="transform-rail"><ArrowRight /><span>{{ previewResult ? '已转换' : '等待运行' }}</span></div>
        <div class="code-pane result-pane">
          <span>实际参数</span>
          <pre>{{ effectiveParameterText }}</pre>
        </div>
      </div>
      <div v-if="previewError" class="inline-error"><CircleAlert class="icon" />{{ previewError }}</div>
    </section>

    <section class="runs-panel">
      <div class="runs-heading">
        <div><span class="panel-kicker">RECENT RUNS</span><h3>最近优化记录</h3><p>只记录命中规则、字段路径和耗时，不保存参数原文。</p></div>
        <button class="button secondary" :disabled="runsLoading" @click="loadRuns"><RefreshCw class="icon" :class="{ spinning: runsLoading }" />刷新记录</button>
      </div>
      <div v-if="runs.length" class="runs-table">
        <div class="runs-row runs-header"><span>状态</span><span>工具 / 规则</span><span>修改字段</span><span>模型</span><span>耗时</span><span>时间</span></div>
        <div v-for="run in runs" :key="`${run.call_id}-${run.rule_id}-${run.timestamp}`" class="runs-row">
          <span><i class="run-status" :class="{ success: run.success }"></i>{{ run.success ? '完成' : '回退' }}</span>
          <span class="run-identity"><strong>{{ run.tool_name }}</strong><small>{{ run.rule_name }}</small></span>
          <span class="path-list"><code v-for="path in run.paths" :key="path">{{ path }}</code><em v-if="!run.paths.length">未修改</em></span>
          <span>{{ run.model_name || '—' }}</span>
          <span>{{ run.duration_ms == null ? '—' : `${run.duration_ms} ms` }}{{ (run.attempts || 1) > 1 ? ` · ${run.attempts} 次` : '' }}</span>
          <span>{{ formatRunTime(run.timestamp) }}</span>
        </div>
      </div>
      <div v-else class="empty-state runs-empty"><Activity class="empty-icon" /><strong>暂无运行记录</strong><span>规则命中后会在这里显示脱敏的执行轨迹。</span></div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  Activity, ArrowRight, Braces, Check, ChevronDown, ChevronRight, CircleAlert, CircleCheck, Cpu,
  FileSliders, LockKeyhole, MousePointer2, Play, Plus, RefreshCw, Save, Search,
  ShieldCheck, Sparkles, Trash2, Wrench, X,
} from 'lucide-vue-next'
import {
  deleteRule, getCatalog, listRules, listRuns, previewRule, saveRule,
  type ModelCatalogItem, type OptimizationRule, type OptimizationRun, type ToolCatalogItem,
} from '../services/optimizer'
import { buildExampleParameters, isStringArraySchema, schemaType, schemaTypeLabel } from '../services/schemaExamples'

type ParameterField = { path: string; type: string; description: string; safe: boolean }
const props = withDefaults(defineProps<{ demoMode?: boolean }>(), { demoMode: false })

const tools = ref<ToolCatalogItem[]>([])
const models = ref<ModelCatalogItem[]>([])
const rules = ref<OptimizationRule[]>([])
const draft = ref<OptimizationRule | null>(null)
const selectedToolName = ref('')
const ruleQuery = ref('')
const loading = ref(false)
const saving = ref(false)
const previewing = ref(false)
const error = ref('')
const previewError = ref('')
const rawParameterText = ref('{}')
const previewResult = ref<any>(null)
const runs = ref<OptimizationRun[]>([])
const runsLoading = ref(false)
const feedback = ref<{ type: 'success' | 'error'; text: string }>({ type: 'success', text: '' })

const promptNames = new Set(['prompt', 'positive_prompt', 'positive_prompts', 'negative_prompt', 'query', 'instruction', 'instructions', 'description', 'content', 'text'])
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value))

function defaultRule(): OptimizationRule {
  return {
    id: `rule-${Date.now()}`,
    name: '未命名优化规则', enabled: true, priority: 100,
    match: { tools: [], sources: ['agent_ast'], platforms: [] },
    targets: [],
    optimizer: {
      model_selector: { models: [], fallback_tags: ['fast'] },
      system_prompt: '保持用户原始意图，不增加未经提供的事实。',
      instruction_template: '提高表达的清晰度、具体性和工具可执行性。',
      temperature: 0.2, max_tokens: 1200,
    },
    execution: { timeout_ms: 15000, max_retries: 3, failure_policy: 'use_original', max_input_chars: 12000 },
    guardrails: { preserve_urls: true, preserve_references: true, deny_sensitive_fields: true, allow_unsafe_fields: false },
  }
}

const availableModelCount = computed(() => models.value.filter((model) => model.available).length)
const filteredRules = computed(() => {
  const query = ruleQuery.value.trim().toLowerCase()
  return query ? rules.value.filter((rule) => `${rule.name} ${rule.id}`.toLowerCase().includes(query)) : rules.value
})
const selectedTool = computed(() => tools.value.find((tool) => tool.name === selectedToolName.value) || null)
const primaryModel = computed({
  get: () => draft.value?.optimizer.model_selector.models[0] || '',
  set: (value: string) => { if (draft.value) draft.value.optimizer.model_selector.models = value ? [value] : [] },
})
const fallbackTagsText = computed({
  get: () => draft.value?.optimizer.model_selector.fallback_tags.join(', ') || '',
  set: (value: string) => { if (draft.value) draft.value.optimizer.model_selector.fallback_tags = value.split(',').map((item) => item.trim()).filter(Boolean) },
})
const parameterFields = computed(() => flattenSchema(selectedTool.value?.input_schema || {}))
const canPreview = computed(() => Boolean(draft.value && selectedToolName.value && draft.value.targets.length))
const isPersistedDraft = computed(() => Boolean(draft.value && rules.value.some((rule) => rule.id === draft.value?.id)))
const validationErrors = computed(() => {
  if (!draft.value) return []
  const items: string[] = []
  if (!draft.value.name.trim()) items.push('请输入规则名称')
  if (!draft.value.match.tools.length) items.push('请选择目标工具')
  if (!draft.value.targets.length) items.push('至少选择一个参数路径')
  const selector = draft.value.optimizer.model_selector
  if (!selector.models.length && !selector.fallback_tags.length) items.push('请选择模型或填写回退标签')
  return items
})
const effectiveParameterText = computed(() => previewResult.value ? JSON.stringify(previewResult.value.effective_parameters, null, 2) : '{\n  "等待预览": true\n}')

function flattenSchema(schema: Record<string, any>, prefix = ''): ParameterField[] {
  const properties = schema?.properties || {}
  return Object.entries(properties).flatMap(([name, raw]: [string, any]) => {
    const path = prefix ? `${prefix}.${name}` : name
    const type = schemaType(raw)
    if ((type === 'object' || raw.properties) && raw.properties) return flattenSchema(raw, path)
    const leaf = name.toLowerCase()
    const arrayOfStrings = isStringArraySchema(raw)
    const safe = (type === 'string' || arrayOfStrings) && (promptNames.has(leaf) || [...promptNames].some((part) => leaf.includes(part)))
    return [{ path, type: schemaTypeLabel(raw), description: raw.description || '', safe }]
  })
}

function createDraft() {
  draft.value = defaultRule()
  selectedToolName.value = ''
  rawParameterText.value = '{}'
  previewResult.value = null
}

function selectRule(rule: OptimizationRule) {
  draft.value = clone(rule)
  selectedToolName.value = rule.match.tools[0] || ''
  seedRawParameters()
  previewResult.value = null
}

function handleToolChange() {
  if (!draft.value) return
  draft.value.match.tools = selectedToolName.value ? [selectedToolName.value] : []
  draft.value.targets = []
  seedRawParameters()
}

function mergeMissing(target: Record<string, any>, defaults: Record<string, any>) {
  for (const [key, value] of Object.entries(defaults)) {
    if (!(key in target)) target[key] = value
    else if (
      target[key] && value && typeof target[key] === 'object' && typeof value === 'object'
      && !Array.isArray(target[key]) && !Array.isArray(value)
    ) mergeMissing(target[key], value)
  }
  return target
}

function seedRawParameters(preserveExisting = false) {
  const preferredPaths = draft.value?.targets.map((target) => target.path) || []
  const seeded = buildExampleParameters(selectedTool.value?.input_schema || {}, preferredPaths)
  let payload = seeded
  if (preserveExisting) {
    try {
      const current = JSON.parse(rawParameterText.value)
      if (current && typeof current === 'object' && !Array.isArray(current)) payload = mergeMissing(current, seeded)
    } catch { /* Invalid JSON remains visible and will be reported by preview. */ }
  }
  rawParameterText.value = JSON.stringify(payload, null, 2)
}

function isTargetSelected(path: string) { return Boolean(draft.value?.targets.some((target) => target.path === path)) }
function toggleTarget(path: string) {
  if (!draft.value) return
  const index = draft.value.targets.findIndex((target) => target.path === path)
  if (index >= 0) draft.value.targets.splice(index, 1)
  else {
    draft.value.targets.push({ path, mode: 'rewrite' })
    seedRawParameters(true)
  }
}

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    if (props.demoMode) {
      tools.value = [
        {
          name: 'image_generation', tool_type: 'direct',
          description: '根据正向与负向提示词生成图像。',
          input_schema: { type: 'object', properties: {
            prompt: { type: 'string', description: '描述画面主体、构图、光线与风格。' },
            negative_prompt: { type: 'string', description: '需要避免的视觉内容。' },
            width: { type: 'integer', description: '图像宽度。' },
            api_token: { type: 'string', description: '上游访问凭证。' },
          } },
        },
        {
          name: 'web_search', tool_type: 'perceptual', description: '在网页中检索信息。',
          input_schema: { type: 'object', properties: { query: { type: 'string', description: '搜索关键词。' } } },
        },
        {
          name: 'send_message', tool_type: 'direct', description: '向目标会话发送消息。',
          input_schema: { type: 'object', properties: { content: { type: 'string', description: '消息正文。' }, recipient: { type: 'string', description: '接收者标识。' } } },
        },
      ]
      models.value = [
        { name: 'gpt-5-mini', tags: ['fast', 'default'], available: true },
        { name: 'qwen3-32b', tags: ['local', 'fast'], available: true },
        { name: 'offline-model', tags: ['backup'], available: false },
      ]
      const sample = defaultRule()
      sample.id = 'image-prompt-enhancer'
      sample.name = '图片提示词增强'
      sample.match.tools = ['image_generation']
      sample.targets = [{ path: 'prompt', mode: 'rewrite' }, { path: 'negative_prompt', mode: 'rewrite_if_present' }]
      sample.optimizer.model_selector.models = ['gpt-5-mini']
      rules.value = [sample]
      selectRule(sample)
      return
    }
    const [catalog, loadedRules, loadedRuns] = await Promise.all([getCatalog(), listRules(), listRuns()])
    tools.value = catalog.tools
    models.value = catalog.models
    rules.value = loadedRules
    runs.value = loadedRuns
    if (draft.value) {
      const refreshed = loadedRules.find((rule) => rule.id === draft.value?.id)
      if (refreshed) selectRule(refreshed)
    }
  } catch (reason: any) {
    error.value = reason?.response?.data?.detail || reason?.message || '请求失败'
  } finally { loading.value = false }
}

async function handleSave() {
  if (!draft.value) return
  if (validationErrors.value.length) {
    feedback.value = { type: 'error', text: validationErrors.value.join('；') }
    return
  }
  saving.value = true
  try {
    if (props.demoMode) {
      const saved = clone(draft.value)
      const demoIndex = rules.value.findIndex((rule) => rule.id === saved.id)
      if (demoIndex >= 0) rules.value[demoIndex] = saved
      else rules.value.push(saved)
      selectRule(saved)
      feedback.value = { type: 'success', text: '演示规则已保存在当前页面' }
      return
    }
    const saved = await saveRule(draft.value)
    const index = rules.value.findIndex((rule) => rule.id === saved.id)
    if (index >= 0) rules.value[index] = saved
    else rules.value.push(saved)
    rules.value.sort((a, b) => a.priority - b.priority)
    selectRule(saved)
    feedback.value = { type: 'success', text: '规则已保存并立即生效' }
  } catch (reason: any) {
    feedback.value = { type: 'error', text: reason?.response?.data?.detail || reason?.message || '保存失败' }
  } finally { saving.value = false }
}

async function handleDelete() {
  if (!draft.value || !isPersistedDraft.value) return
  const target = draft.value
  if (!window.confirm(`确认删除规则「${target.name}」？`)) return
  saving.value = true
  try {
    if (!props.demoMode) await deleteRule(target.id)
    rules.value = rules.value.filter((rule) => rule.id !== target.id)
    if (rules.value.length) selectRule(rules.value[0])
    else createDraft()
    feedback.value = { type: 'success', text: '规则已删除' }
  } catch (reason: any) {
    feedback.value = { type: 'error', text: reason?.response?.data?.detail || reason?.message || '删除失败' }
  } finally { saving.value = false }
}

async function handlePreview() {
  if (!draft.value || !selectedToolName.value) return
  previewing.value = true
  previewError.value = ''
  previewResult.value = null
  try {
    const parameters = JSON.parse(rawParameterText.value)
    if (props.demoMode) {
      const effective = clone(parameters)
      for (const target of draft.value.targets) {
        if (typeof effective[target.path] === 'string' && effective[target.path]) {
          effective[target.path] = `${effective[target.path]}，主体明确，构图完整，光线方向清晰`
        }
      }
      previewResult.value = { raw_parameters: parameters, effective_parameters: effective, transformations: [{ paths: draft.value.targets.map((item) => item.path) }] }
      runs.value.unshift({
        call_id: `preview-${Date.now()}`, tool_name: selectedToolName.value, source: 'preview',
        rule_id: draft.value.id, rule_name: draft.value.name,
        paths: draft.value.targets.map((item) => item.path), model_name: primaryModel.value || 'tag-route',
        duration_ms: null, success: true, timestamp: Math.floor(Date.now() / 1000),
      })
      return
    }
    previewResult.value = await previewRule(draft.value, selectedToolName.value, parameters)
    await loadRuns()
  } catch (reason: any) {
    previewError.value = reason?.response?.data?.detail || reason?.message || '预览失败'
  } finally { previewing.value = false }
}

async function loadRuns() {
  if (props.demoMode) return
  runsLoading.value = true
  try { runs.value = await listRuns() }
  catch (reason: any) { feedback.value = { type: 'error', text: reason?.response?.data?.detail || reason?.message || '运行记录加载失败' } }
  finally { runsLoading.value = false }
}

function formatRunTime(timestamp: number) {
  return new Date(timestamp * 1000).toLocaleString([], { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

watch(parameterFields, () => { if (!rawParameterText.value || rawParameterText.value === '{}') seedRawParameters() })
onMounted(loadData)
</script>

<style scoped>
.optimizer-page { --panel-radius: 0.6rem; display: flex; flex-direction: column; gap: 16px; min-width: 0; padding: 4px 0 24px; color: hsl(var(--foreground)); }
.page-header, .preview-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; }
.page-header h2 { margin: 3px 0 2px; font-size: 1.65rem; line-height: 1.15; letter-spacing: -0.025em; font-weight: 680; }
.page-header p, .preview-heading p { margin: 0; color: hsl(var(--muted-foreground)); font-size: .82rem; }
.eyebrow, .panel-kicker { color: hsl(var(--muted-foreground)); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .65rem; letter-spacing: .14em; font-weight: 700; }
.header-actions { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 8px; }
.status-pill, .type-badge, .count-badge { display: inline-flex; align-items: center; gap: 6px; border: 1px solid hsl(var(--border)); border-radius: 999px; background: hsl(var(--card)); padding: 6px 9px; color: hsl(var(--muted-foreground)); font-size: .72rem; white-space: nowrap; }
.icon { width: 15px; height: 15px; }
.button, .icon-button, .text-button { display: inline-flex; align-items: center; justify-content: center; gap: 7px; border: 1px solid hsl(var(--border)); border-radius: 6px; min-height: 34px; padding: 0 12px; font-size: .8rem; font-weight: 600; transition: background-color .16s ease, color .16s ease, border-color .16s ease, transform .12s ease; }
.button:hover:not(:disabled), .icon-button:hover { background: hsl(var(--muted)); }.button:active:not(:disabled) { transform: translateY(1px); }.button:disabled { cursor: not-allowed; opacity: .48; }
.button.primary { border-color: hsl(var(--primary)); background: hsl(var(--primary)); color: hsl(var(--primary-foreground)); }.button.secondary { background: hsl(var(--card)); }
.button.danger-ghost { border-color: hsl(var(--destructive) / .26); background: hsl(var(--card)); color: hsl(var(--destructive)); }.button.danger-ghost:hover:not(:disabled) { border-color: hsl(var(--destructive) / .38); background: hsl(var(--destructive) / .07); }
.icon-button { width: 34px; padding: 0; background: transparent; }.icon-button :deep(svg) { width: 16px; }.text-button { min-height: auto; margin-left: auto; border: 0; padding: 4px; background: transparent; text-decoration: underline; }
.notice { display: flex; align-items: center; gap: 10px; border: 1px solid hsl(var(--destructive) / .3); border-radius: 8px; background: hsl(var(--destructive) / .07); padding: 12px 14px; font-size: .8rem; }.notice-icon { width: 18px; color: hsl(var(--destructive)); }.notice div { display: flex; flex-direction: column; }.notice span { color: hsl(var(--muted-foreground)); }
.feedback { display: grid; grid-template-columns: 18px 1fr 30px; align-items: center; gap: 9px; border: 1px solid hsl(var(--border)); border-radius: 8px; padding: 9px 10px 9px 12px; background: hsl(var(--card)); font-size: .76rem; box-shadow: 0 4px 14px rgb(0 0 0 / .05); }.feedback.success { border-color: #16a34a40; background: #16a34a0d; }.feedback.success .notice-icon { color: #16a34a; }.feedback.error { border-color: hsl(var(--destructive) / .32); background: hsl(var(--destructive) / .07); }.feedback-close { width: 28px; min-height: 28px; justify-self: end; border: 0; }
.workspace { display: grid; grid-template-columns: 250px minmax(360px, 1fr) 350px; min-height: 590px; border: 1px solid hsl(var(--border)); border-radius: var(--panel-radius); overflow: hidden; background: hsl(var(--card)); transition: opacity .16s ease; }.workspace.loading { opacity: .62; pointer-events: none; }
.panel { min-width: 0; background: hsl(var(--card)); }.panel + .panel { border-left: 1px solid hsl(var(--border)); }
.panel-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 68px; border-bottom: 1px solid hsl(var(--border)); padding: 13px 16px; }.panel-heading h3, .preview-heading h3 { margin: 2px 0 0; font-size: .96rem; font-weight: 650; }.heading-icon { width: 18px; color: hsl(var(--muted-foreground)); }
.panel-body { display: flex; flex-direction: column; gap: 16px; padding: 16px; }.optimizer-body { height: calc(100% - 68px); box-sizing: border-box; }
.validation-strip { display: flex; align-items: center; gap: 7px; border-left: 2px solid #b45309; background: #b453090d; padding: 8px 10px; color: #92400e; font-size: .72rem; }.validation-strip small { margin-left: auto; color: hsl(var(--muted-foreground)); white-space: nowrap; }
.rule-panel { background: hsl(var(--background) / .5); }.rule-search { position: relative; margin: 12px; }.rule-search input { width: 100%; height: 34px; box-sizing: border-box; border: 1px solid hsl(var(--border)); border-radius: 6px; background: hsl(var(--card)); padding: 0 10px 0 32px; font-size: .78rem; outline: none; }.rule-search input:focus { box-shadow: 0 0 0 1px hsl(var(--ring)); }.search-icon { position: absolute; left: 10px; top: 9px; width: 15px; color: hsl(var(--muted-foreground)); }
.rule-list { display: flex; flex-direction: column; gap: 4px; padding: 0 8px 12px; }.rule-card { display: grid; grid-template-columns: 8px 1fr 16px; align-items: center; gap: 9px; width: 100%; border: 1px solid transparent; border-radius: 7px; background: transparent; padding: 10px; text-align: left; transition: background-color .15s ease, border-color .15s ease; }.rule-card:hover { background: hsl(var(--muted) / .7); }.rule-card.active { border-color: hsl(var(--border)); background: hsl(var(--card)); box-shadow: 0 1px 2px rgb(0 0 0 / .04); }.rule-state { width: 7px; height: 7px; border-radius: 50%; background: hsl(var(--muted-foreground) / .4); }.rule-state.on { background: #16a34a; }.rule-copy { display: flex; flex-direction: column; min-width: 0; }.rule-copy strong { overflow: hidden; font-size: .79rem; text-overflow: ellipsis; white-space: nowrap; }.rule-copy small { margin-top: 2px; color: hsl(var(--muted-foreground)); font-size: .68rem; }.rule-chevron { width: 14px; color: hsl(var(--muted-foreground)); }
.field-grid { display: grid; gap: 10px; }.field-grid.two { grid-template-columns: minmax(0, 1fr) minmax(90px, .45fr); }.field-block { display: flex; flex-direction: column; gap: 6px; min-width: 0; }.field-block > span, .section-label { font-size: .72rem; font-weight: 650; }.field-block > small, .section-label-row small { color: hsl(var(--muted-foreground)); font-size: .67rem; line-height: 1.35; }
.field-control { width: 100%; box-sizing: border-box; border: 1px solid hsl(var(--input)); border-radius: 6px; background: hsl(var(--background)); min-height: 36px; padding: 7px 10px; color: inherit; font-size: .78rem; outline: none; transition: box-shadow .15s ease, border-color .15s ease; }.field-control:focus { border-color: hsl(var(--ring) / .55); box-shadow: 0 0 0 2px hsl(var(--ring) / .08); }.textarea { min-height: 105px; resize: vertical; line-height: 1.5; }.compact-textarea { min-height: 78px; }
.select-wrap { position: relative; }.select-wrap select { appearance: none; padding-right: 32px; }.select-icon { pointer-events: none; position: absolute; right: 10px; top: 10px; width: 15px; color: hsl(var(--muted-foreground)); }
.tool-summary { display: grid; grid-template-columns: 34px 1fr auto; align-items: center; gap: 10px; border: 1px solid hsl(var(--border)); border-radius: 8px; background: hsl(var(--background) / .65); padding: 10px; }.tool-mark { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 7px; background: hsl(var(--muted)); }.tool-mark :deep(svg) { width: 16px; }.tool-summary > div:nth-child(2) { display: flex; flex-direction: column; min-width: 0; }.tool-summary strong { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .75rem; }.tool-summary span:not(.type-badge) { overflow: hidden; color: hsl(var(--muted-foreground)); font-size: .67rem; text-overflow: ellipsis; white-space: nowrap; }.type-badge { padding: 3px 7px; font-size: .62rem; }
.section-label-row { display: flex; align-items: flex-end; justify-content: space-between; gap: 8px; margin-top: 2px; }.section-label-row > div { display: flex; flex-direction: column; gap: 2px; }.count-badge { padding: 3px 7px; }
.parameter-list { display: flex; flex-direction: column; gap: 6px; max-height: 310px; overflow: auto; padding-right: 2px; }.parameter-row { display: grid; grid-template-columns: 16px 1fr 17px; align-items: center; gap: 9px; border: 1px solid hsl(var(--border)); border-radius: 7px; padding: 10px; cursor: pointer; transition: background-color .15s ease, border-color .15s ease; }.parameter-row:hover { background: hsl(var(--muted) / .55); }.parameter-row.selected { border-color: hsl(var(--primary) / .35); background: hsl(var(--primary) / .04); }.parameter-row.locked { cursor: not-allowed; opacity: .62; }.parameter-main { display: flex; flex-direction: column; min-width: 0; gap: 4px; }.parameter-name { display: flex; align-items: center; gap: 7px; }.parameter-name code { font-size: .72rem; font-weight: 650; }.parameter-name > span { border-radius: 4px; background: hsl(var(--muted)); padding: 2px 5px; color: hsl(var(--muted-foreground)); font-family: ui-monospace, monospace; font-size: .58rem; }.parameter-main small { overflow: hidden; color: hsl(var(--muted-foreground)); font-size: .65rem; text-overflow: ellipsis; white-space: nowrap; }.lock-icon, .check-icon { width: 15px; color: hsl(var(--muted-foreground)); }.check-icon { color: #16a34a; }
.switch-label { display: flex; align-items: center; gap: 8px; font-size: .7rem; color: hsl(var(--muted-foreground)); }.switch-label input { position: absolute; opacity: 0; }.switch-label i { position: relative; width: 30px; height: 17px; border-radius: 999px; background: hsl(var(--muted)); transition: background .15s; }.switch-label i::after { content: ''; position: absolute; left: 2px; top: 2px; width: 13px; height: 13px; border-radius: 50%; background: hsl(var(--card)); box-shadow: 0 1px 2px rgb(0 0 0 / .18); transition: transform .15s; }.switch-label input:checked + i { background: #16a34a; }.switch-label input:checked + i::after { transform: translateX(13px); }
.segmented { display: grid; grid-template-columns: 1fr 1fr; border: 1px solid hsl(var(--border)); border-radius: 7px; padding: 3px; background: hsl(var(--background)); }.segmented button { border-radius: 5px; padding: 7px 5px; color: hsl(var(--muted-foreground)); font-size: .7rem; }.segmented button.active { background: hsl(var(--card)); color: hsl(var(--foreground)); box-shadow: 0 1px 3px rgb(0 0 0 / .08); }
.advanced-box { margin-top: auto; border: 1px solid hsl(var(--border)); border-radius: 7px; padding: 9px 10px; font-size: .72rem; }.advanced-box summary { display: flex; align-items: center; gap: 7px; cursor: pointer; font-weight: 600; list-style: none; }.summary-chevron { width: 14px; margin-left: auto; transition: transform .15s; }.advanced-box[open] .summary-chevron { transform: rotate(180deg); }.advanced-box label { display: flex; align-items: center; gap: 7px; margin-top: 9px; color: hsl(var(--muted-foreground)); }.warning-option { color: #b45309 !important; }
.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 7px; color: hsl(var(--muted-foreground)); text-align: center; }.empty-state strong { color: hsl(var(--foreground)); font-size: .8rem; }.empty-state span { max-width: 220px; font-size: .68rem; line-height: 1.45; }.empty-icon { width: 24px; height: 24px; opacity: .62; }.empty-state.compact { min-height: 160px; padding: 16px; }.tool-empty { min-height: 240px; border: 1px dashed hsl(var(--border)); border-radius: 8px; }.full-empty { height: 100%; min-height: 430px; }.rule-list .button { margin-top: 5px; }
.preview-panel { border: 1px solid hsl(var(--border)); border-radius: var(--panel-radius); background: hsl(var(--card)); padding: 16px; }.preview-heading { align-items: center; padding-bottom: 14px; }.preview-heading > div { display: grid; grid-template-columns: auto auto; align-items: baseline; gap: 2px 10px; }.preview-heading .panel-kicker { grid-column: 1 / -1; }.preview-heading p { grid-column: 2; }.preview-grid { display: grid; grid-template-columns: 1fr 80px 1fr; align-items: stretch; min-height: 220px; }.code-pane { display: flex; flex-direction: column; overflow: hidden; border: 1px solid hsl(var(--border)); border-radius: 7px; background: hsl(var(--background)); }.code-pane > span { border-bottom: 1px solid hsl(var(--border)); padding: 8px 11px; color: hsl(var(--muted-foreground)); font-family: ui-monospace, monospace; font-size: .65rem; }.code-pane textarea, .code-pane pre { flex: 1; box-sizing: border-box; width: 100%; min-height: 180px; margin: 0; border: 0; background: transparent; padding: 12px; color: inherit; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .72rem; line-height: 1.55; outline: none; resize: none; white-space: pre-wrap; }.transform-rail { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 5px; color: hsl(var(--muted-foreground)); font-size: .62rem; }.transform-rail :deep(svg) { width: 18px; }.inline-error { display: flex; align-items: center; gap: 7px; margin-top: 10px; color: hsl(var(--destructive)); font-size: .75rem; }
.runs-panel { overflow: hidden; border: 1px solid hsl(var(--border)); border-radius: var(--panel-radius); background: hsl(var(--card)); }.runs-heading { display: flex; align-items: center; justify-content: space-between; gap: 18px; border-bottom: 1px solid hsl(var(--border)); padding: 14px 16px; }.runs-heading h3 { margin: 2px 0 0; font-size: .96rem; font-weight: 650; }.runs-heading p { margin: 2px 0 0; color: hsl(var(--muted-foreground)); font-size: .7rem; }.runs-table { overflow-x: auto; }.runs-row { display: grid; grid-template-columns: 76px minmax(170px, 1.2fr) minmax(160px, 1.1fr) minmax(110px, .7fr) 82px 112px; align-items: center; gap: 12px; min-width: 820px; min-height: 48px; border-top: 1px solid hsl(var(--border) / .72); padding: 7px 16px; color: hsl(var(--muted-foreground)); font-size: .7rem; }.runs-row:first-child { border-top: 0; }.runs-row > span { display: flex; align-items: center; min-width: 0; gap: 7px; }.runs-header { min-height: 34px; background: hsl(var(--muted) / .32); color: hsl(var(--muted-foreground)); font-size: .64rem; font-weight: 650; letter-spacing: .03em; }.run-status { flex: 0 0 auto; width: 7px; height: 7px; border-radius: 50%; background: #b45309; }.run-status.success { background: #16a34a; }.run-identity { align-items: flex-start !important; flex-direction: column; gap: 2px !important; }.run-identity strong { overflow: hidden; max-width: 100%; color: hsl(var(--foreground)); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .7rem; text-overflow: ellipsis; white-space: nowrap; }.run-identity small { overflow: hidden; max-width: 100%; text-overflow: ellipsis; white-space: nowrap; }.path-list { flex-wrap: wrap; gap: 4px !important; }.path-list code { border-radius: 4px; background: hsl(var(--muted)); padding: 2px 5px; color: hsl(var(--foreground)); font-size: .62rem; }.path-list em { font-style: normal; }.runs-empty { min-height: 150px; }
.spinning { animation: spin .8s linear infinite; }@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 1180px) { .workspace { grid-template-columns: 220px minmax(360px, 1fr); }.optimizer-panel { grid-column: 1 / -1; border-top: 1px solid hsl(var(--border)); border-left: 0 !important; }.optimizer-body { display: grid; grid-template-columns: 1fr 1fr; height: auto; }.advanced-box { margin-top: 0; }.optimizer-body .field-grid, .optimizer-body .segmented { align-self: end; } }
@media (max-width: 760px) { .optimizer-page { padding: 8px 0 20px; }.page-header, .preview-heading, .runs-heading { align-items: stretch; flex-direction: column; }.header-actions { justify-content: flex-start; }.status-pill { display: none; }.workspace { display: flex; flex-direction: column; border-radius: 8px; }.panel + .panel { border-top: 1px solid hsl(var(--border)); border-left: 0; }.rule-list { max-height: 240px; overflow: auto; }.optimizer-body { display: flex; }.field-grid.two { grid-template-columns: 1fr; }.preview-grid { grid-template-columns: 1fr; gap: 8px; }.transform-rail { flex-direction: row; min-height: 34px; }.transform-rail :deep(svg) { transform: rotate(90deg); }.preview-heading > div { display: block; }.preview-heading p { margin-top: 3px; }.runs-heading .button { align-self: flex-start; } }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; animation-duration: .01ms !important; transition-duration: .01ms !important; } }
</style>
