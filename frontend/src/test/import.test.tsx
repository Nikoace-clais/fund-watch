import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactElement, ReactNode } from 'react'
import { ImportPreview } from '../components/ImportPreview'
import { ProviderConfigProvider } from '../lib/provider-config'
import type { ImportPreviewResult } from '../services/import'

function Providers({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <ProviderConfigProvider>{children}</ProviderConfigProvider>
    </QueryClientProvider>
  )
}

function renderWrapped(ui: ReactElement) {
  return render(ui, { wrapper: Providers })
}

describe('ImportPreview Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [] }),
    })
  })

  it('should render upload area', () => {
    renderWrapped(<ImportPreview onImport={() => {}} />)

    expect(screen.getByText(/上传截图/i)).toBeInTheDocument()
    expect(screen.getByText(/支持 PNG、JPG、WebP/i)).toBeInTheDocument()
  })

  it('should show unconfigured warning when no api_key', () => {
    renderWrapped(<ImportPreview onImport={() => {}} />)
    expect(screen.getByText(/未配置 AI 密钥/i)).toBeInTheDocument()
  })

  it('should show loading state when uploading', async () => {
    let resolvePromise: () => void
    const pendingPromise = new Promise<Response>((resolve) => {
      resolvePromise = () => resolve(new Response())
    })
    ;(global.fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ items: [] }),
      })
      .mockReturnValueOnce(pendingPromise)

    renderWrapped(<ImportPreview onImport={() => {}} />)

    const file = new File(['dummy'], 'test.png', { type: 'image/png' })
    const input = screen.getByTestId('file-input')

    fireEvent.change(input, { target: { files: [file] } })

    expect(screen.getByText(/准备中/i)).toBeInTheDocument()

    resolvePromise!()
  })

  it('should display preview results', async () => {
    const mockResult: ImportPreviewResult = {
      funds: [
        {
          code: '005827',
          name: '易方达蓝筹精选混合',
          type: '混合型',
          confidence: 0.95,
          source: 'code',
          needs_review: false,
        },
      ],
      total_confidence: 0.95,
      needs_review: false,
      total_count: 1,
    }

    renderWrapped(
      <ImportPreview onImport={() => {}} initialData={mockResult} />,
    )

    await waitFor(() => {
      expect(screen.getByText('易方达蓝筹精选混合')).toBeInTheDocument()
      expect(screen.getByText('005827')).toBeInTheDocument()
      expect(screen.getByText('95%')).toBeInTheDocument()
    })
  })

  it('should show needs review warning for low confidence', async () => {
    const mockResult: ImportPreviewResult = {
      funds: [
        {
          code: '005827',
          name: '易方达蓝筹精选混合',
          type: '混合型',
          confidence: 0.65,
          source: 'name_match',
          needs_review: true,
        },
      ],
      total_confidence: 0.65,
      needs_review: true,
      total_count: 1,
    }

    renderWrapped(
      <ImportPreview onImport={() => {}} initialData={mockResult} />,
    )

    expect(screen.getByText(/部分基金置信度较低/i)).toBeInTheDocument()
    expect(screen.getByText('需确认')).toBeInTheDocument()
  })

  it('should handle select all checkbox', async () => {
    const mockResult: ImportPreviewResult = {
      funds: [
        {
          code: '005827',
          name: '基金A',
          type: '混合型',
          confidence: 0.95,
          source: 'code',
          needs_review: false,
        },
        {
          code: '110011',
          name: '基金B',
          type: '股票型',
          confidence: 0.85,
          source: 'code',
          needs_review: false,
        },
      ],
      total_confidence: 0.9,
      needs_review: false,
      total_count: 2,
    }

    renderWrapped(
      <ImportPreview onImport={() => {}} initialData={mockResult} />,
    )

    const selectAllCheckbox = screen.getByTestId(
      'select-all',
    ) as HTMLInputElement

    expect(selectAllCheckbox.checked).toBe(true)

    await userEvent.click(selectAllCheckbox)
    expect(selectAllCheckbox.checked).toBe(false)
  })

  it('should show selected count', () => {
    const mockResult: ImportPreviewResult = {
      funds: [
        {
          code: '005827',
          name: '基金A',
          type: '混合型',
          confidence: 0.95,
          source: 'code',
          needs_review: false,
        },
        {
          code: '110011',
          name: '基金B',
          type: '股票型',
          confidence: 0.65,
          source: 'name_match',
          needs_review: true,
        },
      ],
      total_confidence: 0.8,
      needs_review: true,
      total_count: 2,
    }

    const { container } = renderWrapped(
      <ImportPreview onImport={() => {}} initialData={mockResult} />,
    )

    expect(container.textContent).toContain('已选择')
    expect(container.textContent).toContain('确认导入')
  })

  it('should call onImport with selected codes', async () => {
    const mockImport = vi.fn()
    const mockResult: ImportPreviewResult = {
      funds: [
        {
          code: '005827',
          name: '基金A',
          type: '混合型',
          confidence: 0.95,
          source: 'code',
          needs_review: false,
        },
      ],
      total_confidence: 0.95,
      needs_review: false,
      total_count: 1,
    }

    // portfolios + ocr/status queries fire on mount, then the batch import
    ;(global.fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ items: [] }), // /api/portfolios
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ready: true }), // /api/ocr/status
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ok: true,
          added: ['005827'],
          invalid: [],
          warnings: [],
        }),
      })

    renderWrapped(
      <ImportPreview onImport={mockImport} initialData={mockResult} />,
    )

    const confirmButton = screen.getByRole('button', { name: /确认导入/i })
    await userEvent.click(confirmButton)

    await waitFor(() => {
      expect(mockImport).toHaveBeenCalledWith({
        success: true,
        added: 1,
        total: 1,
        invalid: [],
      })
    })
  })
})
