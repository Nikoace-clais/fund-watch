import { API, request, streamSSE } from './api-client'
import type {
  AiProviderParams,
  AiSelectResponse,
  AiStreamHandlers,
  BatchFundItem,
  CronStatus,
  FundDetailData,
  FundOverviewItem,
  FundPnl,
  MarketIndex,
  NavPoint,
  OcrCfg,
  OcrResult,
  OcrStep,
  OcrStreamHandlers,
  Portfolio,
  PortfolioHoldings,
  PortfolioSummary,
  Quote,
  StockFundsResult,
  StockHolding,
  Transaction,
} from './api-types'

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

// Search funds by name/code
export function searchFunds(q: string) {
  return request<{ results: Array<{ code: string; name: string; type?: string }> }>(`/api/funds/search?q=${encodeURIComponent(q)}`)
}

// Batch add funds
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

// Fund P&L (holding shares, etc.)
export function fetchFundPnl(code: string, portfolioId?: number) {
  const qs = portfolioId != null ? `?portfolio_id=${portfolioId}` : ''
  return request<FundPnl>(`/api/funds/${code}/pnl${qs}`)
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
    history: Array<{ date: string; total_value: number; is_estimate?: boolean }>
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

  await streamSSE(
    `${API}/api/ocr/fund-code`,
    { method: 'POST', body: form },
    (event) => {
      if (event.type === 'step') handlers.onStep({ step: event.step as OcrStep['step'], text: event.text! })
      if (event.type === 'result') handlers.onResult(event.data as OcrResult)
      if (event.type === 'error') handlers.onError(event.text!)
    },
    handlers.onError,
  )
}

/** Stream agentic AI fund selection via SSE. Resolves when the stream ends. */
export async function streamAiSelect(
  theme: string,
  emphasis: string,
  providerParams: AiProviderParams,
  handlers: AiStreamHandlers,
): Promise<void> {
  await streamSSE(
    `${API}/api/ai/select/stream`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ theme, emphasis, ...providerParams }),
    },
    (event) => {
      if (event.type === 'step') handlers.onStep(event.text!)
      if (event.type === 'result') handlers.onResult(event.data as AiSelectResponse)
      if (event.type === 'error') handlers.onError(event.text!)
    },
    handlers.onError,
  )
}

export function fetchFundsHoldingStock(stockCode: string, limit = 50) {
  return request<StockFundsResult>(
    `/api/stocks/${encodeURIComponent(stockCode)}/funds?limit=${limit}`
  )
}
