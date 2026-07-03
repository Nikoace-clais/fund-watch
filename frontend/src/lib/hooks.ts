import { useEffect, type RefObject } from 'react'

/** Invoke onOutside on any mousedown outside ref (only while active). */
export function useClickOutside(
  ref: RefObject<HTMLElement | null>,
  active: boolean,
  onOutside: () => void,
) {
  useEffect(() => {
    if (!active) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onOutside()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [ref, active, onOutside])
}
