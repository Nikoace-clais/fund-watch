import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactElement, ReactNode } from 'react';
import { BatchTab } from '../components/add-fund/BatchTab';

function Providers({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function renderWrapped(ui: ReactElement) {
  return render(ui, { wrapper: Providers });
}

describe('BatchTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, portfolio_id: 1, added: ['110011'], invalid: [], warnings: [] }),
    });
  });

  it('forwards portfolioId to the batch-add request body', async () => {
    renderWrapped(<BatchTab portfolioId={7} />);

    fireEvent.change(screen.getByPlaceholderText(/也支持旧格式/), {
      target: { value: '{"funds": [{"code": "110011"}]}' },
    });
    fireEvent.click(screen.getByRole('button', { name: '导入' }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());

    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const body = JSON.parse(init.body as string);
    expect(body.portfolio_id).toBe(7);
  });

  it('omits portfolio_id when no portfolioId prop is given', async () => {
    renderWrapped(<BatchTab />);

    fireEvent.change(screen.getByPlaceholderText(/也支持旧格式/), {
      target: { value: '{"funds": [{"code": "110011"}]}' },
    });
    fireEvent.click(screen.getByRole('button', { name: '导入' }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());

    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const body = JSON.parse(init.body as string);
    expect(body.portfolio_id).toBeUndefined();
  });
});
