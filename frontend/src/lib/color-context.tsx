import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

export type ColorScheme = 'red-up' | 'green-up'

type ColorContextValue = {
  scheme: ColorScheme
  setScheme: (s: ColorScheme) => void
  /** Tailwind text color class for a return value */
  colorFor: (value: number) => string
  /** Tailwind badge classes (bg + text + border) for a return value */
  badgeClassFor: (value: number) => string
  /** Chart stroke + fill colors for a return value */
  chartColorFor: (value: number) => { stroke: string; fill: string }
}

const STORAGE_KEY = 'fund-watch-color-scheme'

function readStored(): ColorScheme {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v === 'red-up' || v === 'green-up') return v
  } catch {}
  return 'red-up' // default: A-share convention
}

const ColorContext = createContext<ColorContextValue | null>(null)

export function ColorProvider({ children }: { children: ReactNode }) {
  const [scheme, setSchemeState] = useState<ColorScheme>(readStored)

  const setScheme = useCallback((s: ColorScheme) => {
    setSchemeState(s)
    try { localStorage.setItem(STORAGE_KEY, s) } catch {}
  }, [])

  const colorFor = useCallback(
    (value: number) => {
      if (value === 0) return 'text-gray-500'
      const isUp = value > 0
      if (scheme === 'red-up') {
        return isUp ? 'text-red-500' : 'text-green-500'
      }
      return isUp ? 'text-green-500' : 'text-red-500'
    },
    [scheme],
  )

  const badgeClassFor = useCallback(
    (value: number) => {
      if (value === 0) return 'bg-gray-50 text-gray-600 border-gray-200'
      const isUp = value > 0
      const red = 'bg-red-50 text-red-600 border-red-200'
      const green = 'bg-green-50 text-green-600 border-green-200'
      if (scheme === 'red-up') return isUp ? red : green
      return isUp ? green : red
    },
    [scheme],
  )

  const chartColorFor = useCallback(
    (value: number) => {
      if (value === 0) return { stroke: '#94a3b8', fill: '#e2e8f0' }
      const isUp = value > 0
      if (scheme === 'red-up') {
        return isUp
          ? { stroke: '#ef4444', fill: '#fecaca' }
          : { stroke: '#22c55e', fill: '#bbf7d0' }
      }
      return isUp
        ? { stroke: '#22c55e', fill: '#bbf7d0' }
        : { stroke: '#ef4444', fill: '#fecaca' }
    },
    [scheme],
  )

  return (
    <ColorContext.Provider value={{ scheme, setScheme, colorFor, badgeClassFor, chartColorFor }}>
      {children}
    </ColorContext.Provider>
  )
}

export function useColor() {
  const ctx = useContext(ColorContext)
  if (!ctx) throw new Error('useColor must be used within ColorProvider')
  return ctx
}
