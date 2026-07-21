import type { BatchFundItem } from './api'
import { isFundCode } from './utils'

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
      type RawFund = {
        name?: unknown
        code?: unknown
        holding_amount?: unknown
        cumulative_return?: unknown
        holding_return?: unknown
      }
      const funds: BatchFundItem[] = (parsed.funds as unknown[])
        .filter((f): f is RawFund => {
          if (typeof f !== 'object' || f === null) return false
          const r = f as RawFund
          return (
            typeof r.name === 'string' ||
            (typeof r.code === 'string' && isFundCode(r.code))
          )
        })
        .map((f) => ({
          code:
            typeof f.code === 'string' && isFundCode(f.code)
              ? f.code
              : undefined,
          name: typeof f.name === 'string' ? f.name : undefined,
          holding_amount:
            typeof f.holding_amount === 'number' ? f.holding_amount : undefined,
          cumulative_return:
            typeof f.cumulative_return === 'number'
              ? f.cumulative_return
              : undefined,
          holding_return:
            typeof f.holding_return === 'number' ? f.holding_return : undefined,
        }))
      return { codes: [], funds }
    }
    // Old format: {"codes": [...]}
    if (parsed.codes && Array.isArray(parsed.codes)) {
      return {
        codes: parsed.codes.filter(
          (c: unknown) => typeof c === 'string' && isFundCode(c),
        ),
        funds: [],
      }
    }
    if (Array.isArray(parsed)) {
      return {
        codes: parsed.filter(
          (c: unknown) => typeof c === 'string' && isFundCode(c),
        ),
        funds: [],
      }
    }
  } catch {
    // Not JSON
  }

  // Plain text: split by newlines, commas, spaces
  const tokens = trimmed
    .split(/[\n,\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
  return { codes: tokens.filter(isFundCode), funds: [] }
}
