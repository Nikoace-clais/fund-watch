import { useState, useEffect, useRef, useCallback } from 'react'
import { Search, X, Plus, Check, AlertCircle, FileJson, Hash } from 'lucide-react'
import { addFund, batchAddFunds, searchFunds } from '@/lib/api'
import { cn } from '@/lib/utils'

type AddFundModalProps = {
  open: boolean
  onClose: () => void
  onAdded: () => void
}

type Tab = 'search' | 'code' | 'batch'

const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
  { key: 'search', label: '搜索添加', icon: <Search className="w-4 h-4" /> },
  { key: 'code', label: '输入代码', icon: <Hash className="w-4 h-4" /> },
  { key: 'batch', label: '批量导入', icon: <FileJson className="w-4 h-4" /> },
]

export function AddFundModal({ open, onClose, onAdded }: AddFundModalProps) {
  const [activeTab, setActiveTab] = useState<Tab>('search')

  // Close on Escape
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-5 pb-3">
          <h2 className="text-lg font-semibold text-slate-800">添加基金</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 px-6 pb-4">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                'flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                activeTab === tab.key
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100'
              )}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="px-6 pb-6 overflow-y-auto flex-1">
          {activeTab === 'search' && <SearchTab onAdded={onAdded} />}
          {activeTab === 'code' && <CodeTab onAdded={onAdded} />}
          {activeTab === 'batch' && <BatchTab onAdded={onAdded} />}
        </div>
      </div>
    </div>
  )
}

