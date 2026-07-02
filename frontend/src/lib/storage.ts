/** Thin localStorage wrapper: try/catch once instead of at every call site.
 * Preserves each caller's existing on-disk format (raw string vs JSON) —
 * this only collapses the boilerplate, not the storage keys/shapes. */

export function getStoredString(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

export function setStoredString(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // storage unavailable (private browsing, quota) — ignore
  }
}

export function getStoredJSON<T>(key: string): T | null {
  const raw = getStoredString(key)
  if (raw == null) return null
  try {
    return JSON.parse(raw) as T
  } catch {
    return null
  }
}

export function setStoredJSON(key: string, value: unknown): void {
  try {
    setStoredString(key, JSON.stringify(value))
  } catch {
    // value isn't serializable (circular reference, BigInt, etc.) — ignore
  }
}
