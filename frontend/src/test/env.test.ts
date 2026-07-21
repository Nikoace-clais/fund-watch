import { describe, it, expect } from 'vitest'

describe('Environment', () => {
  it('should have test env available', () => {
    // This test verifies the test environment is set up correctly
    expect(import.meta.env).toBeDefined()
  })

  it('should have mocked fetch', () => {
    expect(global.fetch).toBeDefined()
    expect(typeof global.fetch).toBe('function')
  })

  it('should import lib modules', async () => {
    // Verify lib modules can be imported
    const apiModule = await import('../lib/api')
    expect(apiModule).toBeDefined()
    // api.ts exports individual functions, not a default 'api' export
    expect(typeof apiModule.fetchFundsOverview).toBe('function')
  })
})
