import { useEffect, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

/** Modal shell: backdrop, click-outside close, Escape close.
 * Panel look (width/rounding/layout) comes from className. */
export function Modal({
  open = true,
  onClose,
  className,
  children,
}: {
  open?: boolean
  onClose: () => void
  className?: string
  children: ReactNode
}) {
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  useEffect(() => {
    if (!open) return
    const original = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = original
    }
  }, [open])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        className={cn('bg-white shadow-2xl w-full mx-4', className)}
      >
        {children}
      </div>
    </div>
  )
}
