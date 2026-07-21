import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type RefObject,
} from 'react'

/** Invoke onOutside on any mousedown outside ref (only while active). */
export function useClickOutside(
  ref: RefObject<HTMLElement | null>,
  active: boolean,
  onOutside: () => void,
) {
  const onOutsideRef = useRef(onOutside)
  onOutsideRef.current = onOutside

  useEffect(() => {
    if (!active) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node))
        onOutsideRef.current()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [ref, active])
}

/** Owns an AbortController for in-flight requests: `next()` aborts the
 * previous request and returns a fresh signal, `abort()` cancels the current
 * one. The pending request is aborted automatically on unmount. */
export function useAbortRef() {
  const ref = useRef<AbortController | null>(null)

  useEffect(() => () => ref.current?.abort(), [])

  return useMemo(
    () => ({
      next: () => {
        ref.current?.abort()
        const controller = new AbortController()
        ref.current = controller
        return controller.signal
      },
      abort: () => ref.current?.abort(),
    }),
    [],
  )
}

/** Monotonic request sequence guarding against out-of-order responses:
 * `next()` starts a new request and invalidates all older ones, `isCurrent`
 * tells whether a sequence number is still the latest. */
export function useRequestSeq() {
  const ref = useRef(0)

  return useMemo(
    () => ({
      next: () => ++ref.current,
      isCurrent: (seq: number) => seq === ref.current,
    }),
    [],
  )
}

/** A value that auto-clears `ms` after being flashed; re-flashing resets the
 * clock and the pending timer is cleared on unmount. */
export function useFlash<T = boolean>(ms: number) {
  const [value, setValue] = useState<T | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  useEffect(() => () => clearTimeout(timer.current), [])

  const flash = useCallback(
    (v: T) => {
      clearTimeout(timer.current)
      setValue(v)
      timer.current = setTimeout(() => setValue(null), ms)
    },
    [ms],
  )
  const clear = useCallback(() => {
    clearTimeout(timer.current)
    setValue(null)
  }, [])

  return [value, flash, clear] as const
}
