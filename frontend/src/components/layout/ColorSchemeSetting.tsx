import { useRef, useState } from 'react'
import { Settings } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useColor, type ColorScheme } from '@/lib/color-context'
import { useClickOutside } from '@/lib/hooks'

export function ColorSchemeSetting() {
  const { scheme, setScheme } = useColor()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useClickOutside(ref, open, () => setOpen(false))

  const options: { value: ColorScheme; label: string; desc: string }[] = [
    { value: 'red-up', label: '红涨绿跌', desc: 'A股习惯' },
    { value: 'green-up', label: '绿涨红跌', desc: '国际惯例' },
  ]

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          'flex items-center w-full px-3 py-2.5 rounded-md text-sm font-medium transition-colors',
          'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
        )}
      >
        <Settings className="mr-3 h-5 w-5 text-slate-400" />
        设置
      </button>

      {open && (
        <div className="absolute bottom-full left-0 mb-2 w-56 bg-white rounded-xl border border-slate-200 shadow-lg p-3 z-50">
          <p className="text-xs font-medium text-slate-400 uppercase mb-2">涨跌配色</p>
          <div className="space-y-1">
            {options.map((opt) => (
              <button
                key={opt.value}
                onClick={() => {
                  setScheme(opt.value)
                  setOpen(false)
                }}
                className={cn(
                  'w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors',
                  scheme === opt.value
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-slate-600 hover:bg-slate-50',
                )}
              >
                <div className="flex items-center gap-2">
                  <span className="flex gap-0.5">
                    <span className={cn(
                      'inline-block w-3 h-3 rounded-full',
                      opt.value === 'red-up' ? 'bg-red-500' : 'bg-green-500',
                    )} />
                    <span className={cn(
                      'inline-block w-3 h-3 rounded-full',
                      opt.value === 'red-up' ? 'bg-green-500' : 'bg-red-500',
                    )} />
                  </span>
                  <span>{opt.label}</span>
                </div>
                <span className="text-xs text-slate-400">{opt.desc}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
