import api from './api'


export type ToolCatalogItem = {
  name: string
  description: string
  input_schema: Record<string, any>
  tool_type: string
}

export type ModelCatalogItem = {
  name: string
  tags: string[]
  available: boolean
}

export type OptimizationRule = {
  id: string
  name: string
  enabled: boolean
  priority: number
  match: {
    tools: string[]
    sources: string[]
    platforms: string[]
  }
  targets: Array<{ path: string; mode: 'rewrite' | 'rewrite_if_present' }>
  optimizer: {
    model_selector: { models: string[]; fallback_tags: string[] }
    system_prompt: string
    instruction_template: string
    temperature: number
    max_tokens: number
  }
  execution: {
    timeout_ms: number
    max_retries: number
    failure_policy: 'use_original' | 'fail_call'
    max_input_chars: number
  }
  guardrails: {
    preserve_urls: boolean
    preserve_references: boolean
    deny_sensitive_fields: boolean
    allow_unsafe_fields: boolean
  }
}

export type OptimizationRun = {
  call_id: string
  tool_name: string
  source: string
  rule_id: string
  rule_name: string
  paths: string[]
  model_name?: string | null
  duration_ms?: number | null
  attempts?: number
  success: boolean
  error?: string
  timestamp: number
}

export async function getCatalog() {
  const response = await api.get<{ tools: ToolCatalogItem[]; models: ModelCatalogItem[] }>('/tool-optimizer/catalog')
  return response.data
}

export async function listRules() {
  const response = await api.get<{ rules: OptimizationRule[] }>('/tool-optimizer/rules')
  return response.data.rules
}

export async function saveRule(rule: OptimizationRule) {
  const response = await api.post<{ rule: OptimizationRule }>('/tool-optimizer/rules', rule)
  return response.data.rule
}

export async function deleteRule(ruleId: string) {
  await api.delete(`/tool-optimizer/rules/${encodeURIComponent(ruleId)}`)
}

export async function previewRule(rule: OptimizationRule, toolName: string, parameters: Record<string, any>) {
  const response = await api.post('/tool-optimizer/preview', {
    rule,
    tool_name: toolName,
    parameters,
  })
  return response.data
}

export async function listRuns() {
  const response = await api.get<{ runs: OptimizationRun[] }>('/tool-optimizer/runs')
  return response.data.runs
}
