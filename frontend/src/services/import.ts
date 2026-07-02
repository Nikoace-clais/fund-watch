import type { ProviderConfig } from '@/lib/provider-config'
import { streamOcrFundCode, batchAddFunds, searchFunds, type OcrStep, type OcrResult } from '@/lib/api'

export type { OcrStep }

export interface ImportPreviewItem {
  code: string;
  name: string;
  type: string;
  confidence: number;
  source: 'code' | 'name_match' | 'table';
  needs_review: boolean;
  review?: 'confirmed' | 'corrected' | 'unreviewed';
  ocr_name?: string;       // original OCR name before correction
  similarity?: number;     // name match similarity (0-1)
  amount?: number | null;  // holding amount from OCR, drives 持仓 vs 未持仓
}

export interface ImportPreviewResult {
  funds: ImportPreviewItem[];
  total_confidence: number;
  needs_review: boolean;
  total_count: number;
}

export interface ImportConfirmResult {
  success: boolean;
  added: number;
  total: number;
  invalid: string[];
}

// Single source of truth for the high/medium confidence cutoffs — used both
// to bucket funds for display (getConfidenceInfo) and to auto-select them.
export const HIGH_CONFIDENCE = 0.85
export const MEDIUM_CONFIDENCE = 0.75

/**
 * Upload image and get import preview.
 * Uses /api/ocr/fund-code for recognition, then fills missing
 * fund names via /api/funds/search.
 */
export async function previewImport(
  files: File[],
  cfg?: ProviderConfig,
  onStep?: (s: OcrStep) => void,
): Promise<ImportPreviewResult> {
  const ocrCfg = cfg ? {
    provider: cfg.provider,
    api_key: cfg.api_key,
    base_url: cfg.base_url,
    model: cfg.model,
    analysis_model: cfg.analysis_model || undefined,
  } : undefined

  const ocr = await new Promise<OcrResult>((resolve, reject) => {
    streamOcrFundCode(files, ocrCfg, {
      onStep: onStep ?? (() => {}),
      onResult: resolve,
      onError: (msg) => reject(new Error(msg)),
    })
  })
  // Build amount lookup from matched_funds (covers both code & name_match sources)
  const amountByCode = new Map(
    ocr.matched_funds.map((f) => [f.code, f.amount ?? null])
  )
  const nameMatched = new Map(ocr.name_matches.map((m) => [m.code, m]))

  const items: ImportPreviewItem[] = []
  const seen = new Set<string>()
  for (const code of ocr.matched_codes) {
    if (seen.has(code)) continue
    seen.add(code)
    const nm = nameMatched.get(code)
    if (nm) {
      // matched by fuzzy fund-name search — confidence shaped by Pro review result
      const review = nm.review ?? 'unreviewed'
      const confidence =
        review === 'confirmed' ? 0.92
        : review === 'corrected' ? 0.85
        : nm.similarity >= 0.8 ? 0.78
        : 0.60
      items.push({
        code,
        name: nm.name,
        type: nm.type || '—',
        confidence,
        source: 'name_match',
        needs_review: review === 'unreviewed' || confidence < 0.75,
        review,
        ocr_name: nm.ocr_name,
        similarity: nm.similarity,
        amount: nm.amount ?? amountByCode.get(code) ?? null,
      })
    } else {
      // 6-digit code found directly in the screenshot → high confidence
      items.push({
        code,
        name: '',
        type: '—',
        confidence: 0.95,
        source: 'code',
        needs_review: false,
        amount: amountByCode.get(code) ?? null,
      })
    }
  }

  await Promise.allSettled(
    items
      .filter((item) => !item.name)
      .map(async (item) => {
        const r = await searchFunds(item.code)
        const hit = r.results.find((f) => f.code === item.code)
        if (hit) {
          item.name = hit.name
          if (hit.type) item.type = hit.type
        }
      }),
  )
  // Code recognized but no fund found for it → needs manual review
  for (const item of items) {
    if (!item.name) {
      item.name = item.code
      item.confidence = Math.min(item.confidence, 0.7)
      item.needs_review = true
    }
  }

  const total = items.length
  return {
    funds: items,
    total_confidence: total
      ? items.reduce((sum, item) => sum + item.confidence, 0) / total
      : 0,
    needs_review: items.some((item) => item.needs_review),
    total_count: total,
  }
}

/**
 * Confirm import of selected funds via /api/funds/batch.
 * Pass portfolioId to append to an existing portfolio, or portfolioName to create a new one.
 * Omitting both auto-generates a name like「导入 YYYY-MM-DD」.
 *
 * Items with amount > 0 trigger a synthetic buy transaction on the backend,
 * causing them to appear as held positions (持仓) instead of watch-only (未持仓).
 */
export async function confirmImport(
  items: { code: string; amount?: number | null }[],
  opts?: { portfolioId?: number; portfolioName?: string },
): Promise<ImportConfirmResult & { portfolio_id?: number }> {
  const codes = items.map((i) => i.code)
  // ponytail: only pass funds[] when there are amounts; zero-amount import still works via codes[]
  const funds: import('@/lib/api').BatchFundItem[] = items
    .filter((i) => i.amount != null && i.amount > 0)
    .map((i) => ({ code: i.code, holding_amount: i.amount! }))
  const res = await batchAddFunds(codes, funds, opts)
  return {
    success: res.ok,
    added: res.added.length,
    total: codes.length,
    invalid: res.invalid,
    portfolio_id: res.portfolio_id,
  }
}

export function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

export function getConfidenceInfo(confidence: number): { color: string; label: string; className: string } {
  if (confidence >= HIGH_CONFIDENCE) return { color: 'text-green-600', label: '高置信度', className: 'bg-green-100 text-green-800' };
  if (confidence >= MEDIUM_CONFIDENCE) return { color: 'text-yellow-600', label: '中置信度', className: 'bg-yellow-100 text-yellow-800' };
  return { color: 'text-red-600', label: '需确认', className: 'bg-red-100 text-red-800' };
}
