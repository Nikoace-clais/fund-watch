/// <reference types="vite/client" />

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8010'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

/* ── Shared response types (single source of truth for pages/components) ── */

export type FundSnapshot = {
  code: string
  name?: string
  gsz?: number
  gszzl?: number
  gztime?: string
  dwjz?: number
}

export type FundOverviewItem = {
  fund: { code: string; name?: string; sector?: string; holding_shares?: string; created_at: string }
  latest?: FundSnapshot | null
  has_transactions: boolean
}

export type FundDetailData = {
  code: string
  name?: string
  fund_type?: string
  manager?: string
  size?: number
  established_date?: string
  one_month_return?: number
  three_month_return?: number
  six_month_return?: number
  one_year_return?: number
  asset_allocation: Array<{ name: string; value: number }>
  sector?: string
  subscription_rate?: number
  subscription_rate_discounted?: number
  manager_power_scores?: number[] | null
  manager_power_categories?: string[] | null
}

export type NavPoint = { date: string; nav: number; accNav?: number; dailyReturn?: number }

export type StockHolding = { stock_code: string; stock_name: string; percentage: number | null }

export type PortfolioItem = {
  code: string
  name?: string
  shares: string | null
  nav: string | null
  daily_change: number
  current_value: string
  daily_return: string
  total_cost: string | null
  total_return: string
  return_rate: string | null
  is_imported?: boolean
  imported_cumulative_return?: string
}

export type PortfolioSummary = {
  portfolio_id: number
  total_current: string
  total_cost: string
  total_daily_return: string
  total_return: string
  total_return_rate: string
  fund_count: number
  items: PortfolioItem[]
  watch_codes: string[]
}

export type Portfolio = {
  id: number
  name: string
  created_at: string
  fund_count: number
}

export type Quote = {
  fundcode: string
  name?: string
  dwjz?: number
  gsz?: number
  gszzl?: number
  gztime?: string
}

export type MarketIndex = {
  code: string
  name: string
  region: 'domestic' | 'international'
  value: number
  change: number
  change_percent: number
}

export type CronStatus = {
  interval_minutes: number
  trading_hours: string
  last_pull_at: string | null
  pull_count: number
  last_error: string | null
  is_active: boolean
}

export type Transaction = {
  id: number
  portfolio_id?: number | null
  direction: 'buy' | 'sell'
  trade_date: string
  nav: string
  shares: string
  amount: string
  fee: string
  note?: string | null
  source?: string | null
  created_at: string
}

/* ── Endpoints ──────────────────────────────────────────────────────────── */

// Fund list + latest snapshot
export function fetchFundsOverview() {
  return request<{ items: FundOverviewItem[] }>('/api/funds/overview')
}

// Fund detail (manager, size, returns, allocation)
export function fetchFundDetail(code: string) {
  return request<FundDetailData>(`/api/funds/${code}/detail`)
}

// NAV history
export function fetchNavHistory(code: string, limit = 365) {
  return request<{ code: string; count: number; history: NavPoint[] }>(
    `/api/funds/${code}/nav-history?limit=${limit}`
  )
}

// Top holdings
export function fetchFundHoldings(code: string) {
  return request<{ code: string; count: number; holdings: StockHolding[] }>(
    `/api/funds/${code}/holdings`
  )
}

// Portfolios CRUD
export function listPortfolios() {
  return request<{ items: Portfolio[] }>('/api/portfolios')
}

