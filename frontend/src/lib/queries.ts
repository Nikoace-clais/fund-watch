import { QueryClient, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import { isTradingHours } from './utils'
import {
  fetchCronStatus,
  fetchFundDetail,
  fetchFundHoldings,
  fetchFundsOverview,
  fetchMarketIndices,
  fetchNavHistory,
  fetchPortfolioHistory,
  fetchPortfolioSummary,
  fetchQuote,
  fetchTransactions,
} from './api'

// ponytail: refetchInterval callback — stops polling outside trading hours to save requests
const tradingRefetch = () => (isTradingHours() ? 60_000 : false)

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: true,
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
}

/* ---------- hooks ---------- */
export function useFundsOverview() {
  return useQuery({
    queryKey: keys.fundsOverview,
    queryFn: fetchFundsOverview,
    select: (r) => r.items,
    refetchInterval: tradingRefetch,
  })
}

export function usePortfolioSummary() {
  return useQuery({
    queryKey: keys.portfolioSummary,
    queryFn: fetchPortfolioSummary,
    refetchInterval: tradingRefetch,
  })
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
    refetchInterval: tradingRefetch,
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
    refetchInterval: tradingRefetch,
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
