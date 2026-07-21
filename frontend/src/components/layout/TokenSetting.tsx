import { useState } from 'react'
import { KeyRound } from 'lucide-react'
import { getAccessToken, setAccessToken } from '@/lib/api-client'
import { SettingsDropdown } from './SettingsDropdown'

export function TokenSetting() {
  const [hasToken, setHasToken] = useState(() => getAccessToken() != null)

  return (
    <SettingsDropdown
      panelClassName="w-72 p-4 space-y-3"
      trigger={
        <>
          <KeyRound className="mr-3 h-5 w-5 text-slate-400" />
          访问令牌
          {!hasToken && (
            <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-600">
              未设置
            </span>
          )}
        </>
      }
      renderPanel={(close) => (
        <TokenPanel
          onSave={(token) => {
            setAccessToken(token)
            setHasToken(token != null)
            close()
          }}
        />
      )}
    />
  )
}

// Mounted only while the dropdown is open, so the draft naturally resets to
// the stored token each time it opens (same pattern as AiConfigPanel).
function TokenPanel({ onSave }: { onSave: (token: string | null) => void }) {
  const [draft, setDraft] = useState(() => getAccessToken() ?? '')

  return (
    <>
      <p className="text-xs font-medium text-slate-400 uppercase">访问令牌</p>
      <p className="text-xs text-slate-400">
        后端设置 FUND_WATCH_TOKEN 后，所有 API 请求需附带该令牌。
      </p>
      <div>
        <label
          htmlFor="fund-watch-token"
          className="block text-xs text-slate-500 mb-1"
        >
          Token
        </label>
        <input
          id="fund-watch-token"
          type="password"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="输入访问令牌"
          className="w-full px-2.5 py-1.5 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <div className="flex gap-2">
        <button
          onClick={() => onSave(draft.trim())}
          disabled={!draft.trim()}
          className="flex-1 py-1.5 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          保存
        </button>
        <button
          onClick={() => onSave(null)}
          className="flex-1 py-1.5 text-sm rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
        >
          清除
        </button>
      </div>
    </>
  )
}
