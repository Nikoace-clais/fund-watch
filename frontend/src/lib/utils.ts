import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCNY(value: number) {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
  }).format(value)
}

export function formatPercent(value: number) {
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

/** A-share trading windows in CST (UTC+8): weekday 9:30–11:30 and 13:00–15:00. */
export function isTradingHours(): boolean {
  const now = new Date()
  const cstOffset = 8 * 60
  const cst = new Date(now.getTime() + (cstOffset - now.getTimezoneOffset()) * 60_000)
  const day = cst.getDay() // 0=Sun, 6=Sat
  if (day === 0 || day === 6) return false
  const h = cst.getHours(), m = cst.getMinutes()
  const t = h * 60 + m
  return (t >= 9 * 60 + 30 && t < 11 * 60 + 30) || (t >= 13 * 60 && t < 15 * 60)
}
