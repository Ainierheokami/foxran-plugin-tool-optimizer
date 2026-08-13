export type JsonSchema = Record<string, any>


function hasOwn(value: object, key: string) {
  return Object.prototype.hasOwnProperty.call(value, key)
}

function clone<T>(value: T): T {
  return value == null ? value : JSON.parse(JSON.stringify(value))
}

function nonNullVariant(schema: JsonSchema): JsonSchema {
  const variants = schema.anyOf || schema.oneOf || []
  const candidate = variants.find((item: JsonSchema) => item?.type !== 'null')
  return candidate ? { ...schema, ...candidate, anyOf: undefined, oneOf: undefined } : schema
}

export function schemaType(schema: JsonSchema): string {
  const resolved = nonNullVariant(schema || {})
  if (resolved.type) return resolved.type
  if (resolved.properties) return 'object'
  return 'unknown'
}

export function isStringArraySchema(schema: JsonSchema): boolean {
  const resolved = nonNullVariant(schema || {})
  return resolved.type === 'array' && nonNullVariant(resolved.items || {}).type === 'string'
}

export function schemaTypeLabel(schema: JsonSchema): string {
  const variants = schema?.anyOf || schema?.oneOf
  if (Array.isArray(variants)) {
    const labels = variants.map((item: JsonSchema) => item?.type).filter(Boolean)
    if (labels.length) return labels.join(' | ')
  }
  if (isStringArraySchema(schema)) return 'string[]'
  return schemaType(schema)
}

function stringExample(name: string): string {
  const leaf = name.toLowerCase()
  if (leaf.includes('negative')) return '低质量、模糊、构图混乱'
  if (leaf.includes('query')) return '示例搜索关键词'
  if (leaf.includes('prompt') || leaf.includes('instruction')) return '清晰描述主体、动作、环境与期望效果'
  return '示例内容'
}

function exampleValue(schema: JsonSchema, name: string, preferredPaths: string[]): any {
  const resolved = nonNullVariant(schema || {})
  if (hasOwn(resolved, 'const')) return clone(resolved.const)
  if (hasOwn(resolved, 'default') && resolved.default !== null) return clone(resolved.default)
  if (hasOwn(resolved, 'example')) return clone(resolved.example)
  if (Array.isArray(resolved.examples) && resolved.examples.length) return clone(resolved.examples[0])
  if (Array.isArray(resolved.enum) && resolved.enum.length) {
    return clone(resolved.enum.find((item: any) => item !== null) ?? resolved.enum[0])
  }

  switch (schemaType(resolved)) {
    case 'object': {
      const nestedPaths = preferredPaths.map((path) => path === name ? '' : path.slice(name.length + 1)).filter(Boolean)
      return buildExampleParameters(resolved, nestedPaths)
    }
    case 'array':
      return isStringArraySchema(resolved) ? [stringExample(name)] : []
    case 'integer':
    case 'number':
      return typeof resolved.minimum === 'number' ? resolved.minimum : 0
    case 'boolean':
      return false
    case 'string':
      return stringExample(name)
    default:
      return null
  }
}

export function buildExampleParameters(schema: JsonSchema, preferredPaths: string[] = []): Record<string, any> {
  const properties = schema?.properties || {}
  const required = new Set<string>(schema?.required || [])
  const payload: Record<string, any> = {}

  for (const [name, rawValue] of Object.entries(properties)) {
    const raw = rawValue as JsonSchema
    const preferred = preferredPaths.some((path) => path === name || path.startsWith(`${name}.`))
    const shouldInclude = required.has(name) || preferred
    if (!shouldInclude) continue

    const value = exampleValue(raw, name, preferredPaths.filter((path) => path === name || path.startsWith(`${name}.`)))
    if (value !== null || required.has(name) || preferred) payload[name] = value
  }
  return payload
}
