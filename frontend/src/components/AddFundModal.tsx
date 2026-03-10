import { useState, useEffect, useRef, useCallback } from 'react'
import { Search, X, Plus, Check, AlertCircle, FileJson, Hash, Copy, ChevronDown, ChevronUp } from 'lucide-react'
import { addFund, batchAddFunds, searchFunds, type BatchFundItem } from '@/lib/api'
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
  const [result, setResult] = useState<{ added: string[]; invalid: string[]; warnings: string[] } | null>(null)
  const [error, setError] = useState('')

  type ParseResult = { codes: string[]; funds: BatchFundItem[] }

  const parseInput = (input: string): ParseResult => {
    const trimmed = input.trim()
    if (!trimmed) return { codes: [], funds: [] }

    try {
      const parsed = JSON.parse(trimmed)
      // New format: {"funds": [{name?, code?, holding_amount?, cumulative_return?, holding_return?}]}
      if (parsed.funds && Array.isArray(parsed.funds)) {
        const funds: BatchFundItem[] = parsed.funds
          .filter((f: unknown) => typeof (f as any)?.name === 'string' || (typeof (f as any)?.code === 'string' && /^\d{6}$/.test((f as any).code)))
          .map((f: any) => ({
            code: typeof f.code === 'string' && /^\d{6}$/.test(f.code) ? f.code : undefined,
            name: typeof f.name === 'string' ? f.name : undefined,
            holding_amount: typeof f.holding_amount === 'number' ? f.holding_amount : undefined,
            cumulative_return: typeof f.cumulative_return === 'number' ? f.cumulative_return : undefined,
            holding_return: typeof f.holding_return === 'number' ? f.holding_return : undefined,
          }))
        return { codes: [], funds }
      }
      // Old format: {"codes": [...]}
      if (parsed.codes && Array.isArray(parsed.codes)) {
        return {
          codes: parsed.codes.filter((c: unknown) => typeof c === 'string' && /^\d{6}$/.test(c as string)),
          funds: [],
        }
      }
      if (Array.isArray(parsed)) {
        return {
          codes: parsed.filter((c: unknown) => typeof c === 'string' && /^\d{6}$/.test(c as string)),
          funds: [],
        }
      }
    } catch {
      // Not JSON
    }

    // Plain text: split by newlines, commas, spaces
    const tokens = trimmed.split(/[\n,\s]+/).map((s) => s.trim()).filter(Boolean)
    return { codes: tokens.filter((t) => /^\d{6}$/.test(t)), funds: [] }
  }

  const handleImport = async () => {
    setError('')
    setResult(null)
    const { codes, funds } = parseInput(text)
    if (codes.length === 0 && funds.length === 0) {
      setError('未识别到有效的6位基金代码')
      return
    }
    setLoading(true)
    try {
      const data = await batchAddFunds(codes, funds)
      setResult({ added: data.added, invalid: data.invalid ?? [], warnings: data.warnings ?? [] })
      if (data.added.length > 0) onAdded()
    } catch (err: any) {
      setError(err.message || '导入失败')
    } finally {
      setLoading(false)
    }
  }

  const [showPrompt, setShowPrompt] = useState(false)
  const [copied, setCopied] = useState(false)

  const AI_PROMPT = `请识别这张截图中的所有基金持仓信息，按以下 JSON 格式输出：

{"funds": [
  {
    "code": "6位基金代码",
    "name": "基金名称",
    "holding_amount": 持仓金额（数字，单位元），
    "cumulative_return": 累计收益（数字，单位元，亏损为负数），
    "holding_return": 持有收益（数字，单位元，亏损为负数）
  }
]}

注意事项：
- code 和 name 尽量都填，系统会自动交叉验证；只有名称没有代码也可以
- name 填写截图中显示的完整基金名称
- 金额字段若截图中没有，可省略该字段
- 所有金额为纯数字，不带"元"或"¥"符号
- 亏损的收益填写负数，例如 -123.45`

  const handleCopyPrompt = () => {
    navigator.clipboard.writeText(AI_PROMPT).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const PLACEHOLDER = `{"funds": [
  {"code": "110011", "name": "易方达优质精选混合", "holding_amount": 10000.5, "cumulative_return": 500.25, "holding_return": 300.1},
  {"name": "招商中证白酒指数", "holding_amount": 5000}
]}

也支持旧格式：{"codes": ["110011"]}
或每行一个代码：110011`

  return (
    <div className="space-y-4">
      {/* AI prompt helper */}
      <div className="rounded-lg border border-blue-200 bg-blue-50 overflow-hidden">
        <button
          type="button"
          onClick={() => setShowPrompt((v) => !v)}
          className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-medium text-blue-700 hover:bg-blue-100 transition-colors"
        >
          <span>用 AI 识别截图？先复制提示词</span>
          {showPrompt ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {showPrompt && (
          <div className="px-4 pb-3">
            <pre className="text-xs text-slate-600 whitespace-pre-wrap bg-white rounded border border-blue-100 p-3 mb-2 leading-relaxed">
              {AI_PROMPT}
            </pre>
            <button
              type="button"
              onClick={handleCopyPrompt}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                copied
                  ? 'bg-green-100 text-green-700'
                  : 'bg-white border border-blue-200 text-blue-600 hover:bg-blue-50'
              )}
            >
              {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? '已复制' : '复制提示词'}
            </button>
          </div>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-600 mb-1.5">粘贴基金数据</label>
        <textarea
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            setResult(null)
            setError('')
          }}
          rows={7}
          placeholder={PLACEHOLDER}
          className="w-full px-4 py-3 border border-slate-200 rounded-lg text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <p className="mt-1.5 text-xs text-slate-400">
          支持含持仓金额/累计收益/持有收益的 JSON，或旧格式 codes 数组，或纯代码列表
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
          {result.invalid.length > 0 && (
            <div className="flex items-start gap-2 px-3 py-2.5 bg-slate-50 text-slate-500 rounded-lg">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>无法识别 {result.invalid.length} 项：{result.invalid.join(', ')}</span>
            </div>
          )}
          {result.warnings.length > 0 && (
            <div className="flex items-start gap-2 px-3 py-2.5 bg-amber-50 text-amber-700 rounded-lg">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="space-y-1">
                {result.warnings.map((w, i) => <p key={i}>{w}</p>)}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