/* ─── Tab 1: Search ─── */
function SearchTab({ onAdded }: { onAdded: () => void }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Array<{ code: string; name: string; type?: string }>>([])
  const [loading, setLoading] = useState(false)
  const [addedCodes, setAddedCodes] = useState<Set<string>>(new Set())
  const [adding, setAdding] = useState<string | null>(null)
  const [error, setError] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  const doSearch = useCallback(async (q: string) => {
    if (q.trim().length < 1) {
      setResults([])
      return
    }
    setLoading(true)
    setError('')
    try {
      const data = await searchFunds(q.trim())
      setResults(data.results)
    } catch (err: any) {
      setError(err.message || '搜索失败')
      setResults([])
    } finally {
      setLoading(false)
    }
  }, [])

  const handleInput = (value: string) => {
    setQuery(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => doSearch(value), 300)
  }

  const handleAdd = async (code: string) => {
    setAdding(code)
    try {
      await addFund(code)
      setAddedCodes((prev) => new Set(prev).add(code))
      onAdded()
    } catch (err: any) {
      setError(err.message || '添加失败')
    } finally {
      setAdding(null)
    }
  }

  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          type="text"
          value={query}
          onChange={(e) => handleInput(e.target.value)}
          placeholder="输入基金名称或代码搜索..."
          autoFocus
          className="w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm text-red-500">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {loading && (
        <p className="text-sm text-slate-400 text-center py-4">搜索中...</p>
      )}

      {!loading && results.length === 0 && query.trim().length > 0 && (
        <p className="text-sm text-slate-400 text-center py-4">无匹配结果</p>
      )}

      <div className="space-y-1 max-h-64 overflow-y-auto">
        {results.map((item) => {
          const isAdded = addedCodes.has(item.code)
          const isAdding = adding === item.code
          return (
            <button
              key={item.code}
              onClick={() => !isAdded && !isAdding && handleAdd(item.code)}
              disabled={isAdded || isAdding}
              className={cn(
                'w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-left transition-colors',
                isAdded
                  ? 'bg-green-50 cursor-default'
                  : 'hover:bg-slate-50 cursor-pointer'
              )}
            >
              <div className="flex items-center gap-3 min-w-0">
                <span className="text-sm font-mono text-slate-500">{item.code}</span>
                <span className="text-sm text-slate-800 truncate">{item.name}</span>
                {item.type && (
                  <span className="shrink-0 text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                    {item.type}
                  </span>
                )}
              </div>
              <div className="shrink-0 ml-2">
                {isAdded ? (
                  <Check className="w-4 h-4 text-green-500" />
                ) : isAdding ? (
                  <span className="text-xs text-slate-400">添加中...</span>
                ) : (
                  <Plus className="w-4 h-4 text-slate-400" />
                )}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

/* ─── Tab 2: Code Input ─── */
function CodeTab({ onAdded }: { onAdded: () => void }) {
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const isValid = /^\d{6}$/.test(code)

  const handleSubmit = async () => {
    if (!isValid) return
    setLoading(true)
    setMessage(null)
    try {
      await addFund(code)
      setMessage({ type: 'success', text: `基金 ${code} 添加成功` })
      setCode('')
      onAdded()
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '添加失败' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-slate-600 mb-1.5">基金代码</label>
        <div className="flex gap-2">
          <input
            type="text"
            value={code}
            onChange={(e) => {
              setCode(e.target.value.replace(/\D/g, '').slice(0, 6))
              setMessage(null)
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSubmit()
            }}
            placeholder="例如 110011"
            maxLength={6}
            className="flex-1 px-4 py-2.5 border border-slate-200 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <button
            onClick={handleSubmit}
            disabled={!isValid || loading}
            className={cn(
              'px-5 py-2.5 rounded-lg text-sm font-medium transition-colors',
              isValid && !loading
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-slate-100 text-slate-400 cursor-not-allowed'
            )}
          >
            {loading ? '添加中...' : '添加'}
          </button>
        </div>
        {code.length > 0 && !isValid && (
          <p className="mt-1.5 text-xs text-slate-400">请输入6位数字基金代码</p>
        )}
      </div>

      {message && (
        <div
          className={cn(
            'flex items-center gap-2 text-sm px-3 py-2.5 rounded-lg',
            message.type === 'success'
              ? 'bg-green-50 text-green-700'
              : 'bg-red-50 text-red-600'
          )}
        >
          {message.type === 'success' ? (
            <Check className="w-4 h-4 shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 shrink-0" />
          )}
          {message.text}
        </div>
      )}
    </div>
  )
}

/* ─── Tab 3: Batch Import ─── */
function BatchTab({ onAdded }: { onAdded: () => void }) {
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ added: string[]; skipped: string[] } | null>(null)
  const [error, setError] = useState('')

  const parseCodes = (input: string): string[] => {
    const trimmed = input.trim()
    if (!trimmed) return []

    // Try JSON format: {"codes": [...]}
    try {
      const parsed = JSON.parse(trimmed)
      if (parsed.codes && Array.isArray(parsed.codes)) {
        return parsed.codes.filter((c: unknown) => typeof c === 'string' && /^\d{6}$/.test(c))
      }
      if (Array.isArray(parsed)) {
        return parsed.filter((c: unknown) => typeof c === 'string' && /^\d{6}$/.test(c))
      }
    } catch {
      // Not JSON, continue
    }

    // Plain text: split by newlines, commas, spaces
    const tokens = trimmed.split(/[\n,\s]+/).map((s) => s.trim()).filter(Boolean)
    return tokens.filter((t) => /^\d{6}$/.test(t))
  }

  const handleImport = async () => {
    setError('')
    setResult(null)
    const codes = parseCodes(text)
    if (codes.length === 0) {
      setError('未识别到有效的6位基金代码')
      return
    }
    setLoading(true)
    try {
      const data = await batchAddFunds(codes)
      setResult({ added: data.added, skipped: data.skipped })
      if (data.added.length > 0) onAdded()
    } catch (err: any) {
      setError(err.message || '导入失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-slate-600 mb-1.5">粘贴基金代码</label>
        <textarea
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            setResult(null)
            setError('')
          }}
          rows={5}
          placeholder={'{"codes": ["110011", "161725"]}\n\n或每行一个代码：\n110011\n161725'}
          className="w-full px-4 py-3 border border-slate-200 rounded-lg text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <p className="mt-1.5 text-xs text-slate-400">
          支持 JSON 格式、逗号分隔或每行一个代码
        </p>
      </div>

      <button
        onClick={handleImport}
        disabled={!text.trim() || loading}
        className={cn(
          'w-full py-2.5 rounded-lg text-sm font-medium transition-colors',
          text.trim() && !loading
            ? 'bg-blue-600 text-white hover:bg-blue-700'
            : 'bg-slate-100 text-slate-400 cursor-not-allowed'
        )}
      >
        {loading ? '导入中...' : '导入'}
      </button>

      {error && (
        <div className="flex items-center gap-2 text-sm text-red-500 px-3 py-2.5 bg-red-50 rounded-lg">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-2 text-sm">
          {result.added.length > 0 && (
            <div className="flex items-start gap-2 px-3 py-2.5 bg-green-50 text-green-700 rounded-lg">
              <Check className="w-4 h-4 shrink-0 mt-0.5" />
              <span>成功添加 {result.added.length} 只：{result.added.join(', ')}</span>
            </div>
          )}
          {result.skipped.length > 0 && (
            <div className="flex items-start gap-2 px-3 py-2.5 bg-slate-50 text-slate-500 rounded-lg">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>跳过 {result.skipped.length} 只（已存在）：{result.skipped.join(', ')}</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
