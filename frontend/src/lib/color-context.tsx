import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { getStoredString, setStoredString } from './storage'

export type ColorScheme = 'red-up' | 'green-up'

type ColorContextValue = {
  scheme: ColorScheme
  setScheme: (s: ColorScheme) => void
  /** Tailwind text color class for a return value */
  colorFor: (value: number) => string
  /** Tailwind badge classes (bg + text + border) for a return value */
  badgeClassFor: (value: number) => string
  /** Hex color for SVG/canvas contexts where a Tailwind class won't work */
  hexFor: (isUp: boolean) => string
}

const STORAGE_KEY = 'fund-watch-color-scheme'

function readStored(): ColorScheme {
  const v = getStoredString(STORAGE_KEY)
  if (v === 'red-up' || v === 'green-up') return v
  return 'red-up' // default: A-share convention
}

const ColorContext = createContext<ColorContextValue | null>(null)

export function ColorProvider({ children }: { children: ReactNode }) {
  const [scheme, setSchemeState] = useState<ColorScheme>(readStored)

  const setScheme = useCallback((s: ColorScheme) => {
    setSchemeState(s)
    setStoredString(STORAGE_KEY, s)
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

  const hexFor = useCallback(
    (isUp: boolean) => {
      const red = '#ef4444'
      const green = '#22c55e'
      if (scheme === 'red-up') return isUp ? red : green
      return isUp ? green : red
    },
    [scheme],
  )

  return (
    <ColorContext.Provider value={{ scheme, setScheme, colorFor, badgeClassFor, hexFor }}>
      {children}
    </ColorContext.Provider>
  )
}

export function useColor() {
  const ctx = useContext(ColorContext)
  if (!ctx) throw new Error('useColor must be used within ColorProvider')
  return ctx
}
