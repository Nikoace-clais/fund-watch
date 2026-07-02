import type { BatchFundItem } from './api'

export type ParsedBatchInput = { codes: string[]; funds: BatchFundItem[] }

/** Parse the AddFundModal batch-paste textarea: JSON funds/codes array, or
 * plain-text codes separated by newlines/commas/spaces. */
export function parseBatchInput(input: string): ParsedBatchInput {
  const trimmed = input.trim()
  if (!trimmed) return { codes: [], funds: [] }

  try {
    const parsed = JSON.parse(trimmed)
    // New format: {"funds": [{name?, code?, holding_amount?, cumulative_return?, holding_return?}]}
    if (parsed.funds && Array.isArray(parsed.funds)) {
      const funds: BatchFundItem[] = parsed.funds
        .filter((f: unknown) => typeof (f as any)?.name === 'string' || (typeof (f as any)?.code === 'string' && /^\d{6}$/.test((f as any).code)))
        .map((f: any) => ({
          code: typeof f.code === 'string' && /^\d{6}$/.test(f.code) ? f.code : undefined,
          name: typeof f.name === 'string' ? f.name : undefined,
          holding_amount: typeof f.holding_amount === 'number' ? f.holding_amount : undefined,
          cumulative_return: typeof f.cumulative_return === 'number' ? f.cumulative_return : undefined,
          holding_return: typeof f.holding_return === 'number' ? f.holding_return : undefined,
        }))
      return { codes: [], funds }
    }
    // Old format: {"codes": [...]}
    if (parsed.codes && Array.isArray(parsed.codes)) {
      return {
        codes: parsed.codes.filter((c: unknown) => typeof c === 'string' && /^\d{6}$/.test(c as string)),
        funds: [],
      }
    }
    if (Array.isArray(parsed)) {
      return {
        codes: parsed.filter((c: unknown) => typeof c === 'string' && /^\d{6}$/.test(c as string)),
        funds: [],
      }
    }
  } catch {
    // Not JSON
  }

  // Plain text: split by newlines, commas, spaces
  const tokens = trimmed.split(/[\n,\s]+/).map((s) => s.trim()).filter(Boolean)
  return { codes: tokens.filter((t) => /^\d{6}$/.test(t)), funds: [] }
}
