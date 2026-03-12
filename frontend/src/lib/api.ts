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

export type Transaction = {
  id: number
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

export function fetchTransactions(code: string) {
  return request<{ code: string; items: Transaction[] }>(
    `/api/funds/${code}/transactions`
  )
}

export function deleteTransaction(txId: number) {
  return request<{ ok: boolean; deleted: number }>(`/api/transactions/${txId}`, { method: 'DELETE' })
}

export function ocrFundCode(file: File) {
  const form = new FormData()
  form.append('file', file)
  return request<{
    matched_codes: string[]
    matched_funds: { code: string; name: string }[]
    name_matches: { code: string; name: string; matched_keyword: string; type?: string }[]
    raw_text: string
  }>('/api/ocr/fund-code', { method: 'POST', body: form })
}

// ── DCA ────────────────────────────────────────────────────────────────────

export type DcaPlan = {
  id: number
  code: string
  name?: string | null
  amount: string
  frequency: 'daily' | 'weekly' | 'biweekly' | 'monthly'
  day_of_week?: number | null
  day_of_month?: number | null
  start_date: string
  end_date?: string | null
  is_active: number
  created_at: string
}

export type DcaRecord = {
  id: number
  plan_id: number
  scheduled_date: string
  status: 'success' | 'failed'
  transaction_id?: number | null
  note?: string | null
  nav?: string | null
  shares?: string | null
  tx_amount?: string | null
  created_at: string
}

export type DcaStats = {
  plan_id: number
  code: string
  total_periods: number
  success_count: number
  failed_count: number
  total_invested: string
  avg_cost: string
  total_shares: string
  current_value: string
  total_return: string
  return_rate: string
}

export function fetchDcaPlans() {
  return request<{ items: DcaPlan[] }>('/api/dca/plans')
}

export function fetchDcaPlansByCode(code: string) {
  return fetchDcaPlans().then((r) => ({
    items: r.items.filter((p) => p.code === code),
  }))
}

export function createDcaPlan(payload: {
  code: string
  name?: string
  amount: string
  frequency: string
  day_of_week?: number
  day_of_month?: number
  start_date: string
  end_date?: string
}) {
  return request<{ ok: boolean; id: number }>('/api/dca/plans', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function patchDcaPlan(planId: number, payload: Partial<{
  name: string; amount: string; frequency: string
  day_of_week: number; day_of_month: number; end_date: string; is_active: number
}>) {
  return request<{ ok: boolean }>(`/api/dca/plans/${planId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function deleteDcaPlan(planId: number) {
  return request<{ ok: boolean }>(`/api/dca/plans/${planId}`, { method: 'DELETE' })
}

export function fetchDcaRecords(planId: number) {
  return request<{ items: DcaRecord[] }>(`/api/dca/plans/${planId}/records`)
}

export function addDcaRecord(planId: number, payload: {
  scheduled_date: string
  status: 'success' | 'failed'
  transaction_id?: number
  note?: string
}) {
  return request<{ ok: boolean; id: number }>(`/api/dca/plans/${planId}/records`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function patchDcaRecord(recordId: number, payload: Partial<{
  status: string; transaction_id: number | null; note: string | null
}>) {
  return request<{ ok: boolean }>(`/api/dca/records/${recordId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function deleteDcaRecord(recordId: number) {
  return request<{ ok: boolean }>(`/api/dca/records/${recordId}`, { method: 'DELETE' })
}

export function fetchDcaPlanStats(planId: number) {
  return request<DcaStats>(`/api/dca/plans/${planId}/stats`)
}

export function fetchAllDcaStats() {
  return request<{ items: DcaStats[] }>('/api/dca/stats')
}
