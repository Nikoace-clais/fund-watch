import { useRef, useState, type ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { useClickOutside } from '@/lib/hooks'

/** Sidebar trigger button + click-outside-to-close popover panel. */
export function SettingsDropdown({
  trigger,
  panelClassName,
  renderPanel,
}: {
  trigger: ReactNode
  panelClassName?: string
  renderPanel: (close: () => void) => ReactNode
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useClickOutside(ref, open, () => setOpen(false))

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className={cn(
          'flex items-center w-full px-3 py-2.5 rounded-md text-sm font-medium transition-colors',
          'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
        )}
      >
        {trigger}
      </button>

      {open && (
        <div
          className={cn(
            'absolute bottom-full left-0 mb-2 bg-white rounded-xl border border-slate-200 shadow-lg z-50',
            panelClassName,
          )}
        >
          {renderPanel(() => setOpen(false))}
        </div>
      )}
    </div>
  )
}
