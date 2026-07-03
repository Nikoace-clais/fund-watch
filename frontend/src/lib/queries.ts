import { QueryClient, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import { isTradingHours } from './utils'
import {
  addFund,
  addTransaction,
  batchAddFunds,
  createPortfolio,
  deleteFund,
  deletePortfolio,
  deleteTransaction,
  fetchCronStatus,
  fetchFundDetail,
  fetchFundHoldings,
  fetchFundsHoldingStock,
  fetchFundsOverview,
  fetchMarketIndices,
  fetchNavHistory,
  fetchPortfolioHistory,
  fetchPortfolioHoldings,
  fetchPortfolioSummary,
  fetchQuote,
  fetchTransactions,
  getOcrStatus,
  listPortfolios,
  renamePortfolio,
  type BatchFundItem,
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
  portfolios: ['portfolios'] as const,
  fundsOverview: ['funds', 'overview'] as const,
  portfolioSummary: (pf?: number) => ['portfolio', 'summary', pf ?? null] as const,
  portfolioHoldings: (pf?: number) => ['portfolio', 'holdings', pf ?? null] as const,
  portfolioHistory: (limit: number, pf?: number) => ['portfolio', 'history', limit, pf ?? null] as const,
  marketIndices: ['market', 'indices'] as const,
  cronStatus: ['cron', 'status'] as const,
  fundDetail: (code: string) => ['fund', code, 'detail'] as const,
  navHistory: (code: string, limit: number) => ['fund', code, 'nav-history', limit] as const,
  fundHoldings: (code: string) => ['fund', code, 'holdings'] as const,
  quote: (code: string) => ['fund', code, 'quote'] as const,
  transactions: (code: string, pf?: number) => ['fund', code, 'transactions', pf ?? null] as const,
  ocrStatus: ['ocr-status'] as const,
  stockFunds: (stockCode: string) => ['stock-funds', stockCode] as const,
}

/* ---------- hooks ---------- */
export function usePortfolios() {
  return useQuery({
    queryKey: keys.portfolios,
    queryFn: listPortfolios,
    select: (r) => r.items,
  })
}

export function useFundsOverview() {
  return useQuery({
    queryKey: keys.fundsOverview,
    queryFn: fetchFundsOverview,
    select: (r) => r.items,
    refetchInterval: tradingRefetch,
  })
}

export function usePortfolioSummary(portfolioId?: number) {
  return useQuery({
    queryKey: keys.portfolioSummary(portfolioId),
    queryFn: () => fetchPortfolioSummary(portfolioId),
    refetchInterval: tradingRefetch,
  })
}

export function usePortfolioHoldings(portfolioId?: number) {
  return useQuery({
    queryKey: keys.portfolioHoldings(portfolioId),
    queryFn: () => fetchPortfolioHoldings(portfolioId),
  })
}

export function usePortfolioHistory(limit: number, portfolioId?: number) {
  return useQuery({
    queryKey: keys.portfolioHistory(limit, portfolioId),
    queryFn: () => fetchPortfolioHistory(limit, portfolioId),
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

export function useTransactions(code: string | undefined, portfolioId?: number, enabled = true) {
  return useQuery({
    queryKey: keys.transactions(code ?? '', portfolioId),
    queryFn: () => fetchTransactions(code!, portfolioId),
    select: (r) => r.items,
    enabled: !!code && enabled,
  })
}

export function useOcrStatus() {
  return useQuery({
    queryKey: keys.ocrStatus,
    queryFn: getOcrStatus,
    refetchInterval: (q) => (q.state.data?.ready ? false : 2000),
  })
}

export function useStockFundsHolding(stockCode: string) {
  return useQuery({
    queryKey: keys.stockFunds(stockCode),
    queryFn: () => fetchFundsHoldingStock(stockCode, 100),
    enabled: /^\d{6}$/.test(stockCode),
    staleTime: 5 * 60_000,
  })
}

/** 持仓/交易变动后,使组合相关查询失效(overview、summary、history、各基金交易记录) */
export function useInvalidatePortfolio(portfolioId?: number) {
  const qc = useQueryClient()
  return useCallback(() => {
    qc.invalidateQueries({ queryKey: keys.portfolios })
    qc.invalidateQueries({ queryKey: keys.fundsOverview })
    qc.invalidateQueries({ queryKey: keys.portfolioSummary(portfolioId) })
    qc.invalidateQueries({ queryKey: keys.portfolioHoldings(portfolioId) })
    qc.invalidateQueries({ queryKey: ['portfolio', 'history'] })
    qc.invalidateQueries({ queryKey: ['fund'] })
  }, [qc, portfolioId])
}

/* ---------- mutations ---------- */
// All write hooks below share one pattern: mutate, then invalidate the
// portfolio-scoped queries — no per-call-site setLoading/try/finally.

export function useAddFund(portfolioId?: number) {
  const invalidate = useInvalidatePortfolio(portfolioId)
  return useMutation({
    mutationFn: (code: string) => addFund(code),
    onSuccess: invalidate,
  })
}

/** variables.scopeToPortfolio controls whether the delete is scoped to one
 * portfolio or removes the fund globally — callers choose per call site. */
export function useDeleteFund(invalidatePortfolioId?: number) {
  const invalidate = useInvalidatePortfolio(invalidatePortfolioId)
  return useMutation({
    mutationFn: ({ code, scopeToPortfolio }: { code: string; scopeToPortfolio?: number }) =>
      deleteFund(code, scopeToPortfolio),
    onSuccess: invalidate,
  })
}

export function useBatchAddFunds(portfolioId?: number) {
  const invalidate = useInvalidatePortfolio(portfolioId)
  return useMutation({
    mutationFn: ({
      codes,
      funds,
      opts,
    }: {
      codes: string[]
      funds?: BatchFundItem[]
      opts?: { portfolioId?: number; portfolioName?: string }
    }) => batchAddFunds(codes, funds, opts),
    onSuccess: invalidate,
  })
}

export function useAddTransaction(portfolioId?: number) {
  const invalidate = useInvalidatePortfolio(portfolioId)
  return useMutation({
    mutationFn: ({ code, payload }: { code: string; payload: Parameters<typeof addTransaction>[1] }) =>
      addTransaction(code, payload),
    onSuccess: invalidate,
  })
}

export function useDeleteTransaction(portfolioId?: number) {
  const invalidate = useInvalidatePortfolio(portfolioId)
  return useMutation({
    mutationFn: (txId: number) => deleteTransaction(txId),
    onSuccess: invalidate,
  })
}

/** Delete-with-confirm flow shared by the transaction tables. */
export function useDeleteTxConfirm(portfolioId?: number) {
  const deleteTransaction = useDeleteTransaction(portfolioId)
  const handleDelete = (id: number) => {
    if (!confirm('确认删除该条交易记录？')) return
    deleteTransaction.mutate(id, {
      onError: (err: Error) => alert(err.message || '删除失败'),
    })
  }
  const deletingId = deleteTransaction.isPending ? (deleteTransaction.variables ?? null) : null
  return { handleDelete, deletingId }
}

export function useCreatePortfolio() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => createPortfolio(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.portfolios }),
  })
}

export function useRenamePortfolio() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) => renamePortfolio(id, name),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.portfolios }),
  })
}

export function useDeletePortfolio() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deletePortfolio(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.portfolios }),
  })
}
