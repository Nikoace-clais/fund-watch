import { ocrFundCode, batchAddFunds, searchFunds } from '@/lib/api'

export interface ImportPreviewItem {
  code: string;
  name: string;
  type: string;
  confidence: number;
  source: 'code' | 'name_match' | 'table';
  needs_review: boolean;
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

/**
 * Upload image and get import preview.
 * Uses /api/ocr/fund-code for recognition, then fills missing
 * fund names via /api/funds/search.
 */
export async function previewImport(file: File): Promise<ImportPreviewResult> {
  const ocr = await ocrFundCode(file)
  const nameMatched = new Map(ocr.name_matches.map((m) => [m.code, m]))

  const items: ImportPreviewItem[] = []
  const seen = new Set<string>()
  for (const code of ocr.matched_codes) {
    if (seen.has(code)) continue
    seen.add(code)
    const nm = nameMatched.get(code)
    if (nm) {
      // matched by fuzzy fund-name search → medium confidence
      items.push({
        code,
        name: nm.name,
        type: nm.type || '—',
        confidence: 0.78,
        source: 'name_match',
        needs_review: true,
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
 */
export async function confirmImport(codes: string[]): Promise<ImportConfirmResult> {
  const res = await batchAddFunds(codes)
  return {
    success: res.ok,
    added: res.added.length,
    total: codes.length,
    invalid: res.invalid,
  }
}

export function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

export function getConfidenceInfo(confidence: number): { color: string; label: string; className: string } {
  if (confidence >= 0.85) return { color: 'text-green-600', label: '高置信度', className: 'bg-green-100 text-green-800' };
  if (confidence >= 0.75) return { color: 'text-yellow-600', label: '中置信度', className: 'bg-yellow-100 text-yellow-800' };
  return { color: 'text-red-600', label: '需确认', className: 'bg-red-100 text-red-800' };
}
