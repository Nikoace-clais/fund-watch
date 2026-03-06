const API = 'http://127.0.0.1:8010'

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
      code: string; name?: string; shares: string; nav: string
      daily_change: number; current_value: string; daily_return: string
      total_cost: string; total_return: string; return_rate: string
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

// Snapshots history (intraday)
export function fetchSnapshots(code: string, limit = 200) {
  return request<{
    code: string; count: number
    items: Array<{ gsz?: number; gszzl?: number; gztime?: string; captured_at: string }>
  }>(`/api/snapshots/${code}?limit=${limit}`)
}
