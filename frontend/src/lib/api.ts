const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8010'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// Fund list + latest snapshot
export function fetchFundsOverview() {
  return request<{
    items: Array<{
      fund: { code: string; name?: string; sector?: string; holding_shares?: string; created_at: string }
      latest?: { code: string; name?: string; gsz?: number; gszzl?: number; gztime?: string; dwjz?: number } | null
      has_transactions: boolean
    }>
  }>('/api/funds/overview')
}

// Fund detail (manager, size, returns, allocation)
export function fetchFundDetail(code: string) {
  return request<{
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
  }>(`/api/funds/${code}/detail`)
}

// NAV history
export function fetchNavHistory(code: string, limit = 365) {
  return request<{
    code: string
    count: number
    history: Array<{ date: string; nav: number; accNav?: number; dailyReturn?: number }>
  }>(`/api/funds/${code}/nav-history?limit=${limit}`)
}

// Top holdings
export function fetchFundHoldings(code: string) {
  return request<{
    code: string
    count: number
    holdings: Array<{ stock_code: string; stock_name: string; percentage: number | null }>
  }>(`/api/funds/${code}/holdings`)
}

// Portfolio summary
export function fetchPortfolioSummary() {
  return request<{
    total_current: string
    total_cost: string
    total_daily_return: string
    total_return: string
    total_return_rate: string
    fund_count: number
    items: Array<{
      code: string; name?: string; shares: string | null; nav: string | null
      daily_change: number; current_value: string; daily_return: string
      total_cost: string | null; total_return: string; return_rate: string | null
      is_imported?: boolean
      imported_cumulative_return?: string
    }>
  }>('/api/portfolio/summary')
}

// Realtime quote
export function fetchQuote(code: string) {
  return request<{
    fundcode: string; name?: string; dwjz?: number; gsz?: number; gszzl?: number; gztime?: string
  }>(`/api/quote/${code}`)
}

// Add fund
export function addFund(code: string) {
  return request<{ ok: boolean }>(`/api/funds/${code}`, { method: 'POST' })
}

// Delete fund
export function deleteFund(code: string) {
  return request<{ ok: boolean }>(`/api/funds/${code}`, { method: 'DELETE' })
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

export function batchAddFunds(codes: string[], funds?: BatchFundItem[]) {
  return request<{ ok: boolean; added: string[]; invalid: string[]; warnings: string[] }>('/api/funds/batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ codes, funds: funds ?? [] }),
  })
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
}) {
  return request<{ ok: boolean; code: string }>(`/api/funds/${code}/transactions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fee: '0', ...payload }),
  })
}

// Portfolio value history (current holdings × historical NAV)
export function fetchPortfolioHistory(limit = 90) {
  return request<{
    count: number
    history: Array<{ date: string; total_value: number }>
  }>(`/api/portfolio/history?limit=${limit}`)
}

// Market indices (domestic + overseas)
export function fetchMarketIndices() {
  return request<{
    items: Array<{
      code: string
      name: string
      value: number
      change: number
      change_percent: number
    }>
  }>('/api/market/indices')
}

// Cron / scheduler status
export function fetchCronStatus() {
  return request<{
    interval_minutes: number
    trading_hours: string
    last_pull_at: string | null
    pull_count: number
    last_error: string | null
    is_active: boolean
  }>('/api/cron/status')
}

// Snapshots history (intraday)
export function fetchSnapshots(code: string, limit = 200) {
  return request<{
    code: string; count: number
    items: Array<{ gsz?: number; gszzl?: number; gztime?: string; captured_at: string }>
  }>(`/api/snapshots/${code}?limit=${limit}`)
}