export function createPortfolio(name: string) {
  return request<{ ok: boolean; id: number; name: string }>('/api/portfolios', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
}

export function renamePortfolio(id: number, name: string) {
  return request<{ ok: boolean; id: number; name: string }>(`/api/portfolios/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
}

export function deletePortfolio(id: number) {
  return request<{ ok: boolean; id: number }>(`/api/portfolios/${id}`, { method: 'DELETE' })
}

// Portfolio summary
export function fetchPortfolioSummary(portfolioId?: number) {
  const qs = portfolioId != null ? `?portfolio_id=${portfolioId}` : ''
  return request<PortfolioSummary>(`/api/portfolio/summary${qs}`)
}

// Portfolio holdings X-ray
export type HoldingXrayFund = { code: string; name: string; percentage: number | null; contribution: string }
export type HoldingXrayStock = {
  stock_code: string; stock_name: string; industry: string | null
  exposure: string; weight_pct: number; fund_count: number
  funds: HoldingXrayFund[]
}
export type HoldingXraySector = { name: string; exposure: string; weight_pct: number }
export type PortfolioHoldings = {
  portfolio_id: number
  total_value: string; covered_value: string
  stocks: HoldingXrayStock[]; sectors: HoldingXraySector[]; coverage: Record<string, number>
}
export function fetchPortfolioHoldings(portfolioId?: number) {
  const qs = portfolioId != null ? `?portfolio_id=${portfolioId}` : ''
  return request<PortfolioHoldings>(`/api/portfolio/holdings${qs}`)
}

// Realtime quote
export function fetchQuote(code: string) {
  return request<Quote>(`/api/quote/${code}`)
}

// Add fund
export function addFund(code: string) {
  return request<{ ok: boolean }>(`/api/funds/${code}`, { method: 'POST' })
}

// Delete fund
export function deleteFund(code: string, portfolioId?: number) {
  const qs = portfolioId != null ? `?portfolio_id=${portfolioId}` : ''
  return request<{ ok: boolean }>(`/api/funds/${code}${qs}`, { method: 'DELETE' })
}

// Pull snapshots
export function pullSnapshots() {
  return request<{ ok: boolean }>('/api/snapshots/pull', { method: 'POST' })
}

// Search funds by name/code
export function searchFunds(q: string) {
  return request<{ results: Array<{ code: string; name: string; type?: string }> }>(`/api/funds/search?q=${encodeURIComponent(q)}`)
}

// Batch add funds
export type BatchFundItem = {
  code?: string
  name?: string
  holding_amount?: number
  cumulative_return?: number
  holding_return?: number
}

export function batchAddFunds(
  codes: string[],
  funds?: BatchFundItem[],
  opts?: { portfolioId?: number; portfolioName?: string },
) {
  return request<{ ok: boolean; portfolio_id: number; added: string[]; invalid: string[]; warnings: string[] }>(
    '/api/funds/batch',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        codes,
        funds: funds ?? [],
        portfolio_id: opts?.portfolioId,
        portfolio_name: opts?.portfolioName,
      }),
    },
  )
}

// NAV on a specific date
export function fetchNavOnDate(code: string, date: string) {
  return request<{ code: string; date: string; nav: number | null }>(`/api/funds/${code}/nav-on?date=${date}`)
}

// Add transaction (buy/sell)
export function addTransaction(code: string, payload: {
  direction: 'buy' | 'sell'
  trade_date: string
  nav: string
  shares: string
  fee?: string
  note?: string
  portfolio_id?: number
}) {
  return request<{ ok: boolean; code: string }>(`/api/funds/${code}/transactions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fee: '0', ...payload }),
  })
}

// Portfolio value history (current holdings × historical NAV)
export function fetchPortfolioHistory(limit = 90, portfolioId?: number) {
  const qs = portfolioId != null ? `&portfolio_id=${portfolioId}` : ''
  return request<{
    portfolio_id: number
    count: number
    history: Array<{ date: string; total_value: number }>
  }>(`/api/portfolio/history?limit=${limit}${qs}`)
}

// Market indices (domestic + overseas)
export function fetchMarketIndices() {
  return request<{ items: MarketIndex[] }>('/api/market/indices')
}

// Cron / scheduler status
export function fetchCronStatus() {
  return request<CronStatus>('/api/cron/status')
}

// Snapshots history (intraday)
export function fetchSnapshots(code: string, limit = 200) {
  return request<{
    code: string; count: number
    items: Array<{ gsz?: number; gszzl?: number; gztime?: string; captured_at: string }>
  }>(`/api/snapshots/${code}?limit=${limit}`)
}

export function fetchTransactions(code: string, portfolioId?: number) {
  const qs = portfolioId != null ? `?portfolio_id=${portfolioId}` : ''
  return request<{ code: string; items: Transaction[] }>(
    `/api/funds/${code}/transactions${qs}`
  )
}

export function deleteTransaction(txId: number) {
  return request<{ ok: boolean; deleted: number }>(`/api/transactions/${txId}`, { method: 'DELETE' })
}

export function getOcrStatus() {
  return request<{ ready: boolean }>('/api/ocr/status')
}

