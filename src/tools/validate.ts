import type { JsonSchema } from './types.js'

export function validateToolInput(schema: JsonSchema, input: unknown) {
  const errors: string[] = []
  if (schema.type === 'object') {
    if (!isRecord(input)) return ['input must be an object']
    for (const key of readStringArray(schema.required)) {
      if (!(key in input)) errors.push(`missing required field: ${key}`)
    }
    const properties = isRecord(schema.properties) ? schema.properties : {}
    for (const [key, propertySchema] of Object.entries(properties)) {
      if (!(key in input) || !isRecord(propertySchema)) continue
      const value = input[key]
      const type = propertySchema.type
      if (typeof type === 'string' && !matchesJsonType(value, type)) {
        errors.push(`${key} must be ${type}`)
      }
    }
  }
  return errors
}

function matchesJsonType(value: unknown, type: string) {
  if (type === 'array') return Array.isArray(value)
  if (type === 'object') return isRecord(value)
  if (type === 'integer') return Number.isInteger(value)
  return typeof value === type
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function readStringArray(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}
