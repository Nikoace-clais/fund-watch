import { createContext, useContext, useState, useCallback, useMemo, type ReactNode } from 'react'
import type { Portfolio } from './api'
import { usePortfolios } from './queries'
import { getStoredString, setStoredString } from './storage'

type PortfolioContextValue = {
  portfolios: Portfolio[]
  selectedId: number | undefined
  selectPortfolio: (id: number) => void
}

// ponytail: localStorage for portfolio selection — good enough for single-user MVP
const STORAGE_KEY = 'fw_portfolio_id'

const PortfolioContext = createContext<PortfolioContextValue | null>(null)

export function PortfolioProvider({ children }: { children: ReactNode }) {
  const { data: portfolios = [] } = usePortfolios()
  const [rawId, setRawId] = useState<number | null>(() => {
    const v = getStoredString(STORAGE_KEY)
    return v ? parseInt(v, 10) : null
  })

  // Derive the effective ID: use stored if it still exists, else first portfolio
  const selectedId = useMemo(() => {
    if (!portfolios.length) return undefined
    if (rawId != null && portfolios.some((p) => p.id === rawId)) return rawId
    return portfolios[0].id
  }, [portfolios, rawId])

  const selectPortfolio = useCallback((id: number) => {
    setStoredString(STORAGE_KEY, String(id))
    setRawId(id)
  }, [])

  const value = useMemo(
    () => ({ portfolios, selectedId, selectPortfolio }),
    [portfolios, selectedId, selectPortfolio],
  )

  return (
    <PortfolioContext.Provider value={value}>
      {children}
    </PortfolioContext.Provider>
  )
}

export function useSelectedPortfolio() {
  const ctx = useContext(PortfolioContext)
  if (!ctx) throw new Error('useSelectedPortfolio must be used within PortfolioProvider')
  return ctx
}
