import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Shared categorical palette for pie/bar charts (cycled via idx % length). */
export const CHART_COLORS = [
  '#3b82f6',
  '#ef4444',
  '#10b981',
  '#f59e0b',
  '#8b5cf6',
  '#ec4899',
  '#06b6d4',
  '#84cc16',
]

export function formatCNY(value: number) {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
  }).format(value)
}

/** formatCNY with an explicit + prefix for positive values (gains/losses display). */
export function formatCNYSigned(value: number) {
  return `${value > 0 ? '+' : ''}${formatCNY(value)}`
}

/** 2-decimal percent; signed (default) adds '+' for positive values, 0 stays unsigned. */
export function formatPercent(value: number, opts?: { signed?: boolean }) {
  const signed = opts?.signed ?? true
  return `${signed && value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

/** Fixed 2-decimal grouped number (zh-CN locale), no currency symbol. */
export function formatNum2(value: number) {
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

/** Today as YYYY-MM-DD in the browser's local timezone.
 * `new Date().toISOString()` converts to UTC first, which is the wrong date
 * for part of the day in timezones ahead of UTC (e.g. CST, UTC+8). */
export function todayLocal(): string {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** A-share trading windows in CST (UTC+8): weekday 9:30–11:30 and 13:00–15:00. */
export function isTradingHours(): boolean {
  const now = new Date()
  const cstOffset = 8 * 60
  const cst = new Date(
    now.getTime() + (cstOffset - now.getTimezoneOffset()) * 60_000,
  )
  const day = cst.getDay() // 0=Sun, 6=Sat
  if (day === 0 || day === 6) return false
  const h = cst.getHours(),
    m = cst.getMinutes()
  const t = h * 60 + m
  return (t >= 9 * 60 + 30 && t < 11 * 60 + 30) || (t >= 13 * 60 && t < 15 * 60)
}

/** True when `s` is exactly a 6-digit fund code. */
export function isFundCode(s: string): boolean {
  return /^\d{6}$/.test(s)
}
