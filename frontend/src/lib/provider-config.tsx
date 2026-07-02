import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { getStoredJSON, setStoredJSON } from './storage'

export type AiProvider = 'anthropic' | 'openai'

export type ProviderConfig = {
  provider: AiProvider
  api_key: string
  base_url: string        // used only for openai-compatible
  model: string           // orchestration model (e.g. deepseek-v4-flash)
  analysis_model: string  // analysis model (e.g. deepseek-v4-pro); empty = same as model
}

const DEFAULTS: ProviderConfig = {
  provider: 'anthropic',
  api_key: '',
  base_url: 'https://api.openai.com/v1',
  model: 'deepseek-v4-flash',
  analysis_model: '',
}

const STORAGE_KEY = 'fund-watch:ai-provider-config'

function readStored(): ProviderConfig {
  const stored = getStoredJSON<Partial<ProviderConfig>>(STORAGE_KEY)
  return stored ? { ...DEFAULTS, ...stored } : DEFAULTS
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
    setStoredJSON(STORAGE_KEY, c)
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
