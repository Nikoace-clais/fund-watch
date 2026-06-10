import { QueryClient, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import {
  fetchAllDcaStats,
  fetchCronStatus,
  fetchDcaPlans,
  fetchDcaPlanStats,
  fetchDcaRecords,
  fetchFundDetail,
  fetchFundHoldings,
  fetchFundsOverview,
  fetchMarketIndices,
  fetchNavHistory,
  fetchPortfolioHistory,
  fetchPortfolioSummary,
  fetchQuote,
  fetchTransactions,
  type DcaStats,
} from './api'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

/* ---------- query keys ---------- */
export const keys = {
  fundsOverview: ['funds', 'overview'] as const,
  portfolioSummary: ['portfolio', 'summary'] as const,
  portfolioHistory: (limit: number) => ['portfolio', 'history', limit] as const,
  marketIndices: ['market', 'indices'] as const,
  cronStatus: ['cron', 'status'] as const,
  fundDetail: (code: string) => ['fund', code, 'detail'] as const,
  navHistory: (code: string, limit: number) => ['fund', code, 'nav-history', limit] as const,
  fundHoldings: (code: string) => ['fund', code, 'holdings'] as const,
  quote: (code: string) => ['fund', code, 'quote'] as const,
  transactions: (code: string) => ['fund', code, 'transactions'] as const,
  dcaPlans: ['dca', 'plans'] as const,
  dcaAllStats: ['dca', 'stats'] as const,
  dcaPlanStats: (planId: number) => ['dca', 'plan', planId, 'stats'] as const,
  dcaPlanRecords: (planId: number) => ['dca', 'plan', planId, 'records'] as const,
}

/* ---------- hooks ---------- */
export function useFundsOverview() {
  return useQuery({
    queryKey: keys.fundsOverview,
    queryFn: fetchFundsOverview,
    select: (r) => r.items,
  })
}

export function usePortfolioSummary() {
  return useQuery({ queryKey: keys.portfolioSummary, queryFn: fetchPortfolioSummary })
}

export function usePortfolioHistory(limit: number) {
  return useQuery({
    queryKey: keys.portfolioHistory(limit),
    queryFn: () => fetchPortfolioHistory(limit),
    select: (r) => r.history,
  })
}

export function useMarketIndices() {
  return useQuery({
    queryKey: keys.marketIndices,
    queryFn: fetchMarketIndices,
    select: (r) => r.items,
  })
}

export function useCronStatus() {
  return useQuery({
    queryKey: keys.cronStatus,
    queryFn: fetchCronStatus,
    refetchInterval: 60_000,
  })
}

export function useFundDetail(code: string | undefined) {
  return useQuery({
    queryKey: keys.fundDetail(code ?? ''),
    queryFn: () => fetchFundDetail(code!),
    enabled: !!code,
  })
}

export function useNavHistory(code: string | undefined, limit = 365) {
  return useQuery({
    queryKey: keys.navHistory(code ?? '', limit),
    queryFn: () => fetchNavHistory(code!, limit),
    select: (r) => r.history,
    enabled: !!code,
  })
}

export function useFundHoldings(code: string | undefined) {
  return useQuery({
    queryKey: keys.fundHoldings(code ?? ''),
    queryFn: () => fetchFundHoldings(code!),
    select: (r) => r.holdings,
    enabled: !!code,
  })
}

export function useQuote(code: string | undefined) {
  return useQuery({
    queryKey: keys.quote(code ?? ''),
    queryFn: () => fetchQuote(code!),
    enabled: !!code,
  })
}

export function useTransactions(code: string | undefined, enabled = true) {
  return useQuery({
    queryKey: keys.transactions(code ?? ''),
    queryFn: () => fetchTransactions(code!),
    select: (r) => r.items,
    enabled: !!code && enabled,
  })
}

export function useDcaPlans(code?: string) {
  return useQuery({
    queryKey: keys.dcaPlans,
    queryFn: fetchDcaPlans,
    select: (r) => (code ? r.items.filter((p) => p.code === code) : r.items),
  })
}

export function useAllDcaStats() {
  return useQuery({
    queryKey: keys.dcaAllStats,
    queryFn: fetchAllDcaStats,
    select: (r) => {
      const m = new Map<number, DcaStats>()
      r.items.forEach((s) => m.set(s.plan_id, s))
      return m
    },
  })
}

export function useDcaPlanStats(planId: number) {
  return useQuery({
    queryKey: keys.dcaPlanStats(planId),
    queryFn: () => fetchDcaPlanStats(planId),
  })
}

export function useDcaPlanRecords(planId: number, enabled: boolean) {
  return useQuery({
    queryKey: keys.dcaPlanRecords(planId),
    queryFn: () => fetchDcaRecords(planId),
    select: (r) => r.items,
    enabled,
  })
}

/** 持仓/交易变动后,使组合相关查询失效(overview、summary、history、各基金交易记录) */
export function useInvalidatePortfolio() {
  const qc = useQueryClient()
  return useCallback(() => {
    qc.invalidateQueries({ queryKey: keys.fundsOverview })
    qc.invalidateQueries({ queryKey: keys.portfolioSummary })
    qc.invalidateQueries({ queryKey: ['portfolio', 'history'] })
    qc.invalidateQueries({ queryKey: ['fund'] })
  }, [qc])
}
