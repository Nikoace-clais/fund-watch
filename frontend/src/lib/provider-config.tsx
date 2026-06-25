import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

export type AiProvider = 'anthropic' | 'openai'

export type ProviderConfig = {
  provider: AiProvider
  api_key: string
  base_url: string  // used only for openai-compatible
  model: string     // used only for openai-compatible
}

const DEFAULTS: ProviderConfig = {
  provider: 'anthropic',
  api_key: '',
  base_url: 'https://api.openai.com/v1',
  model: 'gpt-4o',
}

const STORAGE_KEY = 'fund-watch:ai-provider-config'

function readStored(): ProviderConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return { ...DEFAULTS, ...JSON.parse(raw) }
  } catch {}
  return DEFAULTS
}

type ContextValue = {
  config: ProviderConfig
  setConfig: (c: ProviderConfig) => void
  isConfigured: boolean
}

const Ctx = createContext<ContextValue | null>(null)

export function ProviderConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfigState] = useState<ProviderConfig>(readStored)

  const setConfig = useCallback((c: ProviderConfig) => {
    setConfigState(c)
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(c)) } catch {}
  }, [])

  const isConfigured = config.api_key.trim().length > 0

  return (
    <Ctx.Provider value={{ config, setConfig, isConfigured }}>
      {children}
    </Ctx.Provider>
  )
}

export function useProviderConfig() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useProviderConfig must be used within ProviderConfigProvider')
  return ctx
}