type OcrCfg = { provider?: string; api_key?: string; base_url?: string; model?: string; analysis_model?: string }

export type OcrNameMatch = {
  code: string
  name: string
  type?: string
  ocr_name: string
  similarity: number
  review?: 'confirmed' | 'corrected' | 'unreviewed'
  corrected_name?: string | null
  amount?: number | null
}

export type OcrResult = {
  matched_codes: string[]
  matched_funds: { code: string; name: string; amount?: number | null }[]
  name_matches: OcrNameMatch[]
  raw_text: string
}

export type OcrStep = {
  step: 'ocr' | 'ai_extract' | 'search' | 'pro_identify' | 'pro_review'
  text: string
}

export type OcrStreamHandlers = {
  onStep: (s: OcrStep) => void
  onResult: (r: OcrResult) => void
  onError: (msg: string) => void
}

export async function streamOcrFundCode(
  files: File[],
  cfg: OcrCfg | undefined,
  handlers: OcrStreamHandlers,
): Promise<void> {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  if (cfg?.provider) form.append('provider', cfg.provider)
  if (cfg?.api_key) form.append('api_key', cfg.api_key)
  if (cfg?.base_url) form.append('base_url', cfg.base_url)
  if (cfg?.model) form.append('model', cfg.model)
  if (cfg?.analysis_model) form.append('analysis_model', cfg.analysis_model)

  const res = await fetch(`${API}/api/ocr/fund-code`, { method: 'POST', body: form })
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => ({}))
    handlers.onError(err.detail || `HTTP ${res.status}`)
    return
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const parts = buf.split('\n\n')
    buf = parts.pop() ?? ''
    for (const part of parts) {
      const line = part.trim()
      if (!line.startsWith('data:')) continue
      try {
        const event = JSON.parse(line.slice('data:'.length).trim())
        if (event.type === 'step')   handlers.onStep({ step: event.step, text: event.text })
        if (event.type === 'result') handlers.onResult(event.data)
        if (event.type === 'error')  handlers.onError(event.text)
      } catch { /* malformed chunk */ }
    }
  }
}

// ── AI Fund Selection ───────────────────────────────────────────────────────

export type AiFundRec = {
  rank: number
  code: string
  name: string
  one_year_return: number | null
  three_year_return: number | null
  max_drawdown: number | null
  fee: string | null
  manager: string | null
  size: number | null
  reason: string
}

export type AiSelectResponse = {
  summary: string
  recommendations: AiFundRec[]
}


export type AiProviderParams = {
  provider: string
  api_key?: string
  base_url?: string
  model?: string
  analysis_model?: string
}

export type AiStreamHandlers = {
  onStep: (text: string) => void
  onResult: (data: AiSelectResponse) => void
  onError: (text: string) => void
}

/** Stream agentic AI fund selection via SSE. Resolves when the stream ends. */
export async function streamAiSelect(
  theme: string,
  emphasis: string,
  providerParams: AiProviderParams,
  handlers: AiStreamHandlers,
): Promise<void> {
  const res = await fetch(`${API}/api/ai/select/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ theme, emphasis, ...providerParams }),
  })
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => ({}))
    handlers.onError(err.detail || `HTTP ${res.status}`)
    return
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const parts = buf.split('\n\n')
    buf = parts.pop() ?? ''
    for (const part of parts) {
      const line = part.trim()
      if (!line.startsWith('data:')) continue
      try {
        const event = JSON.parse(line.slice('data:'.length).trim())
        if (event.type === 'step')   handlers.onStep(event.text)
        if (event.type === 'result') handlers.onResult(event.data)
        if (event.type === 'error')  handlers.onError(event.text)
      } catch {
        // malformed chunk, skip
      }
    }
  }
}

// ── Stock → Funds reverse lookup ────────────────────────────────────────────

export type FundHolderItem = {
  code: string
  name: string
  hold_market_cap: number | null
  shares: number | null
  netasset_ratio: number | null
  company: string | null
}

export type StockFundsResult = {
  stock_code: string
  stock_name: string | null
  report_date: string | null
  count: number
  items: FundHolderItem[]
}

export function fetchFundsHoldingStock(stockCode: string, limit = 50) {
  return request<StockFundsResult>(
    `/api/stocks/${encodeURIComponent(stockCode)}/funds?limit=${limit}`
  )
}
