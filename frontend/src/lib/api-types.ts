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

export type BatchFundItem = {
  code?: string
  name?: string
  holding_amount?: number
  cumulative_return?: number
  holding_return?: number
}

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

export type OcrCfg = { provider?: string; api_key?: string; base_url?: string; model?: string; analysis_model?: string }

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
