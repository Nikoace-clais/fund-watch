import { useEffect, useRef, useState } from 'react'
import { Bot } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useProviderConfig, type ProviderConfig, type AiProvider } from '@/lib/provider-config'
import { useClickOutside } from '@/lib/hooks'

export function AiConfigSetting() {
  const { config, setConfig, isConfigured } = useProviderConfig()
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState<ProviderConfig>(config)
  const ref = useRef<HTMLDivElement>(null)
  useClickOutside(ref, open, () => setOpen(false))

  // refresh draft from saved config each time the popover opens
  useEffect(() => {
    if (open) setDraft(config)
  }, [open, config])

  function save() {
    setConfig(draft)
    setOpen(false)
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          'flex items-center w-full px-3 py-2.5 rounded-md text-sm font-medium transition-colors',
          'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
        )}
      >
        <Bot className="mr-3 h-5 w-5 text-slate-400" />
        AI 配置
        {!isConfigured && (
          <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-600">
            未配置
          </span>
        )}
      </button>

      {open && (
        <div className="absolute bottom-full left-0 mb-2 w-72 bg-white rounded-xl border border-slate-200 shadow-lg p-4 z-50 space-y-3">
          <p className="text-xs font-medium text-slate-400 uppercase">AI Provider 配置</p>

          {/* Provider */}
          <div className="grid grid-cols-2 gap-1.5">
            {(['anthropic', 'openai'] as AiProvider[]).map((p) => (
              <button
                key={p}
                onClick={() => setDraft((d) => ({ ...d, provider: p }))}
                className={cn(
                  'py-1.5 rounded-lg text-sm border transition-colors',
                  draft.provider === p
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-slate-200 text-slate-600 hover:bg-slate-50',
                )}
              >
                {p === 'anthropic' ? 'Anthropic' : 'OpenAI 兼容'}
              </button>
            ))}
          </div>

          {/* API Key */}
          <div>
            <label className="block text-xs text-slate-500 mb-1">API Key</label>
            <input
              type="password"
              value={draft.api_key}
              onChange={(e) => setDraft((d) => ({ ...d, api_key: e.target.value }))}
              placeholder={draft.provider === 'anthropic' ? 'sk-ant-...' : 'sk-...'}
              className="w-full px-2.5 py-1.5 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* OpenAI-compatible extra fields */}
          {draft.provider === 'openai' && (
            <>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Base URL</label>
                <input
                  type="text"
                  value={draft.base_url}
                  onChange={(e) => setDraft((d) => ({ ...d, base_url: e.target.value }))}
                  placeholder="https://api.openai.com/v1"
                  className="w-full px-2.5 py-1.5 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">编排模型</label>
                <input
                  type="text"
                  value={draft.model}
                  onChange={(e) => setDraft((d) => ({ ...d, model: e.target.value }))}
                  placeholder="deepseek-v4-flash"
                  className="w-full px-2.5 py-1.5 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">分析模型（留空=同上）</label>
                <input
                  type="text"
                  value={draft.analysis_model}
                  onChange={(e) => setDraft((d) => ({ ...d, analysis_model: e.target.value }))}
                  placeholder="deepseek-v4-pro"
                  className="w-full px-2.5 py-1.5 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </>
          )}

          <button
            onClick={save}
            className="w-full py-1.5 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors"
          >
            保存
          </button>
        </div>
      )}
    </div>
  )
}
