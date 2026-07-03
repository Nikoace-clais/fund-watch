import { useState, useEffect } from 'react'
import { Search, X, FileJson, Hash } from 'lucide-react'
import { SearchTab } from './add-fund/SearchTab'
import { CodeTab } from './add-fund/CodeTab'
import { BatchTab } from './add-fund/BatchTab'
import { cn } from '@/lib/utils'

type AddFundModalProps = {
  open: boolean
  onClose: () => void
  /** Portfolio to scope added funds/invalidation to; omit for the default portfolio */
  portfolioId?: number
  /** Codes already in the watchlist — pre-marks them as added in search results */
  existingCodes?: string[]
}

type Tab = 'search' | 'code' | 'batch'

const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
  { key: 'search', label: '搜索添加', icon: <Search className="w-4 h-4" /> },
  { key: 'code', label: '输入代码', icon: <Hash className="w-4 h-4" /> },
  { key: 'batch', label: '批量导入', icon: <FileJson className="w-4 h-4" /> },
]

export function AddFundModal({ open, onClose, portfolioId, existingCodes = [] }: AddFundModalProps) {
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
          {activeTab === 'search' && <SearchTab portfolioId={portfolioId} existingCodes={existingCodes} />}
          {activeTab === 'code' && <CodeTab portfolioId={portfolioId} />}
          {activeTab === 'batch' && <BatchTab portfolioId={portfolioId} />}
        </div>
      </div>
    </div>
  )
}
