import { useState, useEffect, useRef, useCallback } from 'react'
import { Search, Plus, Check, AlertCircle } from 'lucide-react'
import { searchFunds } from '@/lib/api'
import { useAddFund } from '@/lib/queries'
import { cn } from '@/lib/utils'

export function SearchTab({ portfolioId, existingCodes }: { portfolioId?: number; existingCodes: string[] }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Array<{ code: string; name: string; type?: string }>>([])
  const [loading, setLoading] = useState(false)
  const [addedCodes, setAddedCodes] = useState<Set<string>>(() => new Set(existingCodes))
  const [error, setError] = useState('')
  const addFund = useAddFund(portfolioId)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

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

  const handleAdd = (code: string) => {
    setError('')
    addFund.mutate(code, {
      onSuccess: () => setAddedCodes((prev) => new Set(prev).add(code)),
      onError: (err: Error) => setError(err.message || '添加失败'),
    })
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
          const isAdding = addFund.isPending && addFund.variables === item.code
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
